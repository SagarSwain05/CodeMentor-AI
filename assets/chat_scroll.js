// Auto-scroll chat to bottom whenever new messages arrive
(function () {
  function scrollToBottom() {
    var el = document.getElementById("chat-scroll-box");
    if (el) el.scrollTop = el.scrollHeight;
  }

  // Scroll on load
  scrollToBottom();

  // Watch for DOM mutations inside the chat box (new messages)
  var observer = new MutationObserver(function (mutations) {
    // Only scroll if user is near the bottom (within 120px)
    var el = document.getElementById("chat-scroll-box");
    if (!el) return;
    var nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (nearBottom) scrollToBottom();
  });

  function attachObserver() {
    var el = document.getElementById("chat-scroll-box");
    if (el) {
      observer.observe(el, { childList: true, subtree: true });
    } else {
      // Retry until the element is rendered
      setTimeout(attachObserver, 300);
    }
  }

  document.addEventListener("DOMContentLoaded", attachObserver);
  // Also try immediately in case DOMContentLoaded already fired
  attachObserver();
})();
