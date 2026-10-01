from pathlib import Path
import json

path = Path("index.html")
html = path.read_text(encoding="utf-8")

article = r'''<article class="storyProject nextStory reveal" id="auto-market-project" style="overflow:hidden;">
  <div class="storyHeader">
    <div><span class="projectNo">04</span><span class="projectType">Applied ML · RAG · AWS</span></div>
    <span style="display:inline-flex;align-items:center;gap:8px;font-size:.76rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;"><i style="width:8px;height:8px;border-radius:50%;background:#52b788;display:inline-block;box-shadow:0 0 0 5px rgba(82,183,136,.12);"></i> Live on AWS</span>
  </div>
  <div class="storyHero compactStory">
    <div class="storyTitle">
      <p class="storyOverline">Auto Market Assistant</p>
      <h3>What is a used car worth — and what do owners actually say?</h3>
      <p>I built an end-to-end system that keeps market-value prediction separate from owner experience: CatBoost estimates historical asking-price context while MiniLM + FAISS retrieves grounded owner-review evidence.</p>
    </div>
    <div class="storyMetric"><strong>$2,866</strong><span>test MAE</span><small>0.883 R² · 84.9% within ±$5K</small></div>
  </div>
  <div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:24px 0 30px;padding:18px;border:1px solid rgba(0,0,0,.12);border-radius:18px;background:rgba(255,255,255,.35);font-size:.83rem;font-weight:700;">
    <span>Vehicle inputs</span><b>→</b><span>CatBoost</span><b>+</b><span>70,665 reviews</span><b>→</b><span>MiniLM + FAISS</span><b>→</b><span>Grounded evidence</span>
  </div>
  <div class="storyChapters threeChapters">
    <section><span>01 · Price model</span><h4>Structured market context, not an LLM guess.</h4><p>The chronological holdout reached $2,866 MAE and 0.883 R² on 238,959 modeling rows.</p></section>
    <section><span>02 · Review retrieval</span><h4>Owner claims stay tied to retrieved evidence.</h4><p>Retrieval over 70,665 matched reviews reached 81.67% Hit@5 and 0.6256 MRR@10.</p></section>
    <section><span>03 · Production</span><h4>The portfolio talks to a real cloud service.</h4><p>FastAPI runs in Docker on AWS ECS Express Mode with ECR images, S3 artifacts, and GitHub Actions deployment.</p></section>
  </div>
  <div style="margin-top:28px;border:1px solid rgba(0,0,0,.14);border-radius:22px;overflow:hidden;background:#07111f;">
    <div style="padding:15px 18px;color:#eef6ff;border-bottom:1px solid #213b56;display:flex;justify-content:space-between;gap:12px;align-items:center;">
      <strong>Try the live vehicle assistant</strong><span style="color:#63e6be;font-size:.78rem;font-weight:800;">AWS ECS</span>
    </div>
    <iframe id="ama-home-frame" src="/auto-market-assistant.html?embed=1" title="Auto Market Assistant live demo" style="display:block;width:100%;height:760px;border:0;background:#07111f;" loading="lazy"></iframe>
  </div>
  <div class="storyFooter" style="margin-top:22px;">
    <div class="tags"><span>CatBoost</span><span>FAISS</span><span>FastAPI</span><span>Docker</span><span>AWS ECS</span></div>
    <a href="/auto-market-assistant.html" style="display:inline-flex;align-items:center;gap:8px;font-weight:800;text-decoration:none;">Open full case study <span>→</span></a>
  </div>
</article>'''

placeholder_start = '<article class="storyProject nextStory reveal">'
if 'id="auto-market-project"' not in html:
    start = html.find(placeholder_start)
    if start == -1:
        raise SystemExit("Could not find Project 04 placeholder in index.html")
    end = html.find("</article>", start)
    if end == -1:
        raise SystemExit("Could not find Project 04 closing tag")
    html = html[:start] + article + html[end + len("</article>"):]

legacy_marker = "<!-- AUTO_MARKET_ASSISTANT_HOME -->"
legacy = html.find(legacy_marker)
if legacy != -1:
    body_close = html.rfind("</body>")
    if body_close == -1:
        raise SystemExit("Could not find </body>")
    html = html[:legacy] + html[body_close:]

mount_id = 'id="auto-market-home-mount"'
if mount_id not in html:
    mount = """<script id="auto-market-home-mount">
(function(){
  var projectHtml=%s;
  function mountAutoMarket(){
    var current=document.getElementById('auto-market-project');
    if(current && current.querySelector('#ama-home-frame')) return;
    var target=document.querySelector('article.nextStory');
    if(!target) return;
    target.outerHTML=projectHtml;
  }
  function resizeFrame(event){
    if(event.origin!==window.location.origin || !event.data || event.data.type!=='auto-market-height') return;
    var frame=document.getElementById('ama-home-frame');
    if(frame && Number(event.data.height)) frame.style.height=Math.max(650,Number(event.data.height)+10)+'px';
  }
  window.addEventListener('message',resizeFrame);
  document.addEventListener('DOMContentLoaded',mountAutoMarket);
  window.addEventListener('load',mountAutoMarket);
  [100,300,700,1400,2500].forEach(function(ms){setTimeout(mountAutoMarket,ms);});
  var observer=new MutationObserver(mountAutoMarket);
  observer.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(function(){observer.disconnect();mountAutoMarket();},6000);
})();
</script>""" % json.dumps(article)

    body_close = html.rfind("</body>")
    if body_close == -1:
        raise SystemExit("Could not find </body>")
    html = html[:body_close] + mount + html[body_close:]

path.write_text(html, encoding="utf-8")
print("Patched index.html")
print("Auto Market project present:", 'id="auto-market-project"' in html)
print("Hydration-safe mount present:", mount_id in html)
print("Legacy appended section removed:", legacy_marker not in html)
