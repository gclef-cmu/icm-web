(function () {
  // sphinx-design tabs are a pure-CSS radio hack, so a URL fragment whose
  // target sits inside a non-default tab points at hidden content the
  // browser can neither show nor scroll to. Check the enclosing tab's
  // radio (the group unchecks the rest), then scroll to the target.
  function revealHashTab() {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    const content = target.closest(".sd-tab-content");
    if (!content) return;
    const label = content.previousElementSibling;
    const input = label && document.getElementById(label.htmlFor);
    if (!input) return;
    input.checked = true;
    // Scroll to the whole set, not the target: our targets sit at the top
    // of each tab, and this keeps the tab labels visible.
    requestAnimationFrame(() => content.parentElement.scrollIntoView());
  }

  window.addEventListener("hashchange", revealHashTab);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", revealHashTab);
  } else {
    revealHashTab();
  }
})();
