/**
 * VS Code-style drag-to-resize for the bottom panel.
 * The handle is the top 8px bar of #bottom-panel-container.
 * After drag ends, fires a Reflex event to keep state in sync.
 */
(function () {
  var isResizing = false;
  var startY = 0;
  var startHeight = 0;
  var MIN_H = 80;
  var MAX_H = 650;

  function getPanel() {
    return document.getElementById("panel-resize-handle");
  }
  function getContainer() {
    return document.getElementById("bottom-panel-container");
  }

  function init() {
    var handle = getPanel();
    if (!handle) {
      // React hasn't rendered yet — wait for it
      var obs = new MutationObserver(function () {
        if (getPanel()) {
          obs.disconnect();
          attachEvents();
        }
      });
      obs.observe(document.documentElement, { childList: true, subtree: true });
      return;
    }
    attachEvents();
  }

  function attachEvents() {
    var handle = getPanel();
    if (!handle || handle._resizeAttached) return;
    handle._resizeAttached = true;

    handle.addEventListener("mousedown", onMouseDown);
    handle.addEventListener("touchstart", onTouchStart, { passive: false });
    handle.addEventListener("dblclick", function () {
      applyHeight(280);
      syncState(280);
    });
  }

  function onMouseDown(e) {
    var container = getContainer();
    if (!container) return;
    isResizing = true;
    startY = e.clientY;
    startHeight = container.getBoundingClientRect().height;
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (!isResizing) return;
    var delta = startY - e.clientY; // drag up = bigger
    var newH = clamp(startHeight + delta, MIN_H, MAX_H);
    applyHeight(newH);
  }

  function onMouseUp() {
    if (!isResizing) return;
    isResizing = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
    // Sync final height back into Reflex state so buttons stay accurate
    var container = getContainer();
    if (container) {
      syncState(Math.round(container.getBoundingClientRect().height));
    }
  }

  function onTouchStart(e) {
    var container = getContainer();
    if (!container) return;
    isResizing = true;
    startY = e.touches[0].clientY;
    startHeight = container.getBoundingClientRect().height;
    document.addEventListener("touchmove", onTouchMove, { passive: false });
    document.addEventListener("touchend", onTouchEnd);
    e.preventDefault();
  }

  function onTouchMove(e) {
    if (!isResizing) return;
    var delta = startY - e.touches[0].clientY;
    applyHeight(clamp(startHeight + delta, MIN_H, MAX_H));
    e.preventDefault();
  }

  function onTouchEnd() {
    isResizing = false;
    document.removeEventListener("touchmove", onTouchMove);
    document.removeEventListener("touchend", onTouchEnd);
    var container = getContainer();
    if (container) {
      syncState(Math.round(container.getBoundingClientRect().height));
    }
  }

  function applyHeight(h) {
    var container = getContainer();
    if (!container) return;
    // Set inline style — overrides the React-driven class height
    container.style.height = h + "px";
    container.style.minHeight = Math.min(h, MIN_H) + "px";
  }

  /** Fire the Reflex set_panel_height event to keep state in sync */
  function syncState(h) {
    try {
      // Reflex 0.8.x exposes applyEvent on the global __reflex object
      if (window.__reflex && window.__reflex.state) {
        window.__reflex.state.set_panel_height(h);
      }
    } catch (_) {}
  }

  function clamp(v, lo, hi) {
    return Math.min(Math.max(v, lo), hi);
  }

  // Boot
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-attach after Next.js client-side navigation (soft nav)
  if (typeof window !== "undefined") {
    window.addEventListener("popstate", function () {
      setTimeout(init, 300);
    });
  }
})();
