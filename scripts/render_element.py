#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Rishab Doshi
"""Render the real element in headless Chrome: hero screenshot and browser smoke test.

The page is built from the element's own controller, Mustache template, JS, and
CSS (PrairieLearn's ``prairielearn`` package is stubbed, as in the tests).
Bootstrap 5 CSS is loaded from jsDelivr to approximate PrairieLearn's styling.

    python3 scripts/render_element.py screenshot   # writes docs/figures/element-editor.png
    python3 scripts/render_element.py smoke        # runs browser checks, exits non-zero on failure

Requires Google Chrome or Chromium (set CHROME=/path/to/chrome to override),
plus chevron and lxml. Chrome needs its temporary profile on a POSIX file
system; if TMPDIR is on exFAT, set CHROME_TMPDIR to a directory elsewhere.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELEMENT = ROOT / "elements" / "pl-er-diagram-builder"
sys.path.insert(0, str(ROOT / "tests"))

from test_controller import in_element_dir, load_controller, load_server, new_data  # noqa: E402

BOOTSTRAP = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"

# Positions for the hero shot. Grading ignores layout.
HERO_LAYOUT = {
    "entities": {"Student": {"x": 40, "y": 150}, "Course": {"x": 470, "y": 150}},
    "relationships": {"Enrolls": {"x": 340, "y": 205}},
}

SMOKE_JS = r"""
(function () {
  var out = {};
  function hidden(id) { return JSON.parse(document.getElementById(id + "-raw-json").value); }
  function click(id) { document.getElementById(id).click(); }
  function canvasEvent(id, type, x, y) {
    var c = document.getElementById(id + "-er-canvas");
    var b = c.getBoundingClientRect();
    var ev = new MouseEvent(type, {
      bubbles: true,
      clientX: b.left + x * (b.width / c.width),
      clientY: b.top + y * (b.height / c.height),
    });
    c.dispatchEvent(ev);
  }
  try {
    var h = hidden("hero");
    out.hero_entities = h.entities.length;
    out.hero_relationships = h.relationships.length;
    canvasEvent("hero", "mousedown", 340, 205);
    canvasEvent("hero", "mouseup", 340, 205);
    out.rel_inspector_visible = !document.getElementById("hero-er-inspector-rel").classList.contains("d-none");
    out.inspector_has_participants = /participant/i.test(document.getElementById("hero-er-inspector-rel").textContent);
    click("hero-er-add-entity");
    out.after_add_entity = hidden("hero").entities.length;
    click("hero-er-undo");
    out.after_undo = hidden("hero").entities.length;
    click("hero-er-redo");
    out.after_redo = hidden("hero").entities.length;
    var s = hidden("starter");
    out.starter_entities = s.entities.map(function (e) { return e.name; });
    out.starter_relationships = s.relationships.length;
  } catch (e) {
    out.error = String(e && e.stack || e);
  }
  var pre = document.createElement("pre");
  pre.id = "smoke-results";
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
"""

SELECT_JS = r"""
(function () {
  var c = document.getElementById("hero-er-canvas");
  var b = c.getBoundingClientRect();
  ["mousedown", "mouseup"].forEach(function (t) {
    c.dispatchEvent(new MouseEvent(t, {
      bubbles: true,
      clientX: b.left + 340 * (b.width / c.width),
      clientY: b.top + 205 * (b.height / c.height),
    }));
  });
  c.blur();
})();
"""


def find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise SystemExit("Chrome not found. Set CHROME=/path/to/chrome.")


def render_panel(tag: str, data: dict) -> str:
    ctl = load_controller()
    ctl.prepare(tag, data)
    with in_element_dir():
        return ctl.render(tag, data)


def hero_html() -> str:
    data = new_data()
    load_server("erDiagram").generate(data)
    doc = json.loads(json.dumps(data["correct_answers"]["er"]))
    doc["layout"] = HERO_LAYOUT
    data["raw_submitted_answers"]["hero-raw"] = json.dumps(doc)
    data["correct_answers"]["hero"] = data["correct_answers"].pop("er")
    tag = '<pl-er-diagram-builder answers-name="hero" height="420" hide-instructions="true"></pl-er-diagram-builder>'
    return render_panel(tag, data)


def starter_html() -> str:
    data = new_data()
    load_server("erDiagramStarter").generate(data)
    data["params"]["starter_init"] = data["params"].pop("er_starter")
    tag = (
        '<pl-er-diagram-builder answers-name="starter" height="300" hide-instructions="true" '
        'starter-params-name="starter_init"></pl-er-diagram-builder>'
    )
    return render_panel(tag, data)


def page(body: str, extra_js: str) -> str:
    css = (ELEMENT / "pl-er-diagram-builder.css").read_text(encoding="utf-8")
    js = (ELEMENT / "pl-er-diagram-builder.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="{BOOTSTRAP}">
<style>body{{background:#fff;padding:16px 20px;}}{css}</style>
<script>{js}</script>
</head><body>
{body}
<script>{extra_js}</script>
</body></html>"""


def chrome_tmp() -> tempfile.TemporaryDirectory:
    """Chrome hangs when its page or profile is on exFAT/FAT; CHROME_TMPDIR can point elsewhere."""
    return tempfile.TemporaryDirectory(dir=os.environ.get("CHROME_TMPDIR") or None)


def run_chrome(html: str, args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    src = tmp / "page.html"
    src.write_text(html, encoding="utf-8")
    cmd = [
        find_chrome(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        "--window-size=1120,600",
        "--virtual-time-budget=4000",
        f"--user-data-dir={tmp / 'profile'}",
        *args,
        src.as_uri(),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=240)


def screenshot() -> int:
    out = ROOT / "docs" / "figures" / "element-editor.png"
    with chrome_tmp() as t:
        proc = run_chrome(page(hero_html(), SELECT_JS), [f"--screenshot={out}"], Path(t))
    if not out.exists():
        print(proc.stderr, file=sys.stderr)
        return 1
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


def smoke() -> int:
    body = hero_html() + "\n<hr>\n" + starter_html()
    with chrome_tmp() as t:
        proc = run_chrome(page(body, SMOKE_JS), ["--dump-dom"], Path(t))
    m = re.search(r'<pre id="smoke-results">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        print("no smoke results in DOM", file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        return 1
    res = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&"))
    expected = {
        "hero_entities": 2,
        "hero_relationships": 1,
        "rel_inspector_visible": True,
        "inspector_has_participants": True,
        "after_add_entity": 3,
        "after_undo": 2,
        "after_redo": 3,
        "starter_entities": ["Employee", "Pay"],
        "starter_relationships": 0,
    }
    failed = 0
    for k, v in expected.items():
        ok = res.get(k) == v
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {k}: {res.get(k)!r} (expected {v!r})")
    if "error" in res:
        failed += 1
        print("FAIL js error:", res["error"])
    print(f"{max(len(expected) - failed, 0)}/{len(expected)} browser checks passed")
    return 1 if failed else 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "screenshot"
    if mode == "screenshot":
        return screenshot()
    if mode == "smoke":
        return smoke()
    raise SystemExit("usage: render_element.py [screenshot|smoke]")


if __name__ == "__main__":
    sys.exit(main())
