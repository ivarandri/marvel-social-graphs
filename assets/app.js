/* Marvel Social Graphs — page interactions
   Vanilla + D3 v7 (loaded from CDN, only used if #net exists). */
(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.add("js");   /* reveal-on-scroll only hides things when JS is running */

  /* ---------- theme toggle ---------- */
  var saved = null;
  try { saved = localStorage.getItem("msg-theme"); } catch (e) {}
  if (saved) root.setAttribute("data-theme", saved);
  var tt = document.getElementById("themeToggle");
  function paintToggle() {
    if (!tt) return;
    var dark = root.getAttribute("data-theme") === "dark";
    tt.textContent = dark ? "☀" : "☾";
    tt.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  }
  paintToggle();
  if (tt) tt.addEventListener("click", function () {
    var dark = root.getAttribute("data-theme") === "dark";
    root.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("msg-theme", dark ? "light" : "dark"); } catch (e) {}
    paintToggle();
    document.dispatchEvent(new CustomEvent("themechange"));
  });

  /* ---------- reveal on scroll ---------- */
  var revs = document.querySelectorAll(".reveal");
  if (revs.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    revs.forEach(function (el) { io.observe(el); });
  } else {
    revs.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---------- animated counters ---------- */
  var counters = document.querySelectorAll("[data-count]");
  if (counters.length && "IntersectionObserver" in window) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        cio.unobserve(en.target);
        var el = en.target, target = +el.getAttribute("data-count"), t0 = null, dur = 1100;
        function step(ts) {
          if (!t0) t0 = ts;
          var p = Math.min(1, (ts - t0) / dur);
          var eased = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(target * eased).toLocaleString("en-US");
          if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { cio.observe(el); });
  } else {
    counters.forEach(function (el) { el.textContent = (+el.getAttribute("data-count")).toLocaleString("en-US"); });
  }

  /* ---------- sortable tables ---------- */
  document.querySelectorAll("table[data-sortable]").forEach(function (table) {
    var tbody = table.tBodies[0];
    table.querySelectorAll("th.sortable").forEach(function (th, colIndex) {
      // find true column index (account for preceding non-th? all th here)
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      th.addEventListener("click", function () {
        var asc = th.getAttribute("aria-sort") !== "ascending";
        table.querySelectorAll("th").forEach(function (o) { o.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var x = a.cells[idx].getAttribute("data-v") || a.cells[idx].textContent.trim();
          var y = b.cells[idx].getAttribute("data-v") || b.cells[idx].textContent.trim();
          var nx = parseFloat(x), ny = parseFloat(y);
          if (!isNaN(nx) && !isNaN(ny)) return asc ? nx - ny : ny - nx;
          return asc ? x.localeCompare(y) : y.localeCompare(x);
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  });

  /* ---------- interactive network ---------- */
  var svg = document.getElementById("net");
  if (!svg || typeof d3 === "undefined") return;

  var host = svg.closest(".net-wrap");
  var src = host.getAttribute("data-src") || "assets/marvel.json";

  var COMP = [
    { name: "giant component", fill: "#9db8e8" },
    { name: "the island", fill: "#e2231a" },
    { name: "isolate", fill: "#ffce3d" }
  ];

  d3.json(src).then(function (graph) {
    var W = 900, H = 560;
    var d3svg = d3.select(svg).attr("viewBox", "0 0 " + W + " " + H);
    var gZoom = d3svg.append("g");
    var gLink = gZoom.append("g").attr("stroke-linecap", "round");
    var gNode = gZoom.append("g");
    var gLabel = gZoom.append("g");

    // giant component -> a box in the middle; island -> pinned cluster top-left;
    // isolates -> pinned row along the bottom. (JSON x/y is a 0..1 layout for the giant.)
    var isolateList = graph.nodes.filter(function (d) { return d.comp === 2; });
    var isoRank = new Map(isolateList.map(function (d, i) { return [d.id, i]; }));
    var nIso = Math.max(1, isolateList.length - 1);

    var nodes = graph.nodes.map(function (d) {
      var o = Object.assign({}, d);
      if (d.comp === 0) {
        o.x = 0.22 * W + d.x * 0.66 * W;
        o.y = 0.12 * H + (1 - d.y) * 0.70 * H;
      } else if (d.comp === 1) {
        o.x = o.fx = 0.05 * W + ((d.x + 0.3) * 2) * 0.13 * W;
        o.y = o.fy = 0.34 * H + ((d.y - 0.4) * 2) * 0.13 * H;
      } else {
        o.x = o.fx = 0.09 * W + (isoRank.get(d.id) / nIso) * 0.82 * W;
        o.y = o.fy = 0.93 * H;
      }
      return o;
    });
    var byId = new Map(nodes.map(function (d) { return [d.id, d]; }));
    var links = graph.links.map(function (l) { return { source: l.s, target: l.t }; });

    var maxIn = d3.max(nodes, function (d) { return d.in; }) || 1;
    var heat = d3.scaleSequential(d3.interpolateInferno).domain([0, Math.sqrt(maxIn)]);
    var colorMode = "group";
    function fillOf(d) {
      return colorMode === "group" ? COMP[d.comp].fill : heat(Math.sqrt(d.in));
    }
    function radius(d) { return 3.2 + Math.sqrt(d.in) * 1.7; }

    var link = gLink.selectAll("line").data(links).join("line");
    var node = gNode.selectAll("circle").data(nodes).join("circle")
      .attr("r", radius).attr("fill", fillOf)
      .call(d3.drag()
        .on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
        .on("end", function (ev, d) {
          if (!ev.active) sim.alphaTarget(0);
          if (d.comp === 0) { d.fx = null; d.fy = null; }   // keep island + isolates pinned
        }));
    node.append("title").text(function (d) { return d.name + "  ·  in " + d.in + " / out " + d.out; });

    var hubs = nodes.slice().sort(function (a, b) { return b.in - a.in; }).slice(0, 6);
    var giantNodes = nodes.filter(function (d) { return d.comp === 0; });
    var leader = gLabel.selectAll("line.leader").data(hubs).join("line")
      .attr("class", "leader").attr("stroke", "#999").attr("stroke-width", 0.8);
    var label = gLabel.selectAll("text.hublbl").data(hubs).join("text")
      .attr("class", "lbl hublbl").attr("text-anchor", "middle").attr("dy", 4)
      .text(function (d) { return d.short; });

    // static captions for the two off-blob groups
    gLabel.append("text").attr("class", "lbl").attr("x", 0.02 * W).attr("y", 0.20 * H)
      .attr("fill", "#e2231a").text("the island (9)");
    gLabel.append("text").attr("class", "lbl").attr("x", 0.09 * W).attr("y", 0.985 * H)
      .attr("fill", "#b98a00").text("the 17 isolates — linked by nobody");

    var sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(function (d) { return d.id; }).distance(26).strength(0.3))
      .force("charge", d3.forceManyBody().strength(-45))
      .force("collide", d3.forceCollide().radius(function (d) { return radius(d) + 2.5; }))
      .force("x", d3.forceX(0.52 * W).strength(0.028))
      .force("y", d3.forceY(0.46 * H).strength(0.028))
      .alpha(0.7).alphaDecay(0.03)
      .on("tick", tick);

    function tick() {
      nodes.forEach(function (d) {
        if (d.comp === 0) {
          d.x = Math.max(14, Math.min(W - 14, d.x));
          d.y = Math.max(14, Math.min(H - 26, d.y));
        }
      });
      link.attr("x1", function (d) { return d.source.x; }).attr("y1", function (d) { return d.source.y; })
          .attr("x2", function (d) { return d.target.x; }).attr("y2", function (d) { return d.target.y; });
      node.attr("cx", function (d) { return d.x; }).attr("cy", function (d) { return d.y; });

      var cx0 = 0, cy0 = 0;
      giantNodes.forEach(function (d) { cx0 += d.x; cy0 += d.y; });
      cx0 /= giantNodes.length; cy0 /= giantNodes.length;
      function lpos(d) {
        var dx = d.x - cx0, dy = d.y - cy0, m = Math.hypot(dx, dy) || 1;
        return [d.x + (dx / m) * 60, d.y + (dy / m) * 60];
      }
      label.attr("x", function (d) { return lpos(d)[0]; }).attr("y", function (d) { return lpos(d)[1]; });
      leader.attr("x1", function (d) { return d.x; }).attr("y1", function (d) { return d.y; })
            .attr("x2", function (d) { return lpos(d)[0]; }).attr("y2", function (d) { return lpos(d)[1] - 4; });
    }

    d3svg.call(d3.zoom().scaleExtent([0.4, 6]).on("zoom", function (ev) {
      gZoom.attr("transform", ev.transform);
    }));

    /* ----- focus / neighbours ----- */
    var adj = new Map();
    nodes.forEach(function (d) { adj.set(d.id, new Set()); });
    graph.links.forEach(function (l) { adj.get(l.s).add(l.t); adj.get(l.t).add(l.s); });

    function focus(d) {
      if (!d) { clearFocus(); return; }
      svg.classList.add("dim");
      var keep = adj.get(d.id);
      node.classed("hot", function (o) { return o.id === d.id || keep.has(o.id); });
      link.classed("hot", function (o) { return o.source.id === d.id || o.target.id === d.id; });
      showCard(d);
    }
    function clearFocus() {
      svg.classList.remove("dim");
      node.classed("hot", false);
      link.classed("hot", false);
      hideCard();
    }
    node.on("click", function (ev, d) { ev.stopPropagation(); focus(d); });
    d3svg.on("click", clearFocus);

    /* ----- node card ----- */
    var card = null;
    function showCard(d) {
      hideCard();
      card = document.createElement("div");
      card.className = "node-card";
      card.innerHTML =
        '<button class="x" aria-label="close">×</button>' +
        '<h4>' + esc(d.short) + '</h4>' +
        '<div class="kv"><span>linked&nbsp;<b>to</b> by</span><span>' + d.in + ' pages</span></div>' +
        '<div class="kv"><span>links&nbsp;<b>out</b> to</span><span>' + d.out + ' pages</span></div>' +
        '<div class="kv"><span>lives in</span><span>' + COMP[d.comp].name + '</span></div>' +
        (d.url ? '<a href="' + d.url + '" target="_blank" rel="noopener">Wikipedia →</a>' : '');
      host.appendChild(card);
      card.querySelector(".x").addEventListener("click", function (e) { e.stopPropagation(); clearFocus(); });
    }
    function hideCard() { if (card) { card.remove(); card = null; } }
    function esc(s) { return s.replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]); }); }

    /* ----- search ----- */
    var input = host.querySelector(".net-search input");
    var dl = host.querySelector(".net-search datalist");
    if (dl) nodes.slice().sort(function (a, b) { return a.short.localeCompare(b.short); })
      .forEach(function (d) { var o = document.createElement("option"); o.value = d.short; dl.appendChild(o); });
    function runSearch() {
      var q = input.value.trim().toLowerCase();
      if (!q) { clearFocus(); return; }
      var hit = nodes.find(function (d) { return d.short.toLowerCase() === q; })
             || nodes.find(function (d) { return d.short.toLowerCase().indexOf(q) === 0; })
             || nodes.find(function (d) { return d.name.toLowerCase().indexOf(q) >= 0; });
      if (hit) focus(hit);
    }
    if (input) {
      input.addEventListener("change", runSearch);
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") runSearch(); });
    }

    /* ----- legend / filter chips ----- */
    host.querySelectorAll(".chip[data-comp]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        chip.classList.toggle("on");
        var show = {};
        host.querySelectorAll(".chip[data-comp]").forEach(function (c) { show[c.getAttribute("data-comp")] = c.classList.contains("on"); });
        node.style("display", function (d) { return show[d.comp] ? null : "none"; });
        label.style("display", function (d) { return show[d.comp] ? null : "none"; });
        link.style("display", function (d) { return (show[d.source.comp] && show[d.target.comp]) ? null : "none"; });
      });
    });

    /* ----- colour mode chips ----- */
    host.querySelectorAll(".chip[data-color]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        host.querySelectorAll(".chip[data-color]").forEach(function (c) { c.classList.remove("on"); });
        chip.classList.add("on");
        colorMode = chip.getAttribute("data-color");
        node.transition().duration(400).attr("fill", fillOf);
      });
    });

    /* redraw labels stroke on theme change */
    document.addEventListener("themechange", function () { /* CSS vars handle it */ });
  }).catch(function (err) {
    host.innerHTML = '<p class="muted" style="padding:2rem">Could not load the network data (' + err + ').</p>';
  });
})();
