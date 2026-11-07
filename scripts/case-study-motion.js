// A lightweight reading progress indicator for standalone portfolio case studies.
(function () {
  const progress = document.getElementById("caseProgress");
  if (!progress) return;
  let scheduled = false;
  function update() {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const fraction = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
    progress.style.transform = "scaleX(" + fraction + ")";
    scheduled = false;
  }
  window.addEventListener("scroll", function () {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(update);
    }
  }, { passive: true });
  window.addEventListener("resize", update);
  update();
})();
