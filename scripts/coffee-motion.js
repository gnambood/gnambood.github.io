// Decorative motion only: no model inference, network calls or data changes.
(() => {
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!prefersReduced.matches && "IntersectionObserver" in window) {
    document.documentElement.classList.add("js");
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    }, {threshold: 0.1, rootMargin: "0px 0px -25px 0px"});
    document.querySelectorAll("[data-reveal]").forEach(el => observer.observe(el));
  }
  const wrap = document.querySelector(".portrait-wrap");
  const stage = document.querySelector(".portrait-stage");
  if (!wrap || !stage || prefersReduced.matches ||
      !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  wrap.addEventListener("pointermove", event => {
    const r = wrap.getBoundingClientRect();
    const x = (event.clientX - r.left - r.width / 2) / r.width;
    const y = (event.clientY - r.top - r.height / 2) / r.height;
    stage.style.transform = "translate3d(" + (x * 9).toFixed(2) + "px," +
      (y * 7).toFixed(2) + "px,0)";
  });
  wrap.addEventListener("pointerleave", () => { stage.style.transform = ""; });
})();
