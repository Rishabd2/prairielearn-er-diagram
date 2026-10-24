/* eslint-disable */
// ER diagram editor: semantic JSON + layout, canvas editing, textarea sync.
const ERDiagramBuilder = (function () {
  const DEBOUNCE_MS = 320;
  const DIAMOND_HALF = 48;
  const ENTITY_MIN_W = 140;
  const LINE_H = 18;
  const TITLE_H = 22;
  const PAD = 10;
  const ZOOM_MIN = 0.5;
  const ZOOM_MAX = 2.0;
  const ZOOM_STEP = 0.1;
  const MAX_UNDO = 50;

  function ensureDocShape(doc) {
    if (!doc.entities) doc.entities = [];
    if (!doc.relationships) doc.relationships = [];
    if (!doc.layout) doc.layout = { entities: {}, relationships: {} };
    if (!doc.layout.entities) doc.layout.entities = {};
    if (!doc.layout.relationships) doc.layout.relationships = {};
  }

  function cloneDoc(doc) {
    return JSON.parse(JSON.stringify(doc));
  }

  function measureEntity(ctx, entity) {
    ctx.font = 'bold 15px system-ui, -apple-system, sans-serif';
    const titleW = ctx.measureText(entity.name || "").width;
    ctx.font = '13px ui-monospace, monospace';
    let maxW = titleW;
    const lines = [];
    lines.push({ text: entity.name, bold: true });
    for (const a of entity.key_attributes || []) {
      const s = String(a) + " (key)";
      maxW = Math.max(maxW, ctx.measureText(s).width);
      lines.push({ text: s, key: true });
    }
    for (const a of entity.attributes || []) {
      const s = String(a);
      maxW = Math.max(maxW, ctx.measureText(s).width);
      lines.push({ text: s });
    }
    const w = Math.max(ENTITY_MIN_W, maxW + 2 * PAD);
    const h = Math.max(
      TITLE_H + LINE_H,
      PAD + lines.length * LINE_H + PAD,
    );
    return { w, h, lines };
  }

  function rectCenter(r) {
    return { x: r.x + r.w / 2, y: r.y + r.h / 2 };
  }

  function pointInRect(px, py, r) {
    return px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h;
  }

  function pointInDiamond(px, py, cx, cy, half) {
    return Math.abs(px - cx) + Math.abs(py - cy) <= half;
  }

  function traceDiamondPath(c, cx, cy, half) {
    c.moveTo(cx, cy - half);
    c.lineTo(cx + half, cy);
    c.lineTo(cx, cy + half);
    c.lineTo(cx - half, cy);
    c.closePath();
  }

  /** Closest point on rectangle border toward target. */
  function rectExitToward(r, tx, ty) {
    const cx = r.x + r.w / 2;
    const cy = r.y + r.h / 2;
    const vx = tx - cx;
    const vy = ty - cy;
    if (vx === 0 && vy === 0) return { x: cx, y: r.y };
    const ax = Math.abs(vx);
    const ay = Math.abs(vy);
    let x, y;
    if (ax / r.w > ay / r.h) {
      x = vx > 0 ? r.x + r.w : r.x;
      y = cy + (vy / vx) * (x - cx);
      y = Math.max(r.y, Math.min(r.y + r.h, y));
    } else {
      y = vy > 0 ? r.y + r.h : r.y;
      x = cx + (vx / vy) * (y - cy);
      x = Math.max(r.x, Math.min(r.x + r.w, x));
    }
    return { x, y };
  }

  /** Entry point on diamond boundary from direction of (fx, fy). */
  function diamondEntry(cx, cy, half, fx, fy) {
    const dx = fx - cx;
    const dy = fy - cy;
    const adx = Math.abs(dx);
    const ady = Math.abs(dy);
    const s = adx + ady || 1;
    const ux = dx / s;
    const uy = dy / s;
    const t = half / (Math.abs(ux) + Math.abs(uy));
    return { x: cx + ux * t, y: cy + uy * t };
  }

  class ERDiagramBuilder {
    getById(id) {
      if (this.rootElement && this.rootElement.querySelector) {
        const esc =
          typeof CSS !== "undefined" && CSS.escape
            ? CSS.escape(id)
            : id.replace(/([^\w-])/g, "\\$1");
        return this.rootElement.querySelector("#" + esc);
      }
      return document.getElementById(id);
    }

    constructor(name, options) {
      this.answersName = name;
      this.idPrefix = options.idPrefix !== undefined ? options.idPrefix : name;
      this.rootElement = options.rootElement || null;
      this.editable = options.editable;
      this.canvas = this.getById(this.idPrefix + "-er-canvas");
      this.wrap = this.getById(this.idPrefix + "-er-canvas-wrap");
      this.textarea = this.getById(this.idPrefix + "-er-json-text");
      this.jsonError = this.getById(this.idPrefix + "-er-json-error");
      this.hiddenInput = this.getById(this.idPrefix + "-raw-json");
      this.modeHint = this.getById(this.idPrefix + "-er-mode-hint");
      this.zoomInBtn = this.getById(this.idPrefix + "-er-zoom-in");
      this.zoomOutBtn = this.getById(this.idPrefix + "-er-zoom-out");
      this.zoomLevel = this.getById(this.idPrefix + "-er-zoom-level");
      this.undoBtn = this.getById(this.idPrefix + "-er-undo");
      this.redoBtn = this.getById(this.idPrefix + "-er-redo");
      this.undoStack = [];
      this.redoStack = [];
      this._inspectorSelectionKey = "";
      this._inspectorOpenSnapshot = "";
      this._inspectorDirty = false;
      this._inspectorUndoPushed = false;
      this._dragUndoPushed = false;

      this.doc = {
        entities: [],
        relationships: [],
        layout: { entities: {}, relationships: {} },
      };
      this.selected = null;
      this.mode = "select";
      this.relPickEntity = null;
      this.drag = null;
      this.textareaProgrammatic = false;
      this._debouncedParseTimer = null;
      this.zoom = 1;
      this.canvasHeight = options.height || 600;
      if (this.canvas) {
        this.canvas.setAttribute("data-height", String(this.canvasHeight));
      }

      this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
      this._onCanvasKeydown = (e) => {
        if (!this.editable) return;
        const ae = document.activeElement;
        if (ae === this.textarea) return;
        if (e.key === "Escape" && this.mode === "add_rel") {
          e.preventDefault();
          this.cancelAddRelMode();
          return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "y")) {
          if (this.inspectorRoot && this.inspectorRoot.contains(ae)) return;
          const tag = ae && ae.tagName;
          if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
          if (e.key === "z" && e.shiftKey) {
            e.preventDefault();
            this.redo();
            return;
          }
          if (e.key === "z" && !e.shiftKey) {
            e.preventDefault();
            this.undo();
            return;
          }
          if (e.key === "y") {
            e.preventDefault();
            this.redo();
            return;
          }
        }
        if (e.key === "Delete" || e.key === "Backspace") {
          if (this.inspectorRoot && this.inspectorRoot.contains(ae)) return;
          const tag = ae && ae.tagName;
          if (
            tag === "INPUT" ||
            tag === "TEXTAREA" ||
            tag === "SELECT"
          ) {
            return;
          }
          e.preventDefault();
          this.deleteSelected();
        }
      };
      this.restoreBackup(options.backupJson);
      this.setFormatErrors(options.formatErrorsJson);
      this.ensureLayoutDefaults();
      this.flushTextareaAndHidden();
      this.updateModeHint();

      const ro = new ResizeObserver(() => {
        this.syncCanvasSize();
        this.draw();
      });
      if (this.wrap) ro.observe(this.wrap);

      this.setupZoomControls();

      if (!this.editable) {
        this.syncCanvasSize();
        this.draw();
        return;
      }

      if (this.canvas) {
        this.canvas.addEventListener("keydown", this._onCanvasKeydown);
      }

      if (this.hiddenInput && this.hiddenInput.form) {
        this.hiddenInput.form.addEventListener("submit", () => {
          this.commitPendingBeforeSubmit();
        });
      }

      this.textarea.addEventListener("input", () => {
        if (this.textareaProgrammatic) return;
        clearTimeout(this._debouncedParseTimer);
        this._debouncedParseTimer = setTimeout(() => {
          this._debouncedParseTimer = null;
          this.syncDocFromTextarea();
        }, DEBOUNCE_MS);
      });

      this.textarea.addEventListener("blur", () => {
        clearTimeout(this._debouncedParseTimer);
        this._debouncedParseTimer = null;
        if (this.textareaProgrammatic) return;
        this.normalizeTextareaOnBlur();
      });

      this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
      this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
      this.canvas.addEventListener("mouseup", (e) => this.onMouseUp(e));
      this.canvas.addEventListener("dblclick", (e) => this.onDblClick(e));

      this.getById(this.idPrefix + "-er-add-entity").addEventListener("click", () => {
        this.mode = "select";
        this.relPickEntity = null;
        this.addEntity();
        this.updateModeHint();
        this.updateAddRelButtonUI();
      });
      this.getById(this.idPrefix + "-er-add-rel").addEventListener("click", () => {
        if (this.mode === "add_rel") {
          this.cancelAddRelMode();
        } else {
          this.enterAddRelMode();
        }
      });
      this.getById(this.idPrefix + "-er-clear").addEventListener("click", () => {
        if (!window.confirm("Clear the entire diagram?")) return;
        this.pushUndoCheckpoint();
        this.doc = {
          entities: [],
          relationships: [],
          layout: { entities: {}, relationships: {} },
        };
        this.selected = null;
        this.mode = "select";
        this.relPickEntity = null;
        this._inspectorDirty = false;
        this.flushTextareaAndHidden();
        this.updateModeHint();
        this.updateAddRelButtonUI();
        this.draw();
        this.renderInspector();
        this.updateUndoRedoUi();
      });

      if (this.undoBtn) {
        this.undoBtn.addEventListener("click", () => this.undo());
      }
      if (this.redoBtn) {
        this.redoBtn.addEventListener("click", () => this.redo());
      }

      this.syncCanvasSize();
      this.draw();

      if (this.editable) {
        this.inspectorRoot = this.getById(this.idPrefix + "-er-inspector");
        this.inspectorEmpty = this.getById(this.idPrefix + "-er-inspector-empty");
        this.inspectorEntity = this.getById(this.idPrefix + "-er-inspector-entity");
        this.inspectorRel = this.getById(this.idPrefix + "-er-inspector-rel");
        this.renderInspector();
        this.updateUndoRedoUi();
      }
    }

    pushUndoCheckpoint() {
      if (!this.editable) return;
      const s = JSON.stringify(this.doc);
      if (
        this.undoStack.length &&
        this.undoStack[this.undoStack.length - 1] === s
      ) {
        return;
      }
      this.undoStack.push(s);
      if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
      this.redoStack = [];
    }

    undo() {
      if (!this.editable || this.undoStack.length === 0) return;
      const cur = JSON.stringify(this.doc);
      this.redoStack.push(cur);
      const prev = this.undoStack.pop();
      try {
        this.doc = JSON.parse(prev);
        ensureDocShape(this.doc);
        this.ensureLayoutDefaults();
      } catch (e) {
        return;
      }
      this._inspectorDirty = false;
      this._inspectorUndoPushed = false;
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    redo() {
      if (!this.editable || this.redoStack.length === 0) return;
      const cur = JSON.stringify(this.doc);
      this.undoStack.push(cur);
      const next = this.redoStack.pop();
      try {
        this.doc = JSON.parse(next);
        ensureDocShape(this.doc);
        this.ensureLayoutDefaults();
      } catch (e) {
        return;
      }
      this._inspectorDirty = false;
      this._inspectorUndoPushed = false;
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    updateUndoRedoUi() {
      if (this.undoBtn) {
        this.undoBtn.disabled = this.undoStack.length === 0;
      }
      if (this.redoBtn) {
        this.redoBtn.disabled = this.redoStack.length === 0;
      }
    }

    beforeCanvasSelectionChange() {
      if (!this.editable) return;
      if (this._inspectorDirty) {
        this.flushTextareaAndHidden();
        this._inspectorDirty = false;
        this._inspectorUndoPushed = false;
        this._inspectorOpenSnapshot = JSON.stringify(this.doc);
      }
    }

    inspectorEditStart() {
      if (!this.editable || !this.selected) return;
      if (!this._inspectorUndoPushed) {
        this.pushUndoCheckpoint();
        this._inspectorUndoPushed = true;
      }
      this._inspectorDirty = true;
    }

    commitInspectorApply() {
      if (!this._inspectorDirty) return;
      this.flushTextareaAndHidden();
      this._inspectorDirty = false;
      this._inspectorUndoPushed = false;
      this._inspectorOpenSnapshot = JSON.stringify(this.doc);
      this.updateUndoRedoUi();
    }

    commitInspectorDiscard() {
      if (!this._inspectorOpenSnapshot) return;
      try {
        this.doc = JSON.parse(this._inspectorOpenSnapshot);
        ensureDocShape(this.doc);
        this.ensureLayoutDefaults();
      } catch (e) {
        return;
      }
      this._inspectorDirty = false;
      this._inspectorUndoPushed = false;
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    previewInspectorRedraw() {
      // Keep hidden submitted payload synced even before Apply/selection change.
      this.flushTextareaAndHidden();
      this.recomputeEntitySizes();
      this.draw();
    }

    previewRedrawRerenderInspector() {
      this.previewInspectorRedraw();
      this.renderInspector();
    }

    /** World size = max(viewport-fill, content extent). Decoupled from viewport so the canvas can grow as entities are placed/dragged outward. */
    computeWorldSize() {
      const z = this.zoom || 1;
      const wrapW = this.wrap ? this.wrap.clientWidth : 0;
      const wrapH = this.wrap ? this.wrap.clientHeight : 0;
      // Ensure the canvas display always fills the wrap at the current zoom.
      const minW = Math.max(280, Math.ceil(wrapW / z));
      const minH = Math.max(this.canvasHeight || 600, Math.ceil(wrapH / z));
      const PAD_AROUND = 80;
      let maxX = minW;
      let maxY = minH;
      for (const e of this.doc.entities) {
        const L = this.doc.layout.entities[e.name];
        if (!L) continue;
        const wEnt = L.width || ENTITY_MIN_W;
        const hEnt = L.height || TITLE_H + LINE_H;
        maxX = Math.max(maxX, L.x + wEnt + PAD_AROUND);
        maxY = Math.max(maxY, L.y + hEnt + PAD_AROUND);
      }
      for (const r of this.doc.relationships) {
        const L = this.doc.layout.relationships[r.name];
        if (!L) continue;
        maxX = Math.max(maxX, L.x + DIAMOND_HALF + PAD_AROUND);
        maxY = Math.max(maxY, L.y + DIAMOND_HALF + PAD_AROUND);
      }
      return { w: maxX, h: maxY };
    }

    syncCanvasSize() {
      if (!this.wrap || !this.canvas) return;
      const z = this.zoom;
      const world = this.computeWorldSize();
      const pxW = Math.ceil(world.w * z);
      const pxH = Math.ceil(world.h * z);
      // Skip writes when nothing changed; assigning canvas.width clears the buffer.
      if (this.canvas.width !== pxW) this.canvas.width = pxW;
      if (this.canvas.height !== pxH) this.canvas.height = pxH;
      const styleW = pxW + "px";
      const styleH = pxH + "px";
      // Pin the displayed canvas size so zoom actually scales the visible canvas;
      // without this, .pl-er-canvas { width: 100% } cancels the buffer scaling.
      if (this.canvas.style.width !== styleW) this.canvas.style.width = styleW;
      if (this.canvas.style.height !== styleH) this.canvas.style.height = styleH;
    }

    setupZoomControls() {
      this.updateZoomUI();
      if (this.zoomInBtn) {
        this.zoomInBtn.addEventListener("click", () => this.changeZoom(ZOOM_STEP));
      }
      if (this.zoomOutBtn) {
        this.zoomOutBtn.addEventListener("click", () => this.changeZoom(-ZOOM_STEP));
      }
    }

    updateZoomUI() {
      const pct = Math.round(this.zoom * 100);
      if (this.zoomLevel) {
        this.zoomLevel.textContent = pct + "%";
      }
      if (this.zoomInBtn) {
        this.zoomInBtn.disabled = this.zoom >= ZOOM_MAX;
      }
      if (this.zoomOutBtn) {
        this.zoomOutBtn.disabled = this.zoom <= ZOOM_MIN;
      }
    }

    changeZoom(delta) {
      const next = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, this.zoom + delta));
      this.zoom = Math.round(next * 100) / 100;
      this.updateZoomUI();
      this.syncCanvasSize();
      this.draw();
    }

    restoreBackup(backupJson) {
      if (backupJson === null || backupJson === undefined) {
        ensureDocShape(this.doc);
        return;
      }
      try {
        const d = typeof backupJson === "string" ? JSON.parse(backupJson) : backupJson;
        this.doc = d;
        ensureDocShape(this.doc);
      } catch (e) {
        ensureDocShape(this.doc);
      }
    }

    setFormatErrors(formatErrorsJson) {
      if (!formatErrorsJson || !this.jsonError) return;
      try {
        const err =
          typeof formatErrorsJson === "string"
            ? JSON.parse(formatErrorsJson)
            : formatErrorsJson;
        if (err && err.message) {
          this.jsonError.textContent = err.message.replace(/<[^>]+>/g, "");
        }
      } catch (e) {}
    }

    ensureLayoutDefaults() {
      ensureDocShape(this.doc);
      // Infinite-canvas semantics: only enforce a positive top-left so things
      // remain reachable; the right/bottom extent is unbounded and the canvas
      // grows to fit (see computeWorldSize).
      const MIN_POS = 10;
      this.doc.entities.forEach((e, i) => {
        if (!this.doc.layout.entities[e.name]) {
          this.doc.layout.entities[e.name] = {
            x: 60 + (i % 3) * 220,
            y: 80 + Math.floor(i / 3) * 160,
          };
        }
        const le = this.doc.layout.entities[e.name];
        if (!Number.isFinite(le.x)) le.x = 60 + (i % 3) * 220;
        if (!Number.isFinite(le.y)) le.y = 80 + Math.floor(i / 3) * 160;
        le.x = Math.max(MIN_POS, le.x);
        le.y = Math.max(MIN_POS, le.y);
      });
      this.doc.relationships.forEach((r, j) => {
        if (!this.doc.layout.relationships[r.name]) {
          const parts = r.participants || [];
          let cx = 320,
            cy = 280 + j * 40;
          if (parts.length >= 2) {
            const a = this.getRect(parts[0].entity);
            const b = this.getRect(parts[1].entity);
            if (a && b) {
              cx = (rectCenter(a).x + rectCenter(b).x) / 2;
              cy = (rectCenter(a).y + rectCenter(b).y) / 2;
            }
          }
          this.doc.layout.relationships[r.name] = { x: cx, y: cy };
        }
        const lr = this.doc.layout.relationships[r.name];
        if (!Number.isFinite(lr.x)) lr.x = 320;
        if (!Number.isFinite(lr.y)) lr.y = 280 + j * 40;
        lr.x = Math.max(MIN_POS, lr.x);
        lr.y = Math.max(MIN_POS, lr.y);
      });
      this.recomputeEntitySizes();
    }

    recomputeEntitySizes() {
      if (!this.ctx) return;
      const c = this.ctx;
      this.doc.entities.forEach((e) => {
        const { w, h } = measureEntity(c, e);
        const L = this.doc.layout.entities[e.name];
        if (L) {
          L.width = w;
          L.height = h;
        }
      });
    }

    getRect(entityName) {
      if (!this.ctx) return null;
      const e = this.doc.entities.find((x) => x.name === entityName);
      if (!e) return null;
      const L = this.doc.layout.entities[e.name];
      if (!L) return null;
      const { w, h } = measureEntity(this.ctx, e);
      return { x: L.x, y: L.y, w, h };
    }

    getDiamond(relName) {
      const L = this.doc.layout.relationships[relName];
      if (!L) return null;
      return { cx: L.x, cy: L.y, half: DIAMOND_HALF };
    }

    hitTest(mx, my) {
      for (let i = this.doc.entities.length - 1; i >= 0; i--) {
        const e = this.doc.entities[i];
        const r = this.getRect(e.name);
        if (r && pointInRect(mx, my, r)) {
          return { type: "entity", name: e.name };
        }
      }
      for (let i = this.doc.relationships.length - 1; i >= 0; i--) {
        const r = this.doc.relationships[i];
        const d = this.getDiamond(r.name);
        if (d && pointInDiamond(mx, my, d.cx, d.cy, d.half)) {
          return { type: "relationship", name: r.name };
        }
      }
      return null;
    }

    updateModeHint() {
      if (!this.modeHint) return;
      if (this.mode === "add_rel") {
        if (this.relPickEntity) {
          this.modeHint.textContent =
            'First participant: "' +
            this.relPickEntity +
            '".\n' +
            "Click another entity to link them. To cancel, click empty space, press Esc, or click “Add relationship” again.";
        } else {
          this.modeHint.textContent =
            'Click two entities to create a relationship. Click empty space, press Esc, or click "Add relationship" again to cancel.';
        }
      } else {
        this.modeHint.textContent = "";
      }
    }

    updateAddRelButtonUI() {
      const btn = this.getById(this.idPrefix + "-er-add-rel");
      if (!btn) return;
      const active = this.mode === "add_rel";
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    }

    enterAddRelMode() {
      this.mode = "add_rel";
      // If an entity is already selected, treat it as the first participant
      // so the workflow continues smoothly instead of leaving a stale
      // selection visible alongside an empty pick state.
      if (this.selected && this.selected.type === "entity") {
        this.relPickEntity = this.selected.name;
      } else {
        this.relPickEntity = null;
      }
      this.selected = null;
      this.updateModeHint();
      this.updateAddRelButtonUI();
      this.draw();
      this.renderInspector();
      // Focus the canvas so the Esc keybinding works without an extra click.
      if (this.canvas) {
        try {
          this.canvas.focus({ preventScroll: true });
        } catch (e) {
          this.canvas.focus();
        }
      }
    }

    cancelAddRelMode() {
      this.mode = "select";
      this.relPickEntity = null;
      this.updateModeHint();
      this.updateAddRelButtonUI();
      this.draw();
    }

    onMouseDown(e) {
      if (this.editable && this.canvas) {
        this.canvas.focus();
      }
      if (this.textarea && document.activeElement === this.textarea) {
        this.textarea.blur();
      }
      if (this.editable) this.beforeCanvasSelectionChange();
      const mouse = this.canvasMouse(e);
      const hit = this.hitTest(mouse.x, mouse.y);

      if (this.mode === "add_rel") {
        if (hit && hit.type === "entity") {
          if (!this.relPickEntity) {
            this.relPickEntity = hit.name;
            this.updateModeHint();
            this.draw();
            this.renderInspector();
            return;
          }
          if (this.relPickEntity === hit.name) return;
          const eFirst = this.relPickEntity;
          this.relPickEntity = null;
          this.mode = "select";
          this.updateModeHint();
          this.updateAddRelButtonUI();
          this.createRelationship(eFirst, hit.name);
          return;
        }
        // Clicking empty canvas or a relationship while in add_rel mode
        // exits the mode so the user is never trapped with no escape.
        this.cancelAddRelMode();
        this.selected = null;
        this.drag = null;
        this.renderInspector();
        return;
      }

      if (!hit) {
        this.selected = null;
        this.drag = null;
        this.draw();
        this.renderInspector();
        return;
      }

      this.selected = { type: hit.type, name: hit.name };
      if (hit.type === "entity") {
        const r = this.getRect(hit.name);
        this.drag = {
          kind: "entity",
          name: hit.name,
          ox: mouse.x - r.x,
          oy: mouse.y - r.y,
        };
      } else {
        const d = this.getDiamond(hit.name);
        this.drag = {
          kind: "relationship",
          name: hit.name,
          ox: mouse.x - d.cx,
          oy: mouse.y - d.cy,
        };
      }
      this.draw();
      this.renderInspector();
    }

    onMouseMove(e) {
      if (!this.drag) return;
      if (!this._dragUndoPushed) {
        this.pushUndoCheckpoint();
        this._dragUndoPushed = true;
      }
      const mouse = this.canvasMouse(e);
      if (this.drag.kind === "entity") {
        const L = this.doc.layout.entities[this.drag.name];
        if (L) {
          L.x = mouse.x - this.drag.ox;
          L.y = mouse.y - this.drag.oy;
        }
      } else {
        const L = this.doc.layout.relationships[this.drag.name];
        if (L) {
          L.x = mouse.x - this.drag.ox;
          L.y = mouse.y - this.drag.oy;
        }
      }
      this.draw();
    }

    onMouseUp(_e) {
      if (this.drag && this._dragUndoPushed && this.hiddenInput) {
        this.flushTextareaAndHidden();
        this.updateUndoRedoUi();
      }
      this.drag = null;
      this._dragUndoPushed = false;
    }

    onDblClick(e) {
      const mouse = this.canvasMouse(e);
      if (this.hitTest(mouse.x, mouse.y)) return;
      this.addEntityAt(mouse.x, mouse.y);
    }

    canvasMouse(e) {
      const bbox = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / bbox.width;
      const scaleY = this.canvas.height / bbox.height;
      return {
        x: ((e.clientX - bbox.left) * scaleX) / this.zoom,
        y: ((e.clientY - bbox.top) * scaleY) / this.zoom,
      };
    }

    nextAvailableName(prefix, existingNames) {
      const used = new Set(existingNames);
      let i = 1;
      while (used.has(prefix + i)) i += 1;
      return prefix + i;
    }

    addEntity() {
      this.pushUndoCheckpoint();
      const name = this.nextAvailableName(
        "Entity_",
        this.doc.entities.map((x) => x.name),
      );
      const n = this.doc.entities.length;
      this.doc.entities.push({
        name,
        key_attributes: [],
        attributes: [],
      });
      this.doc.layout.entities[name] = {
        x: 60 + (n % 3) * 220,
        y: 80 + Math.floor(n / 3) * 160,
      };
      this.recomputeEntitySizes();
      this.selected = { type: "entity", name };
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    addEntityAt(x, y) {
      this.pushUndoCheckpoint();
      const name = this.nextAvailableName(
        "Entity_",
        this.doc.entities.map((z) => z.name),
      );
      this.doc.entities.push({
        name,
        key_attributes: [],
        attributes: [],
      });
      this.doc.layout.entities[name] = { x: x - 70, y: y - 40 };
      this.recomputeEntitySizes();
      this.selected = { type: "entity", name };
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    createRelationship(e1, e2) {
      this.pushUndoCheckpoint();
      const name = this.nextAvailableName(
        "Rel_",
        this.doc.relationships.map((x) => x.name),
      );
      const r1 = this.getRect(e1);
      const r2 = this.getRect(e2);
      let cx = 300,
        cy = 250;
      if (r1 && r2) {
        cx = (rectCenter(r1).x + rectCenter(r2).x) / 2;
        cy = (rectCenter(r1).y + rectCenter(r2).y) / 2;
      }
      this.doc.relationships.push({
        name,
        participants: [
          { entity: e1, cardinality: "many", participation: "partial" },
          { entity: e2, cardinality: "many", participation: "partial" },
        ],
        attributes: [],
      });
      this.doc.layout.relationships[name] = { x: cx, y: cy };
      this.selected = { type: "relationship", name };
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    deleteSelected() {
      if (!this.selected) return;
      this.pushUndoCheckpoint();
      if (this.selected.type === "entity") {
        const n = this.selected.name;
        this.doc.entities = this.doc.entities.filter((e) => e.name !== n);
        delete this.doc.layout.entities[n];
        this.doc.relationships = this.doc.relationships.filter((r) => {
          const parts = r.participants || [];
          if (parts.some((p) => p.entity === n)) {
            delete this.doc.layout.relationships[r.name];
            return false;
          }
          return true;
        });
      } else {
        const n = this.selected.name;
        this.doc.relationships = this.doc.relationships.filter((r) => r.name !== n);
        delete this.doc.layout.relationships[n];
      }
      this.selected = null;
      this.flushTextareaAndHidden();
      this.draw();
      this.renderInspector();
      this.updateUndoRedoUi();
    }

    /** Debounced while typing: updates model + submit hidden + canvas; does not replace textarea (preserves caret). */
    syncDocFromTextarea() {
      const raw = this.textarea.value;
      try {
        const d = JSON.parse(raw);
        ensureDocShape(d);
        this.doc = d;
        this.ensureLayoutDefaults();
        if (this.jsonError) this.jsonError.textContent = "";
        this.hiddenInput.value = JSON.stringify(this.doc, null, 2);
        this.draw();
        this.syncSelectionAfterDocChange();
        this.renderInspector();
      } catch (err) {
        if (this.jsonError) this.jsonError.textContent = "Invalid JSON: " + err.message;
      }
    }

    /** On blur: pretty-print textarea and hidden when valid; on error leave last-good hidden unchanged. */
    normalizeTextareaOnBlur() {
      const raw = this.textarea.value;
      try {
        const d = JSON.parse(raw);
        this.pushUndoCheckpoint();
        ensureDocShape(d);
        this.doc = d;
        this.ensureLayoutDefaults();
        if (this.jsonError) this.jsonError.textContent = "";
        const normalized = JSON.stringify(this.doc, null, 2);
        this.hiddenInput.value = normalized;
        this.textareaProgrammatic = true;
        this.textarea.value = normalized;
        this.textareaProgrammatic = false;
        this.draw();
        this.syncSelectionAfterDocChange();
        this.renderInspector();
        this.updateUndoRedoUi();
      } catch (err) {
        if (this.jsonError) this.jsonError.textContent = "Invalid JSON: " + err.message;
      }
    }

    flushTextareaAndHidden() {
      ensureDocShape(this.doc);
      this.recomputeEntitySizes();
      const s = JSON.stringify(this.doc, null, 2);
      if (!this.hiddenInput) return;
      this.hiddenInput.value = s;
      if (this.textarea && document.activeElement !== this.textarea) {
        this.textareaProgrammatic = true;
        this.textarea.value = s;
        this.textareaProgrammatic = false;
      }
      if (this.jsonError) this.jsonError.textContent = "";
    }

    commitPendingBeforeSubmit() {
      if (!this.editable) return;
      const ae = document.activeElement;
      if (
        ae &&
        (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA" || ae.tagName === "SELECT")
      ) {
        ae.blur();
      }
      if (this._debouncedParseTimer) {
        clearTimeout(this._debouncedParseTimer);
        this._debouncedParseTimer = null;
      }
      if (this.textarea && !this.textareaProgrammatic) {
        this.syncDocFromTextarea();
      }
      if (this._inspectorDirty) {
        this.commitInspectorApply();
      } else {
        this.flushTextareaAndHidden();
      }
    }

    renameEntity(oldName, newName) {
      newName = (newName || "").trim();
      if (!newName || newName === oldName) return true;
      if (this.doc.entities.some((e) => e.name === newName)) {
        window.alert("An entity with that name already exists.");
        return false;
      }
      const ent = this.doc.entities.find((e) => e.name === oldName);
      if (!ent) return false;
      ent.name = newName;
      const lo = this.doc.layout.entities[oldName];
      if (lo) {
        delete this.doc.layout.entities[oldName];
        this.doc.layout.entities[newName] = lo;
      }
      for (const r of this.doc.relationships) {
        for (const p of r.participants || []) {
          if (p.entity === oldName) p.entity = newName;
        }
      }
      if (this.selected && this.selected.type === "entity" && this.selected.name === oldName) {
        this.selected.name = newName;
      }
      if (this.drag && this.drag.kind === "entity" && this.drag.name === oldName) {
        this.drag.name = newName;
      }
      if (this.relPickEntity === oldName) this.relPickEntity = newName;
      return true;
    }

    renameRelationship(oldName, newName) {
      newName = (newName || "").trim();
      if (!newName || newName === oldName) return true;
      if (this.doc.relationships.some((r) => r.name === newName)) {
        window.alert("A relationship with that name already exists.");
        return false;
      }
      const rel = this.doc.relationships.find((r) => r.name === oldName);
      if (!rel) return false;
      rel.name = newName;
      const lo = this.doc.layout.relationships[oldName];
      if (lo) {
        delete this.doc.layout.relationships[oldName];
        this.doc.layout.relationships[newName] = lo;
      }
      if (this.selected && this.selected.type === "relationship" && this.selected.name === oldName) {
        this.selected.name = newName;
      }
      if (this.drag && this.drag.kind === "relationship" && this.drag.name === oldName) {
        this.drag.name = newName;
      }
      return true;
    }

    syncSelectionAfterDocChange() {
      if (this.selected) {
        if (this.selected.type === "entity") {
          if (!this.doc.entities.some((e) => e.name === this.selected.name)) {
            this.selected = null;
          }
        } else if (this.selected.type === "relationship") {
          if (!this.doc.relationships.some((r) => r.name === this.selected.name)) {
            this.selected = null;
          }
        }
      }
      if (
        this.relPickEntity &&
        !this.doc.entities.some((e) => e.name === this.relPickEntity)
      ) {
        this.relPickEntity = null;
        if (this.mode === "add_rel") this.updateModeHint();
      }
    }

    renderInspector() {
      if (!this.editable || !this.inspectorRoot) return;

      const empty = this.inspectorEmpty;
      const panelE = this.inspectorEntity;
      const panelR = this.inspectorRel;
      if (!this.selected) {
        empty.classList.remove("d-none");
        panelE.classList.add("d-none");
        panelR.classList.add("d-none");
        empty.textContent = "Select an entity or relationship on the canvas.";
        return;
      }
      empty.classList.add("d-none");
      if (this.selected.type === "entity") {
        panelR.classList.add("d-none");
        panelE.classList.remove("d-none");
        this.renderInspectorEntity();
      } else {
        panelE.classList.add("d-none");
        panelR.classList.remove("d-none");
        this.renderInspectorRel();
      }
    }

    renderInspectorEntity() {
      const panel = this.inspectorEntity;
      panel.innerHTML = "";
      const ent = this.doc.entities.find((e) => e.name === this.selected.name);
      if (!ent) {
        this.selected = null;
        this.renderInspector();
        return;
      }
      if (!Array.isArray(ent.key_attributes)) ent.key_attributes = [];
      if (!Array.isArray(ent.attributes)) ent.attributes = [];

      const selKeyEnt = "entity:" + ent.name;
      if (selKeyEnt !== this._inspectorSelectionKey) {
        this._inspectorSelectionKey = selKeyEnt;
        this._inspectorOpenSnapshot = JSON.stringify(this.doc);
        this._inspectorDirty = false;
        this._inspectorUndoPushed = false;
      }

      const toolbar = document.createElement("div");
      toolbar.className =
        "d-flex justify-content-between align-items-center gap-2 mb-2";
      const titleEnt = document.createElement("div");
      titleEnt.className = "small fw-bold mb-0";
      titleEnt.textContent = "Entity";
      const delEnt = document.createElement("button");
      delEnt.type = "button";
      delEnt.className = "btn btn-outline-danger btn-sm";
      delEnt.textContent = "Delete selection";
      delEnt.addEventListener("click", () => this.deleteSelected());
      toolbar.appendChild(titleEnt);
      toolbar.appendChild(delEnt);
      panel.appendChild(toolbar);

      // Apply/Discard will be appended after the attribute sections so
      // they appear at the end of the inspector panel.

      const nameLbl = document.createElement("label");
      nameLbl.className = "form-label small mb-0";
      nameLbl.textContent = "Name";
      panel.appendChild(nameLbl);
      const nameIn = document.createElement("input");
      nameIn.type = "text";
      nameIn.className = "form-control form-control-sm mb-2";
      nameIn.value = ent.name;
      nameIn.addEventListener("blur", () => {
        const nv = nameIn.value.trim();
        if (!nv) {
          nameIn.value = ent.name;
          return;
        }
        if (nv !== ent.name) {
          this.inspectorEditStart();
          const prev = ent.name;
          if (!this.renameEntity(prev, nv)) {
            nameIn.value = ent.name;
          } else {
            this.previewRedrawRerenderInspector();
          }
        }
      });
      panel.appendChild(nameIn);

      const weakWrap = document.createElement("div");
      weakWrap.className = "form-check mb-2";
      const weakCb = document.createElement("input");
      weakCb.type = "checkbox";
      weakCb.className = "form-check-input";
      weakCb.id = this.answersName + "-er-insp-weak-e";
      weakCb.checked = ent.weak === true;
      weakCb.addEventListener("change", () => {
        this.inspectorEditStart();
        ent.weak = weakCb.checked;
        this.previewInspectorRedraw();
      });
      const weakLbl = document.createElement("label");
      weakLbl.className = "form-check-label small";
      weakLbl.htmlFor = weakCb.id;
      weakLbl.textContent = "Weak entity (double rectangle)";
      weakWrap.appendChild(weakCb);
      weakWrap.appendChild(weakLbl);
      panel.appendChild(weakWrap);

      const addAttrSection = (labelText, arr, isKey) => {
        const lbl = document.createElement("div");
        lbl.className = "small fw-bold mt-2 mb-1";
        lbl.textContent = labelText;
        panel.appendChild(lbl);
        const list = document.createElement("div");
        list.className = "er-insp-attr-list";
        const stripEmpty = () => {
          const cleaned = arr.map((s) => String(s).trim()).filter((s) => s.length > 0);
          arr.length = 0;
          cleaned.forEach((x) => arr.push(x));
        };
        arr.forEach((val, idx) => {
          const row = document.createElement("div");
          row.className = "input-group input-group-sm mb-1 er-insp-row";
          const inp = document.createElement("input");
          inp.type = "text";
          inp.className = "form-control";
          inp.value = val;
          inp.placeholder = isKey ? "key attribute" : "attribute";
          inp.addEventListener("change", () => {
            this.inspectorEditStart();
            arr[idx] = inp.value.trim();
            stripEmpty();
            this.previewInspectorRedraw();
          });
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn btn-outline-secondary btn-sm";
          btn.textContent = "×";
          btn.title = "Remove";
          btn.addEventListener("click", () => {
            this.inspectorEditStart();
            arr.splice(idx, 1);
            stripEmpty();
            this.previewRedrawRerenderInspector();
          });
          row.appendChild(inp);
          row.appendChild(btn);
          list.appendChild(row);
        });
        panel.appendChild(list);
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "btn btn-outline-secondary btn-sm mb-2";
        addBtn.textContent = isKey ? "Add key attribute" : "Add attribute";
        addBtn.addEventListener("click", () => {
          this.inspectorEditStart();
          arr.push("");
          this.previewRedrawRerenderInspector();
        });
        panel.appendChild(addBtn);
      };

      addAttrSection("Key attributes", ent.key_attributes, true);
      addAttrSection("Attributes", ent.attributes, false);

      const applyRowE = document.createElement("div");
      applyRowE.className = "d-flex justify-content-end gap-2 flex-wrap mt-3";
      const applyEBtn = document.createElement("button");
      applyEBtn.type = "button";
      applyEBtn.className = "btn btn-primary btn-sm";
      applyEBtn.textContent = "Apply Change";
      applyEBtn.addEventListener("click", () => this.commitInspectorApply());
      const discardEBtn = document.createElement("button");
      discardEBtn.type = "button";
      discardEBtn.className = "btn btn-outline-secondary btn-sm";
      discardEBtn.textContent = "Discard";
      discardEBtn.addEventListener("click", () => this.commitInspectorDiscard());
      applyRowE.appendChild(applyEBtn);
      applyRowE.appendChild(discardEBtn);
      panel.appendChild(applyRowE);
    }

    renderInspectorRel() {
      const panel = this.inspectorRel;
      panel.innerHTML = "";
      const rel = this.doc.relationships.find((r) => r.name === this.selected.name);
      if (!rel) {
        this.selected = null;
        this.renderInspector();
        return;
      }
      if (!rel.participants) rel.participants = [];
      if (!rel.attributes) rel.attributes = [];

      const selKeyRel = "relationship:" + rel.name;
      if (selKeyRel !== this._inspectorSelectionKey) {
        this._inspectorSelectionKey = selKeyRel;
        this._inspectorOpenSnapshot = JSON.stringify(this.doc);
        this._inspectorDirty = false;
        this._inspectorUndoPushed = false;
      }

      const toolbarR = document.createElement("div");
      toolbarR.className =
        "d-flex justify-content-between align-items-center gap-2 mb-2";
      const titleRel = document.createElement("div");
      titleRel.className = "small fw-bold mb-0";
      titleRel.textContent = "Relationship";
      const delRel = document.createElement("button");
      delRel.type = "button";
      delRel.className = "btn btn-outline-danger btn-sm";
      delRel.textContent = "Delete selection";
      delRel.addEventListener("click", () => this.deleteSelected());
      toolbarR.appendChild(titleRel);
      toolbarR.appendChild(delRel);
      panel.appendChild(toolbarR);

      const nameLbl = document.createElement("label");
      nameLbl.className = "form-label small mb-0";
      nameLbl.textContent = "Name";
      panel.appendChild(nameLbl);
      const nameIn = document.createElement("input");
      nameIn.type = "text";
      nameIn.className = "form-control form-control-sm mb-2";
      nameIn.value = rel.name;
      nameIn.addEventListener("blur", () => {
        const nv = nameIn.value.trim();
        if (!nv) {
          nameIn.value = rel.name;
          return;
        }
        if (nv !== rel.name) {
          this.inspectorEditStart();
          if (!this.renameRelationship(rel.name, nv)) {
            nameIn.value = rel.name;
          } else {
            this.previewRedrawRerenderInspector();
          }
        }
      });
      panel.appendChild(nameIn);

      const weakWrap = document.createElement("div");
      weakWrap.className = "form-check mb-2";
      const weakCb = document.createElement("input");
      weakCb.type = "checkbox";
      weakCb.className = "form-check-input";
      weakCb.id = this.answersName + "-er-insp-weak-r";
      weakCb.checked = rel.weak === true;
      weakCb.addEventListener("change", () => {
        this.inspectorEditStart();
        rel.weak = weakCb.checked;
        this.previewInspectorRedraw();
      });
      const weakLbl = document.createElement("label");
      weakLbl.className = "form-check-label small";
      weakLbl.htmlFor = weakCb.id;
      weakLbl.textContent = "Weak / identifying (double diamond)";
      weakWrap.appendChild(weakCb);
      weakWrap.appendChild(weakLbl);
      panel.appendChild(weakWrap);

      const pHead = document.createElement("div");
      pHead.className = "small fw-bold mt-2 mb-1";
      pHead.textContent = "Participants (at least 2, unique entities)";
      panel.appendChild(pHead);

      const entityNames = () => this.doc.entities.map((e) => e.name);

      const refreshParticipantUI = () => {
        this.previewRedrawRerenderInspector();
      };

      const dupCheck = () => {
        const seen = new Set();
        for (const p of rel.participants) {
          if (seen.has(p.entity)) return true;
          seen.add(p.entity);
        }
        return false;
      };

      rel.participants.forEach((part, pidx) => {
        const row = document.createElement("div");
        row.className = "d-flex flex-wrap align-items-center mb-1 er-insp-row";

        const selEnt = document.createElement("select");
        selEnt.className = "form-select form-select-sm";
        selEnt.style.maxWidth = "140px";
        const names = entityNames();
        if (part.entity && !names.includes(part.entity)) {
          const o0 = document.createElement("option");
          o0.value = part.entity;
          o0.textContent = part.entity + " (?)";
          o0.selected = true;
          selEnt.appendChild(o0);
        }
        names.forEach((en) => {
          const o = document.createElement("option");
          o.value = en;
          o.textContent = en;
          if (en === part.entity) o.selected = true;
          selEnt.appendChild(o);
        });
        selEnt.addEventListener("change", () => {
          this.inspectorEditStart();
          const v = selEnt.value;
          const old = part.entity;
          part.entity = v;
          if (dupCheck()) {
            part.entity = old;
            selEnt.value = old;
            window.alert("Each participant must be a different entity.");
            return;
          }
          this.ensureLayoutDefaults();
          this.previewInspectorRedraw();
        });

        const selCard = document.createElement("select");
        selCard.className = "form-select form-select-sm";
        selCard.style.maxWidth = "96px";
        ["one", "many"].forEach((c) => {
          const o = document.createElement("option");
          o.value = c;
          o.textContent = c;
          if (c === part.cardinality) o.selected = true;
          selCard.appendChild(o);
        });
        selCard.addEventListener("change", () => {
          this.inspectorEditStart();
          part.cardinality = selCard.value;
          this.previewInspectorRedraw();
        });

        const selPart = document.createElement("select");
        selPart.className = "form-select form-select-sm";
        selPart.style.maxWidth = "88px";
        ["total", "partial"].forEach((c) => {
          const o = document.createElement("option");
          o.value = c;
          o.textContent = c;
          if (c === part.participation) o.selected = true;
          selPart.appendChild(o);
        });
        selPart.addEventListener("change", () => {
          this.inspectorEditStart();
          part.participation = selPart.value;
          this.previewInspectorRedraw();
        });

        const rem = document.createElement("button");
        rem.type = "button";
        rem.className = "btn btn-outline-danger btn-sm";
        rem.textContent = "×";
        rem.disabled = rel.participants.length <= 2;
        rem.addEventListener("click", () => {
          if (rel.participants.length <= 2) return;
          this.inspectorEditStart();
          rel.participants.splice(pidx, 1);
          refreshParticipantUI();
        });

        row.appendChild(selEnt);
        row.appendChild(selCard);
        row.appendChild(selPart);
        row.appendChild(rem);
        panel.appendChild(row);
      });

      const used = new Set(rel.participants.map((p) => p.entity));
      const unused = entityNames().filter((n) => !used.has(n));
      const addP = document.createElement("button");
      addP.type = "button";
      addP.className = "btn btn-outline-secondary btn-sm mb-2";
      addP.textContent = "Add participant";
      addP.disabled = unused.length === 0;
      addP.addEventListener("click", () => {
        if (unused.length === 0) return;
        this.inspectorEditStart();
        rel.participants.push({
          entity: unused[0],
          cardinality: "many",
          participation: "partial",
        });
        this.ensureLayoutDefaults();
        refreshParticipantUI();
      });
      panel.appendChild(addP);

      const rl = document.createElement("div");
      rl.className = "small fw-bold mt-2 mb-1";
      rl.textContent = "Relationship attributes";
      panel.appendChild(rl);
      const arr = rel.attributes;
      arr.forEach((val, idx) => {
        const row = document.createElement("div");
        row.className = "input-group input-group-sm mb-1";
        const inp = document.createElement("input");
        inp.type = "text";
        inp.className = "form-control";
        inp.value = val;
        inp.addEventListener("change", () => {
          this.inspectorEditStart();
          arr[idx] = inp.value.trim();
          const cleaned = arr.map((s) => String(s).trim()).filter((s) => s.length > 0);
          arr.length = 0;
          cleaned.forEach((x) => arr.push(x));
          this.previewInspectorRedraw();
        });
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-outline-secondary btn-sm";
        btn.textContent = "×";
        btn.addEventListener("click", () => {
          this.inspectorEditStart();
          arr.splice(idx, 1);
          this.previewRedrawRerenderInspector();
        });
        row.appendChild(inp);
        row.appendChild(btn);
        panel.appendChild(row);
      });
      const addA = document.createElement("button");
      addA.type = "button";
      addA.className = "btn btn-outline-secondary btn-sm";
      addA.textContent = "Add attribute";
      addA.addEventListener("click", () => {
        this.inspectorEditStart();
        arr.push("");
        this.previewRedrawRerenderInspector();
      });
      panel.appendChild(addA);

      const applyRowR = document.createElement("div");
      applyRowR.className = "d-flex justify-content-end gap-2 flex-wrap mt-3";
      const applyRBtn = document.createElement("button");
      applyRBtn.type = "button";
      applyRBtn.className = "btn btn-primary btn-sm";
      applyRBtn.textContent = "Apply Change";
      applyRBtn.addEventListener("click", () => this.commitInspectorApply());
      const discardRBtn = document.createElement("button");
      discardRBtn.type = "button";
      discardRBtn.className = "btn btn-outline-secondary btn-sm";
      discardRBtn.textContent = "Discard";
      discardRBtn.addEventListener("click", () => this.commitInspectorDiscard());
      applyRowR.appendChild(applyRBtn);
      applyRowR.appendChild(discardRBtn);
      panel.appendChild(applyRowR);
    }

    draw() {
      if (!this.ctx || !this.canvas) return;
      // Measure entities first so computeWorldSize() sees up-to-date dimensions,
      // then resize the canvas so it grows to fit content placed/dragged outward.
      this.recomputeEntitySizes();
      this.syncCanvasSize();
      const c = this.ctx;
      const w = this.canvas.width;
      const h = this.canvas.height;
      c.setTransform(1, 0, 0, 1, 0, 0);
      c.clearRect(0, 0, w, h);
      c.fillStyle = "#fafafa";
      c.fillRect(0, 0, w, h);
      c.setTransform(this.zoom, 0, 0, this.zoom, 0, 0);

      for (const rel of this.doc.relationships) {
        const d = this.getDiamond(rel.name);
        if (!d) continue;
        for (const p of rel.participants || []) {
          const er = this.getRect(p.entity);
          if (!er) continue;
          const ec = rectCenter(er);
          const start = rectExitToward(er, d.cx, d.cy);
          const end = diamondEntry(d.cx, d.cy, d.half, ec.x, ec.y);
          const card =
            p.cardinality === "one" ? "1" : p.cardinality === "many" ? "N" : "?";
          const isTotal = p.participation === "total";
          this.drawEdge(start.x, start.y, end.x, end.y, card, isTotal, start, end);
        }
      }

      for (const rel of this.doc.relationships) {
        const d = this.getDiamond(rel.name);
        if (!d) continue;
        const sel =
          this.selected &&
          this.selected.type === "relationship" &&
          this.selected.name === rel.name;
        this.drawDiamond(d.cx, d.cy, d.half, rel, sel);
      }

      for (const ent of this.doc.entities) {
        const r = this.getRect(ent.name);
        if (!r) continue;
        const sel =
          this.selected &&
          this.selected.type === "entity" &&
          this.selected.name === ent.name;
        const pick =
          this.mode === "add_rel" && this.relPickEntity === ent.name;
        this.drawEntityBox(r, ent, sel || pick);
      }

      if (this.mode === "add_rel" && this.relPickEntity) {
        c.fillStyle = "rgba(0,100,200,0.08)";
        const r = this.getRect(this.relPickEntity);
        if (r) c.fillRect(r.x - 4, r.y - 4, r.w + 8, r.h + 8);
      }
    }

    drawEdge(x1, y1, x2, y2, cardLabel, isTotal, start, end) {
      const c = this.ctx;
      c.strokeStyle = "#333";
      c.lineWidth = isTotal ? 2.2 : 1.3;
      c.beginPath();
      c.moveTo(x1, y1);
      c.lineTo(x2, y2);
      c.stroke();
      if (isTotal) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.hypot(dx, dy) || 1;
        const ox = (-dy / len) * 3;
        const oy = (dx / len) * 3;
        c.lineWidth = 1.3;
        c.beginPath();
        c.moveTo(x1 + ox, y1 + oy);
        c.lineTo(x2 + ox, y2 + oy);
        c.stroke();
      }
      const t = 0.35;
      const lx = x1 + (x2 - x1) * t;
      const ly = y1 + (y2 - y1) * t;
      c.fillStyle = "#111";
      c.font = "12px system-ui, sans-serif";
      c.fillText(cardLabel, lx + 4, ly - 4);
    }

    drawDiamond(cx, cy, half, rel, selected) {
      const c = this.ctx;
      const label = rel.name || "";
      const attrs = rel.attributes || [];
      const isWeak = rel.weak === true;
      c.beginPath();
      traceDiamondPath(c, cx, cy, half);
      c.fillStyle = selected ? "#fff3cd" : "#fff8e8";
      c.fill();
      c.lineWidth = selected ? 2.5 : 1.2;
      c.strokeStyle = "#704214";
      c.stroke();
      if (isWeak) {
        c.beginPath();
        traceDiamondPath(c, cx, cy, Math.max(12, half - 9));
        c.lineWidth = selected ? 2 : 1.2;
        c.strokeStyle = "#704214";
        c.stroke();
      }
      c.fillStyle = "#222";
      c.font = "bold 13px system-ui, sans-serif";
      const tw = c.measureText(label).width;
      c.fillText(label, cx - tw / 2, cy + 4);
      if (attrs.length > 0) {
        c.font = "12px ui-monospace, monospace";
        c.fillStyle = "#2d5016";
        let y = cy + half + 14;
        for (const a of attrs) {
          const s = String(a);
          const aw = c.measureText(s).width;
          c.fillText(s, cx - aw / 2, y);
          y += LINE_H;
        }
      }
    }

    drawEntityBox(r, ent, selected) {
      const c = this.ctx;
      const isWeak = ent.weak === true;
      c.fillStyle = selected ? "#e7f1ff" : "#ffffff";
      c.strokeStyle = selected ? "#0d6efd" : "#444";
      c.lineWidth = selected ? 2 : 1;
      c.fillRect(r.x, r.y, r.w, r.h);
      c.strokeRect(r.x, r.y, r.w, r.h);
      if (isWeak) {
        c.lineWidth = selected ? 2 : 1.2;
        c.strokeStyle = selected ? "#0d6efd" : "#222";
        c.strokeRect(r.x + 4, r.y + 4, r.w - 8, r.h - 8);
      }
      let y = r.y + PAD + 14;
      c.fillStyle = "#111";
      c.font = "bold 15px system-ui, -apple-system, sans-serif";
      c.fillText(ent.name, r.x + PAD, y);
      y += LINE_H;
      c.font = "13px ui-monospace, monospace";
      for (const a of ent.key_attributes || []) {
        const s = String(a) + " (key)";
        c.fillStyle = "#0a58ca";
        c.fillText(s, r.x + PAD, y);
        c.beginPath();
        c.strokeStyle = "#0a58ca";
        c.lineWidth = 1;
        const tw = c.measureText(s).width;
        c.moveTo(r.x + PAD, y + 2);
        c.lineTo(r.x + PAD + tw, y + 2);
        c.stroke();
        y += LINE_H;
      }
      c.fillStyle = "#333";
      for (const a of ent.attributes || []) {
        c.fillText(String(a), r.x + PAD, y);
        y += LINE_H;
      }
    }
  }

  window.ERDiagramBuilder = ERDiagramBuilder;
  return ERDiagramBuilder;
})();
