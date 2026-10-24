#!/usr/bin/env python3
"""Draw Chen-style ER diagrams from examples/*.json into docs/figures/."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon, Rectangle

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.antialiased": True,
    }
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
OUT = ROOT / "docs" / "figures"

BG = "#F7F4EE"
INK = "#1C1916"
ENTITY_FILL = "#E4EDF5"
ENTITY_EDGE = "#1F3A5F"
REL_FILL = "#F3E6D4"
REL_EDGE = "#6B4423"
ATTR_FILL = "#EEF3EA"
ATTR_EDGE = "#3D5A45"
KEY_FILL = "#F4E9B0"
LINE = "#2A2622"
MUTED = "#5A534C"


def load_schema(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        "entities": doc["entities"],
        "relationships": doc["relationships"],
    }


def layout(doc: dict) -> dict:
    entities = doc["entities"]
    n = max(len(entities), 1)
    gap = 5.1
    start_x = -(n - 1) * gap / 2
    pos = {}
    sizes = {}
    for i, e in enumerate(entities):
        # Name-only Chen boxes. Weak entities get a slightly wider frame.
        w, h = (2.85, 1.15) if e.get("weak") else (2.55, 0.95)
        sizes[e["name"]] = (w, h)
        pos[e["name"]] = (start_x + i * gap, 0.0)

    rel_pos = {}
    used = []
    for r in doc["relationships"]:
        parts = [p["entity"] for p in r["participants"] if p["entity"] in pos]
        xs = [pos[name][0] for name in parts]
        ys = [pos[name][1] for name in parts]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        if len(parts) >= 3:
            cy += 2.3
        else:
            # If the midpoint sits on another entity, drop the diamond below.
            for name, (ex, ey) in pos.items():
                if name in parts:
                    continue
                if abs(ex - cx) < 1.6 and abs(ey - cy) < 0.9:
                    cy = ey - 2.55
                    break
        for ox, oy in used:
            if math.hypot(cx - ox, cy - oy) < 1.8:
                cy -= 2.0
        rel_pos[r["name"]] = (cx, cy)
        used.append((cx, cy))
    return {"entity": pos, "size": sizes, "rel": rel_pos}


def _draw_entity(ax, entity: dict, xy, size) -> None:
    x, y = xy
    w, h = size
    left, bottom = x - w / 2, y - h / 2
    ax.add_patch(
        FancyBboxPatch(
            (left, bottom),
            w,
            h,
            boxstyle="square,pad=0",
            linewidth=1.7,
            edgecolor=ENTITY_EDGE,
            facecolor=ENTITY_FILL,
            zorder=3,
        )
    )
    if entity.get("weak"):
        ax.add_patch(
            Rectangle(
                (left + 0.11, bottom + 0.11),
                w - 0.22,
                h - 0.22,
                linewidth=1.35,
                edgecolor=ENTITY_EDGE,
                facecolor="none",
                zorder=4,
            )
        )
    ax.text(x, y, entity["name"], ha="center", va="center", fontsize=12, color=INK, zorder=5)


def _diamond_size(name: str) -> tuple[float, float]:
    return max(1.25, 0.075 * len(name) + 0.85), 0.70


def _draw_diamond(ax, name: str, xy, weak: bool) -> None:
    x, y = xy
    hw, hh = _diamond_size(name)
    pts = [(x, y + hh), (x + hw, y), (x, y - hh), (x - hw, y)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=REL_FILL, edgecolor=REL_EDGE, lw=1.6, zorder=3))
    if weak:
        s = 0.78
        ipts = [(x, y + hh * s), (x + hw * s, y), (x, y - hh * s), (x - hw * s, y)]
        ax.add_patch(Polygon(ipts, closed=True, facecolor="none", edgecolor=REL_EDGE, lw=1.15, zorder=4))
    ax.text(x, y, name, ha="center", va="center", fontsize=10, color=INK, zorder=5)


def _draw_attr_oval(ax, label: str, xy, key: bool = False) -> None:
    x, y = xy
    w = max(1.35, 0.155 * len(label) + 0.7)
    h = 0.48
    ax.add_patch(
        Ellipse(
            (x, y),
            w,
            h,
            facecolor=KEY_FILL if key else ATTR_FILL,
            edgecolor=ATTR_EDGE,
            lw=1.15,
            zorder=3,
        )
    )
    ax.text(x, y + (0.03 if key else 0.0), label, ha="center", va="center", fontsize=9, color=INK, zorder=5)
    if key:
        tw = max(0.38, 0.062 * len(label))
        ax.plot([x - tw, x + tw], [y - 0.10, y - 0.10], color=INK, lw=0.8, zorder=5)


def _box_exit(xy, size, toward) -> tuple[float, float]:
    x, y = xy
    w, h = size
    tx, ty = toward
    vx, vy = tx - x, ty - y
    if vx == 0 and vy == 0:
        return x + w / 2, y
    axr, ayr = w / 2, h / 2
    scale = min(axr / abs(vx) if vx else 1e9, ayr / abs(vy) if vy else 1e9)
    return x + vx * scale, y + vy * scale


def _diamond_entry(cx, cy, toward, hw, hh) -> tuple[float, float]:
    tx, ty = toward
    vx, vy = tx - cx, ty - cy
    if vx == 0 and vy == 0:
        return cx, cy + hh
    # Intersect the diamond |x|/hw + |y|/hh = 1.
    t = 1.0 / (abs(vx) / hw + abs(vy) / hh)
    return cx + vx * t, cy + vy * t


def _edge(ax, p1, p2, total: bool) -> None:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=LINE, lw=1.45, zorder=2, solid_capstyle="round")
    if total:
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length * 0.07, dx / length * 0.07
        ax.plot(
            [p1[0] + nx, p2[0] + nx],
            [p1[1] + ny, p2[1] + ny],
            color=LINE,
            lw=1.15,
            zorder=2,
            solid_capstyle="round",
        )


def _card_label(cardinality: str) -> str:
    return "N" if cardinality == "many" else "1"


def _attr_slots(count: int, spread: float) -> list[float]:
    if count <= 1:
        return [0.0]
    return [(i - (count - 1) / 2) * spread for i in range(count)]


def render_one(path: Path, title: str) -> None:
    doc = load_schema(path)
    loc = layout(doc)

    fig, ax = plt.subplots(figsize=(12.0, 7.0), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    for r in doc["relationships"]:
        rx, ry = loc["rel"][r["name"]]
        attrs = r.get("attributes") or []
        for offset, attr in zip(_attr_slots(len(attrs), 1.55), attrs):
            ax.plot([rx, rx + offset], [ry + 0.72, ry + 1.45], color=LINE, lw=0.85, zorder=1)
            _draw_attr_oval(ax, attr, (rx + offset, ry + 1.55), key=False)

    for r in doc["relationships"]:
        rx, ry = loc["rel"][r["name"]]
        _draw_diamond(ax, r["name"], (rx, ry), bool(r.get("weak")))
        for p in r["participants"]:
            ex, ey = loc["entity"][p["entity"]]
            size = loc["size"][p["entity"]]
            start = _box_exit((ex, ey), size, (rx, ry))
            dhw, dhh = _diamond_size(r["name"])
            end = _diamond_entry(rx, ry, (ex, ey), dhw, dhh)
            _edge(ax, start, end, p["participation"] == "total")
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            # Park the 1/N label on the outside of the segment.
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length * 0.22, dx / length * 0.22
            ax.text(
                mid_x + nx,
                mid_y + ny,
                _card_label(p["cardinality"]),
                ha="center",
                va="center",
                fontsize=9,
                color=INK,
                zorder=5,
            )

    for e in doc["entities"]:
        name = e["name"]
        ex, ey = loc["entity"][name]
        ew, eh = loc["size"][name]
        _draw_entity(ax, e, (ex, ey), (ew, eh))
        keys = e.get("key_attributes") or []
        attrs = e.get("attributes") or []
        rel_below = any(
            abs(loc["rel"][r["name"]][0] - ex) < 2.2 and loc["rel"][r["name"]][1] < ey - 0.6
            for r in doc["relationships"]
        )
        for offset, key in zip(_attr_slots(len(keys), 1.6), keys):
            ax.plot([ex, ex + offset], [ey + eh / 2, ey + eh / 2 + 1.2], color=LINE, lw=0.85, zorder=1)
            _draw_attr_oval(ax, key, (ex + offset, ey + eh / 2 + 1.3), key=True)
        if rel_below:
            # Park descriptive attributes in the top band, to the right of keys.
            start = (len(keys) + 1) / 2 * 1.6
            for i, attr in enumerate(attrs):
                ox = start + i * 1.6
                ax.plot([ex, ex + ox], [ey + eh / 2, ey + eh / 2 + 1.2], color=LINE, lw=0.85, zorder=1)
                _draw_attr_oval(ax, attr, (ex + ox, ey + eh / 2 + 1.3), key=False)
        else:
            for offset, attr in zip(_attr_slots(len(attrs), 1.6), attrs):
                ax.plot([ex, ex + offset], [ey - eh / 2, ey - eh / 2 - 1.2], color=LINE, lw=0.85, zorder=1)
                _draw_attr_oval(ax, attr, (ex + offset, ey - eh / 2 - 1.3), key=False)

    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=14)
    ax.text(
        0.0,
        -0.07,
        "Chen notation. Double line = total participation. Underlined oval = key. Double box or diamond = weak / identifying.",
        transform=ax.transAxes,
        fontsize=8,
        color=MUTED,
    )
    ax.set_aspect("equal")
    ax.axis("off")
    ax.relim()
    ax.autoscale_view()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    pad_x = max(0.6, (x1 - x0) * 0.08)
    pad_y = max(0.6, (y1 - y0) * 0.12)
    ax.set_xlim(x0 - pad_x, x1 + pad_x)
    ax.set_ylim(y0 - pad_y, y1 + pad_y)
    fig.tight_layout()

    stem = path.stem
    png = OUT / f"{stem}.png"
    svg = OUT / f"{stem}.svg"
    fig.savefig(png, dpi=200, bbox_inches="tight", facecolor=BG)
    fig.savefig(svg, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"wrote {png.relative_to(ROOT)}")
    print(f"wrote {svg.relative_to(ROOT)}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("student-course.json", "Student / Course enrollment"),
        ("books-authors.json", "Books, authors, and categories"),
        ("employee-pay.json", "Weak entity: Pay identified by Employee"),
    ]
    for name, title in jobs:
        render_one(EXAMPLES / name, title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
