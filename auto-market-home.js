(() => {
  const PROJECT_ID = "auto-market-project";

  function removeLegacyBlock() {
    document.querySelectorAll("body > section#auto-market-assistant").forEach((node) => node.remove());
  }

  function addNavLink() {
    const nav = document.querySelector(".navLinks");
    if (!nav || nav.querySelector('a[href="#' + PROJECT_ID + '"]')) return;
    const link = document.createElement("a");
    link.href = "#" + PROJECT_ID;
    link.textContent = "Auto Market";
    const experience = nav.querySelector('a[href="#experience"]');
    nav.insertBefore(link, experience || null);
  }

  function buildProject() {
    const article = document.createElement("article");
    article.className = "storyProject reveal";
    article.id = PROJECT_ID;
    article.innerHTML = `
      <div class="storyHeader">
        <div><span class="projectNo">04</span><span class="projectType">Machine Learning · RAG · Production AI</span></div>
        <span class="publicationBadge"><i></i> Live on AWS</span>
      </div>
      <div class="storyHero compactStory">
        <div class="storyTitle">
          <p class="storyOverline">Auto Market Assistant</p>
          <h3>What if one tool could explain both what a used car is worth and what owners actually experienced?</h3>
          <p>I separated market-value prediction from owner-review evidence, then deployed both behind a FastAPI service on AWS so the portfolio can query the real pipeline.</p>
        </div>
        <div class="storyMetric"><strong>0.883</strong><span>test R²</span><small>$2,866 MAE</small></div>
      </div>
      <div style="background:#07111f;padding:28px;border-top:1px solid #213b56;border-bottom:1px solid #213b56;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:16px;">
          <div>
            <strong style="color:#eef6ff;font:500 22px Georgia,serif;">Try the live vehicle assistant</strong>
            <p style="color:#9db0c8;margin:5px 0 0;font-size:12px;">Choose from supported makes, models, years, mileage bands, conditions, and owner questions loaded from the deployed dataset.</p>
          </div>
          <span style="color:#63e6be;border:1px solid #315d59;border-radius:99px;padding:7px 10px;font-size:9px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;">AWS ECS · Live API</span>
        </div>
        <div style="border:1px solid #213b56;border-radius:18px;overflow:hidden;background:#07111f;">
          <iframe id="ama-home-frame" src="/auto-market-assistant.html?embed=1&v=3" title="Auto Market Assistant live demo" style="display:block;width:100%;height:900px;border:0;background:#07111f;" loading="lazy"></iframe>
        </div>
      </div>
      <div class="storyChapters threeChapters">
        <section><span>01 · Price model</span><h4>Structured market context stays separate from language generation.</h4><p>CatBoost estimates historical Craigslist asking-price context from engineered vehicle features and returns comparable listing statistics alongside the estimate.</p></section>
        <section><span>02 · Owner evidence</span><h4>Review answers begin with retrieval, not invention.</h4><p>MiniLM embeddings and FAISS retrieve matched Edmunds owner reviews. The live CPU deployment returns citation-validated evidence directly from those sources.</p></section>
        <section><span>03 · Production</span><h4>The same project runs beyond the notebook.</h4><p>FastAPI, Docker, Amazon ECR, ECS Express Mode, S3-backed artifacts, IAM roles, and GitHub Actions turn the model into a reproducible deployed service.</p></section>
      </div>
      <div class="storyFooter">
        <div class="tags"><span>CatBoost</span><span>MiniLM</span><span>FAISS</span><span>FastAPI</span><span>Docker</span><span>AWS ECS</span><span>S3</span></div>
        <p><a href="/auto-market-assistant.html?v=3" style="color:inherit;font-weight:700;">Open full case study →</a></p>
      </div>
    `;
    return article;
  }

  function mount() {
    removeLegacyBlock();
    const stories = document.querySelector("#work .storyProjects");
    if (!stories) return;

    let project = document.getElementById(PROJECT_ID);
    const brewing = [...stories.querySelectorAll(".nextStory")].find((node) =>
      node.textContent.includes("Currently brewing")
    );

    if (!project) {
      project = buildProject();
      stories.insertBefore(project, brewing || null);
    }

    if (brewing) {
      const number = brewing.querySelector(".projectNo");
      if (number) number.textContent = "05";
    }
    addNavLink();
  }

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    if (!event.data || event.data.type !== "auto-market-height") return;
    const frame = document.getElementById("ama-home-frame");
    if (frame && Number(event.data.height)) {
      frame.style.height = Math.max(760, Number(event.data.height) + 16) + "px";
    }
  });

  document.addEventListener("DOMContentLoaded", mount);
  window.addEventListener("load", mount);
  setTimeout(mount, 150);
  setTimeout(mount, 800);
  setTimeout(mount, 1800);
})();
