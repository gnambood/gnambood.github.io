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

  // Slight, input-driven 3D perspective only on precise pointers.
  // No perpetual motion or additional decoration over the original artwork.
  var frame=document.querySelector(".portrait-wrap");
  var stage=document.querySelector(".portrait-stage");
  var reduce=matchMedia("(prefers-reduced-motion: reduce)");
  if(frame && stage && !reduce.matches && matchMedia("(hover:hover) and (pointer:fine)").matches){
    frame.addEventListener("pointermove",function(event){
      var bounds=frame.getBoundingClientRect();
      var x=(event.clientX-bounds.left)/bounds.width-.5;
      var y=(event.clientY-bounds.top)/bounds.height-.5;
      stage.style.setProperty("--tilt-x",(x*3).toFixed(2)+"deg");
      stage.style.setProperty("--tilt-y",(-y*3).toFixed(2)+"deg");
    });
    frame.addEventListener("pointerleave",function(){
      stage.style.removeProperty("--tilt-x");
      stage.style.removeProperty("--tilt-y");
    });
  }
})();
