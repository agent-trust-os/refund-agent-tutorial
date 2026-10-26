(function () {
  var $ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var slug = function (t) { return t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); };

  // copy button on every code block
  $("pre").forEach(function (pre) {
    var box = document.createElement("div");
    box.className = "code";
    var prev = pre.previousElementSibling;
    pre.parentNode.insertBefore(box, prev && prev.classList.contains("path") ? prev : pre);
    if (prev && prev.classList.contains("path")) box.appendChild(prev);
    box.appendChild(pre);
    var btn = document.createElement("button");
    btn.className = "copy"; btn.type = "button"; btn.textContent = "Copy";
    btn.onclick = function () {
      var done = function (ok) { btn.textContent = ok ? "Copied" : "Press Ctrl+C"; setTimeout(function () { btn.textContent = "Copy"; }, 1500); };
      try { navigator.clipboard.writeText(pre.innerText.replace(/ /g, " ").replace(/\n +\n/g, "\n\n")).then(function () { done(true); }, function () { done(false); }); }
      catch (e) { done(false); }
    };
    box.appendChild(btn);
  });

  // current page in the sidebar
  var here = location.pathname.split("/").pop();
  $(".side a").forEach(function (a) { if (a.getAttribute("href") === here) a.classList.add("on"); });
  var menu = $(".menu")[0];
  if (menu) menu.onclick = function () { document.body.classList.toggle("nav"); };

  // "On this page" from h2 and step h3, with anchors and scroll spy
  var toc = document.getElementById("toc");
  var heads = $("article h2, article .step > h3");
  var links = heads.map(function (h) {
    var label = (h.getAttribute("data-toc") || h.textContent).replace(/TODO \d+/, "").trim();
    if (!h.id) h.id = slug(label);
    var anchor = document.createElement("a");
    anchor.className = "anchor"; anchor.href = "#" + h.id; anchor.textContent = "#"; anchor.setAttribute("aria-label", "Link to this section");
    h.appendChild(anchor);
    var a = document.createElement("a");
    a.href = "#" + h.id; a.textContent = label;
    if (h.tagName === "H3") a.className = "sub";
    if (toc) toc.appendChild(a);
    return a;
  });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "-80px 0px -70% 0px" });
    heads.forEach(function (h) { io.observe(h); });
  }
})();
