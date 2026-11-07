// Decorative motion for the personal portfolio; no external requests or model calls.
(function(){
  var progress=document.getElementById("readProgress");
  var scrolling=false;
  function updateProgress(){var doc=document.documentElement;var max=doc.scrollHeight-innerHeight;progress.style.transform="scaleX("+(max>0?Math.min(1,Math.max(0,scrollY/max)):0)+")";scrolling=false}
  addEventListener("scroll",function(){if(!scrolling){scrolling=true;requestAnimationFrame(updateProgress)}},{passive:true});
  addEventListener("resize",updateProgress);updateProgress();
  if("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches){
    document.documentElement.classList.add("has-js");
    var observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){entry.target.classList.add("in-view");observer.unobserve(entry.target)}})},{threshold:.08});
    document.querySelectorAll(".reveal").forEach(function(node){observer.observe(node)});
  }

  // Gently follow the pointer on large screens. Do not affect touch devices.
  var stage=document.querySelector(".portrait-stage");
  if(stage && !matchMedia("(prefers-reduced-motion: reduce)").matches && matchMedia("(hover:hover) and (pointer:fine)").matches){
    stage.addEventListener("pointermove",function(event){
      var bounds=stage.getBoundingClientRect();
      var x=(event.clientX-bounds.left-bounds.width/2)/bounds.width;
      var y=(event.clientY-bounds.top-bounds.height/2)/bounds.height;
      stage.style.setProperty("--pointer-x",(x*8).toFixed(2)+"px");
      stage.style.setProperty("--pointer-y",(y*6).toFixed(2)+"px");
    });
    stage.addEventListener("pointerleave",function(){
      stage.style.removeProperty("--pointer-x");
      stage.style.removeProperty("--pointer-y");
    });
  }
})();
