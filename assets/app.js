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

/* ============================================================
   Week 2 — friendship-paradox explorer + summary widgets
   (own IIFE: runs on week2.html, needs no D3)
   ============================================================ */
(function () {
  "use strict";
  var host = document.querySelector(".fp-wrap");
  if (!host) return;
  var src = host.getAttribute("data-src") || "assets/week2.json";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m];
    });
  }

  fetch(src).then(function (r) { return r.json(); }).then(function (data) {
    var chars = data.chars;
    var byKey = {};
    chars.forEach(function (c) {
      byKey[c.short.toLowerCase()] = c;
      byKey[c.name.toLowerCase()] = c;
    });

    var select = host.querySelector("#fpSelect");
    var sorted = chars.slice().sort(function (a, b) { return a.short.localeCompare(b.short); });
    sorted.forEach(function (c) {
      var o = document.createElement("option");
      o.value = c.short; o.textContent = c.short + (c.deg ? " (" + c.deg + ")" : " (isolate)");
      select.appendChild(o);
    });

    var card = document.getElementById("fpCard");

    function render(c) {
      if (!c) return;
      select.value = c.short;
      if (!c.deg) {
        card.innerHTML =
          '<div class="fp-verdict grey">no friends to compare</div>' +
          '<p><strong>' + esc(c.short) + '</strong> is one of the 17 isolates — zero links, ' +
          'so the friendship paradox has nothing to say here.</p>';
        return;
      }
      var scale = Math.max(c.fd[0], c.deg);            // fit both the tallest friend and the line
      var above = c.fd.filter(function (d) { return d > c.deg; }).length;
      var bars = c.fd.map(function (d) {
        var h = Math.max(3, Math.round(d / scale * 100));
        return '<span class="fp-bar' + (d > c.deg ? " hi" : "") +
               '" style="height:' + h + '%" title="' + d + ' links"></span>';
      }).join("");
      var linePct = Math.max(0, 100 - (c.deg / scale * 100));
      var lblStyle = linePct < 14 ? ' style="top:3px"' : "";   // keep the label inside the box
      card.innerHTML =
        '<div class="fp-verdict ' + (c.holds ? "yes" : "no") + '">' +
          (c.holds ? "their friends are cooler" : "they’re the cool one") +
        "</div>" +
        '<div class="fp-nums">' +
          "<div><b>" + c.deg + "</b><span>their links</span></div>" +
          "<div><b>" + c.meanFriend + "</b><span>avg friend’s links</span></div>" +
          "<div><b>" + above + " / " + c.fd.length + "</b><span>friends more connected</span></div>" +
        "</div>" +
        '<div class="fp-chart">' +
          '<div class="fp-line" style="top:' + linePct.toFixed(1) + '%">' +
            "<span" + lblStyle + ">" + esc(c.short) + " = " + c.deg + "</span></div>" +
          bars +
        "</div>" +
        '<p class="fp-top">Most connected friend: <strong>' + esc(c.topFriend.short) +
          "</strong> (" + c.topFriend.deg + " links)</p>";
    }

    function pickRandomNobody() {
      var pool = chars.filter(function (c) { return c.deg >= 3 && c.deg <= 12; });
      return pool[Math.floor(Math.random() * pool.length)];
    }

    select.addEventListener("change", function () {
      var c = byKey[select.value.toLowerCase()];
      if (c) render(c);
    });
    host.querySelectorAll(".fp-search .chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var p = chip.getAttribute("data-pick");
        var c = p === "random" ? pickRandomNobody() : byKey[p.toLowerCase()];
        if (c) render(c);
      });
    });

    var q = new URLSearchParams(location.search).get("c");
    var start = (q && byKey[q.toLowerCase()]) || pickRandomNobody();
    render(start);

    /* ----- "who drives it" table ----- */
    var tf = document.getElementById("topFriends");
    if (tf) {
      tf.innerHTML = data.paradox.topFriends.map(function (f) {
        return "<tr><td>" + esc(f.short) + '</td><td class="num">' + f.count + " characters</td></tr>";
      }).join("");
    }

    /* ----- shuffle-test mini bars ----- */
    var sb = document.getElementById("shuffleBars");
    if (sb) {
      var s = data.shuffle, rec = data.reciprocity;
      function row(lab, real, realMax, segs, verdict) {
        var body = segs.map(function (seg) {
          var w = Math.max(2, Math.round(seg.v / realMax * 100));
          return '<div class="seg ' + seg.cls + '"><span class="fill" style="width:' + w +
                 '%"></span><span>' + seg.t + "</span></div>";
        }).join("");
        return '<div class="bar-row"><div class="lab">' + lab +
               ' <span class="tag2 ' + (verdict === "survives" ? "survive" : "die") + '">' + verdict +
               '</span></div><div class="bar-track">' + body + "</div></div>";
      }
      sb.innerHTML =
        row("clustering C", s.C_real, s.C_real, [
          { v: s.C_real, t: "real " + s.C_real, cls: "real" },
          { v: s.C_swap, t: "degree-shuffle " + s.C_swap, cls: "nulls" },
          { v: s.C_gnm, t: "random graph " + s.C_gnm, cls: "rand" }
        ], "survives") +
        row("transitivity", s.T_real, s.T_real, [
          { v: s.T_real, t: "real " + s.T_real, cls: "real" },
          { v: s.T_swap, t: "degree-shuffle " + s.T_swap, cls: "nulls" }
        ], "survives") +
        row("reciprocity", rec.real, rec.real, [
          { v: rec.real, t: "real " + Math.round(rec.real * 100) + "%", cls: "real" },
          { v: rec.null, t: "degree-shuffle " + Math.round(rec.null * 100) + "%", cls: "nulls" }
        ], "survives") +
        row("isolated nodes", s.isolates_real, s.isolates_real, [
          { v: s.isolates_real, t: "real " + s.isolates_real, cls: "real" },
          { v: s.isolates_real, t: "degree-shuffle " + s.isolates_real + " (identical)", cls: "nulls" },
          { v: 0.2, t: "random graph ~0", cls: "rand" }
        ], "dies");
    }

    /* ----- three fake Marvels table ----- */
    var mt = document.getElementById("modelsTable");
    if (mt) {
      var m = data.models;
      var order = [
        ["Marvel (real)", m.real], ["random G(n,m)", m.random],
        ["Watts–Strogatz", m.ws], ["Barabási–Albert", m.ba]
      ];
      mt.innerHTML = order.map(function (r) {
        return "<tr><td>" + r[0] + '</td><td class="num">' + r[1].C +
               '</td><td class="num">' + r[1].d + '</td><td class="num">' + r[1].maxk + "</td></tr>";
      }).join("");
    }
  }).catch(function (err) {
    var card = document.getElementById("fpCard");
    if (card) card.innerHTML = '<p class="muted">Could not load week2.json (' + err + ").</p>";
  });
})();

/* ============================================================
   Week 3 — six clicks to Spider-Man, break the universe,
   brokers vs the null, the X-Men clique  (own IIFE, no D3)
   ============================================================ */
(function () {
  "use strict";
  var root = document.getElementById("w3");
  if (!root) return;
  var SVGNS = "http://www.w3.org/2000/svg";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m];
    });
  }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }).then(function (data) {
    var chars = data.chars, N = chars.length;
    var byName = {};
    chars.forEach(function (c, i) { byName[c.short.toLowerCase()] = i; });
    var inDeg = new Array(N).fill(0);
    data.out.forEach(function (lst) { lst.forEach(function (j) { inDeg[j]++; }); });

    /* ---------------- six clicks ---------------- */
    var fromIn = document.getElementById("scFrom"), toIn = document.getElementById("scTo");
    var out = document.getElementById("scResult");
    var dl = document.getElementById("scList");
    chars.map(function (c) { return c.short; }).sort().forEach(function (s) {
      var o = document.createElement("option"); o.value = s; dl.appendChild(o);
    });
    var mode = "out";

    function bfs(adj, s, t) {
      if (s === t) return [s];
      var prev = new Array(N).fill(-1), seen = new Array(N).fill(false), q = [s], h = 0;
      seen[s] = true;
      while (h < q.length) {
        var u = q[h++];
        for (var k = 0; k < adj[u].length; k++) {
          var v = adj[u][k];
          if (seen[v]) continue;
          seen[v] = true; prev[v] = u;
          if (v === t) {
            var path = [t];
            while (prev[path[0]] !== -1) path.unshift(prev[path[0]]);
            return path;
          }
          q.push(v);
        }
      }
      return null;
    }

    function run() {
      var s = byName[(fromIn.value || "").trim().toLowerCase()];
      var t = byName[(toIn.value || "Spider-Man").trim().toLowerCase()];
      if (s === undefined || t === undefined) {
        out.innerHTML = '<p class="muted">Pick two characters from the list.</p>';
        return;
      }
      var path = bfs(mode === "out" ? data.out : data.und, s, t);
      if (!path) {
        var why;
        if (mode === "out" && data.out[s].length === 0)
          why = esc(chars[s].short) + "'s page links to no other Marvel superhero: there is nowhere to click.";
        else if (mode === "out" && inDeg[t] === 0)
          why = "No Marvel superhero page links to " + esc(chars[t].short) + ".";
        else if (!bfs(data.und, s, t))
          why = "They live in different pieces of the universe: one of them is a loner or on the 9-character island.";
        else
          why = "Following links you can't get there, but ignoring direction you can (try the other mode). One-way streets!";
        out.innerHTML = '<div class="sc-verdict fail">No path!</div><p class="sc-why">' + why + "</p>";
        return;
      }
      var steps = path.length - 1;
      var html = '<div class="sc-verdict">' + (steps === 0 ? "You're already there" :
        steps + (steps === 1 ? " click" : " clicks")) + "</div><div class=\"sc-chain\">";
      path.forEach(function (i, n) {
        var tilt = (n % 2 ? 1.5 : -1.5) + "deg";
        if (n > 0) html += '<span class="sc-arrow" style="--i:' + n + '">→</span>';
        html += '<a class="sc-card' + (n === 0 || n === steps ? " ends" : "") + '" style="--i:' + n + ";--tilt:" + tilt +
          '" href="' + esc(chars[i].url) + '" target="_blank" rel="noopener">' + esc(chars[i].short) + "</a>";
      });
      html += "</div>";
      if (mode === "out" && steps > 0)
        html += '<p class="sc-why">Every arrow is a link written in the running text of the page on its left. Click a card to check it on Wikipedia.</p>';
      out.innerHTML = html;
    }

    function set(f, t) { fromIn.value = f; toIn.value = t; run(); }
    var hard = 0, esc_ = 0;
    fromIn.addEventListener("change", run);
    toIn.addEventListener("change", run);
    document.getElementById("scSwap").addEventListener("click", function () { set(toIn.value || "Spider-Man", fromIn.value); });
    document.getElementById("scRandom").addEventListener("click", function () {
      var pool = chars.map(function (c, i) { return i; }).filter(function (i) { return data.out[i].length > 0 && i !== data.spider; });
      set(chars[pool[Math.floor(Math.random() * pool.length)]].short, toIn.value || "Spider-Man");
    });
    document.getElementById("scHard").addEventListener("click", function () {
      var f = data.clicks.toFarthest; setMode("out"); set(f[hard++ % f.length], "Spider-Man");
    });
    document.getElementById("scEscape").addEventListener("click", function () {
      var f = data.clicks.fromFarthest; setMode("out"); set("Spider-Man", f[esc_++ % f.length]);
    });
    function setMode(m) {
      mode = m;
      root.querySelectorAll(".sc-controls .chip[data-mode]").forEach(function (c) {
        c.classList.toggle("on", c.getAttribute("data-mode") === m);
      });
    }
    root.querySelectorAll(".sc-controls .chip[data-mode]").forEach(function (c) {
      c.addEventListener("click", function () { setMode(c.getAttribute("data-mode")); run(); });
    });
    var qs = new URLSearchParams(location.search);            // shareable: ?from=Thena&to=Spider-Man&mode=und
    if (qs.get("mode") === "und") setMode("und");
    set(qs.get("from") || data.clicks.toFarthest[0], qs.get("to") || "Spider-Man");

    /* histograms: how many clicks to reach him / to get away from him */
    function hist(title, rows, cls, total) {
      var mx = Math.max.apply(null, rows.map(function (r) { return r[1]; }));
      return '<div class="panel ' + cls + '"><h4>' + title + "</h4>" + rows.map(function (r) {
        return '<div class="hist-row"><span>' + r[0] + (r[0] === 1 ? " click" : " clicks") +
          '</span><span class="bar" style="width:' + Math.max(2, 100 * r[1] / mx) + '%"></span><span>' + r[1] + "</span></div>";
      }).join("") + (total ? '<p class="muted" style="margin:.5rem 0 0;font-size:.8rem">' + total + "</p>" : "") + "</div>";
    }
    document.getElementById("scHist").innerHTML =
      hist("clicks needed to reach Spider-Man", data.clicks.toHist, "to",
        data.clicks.cantReach + " characters can't reach him at all") +
      hist("clicks needed to get away from him", data.clicks.fromHist, "from", "starting from his page (9 out-links)");

    /* ---------------- break the universe ---------------- */
    var A = data.attack, W = 720, H = 360, m = { l: 52, r: 16, t: 16, b: 42 };
    var svg = document.getElementById("atkChart");
    var sx = function (k) { return m.l + (W - m.l - m.r) * k / A.K; };
    var sy = function (s) { return m.t + (H - m.t - m.b) * (1 - s / A.n); };
    var g = el("g", { "class": "grid" }, svg);
    [0, 50, 100, 150, 200, 250].forEach(function (v) {
      el("line", { x1: m.l, x2: W - m.r, y1: sy(v), y2: sy(v) }, g);
      el("text", { x: m.l - 8, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = v;
    });
    [0, 20, 40, 60, 80, 100].forEach(function (k) {
      el("text", { x: sx(k), y: H - m.b + 18, "text-anchor": "middle" }, svg).textContent = k;
    });
    el("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle" }, svg).textContent = "characters deleted";
    el("text", { x: 14, y: (m.t + H - m.b) / 2, "text-anchor": "middle",
      transform: "rotate(-90 14 " + (m.t + H - m.b) / 2 + ")" }, svg).textContent = "size of the biggest connected piece";
    var css = getComputedStyle(document.documentElement);
    var series = [
      { key: "random", color: "#8a8578", dash: "6 5", label: "Random" },
      { key: "degree", color: css.getPropertyValue("--blue").trim() || "#1a6dff", label: "Popularity Hunter" },
      { key: "betweenness", color: css.getPropertyValue("--red").trim() || "#e62429", label: "Broker Hunter" }
    ];
    series.forEach(function (s, i) {
      el("path", { d: A[s.key].map(function (v, k) { return (k ? "L" : "M") + sx(k).toFixed(1) + "," + sy(v).toFixed(1); }).join(""),
        fill: "none", stroke: s.color, "stroke-width": 3, "stroke-dasharray": s.dash || "none" }, svg);
      el("rect", { x: W - m.r - 170, y: m.t + 6 + i * 20, width: 14, height: 4, fill: s.color }, svg);
      el("text", { x: W - m.r - 150, y: m.t + 12 + i * 20 }, svg).textContent = s.label;
      s.dot = el("circle", { r: 6, fill: s.color, stroke: "#16130f", "stroke-width": 2 }, svg);
    });
    var marker = el("line", { y1: m.t, y2: H - m.b, stroke: "currentColor", "stroke-dasharray": "3 3" }, svg);
    marker.style.color = "var(--ink)";

    var slider = document.getElementById("atkSlider"), kLabel = document.getElementById("atkK");
    var readout = document.getElementById("atkReadout");
    function draw(k) {
      marker.setAttribute("x1", sx(k)); marker.setAttribute("x2", sx(k));
      series.forEach(function (s) { s.dot.setAttribute("cx", sx(k)); s.dot.setAttribute("cy", sy(A[s.key][k])); });
      kLabel.textContent = k + " deleted";
      function box(title, key, order) {
        var gone = k === 0 ? "nobody yet" : order ? "last deleted: <strong>" + esc(order[k - 1]) + "</strong>" : "anyone at all";
        return "<div><span class=\"muted\">" + title + '</span><b>' + Math.round(A[key][k]) + " / " + A.n +
          '</b><span class="gone">' + gone + "</span></div>";
      }
      readout.innerHTML = box("Random", "random") + box("Popularity Hunter", "degree", A.degreeOrder) +
        box("Broker Hunter", "betweenness", A.betweennessOrder);
    }
    slider.addEventListener("input", function () { draw(+slider.value); });
    var timer = null, play = document.getElementById("atkPlay");
    play.addEventListener("click", function () {
      if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ play"; return; }
      if (+slider.value >= A.K) slider.value = 0;
      play.textContent = "❚❚ pause";
      timer = setInterval(function () {
        var k = +slider.value + 1;
        slider.value = k; draw(k);
        if (k >= A.K) { clearInterval(timer); timer = null; play.textContent = "▶ play"; }
      }, 70);
    });
    draw(0);

    /* ---------------- brokers vs the degree-preserving null ---------------- */
    var bb = document.getElementById("brokerBars");
    var mx = Math.max.apply(null, data.brokers.map(function (b) { return Math.max(b.real, b.null); })) / 0.8;  // leave room for labels
    bb.innerHTML = data.brokers.map(function (b) {
      var tag = b.z >= 2 ? "survive" : "die";
      var word = b.z >= 2 ? "broker" : b.z <= -2 ? "anti-broker" : "just popular";
      return '<div class="bar-row"><div class="lab">' + esc(b.short) + ' <span class="muted">(' + b.deg + ' links)</span><br>' +
        '<span class="tag2 ' + tag + '">z = ' + (b.z > 0 ? "+" : "−") + Math.abs(b.z) + " · " + word + "</span></div>" +
        '<div class="bar-track"><div class="seg real"><span class="fill" style="width:' + (100 * b.real / mx) +
        '%"></span><span>real ' + (100 * b.real).toFixed(1) + "%</span></div>" +
        '<div class="seg nulls"><span class="fill" style="width:' + (100 * b.null / mx) +
        '%"></span><span>shuffled ' + (100 * b.null).toFixed(1) + "%</span></div></div></div>";
    }).join("");

    /* ---------------- the X-Men clique ---------------- */
    var C = data.cliques, members = C.core.concat(C.extras);
    var cs = document.getElementById("cqChart"), cx = 220, cy = 200, R = 150;
    var pos = {}, circles = {}, labels = {};
    members.forEach(function (nm, i) {
      var a = -Math.PI / 2 + 2 * Math.PI * i / members.length;
      pos[nm] = [cx + R * Math.cos(a), cy + R * Math.sin(a)];
    });
    var lines = [];
    members.forEach(function (a, i) {
      members.slice(i + 1).forEach(function (b) {
        var ia = byName[a.toLowerCase()], ib = byName[b.toLowerCase()];
        if (data.und[ia].indexOf(ib) >= 0)
          lines.push({ a: a, b: b, e: el("line", { x1: pos[a][0], y1: pos[a][1], x2: pos[b][0], y2: pos[b][1] }, cs) });
      });
    });
    members.forEach(function (nm) {
      var core = C.core.indexOf(nm) >= 0;
      circles[nm] = el("circle", { cx: pos[nm][0], cy: pos[nm][1], r: 13, fill: core ? "#e62429" : "#ffd23f" }, cs);
      var p = pos[nm], right = p[0] >= cx;
      labels[nm] = el("text", { x: p[0] + (right ? 18 : -18), y: p[1] + 4, "text-anchor": right ? "start" : "end" }, cs);
      labels[nm].textContent = nm.replace(" (Guardians of the Galaxy)", "");
    });
    function showClique(i) {
      var set = i === null ? null : C.eights[i];
      lines.forEach(function (l) {
        l.e.classList.toggle("on", !!set && set.indexOf(l.a) >= 0 && set.indexOf(l.b) >= 0);
      });
      members.forEach(function (nm) {
        var dim = !!set && set.indexOf(nm) < 0;
        circles[nm].classList.toggle("dim", dim); labels[nm].classList.toggle("dim", dim);
      });
      document.getElementById("cqNote").innerHTML = set ?
        "Clique " + (i + 1) + ": the core six plus <strong>" + esc(set.filter(function (x) { return C.core.indexOf(x) < 0; })
          .map(function (x) { return x.replace(" (Guardians of the Galaxy)", ""); }).join(" and ")) +
        "</strong>. All 28 pairs linked." :
        "Red: the six who are in all six cliques. Pick a clique to light up its 28 links.";
      document.querySelectorAll("#cqButtons .chip").forEach(function (b) {
        b.classList.toggle("on", b.getAttribute("data-i") === String(i));
      });
    }
    var btns = document.getElementById("cqButtons");
    btns.innerHTML = '<button class="chip on" type="button" data-i="null">all links</button>' +
      C.eights.map(function (_, i) { return '<button class="chip" type="button" data-i="' + i + '">clique ' + (i + 1) + "</button>"; }).join("");
    btns.querySelectorAll(".chip").forEach(function (b) {
      b.addEventListener("click", function () {
        var v = b.getAttribute("data-i"); showClique(v === "null" ? null : +v);
      });
    });
  }).catch(function (err) {
    var r = document.getElementById("scResult");
    if (r) r.innerHTML = '<p class="muted">Could not load week3.json (' + err + ").</p>";
  });
})();

/* ============================================================
   Week 4 — the sorting hat, snip the threads, Aristotle's rooms
   (own IIFE, no D3; the network is drawn on a canvas)
   ============================================================ */
(function () {
  "use strict";
  var root = document.getElementById("w4");
  if (!root) return;
  var SVGNS = "http://www.w3.org/2000/svg";
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m];
    });
  }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  var HOUSE_COL = {
    "Immanuel Kant": "#1a6dff", "The Buddha": "#8b5cf6", "Aristotle": "#ffd23f", "Confucius": "#ff7a1a",
    "René Descartes": "#16b364", "Bertrand Russell": "#ff5fa2", "Thomas Aquinas": "#e62429",
    "Avicenna": "#00b8d9", "Plato": "#b7791f", "Karl Marx": "#7a1f1f", "John Locke": "#6b8e23"
  };
  var MINOR = "#a8a29a";
  function textOn(hex) {                       // dark text on light fills, white on dark ones
    var n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    return 0.299 * r + 0.587 * g + 0.114 * b > 140 ? "#16130f" : "#fff";
  }
  function lastName(n) {
    var special = { "The Buddha": "Buddha", "Thomas Aquinas": "Aquinas", "René Descartes": "Descartes",
      "Immanuel Kant": "Kant", "Bertrand Russell": "Russell", "Karl Marx": "Marx", "John Locke": "Locke",
      "David Hume": "Hume", "Al-Ghazali": "al-Ghazali", "Władysław Tatarkiewicz": "Tatarkiewicz",
      "Jules Barthélemy-Saint-Hilaire": "Barthélemy-Saint-Hilaire", "Hans Kelsen": "Kelsen", "Jerome Frank": "Frank" };
    return special[n] || n;
  }

  fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }).then(function (data) {
    var P = data.p, H = data.houses, S = data.stats, R = S.runs;
    var hcol = H.map(function (h) { return HOUSE_COL[h.id] || MINOR; });
    var byName = {};
    P.forEach(function (p, i) { byName[p.n.toLowerCase()] = i; });
    function counts(p) {
      var c = {};
      p.v.forEach(function (h) { c[h] = (c[h] || 0) + 1; });
      return Object.keys(c).map(function (h) { return [+h, c[h]]; }).sort(function (a, b) { return b[1] - a[1]; });
    }
    var modal = P.map(function (p) { return counts(p)[0][0]; });

    /* numbers quoted in the text */
    var fmt = {
      Qnull: S.Qnull.toFixed(2), nmi: S.nmiMin.toFixed(2) + "–" + S.nmiMax.toFixed(2),
      Qw: S.Qw.toFixed(2), nmiW: S.nmiW.toFixed(2)
    };
    root.querySelectorAll("[data-f]").forEach(function (e) {
      var k = e.getAttribute("data-f"); if (fmt[k]) e.textContent = fmt[k];
    });

    /* ---------------- the sorting hat ---------------- */
    var input = document.getElementById("hatInput"), card = document.getElementById("hatCard");
    var dl = document.getElementById("hatList");
    P.map(function (p) { return p.n; }).sort().forEach(function (n) {
      var o = document.createElement("option"); o.value = n; dl.appendChild(o);
    });
    function houseName(h) { return "House " + lastName(H[h].id); }

    function sort(i) {
      var p = P[i], c = counts(p), top = c[0], nh = c.length;
      var self = H[top[0]].id === p.n;
      var verdict, cls;
      if (self && top[1] === R) { verdict = "Heads their own house, every time"; cls = "loyal"; }
      else if (top[1] === R) { verdict = "Loyal: " + houseName(top[0]); cls = "loyal"; }
      else if (top[1] >= 15) { verdict = "Mostly " + houseName(top[0]); cls = "mostly"; }
      else if (nh >= 4) { verdict = "Hopelessly torn: " + nh + " houses"; cls = "torn"; }
      else { verdict = "Torn: " + lastName(H[c[0][0]].id) + " or " + lastName(H[c[1][0]].id) + "?"; cls = "torn"; }
      if (self && top[1] < R) verdict = "Heads their own house in " + top[1] + " of " + R + " runs";

      var tokens = p.v.map(function (h, r) {
        return '<span class="hat-tok" style="--c:' + hcol[h] + ";color:" + textOn(hcol[h]) + ";--i:" + r + '" title="run ' + (r + 1) + ": " +
          esc(houseName(h)) + '">' + esc(lastName(H[h].id).charAt(0)) + "</span>";
      }).join("");
      var bars = c.map(function (hc) {
        return '<div class="hat-row"><span class="hat-hn">' + esc(houseName(hc[0])) + '</span><span class="hat-bar"><span style="width:' +
          (100 * hc[1] / R) + "%;background:" + hcol[hc[0]] + '"></span></span><b>' + hc[1] + "</b></div>";
      }).join("");
      var same = p.w === top[0];
      card.innerHTML =
        '<div class="hat-head"><a href="' + esc(p.u) + '" target="_blank" rel="noopener">' + esc(p.n) + "</a>" +
        '<span class="muted">' + p.k + " links · strength " + p.s + " · " + esc(p.era) + " list</span></div>" +
        '<div class="hat-toks">' + tokens + "</div>" +
        '<div class="hat-verdict ' + cls + '" style="--d:' + (R * 55 + 150) + 'ms">' + esc(verdict) + "</div>" +
        '<div class="hat-bars">' + bars + "</div>" +
        '<div class="hat-facts"><span><b>With weights:</b> ' + esc(houseName(p.w)) + (same ? " (agrees)" : " (disagrees!)") + "</span>" +
        "<span><b>Link communities:</b> " + (p.r === 0 ? "in no room of 2+ links" : "lives in " + p.r + (p.r === 1 ? " room" : " rooms")) + "</span></div>";
      input.value = p.n;
      try {
        var q = new URLSearchParams(location.search); q.set("p", p.n);
        history.replaceState(null, "", "?" + q.toString() + location.hash);
      } catch (e) {}
    }
    function pick(n) {
      if (n === "random") {
        var pool = P.map(function (p, i) { return i; }).filter(function (i) { return P[i].k >= 10; });
        return sort(pool[Math.floor(Math.random() * pool.length)]);
      }
      var i = byName[(n || "").trim().toLowerCase()];
      if (i === undefined) { card.innerHTML = '<p class="muted">Pick a philosopher from the list.</p>'; return; }
      sort(i);
    }
    input.addEventListener("change", function () { pick(input.value); });
    root.querySelectorAll(".hat-wrap .chip[data-pick]").forEach(function (b) {
      b.addEventListener("click", function () { pick(b.getAttribute("data-pick")); });
    });
    pick(new URLSearchParams(location.search).get("p") || "Charles Darwin");

    /* the hardest cases */
    var torn = P.map(function (p, i) { return i; }).filter(function (i) { return P[i].k >= 15; })
      .sort(function (a, b) { return P[b].e - P[a].e; }).slice(0, 12);
    var board = document.getElementById("tornBoard");
    board.innerHTML = torn.map(function (i) {
      var p = P[i];
      var segs = counts(p).map(function (hc) {
        return '<span style="flex:' + hc[1] + ";background:" + hcol[hc[0]] + ";color:" + textOn(hcol[hc[0]]) + '" title="' + esc(houseName(hc[0])) + ": " +
          hc[1] + ' runs">' + (hc[1] >= 3 ? esc(lastName(H[hc[0]].id)) : "") + "</span>";
      }).join("");
      return '<button class="torn-row" type="button" data-i="' + i + '"><span class="torn-n">' + esc(p.n) +
        ' <span class="muted">(' + p.k + ")</span></span><span class=\"torn-bar\">" + segs + "</span></button>";
    }).join("");
    board.querySelectorAll(".torn-row").forEach(function (b) {
      b.addEventListener("click", function () {
        sort(+b.getAttribute("data-i"));
        document.querySelector(".hat-wrap").scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
    var shown = H.map(function (h, i) { return i; }).filter(function (i) { return HOUSE_COL[H[i].id]; });
    document.getElementById("tornLegend").innerHTML = shown.map(function (i) {
      return '<span><i style="background:' + hcol[i] + '"></i>' + esc(houseName(i)) + "</span>";
    }).join("") + '<span><i style="background:' + MINOR + '"></i>minor houses</span>';

    /* ---------------- snip the threads ---------------- */
    var BB = data.bb, NE = BB.length;
    var cv = document.getElementById("thrCanvas"), ctx = cv.getContext("2d");
    var slider = document.getElementById("thrSlider"), readout = document.getElementById("thrReadout");
    var hover = document.getElementById("thrHover"), cardsEl = document.getElementById("thrCards");
    var AMIN = 0.01, AMAX = 0.3;
    function alphaOf(v) { return AMIN * Math.pow(AMAX / AMIN, v / 1000); }
    var labelSet = {};
    ["Aristotle", "Plato", "Immanuel Kant", "René Descartes", "Thomas Aquinas", "Bertrand Russell", "Avicenna",
      "The Buddha", "Confucius", "Voltaire", "Karl Marx"].forEach(function (n) { labelSet[byName[n.toLowerCase()]] = true; });

    // group the threads by link: Descartes & Locke hang on the same one
    var threads = [], tkey = {};
    data.threads.forEach(function (t) {
      var k = t.iu + "-" + t.iv;
      if (!tkey[k]) { tkey[k] = { u: t.u, v: t.v, iu: t.iu, iv: t.iv, alpha: t.alpha, w: t.w, heads: [], pieces: t.pieces }; threads.push(tkey[k]); }
      tkey[k].heads.push(lastName(t.head));
    });
    threads.sort(function (a, b) { return b.alpha - a.alpha; });
    cardsEl.innerHTML = threads.map(function (t, j) {
      return '<div class="thr-card" data-j="' + j + '"><b>' + esc(t.u) + " – " + esc(t.v) + "</b>" +
        "<span>ties " + esc(t.heads.join(" & ")) + " to Aristotle · α* = " + t.alpha.toFixed(3) + "</span></div>";
    }).join("");
    var tcards = cardsEl.querySelectorAll(".thr-card");

    var W = 0, Hh = 0, dpr = 1, state = null;
    function resize() {
      var w = cv.parentElement.clientWidth;
      W = cv.clientWidth || w; Hh = Math.round(W * 0.78);
      dpr = window.devicePixelRatio || 1;
      cv.width = W * dpr; cv.height = Hh * dpr; cv.style.height = Hh + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(+slider.value);
    }
    function xy(i) { var q = P[i].xy; return q ? [18 + q[0] * (W - 36), 18 + q[1] * (Hh - 36)] : null; }
    function css(v, f) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim() || f; }

    function draw(v) {
      if (!W) return;
      var a = alphaOf(v), n = 0;
      while (n < NE && BB[n][2] < a) n++;                    // links are sorted by alpha*
      var parent = {}, size = {};
      function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
      for (var e = 0; e < n; e++) {
        var u = BB[e][0], w = BB[e][1];
        if (parent[u] === undefined) { parent[u] = u; size[u] = 1; }
        if (parent[w] === undefined) { parent[w] = w; size[w] = 1; }
        var ru = find(u), rw = find(w);
        if (ru !== rw) { if (size[ru] < size[rw]) { var t = ru; ru = rw; rw = t; } parent[rw] = ru; size[ru] += size[rw]; }
      }
      var att = Object.keys(parent).map(Number), gcRoot = -1, gcSize = 0;
      att.forEach(function (x) { var r = find(x); if (size[r] > gcSize) { gcSize = size[r]; gcRoot = r; } });
      state = { att: att.filter(function (i) { return P[i].xy; }), find: find, gc: gcRoot };

      var ink = css("--ink", "#16130f"), muted = css("--muted", "#6a6357"), panel = css("--panel", "#fff");
      ctx.clearRect(0, 0, W, Hh);
      ctx.globalAlpha = 0.18; ctx.strokeStyle = muted; ctx.lineWidth = 0.6;
      ctx.beginPath();
      for (e = 0; e < n; e++) {
        var p1 = xy(BB[e][0]), p2 = xy(BB[e][1]);
        if (p1 && p2) { ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); }
      }
      ctx.stroke(); ctx.globalAlpha = 1;
      threads.forEach(function (t) {                            // the threads: solid when holding, dashed when cut
        var p1 = xy(t.iu), p2 = xy(t.iv), on = t.alpha < a;
        ctx.strokeStyle = on ? "#e62429" : muted; ctx.lineWidth = on ? 3 : 1.5;
        ctx.setLineDash(on ? [] : [4, 4]); ctx.globalAlpha = on ? 1 : 0.7;
        ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
      });
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      var drawn = att.filter(function (i) { return P[i].xy; });   // small pieces at alpha 0.3 have no position
      drawn.sort(function (x, y) { return P[x].s - P[y].s; });
      drawn.forEach(function (i) {
        var q = xy(i), inGc = find(i) === gcRoot;
        ctx.beginPath(); ctx.arc(q[0], q[1], 1.6 + Math.sqrt(P[i].s) / 3.2, 0, 2 * Math.PI);
        ctx.fillStyle = inGc ? hcol[modal[i]] : muted;
        ctx.globalAlpha = inGc ? 1 : 0.45; ctx.fill();
        ctx.globalAlpha = 1; ctx.lineWidth = 0.7; ctx.strokeStyle = ink; if (P[i].s > 60) ctx.stroke();
      });
      ctx.font = "700 11px Barlow, sans-serif"; ctx.lineWidth = 3; ctx.strokeStyle = panel; ctx.fillStyle = ink;
      drawn.forEach(function (i) {
        if (!labelSet[i]) return;
        var q = xy(i), txt = lastName(P[i].n);
        ctx.strokeText(txt, q[0] + 7, q[1] + 4); ctx.fillText(txt, q[0] + 7, q[1] + 4);
      });
      readout.innerHTML = '<div><span class="muted">α</span><b>' + a.toFixed(3) + "</b></div>" +
        '<div><span class="muted">links kept</span><b>' + n.toLocaleString("en-US") + "</b></div>" +
        '<div><span class="muted">philosophers attached</span><b>' + att.length.toLocaleString("en-US") + "</b></div>" +
        '<div><span class="muted">biggest piece</span><b>' + gcSize.toLocaleString("en-US") + "</b></div>";
      tcards.forEach(function (c) {
        var t = threads[+c.getAttribute("data-j")];
        c.classList.toggle("cut", t.alpha >= a);
      });
    }
    slider.addEventListener("input", function () { draw(+slider.value); });
    var timer = null, play = document.getElementById("thrPlay");
    play.addEventListener("click", function () {
      if (timer) { clearInterval(timer); timer = null; play.textContent = "✂ snip"; return; }
      if (+slider.value <= 0) slider.value = 1000;
      play.textContent = "❚❚ pause";
      timer = setInterval(function () {
        var v = +slider.value - 6; slider.value = Math.max(0, v); draw(+slider.value);
        if (v <= 0) { clearInterval(timer); timer = null; play.textContent = "✂ snip"; }
      }, 40);
    });
    cv.addEventListener("mousemove", function (ev) {
      if (!state) return;
      var b = cv.getBoundingClientRect(), mx = ev.clientX - b.left, my = ev.clientY - b.top, best = -1, bd = 100;
      state.att.forEach(function (i) {
        var q = xy(i), d = (q[0] - mx) * (q[0] - mx) + (q[1] - my) * (q[1] - my);
        if (d < bd) { bd = d; best = i; }
      });
      hover.innerHTML = best < 0 ? "Hover a dot to see who it is." :
        "<b>" + esc(P[best].n) + "</b> · " + esc(houseName(modal[best])) + " · " + P[best].k + " links" +
        (state.find(best) === state.gc ? "" : " · <em>drifted off the main piece</em>");
    });
    var qa = parseFloat(new URLSearchParams(location.search).get("a"));   // shareable: ?a=0.1
    if (qa >= AMIN && qa <= AMAX) slider.value = Math.round(1000 * Math.log(qa / AMIN) / Math.log(AMAX / AMIN));
    window.addEventListener("resize", function () { resize(); });
    document.addEventListener("themechange", function () { draw(+slider.value); });
    resize();

    /* ---------------- Aristotle's rooms ---------------- */
    var AR = data.aristotle, rooms = AR.rooms;
    var ROOM_COL = ["#e62429", "#1a6dff", "#16b364", "#ff7a1a", "#8b5cf6", "#00b8d9", "#ff5fa2"];
    var real = rooms.filter(function (r) { return r.links >= 2; }), loose = rooms.filter(function (r) { return r.links < 2; });
    var TOPN = 7;
    var groups = real.slice(0, TOPN).map(function (r, j) { return { rooms: [r], col: ROOM_COL[j], key: "r" + j }; });
    groups.push({ rooms: real.slice(TOPN), col: "#8a8578", key: "small" });
    groups.push({ rooms: loose, col: "#cfc9bb", key: "loose" });
    var svg = document.getElementById("arChart"), cx = 280, cy = 280, R0 = 60, R1 = 235;
    var total = AR.k, gap = 0.035, spokes = [];
    var usable = 2 * Math.PI - gap * groups.length, ang = -Math.PI / 2;
    groups.forEach(function (g, gi) {
      g.n = g.rooms.reduce(function (s, r) { return s + r.n; }, 0);
      g.a0 = ang;
      g.rooms.forEach(function (r) {
        r.nbrs.forEach(function (j) {
          var t = ang + usable / total / 2;
          var len = R1 - 40 + Math.min(40, Math.sqrt(P[j].k) * 3);
          var x = cx + len * Math.cos(t), y = cy + len * Math.sin(t);
          var ln = el("line", { x1: cx + R0 * Math.cos(t), y1: cy + R0 * Math.sin(t), x2: x, y2: y, stroke: g.col }, svg);
          var dot = el("circle", { cx: x, cy: y, r: 2 + Math.sqrt(P[j].k) / 4, fill: g.col }, svg);
          var tt = el("title", {}, dot); tt.textContent = P[j].n;
          spokes.push({ g: gi, ln: ln, dot: dot });
          ang += usable / total;
        });
      });
      g.a1 = ang; ang += gap;
      if (gi < TOPN) {
        var mid = (g.a0 + g.a1) / 2, lr = R1 + 12;
        var tx = el("text", { x: cx + lr * Math.cos(mid), y: cy + lr * Math.sin(mid) + 4, "text-anchor": "middle", "class": "ar-num" }, svg);
        tx.textContent = gi + 1;
      }
    });
    el("circle", { cx: cx, cy: cy, r: R0 - 6, "class": "ar-center" }, svg);
    var ct = el("text", { x: cx, y: cy + 5, "text-anchor": "middle", "class": "ar-center-t" }, svg);
    ct.textContent = "Aristotle";

    function roomLabel(r) { return r.top.filter(function (n) { return n !== "Plato"; }).slice(0, 3).join(", "); }
    var btns = document.getElementById("arRooms"), note = document.getElementById("arNote");
    btns.innerHTML = groups.map(function (g, gi) {
      var lab = gi < TOPN ? "<b>" + (gi + 1) + ".</b> " + esc(roomLabel(g.rooms[0])) :
        g.key === "small" ? "<b>" + g.rooms.length + " small rooms</b>" : "<b>" + g.rooms.length + " loose links</b>";
      return '<button class="ar-btn" type="button" data-g="' + gi + '"><i style="background:' + g.col + '"></i><span>' + lab +
        '</span><em>' + g.n + "</em></button>";
    }).join("");
    function showGroup(gi) {
      spokes.forEach(function (s) {
        var dim = gi !== null && s.g !== gi;
        s.ln.classList.toggle("dim", dim); s.dot.classList.toggle("dim", dim);
      });
      btns.querySelectorAll(".ar-btn").forEach(function (b) { b.classList.toggle("on", +b.getAttribute("data-g") === gi); });
      if (gi === null) { note.textContent = "Each spoke is one of Aristotle's links, grouped by room."; return; }
      var g = groups[gi];
      if (gi < TOPN) {
        var r = g.rooms[0];
        note.innerHTML = "<b>" + r.n + " of his " + AR.k + " links</b> sit in this room: " + r.size + " philosophers, " + r.links +
          " links. With: " + esc(r.top.join(", ")) + ". Their usual houses: " +
          esc(r.houses.map(function (h) { return lastName(h[0]) + " " + h[1]; }).join(", ")) + ".";
      } else if (g.key === "small") {
        note.innerHTML = "<b>" + g.n + " links</b> in " + g.rooms.length + " small rooms of 2–" +
          Math.max.apply(null, g.rooms.map(function (r) { return r.size; })) + " philosophers each, most of them with Plato too.";
      } else {
        note.innerHTML = "<b>" + g.n + " links</b> that didn't cluster with anything: a room of one link each. " +
          "The sparse edge of the network, where link communities struggle.";
      }
    }
    btns.querySelectorAll(".ar-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        var gi = +b.getAttribute("data-g");
        showGroup(b.classList.contains("on") ? null : gi);
      });
    });
    showGroup(null);
  }).catch(function (err) {
    var c = document.getElementById("hatCard");
    if (c) c.innerHTML = '<p class="muted">Could not load week4.json (' + err + ").</p>";
  });
})();

/* ============================================================
   Week 5 — friends, foes and family: the feud map, receipts,
   community-crossing bars, the Hulk board, validation, frenemies
   (own IIFE, no D3)
   ============================================================ */
(function () {
  "use strict";
  var root = document.getElementById("w5");
  if (!root) return;
  var SVGNS = "http://www.w3.org/2000/svg";
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m];
    });
  }
  function el(tag, attrs, parent) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  var TYPE_COL = { foe: "#e62429", ally: "#1a6dff", family: "#d6339a" };
  var COMM_COL = ["#ffb3b3", "#b9d3ff", "#ffe08a", "#d9c2ff", "#a8e6c8", "#ffcfa1", "#c8f08f", "#9fe3f0"];
  var TYPED = { foe: 1, ally: 1, family: 1 };

  fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }).then(function (data) {
    var C = data.chars, E = data.edges, S = data.stats;
    var byName = {};
    C.forEach(function (c, i) { byName[c.n.toLowerCase()] = i; });
    var out = C.map(function () { return []; }), inn = C.map(function () { return []; });
    E.forEach(function (e, j) { out[e[0]].push(j); inn[e[1]].push(j); });

    /* ---------------- the feud map ---------------- */
    var svg = document.getElementById("fmMap"), W = 1000, H = 760, pad = 24;
    function X(i) { return pad + C[i].xy[0] * (W - 2 * pad); }
    function Y(i) { return pad + C[i].xy[1] * (H - 2 * pad); }
    var gE = el("g", { "class": "fm-edges" }, svg), gN = el("g", { "class": "fm-nodes" }, svg), gL = el("g", { "class": "fm-labels" }, svg);
    var lines = [];
    E.forEach(function (e, j) {
      if (!C[e[0]].xy || !C[e[1]].xy || e[0] === e[1]) return;
      var t = TYPED[e[2]] ? e[2] : "other";
      var ln = el("line", { x1: X(e[0]), y1: Y(e[0]), x2: X(e[1]), y2: Y(e[1]), "class": "t-" + t }, gE);
      if (TYPED[t]) ln.setAttribute("stroke", TYPE_COL[t]);
      lines.push({ ln: ln, t: t, a: e[0], b: e[1] });
    });
    var circles = {};
    C.forEach(function (c, i) {
      if (!c.xy) return;
      var r = 2.5 + Math.sqrt(c.k) * 0.9;
      var ci = el("circle", { cx: X(i), cy: Y(i), r: r, fill: COMM_COL[c.c] || "#ccc" }, gN);
      var tt = el("title", {}, ci); tt.textContent = c.n;
      ci.addEventListener("click", function () { pick(i); });
      circles[i] = ci;
    });
    // name each community cluster, just outside it
    data.comms.forEach(function (cm, ci) {
      var mem = C.map(function (c, i) { return i; }).filter(function (i) { return C[i].c === ci && C[i].xy; });
      var mx_ = mem.reduce(function (s, i) { return s + X(i); }, 0) / mem.length;
      var my_ = mem.reduce(function (s, i) { return s + Y(i); }, 0) / mem.length;
      var dx = mx_ - W / 2, dy = my_ - H / 2, d = Math.sqrt(dx * dx + dy * dy) || 1;
      var lx = Math.max(95, Math.min(W - 95, mx_ + dx / d * 125)), ly = Math.max(28, Math.min(H - 14, my_ + dy / d * 105 + 8));
      var t = el("text", { x: lx, y: ly, "text-anchor": "middle", "class": "cl" }, gL);
      t.textContent = cm.name.replace("Cloak and Dagger", "Cloak & Dagger");
    });
    // label the biggest characters
    C.map(function (c, i) { return i; }).filter(function (i) { return C[i].xy && C[i].k >= 35; }).forEach(function (i) {
      var t = el("text", { x: X(i) + 9, y: Y(i) + 6 }, gL); t.textContent = C[i].n;
    });
    var show = { foe: true, ally: true, family: true, other: false };
    function paint(focus) {
      lines.forEach(function (l) {
        var on = show[l.t] && (focus === undefined || focus === null || l.a === focus || l.b === focus);
        l.ln.style.display = on ? "" : "none";
        l.ln.classList.toggle("hot", focus !== undefined && focus !== null && on);
      });
      Object.keys(circles).forEach(function (i) {
        circles[i].classList.toggle("sel", +i === focus);
      });
    }
    root.querySelectorAll(".fm-toggles .chip").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-type"); show[t] = !show[t]; b.classList.toggle("on", show[t]); paint(current);
      });
    });
    document.getElementById("fmLegend").innerHTML = data.comms.map(function (c, i) {
      return '<span><i style="background:' + COMM_COL[i] + '"></i>' + esc(c.name) + "'s community (" + c.size + ")</span>";
    }).join("");

    /* ---------------- receipts ---------------- */
    var input = document.getElementById("fmInput"), card = document.getElementById("fmCard");
    var dl = document.getElementById("fmList");
    C.map(function (c) { return c.n; }).sort().forEach(function (n) {
      var o = document.createElement("option"); o.value = n; dl.appendChild(o);
    });
    function highlight(sent, spans, words) {
      var parts = [], last = 0;
      spans.slice().sort(function (a, b) { return a[0] - b[0]; }).forEach(function (sp) {
        if (sp[0] < last) return;
        parts.push([sent.slice(last, sp[0]), false]); parts.push([sent.slice(sp[0], sp[1]), true]); last = sp[1];
      });
      parts.push([sent.slice(last), false]);
      var re = words.length ? new RegExp("\\b(" + words.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")\\b", "gi") : null;
      return parts.map(function (p) {
        if (p[1]) return "<b>" + esc(p[0]) + "</b>";
        var s = esc(p[0]);
        return re ? s.replace(re, "<mark>$1</mark>") : s;
      }).join("");
    }
    var current = null, tab = "foe";
    function pick(i) {
      if (i === "random") {
        var pool = C.map(function (c, j) { return j; }).filter(function (j) { return out[j].concat(inn[j]).some(function (k) { return TYPED[E[k][2]]; }); });
        i = pool[Math.floor(Math.random() * pool.length)];
      }
      current = i; input.value = C[i].n; paint(i); render();
      try { var q = new URLSearchParams(location.search); q.set("c", C[i].n); history.replaceState(null, "", "?" + q.toString()); } catch (e) {}
    }
    function render() {
      var i = current, rows = { foe: [], ally: [], family: [] };
      out[i].forEach(function (j) { if (TYPED[E[j][2]]) rows[E[j][2]].push({ j: j, other: E[j][1], dir: "out" }); });
      inn[i].forEach(function (j) { if (TYPED[E[j][2]]) rows[E[j][2]].push({ j: j, other: E[j][0], dir: "in" }); });
      if (!rows[tab].length) tab = ["foe", "ally", "family"].filter(function (t) { return rows[t].length; })[0] || "foe";
      var head = '<div class="fm-head"><a href="' + esc(C[i].u) + '" target="_blank" rel="noopener">' + esc(C[i].n) + "</a>" +
        (C[i].c >= 0 ? '<span class="muted">' + esc(data.comms[C[i].c].name) + "'s community</span>" : "") + "</div>";
      var tabs = '<div class="fm-tabs">' + ["foe", "ally", "family"].map(function (t) {
        return '<button type="button" class="fm-tab ' + t + (t === tab ? " on" : "") + '" data-t="' + t + '">' +
          { foe: "foes", ally: "allies", family: "family" }[t] + " <b>" + rows[t].length + "</b></button>";
      }).join("") + "</div>";
      var list = rows[tab].length ? rows[tab].map(function (r) {
        var e = E[r.j], o = C[r.other];
        var who = r.dir === "out" ? esc(C[i].n) + "'s page on <strong>" + esc(o.n) + "</strong>" : "<strong>" + esc(o.n) + "</strong>'s page on " + esc(C[i].n);
        return '<div class="rc ' + tab + '"><div class="rc-who">' + who + '</div><p>' + highlight(e[3], e[4], e[5]) + "</p></div>";
      }).join("") : '<p class="muted">No ' + tab + " links found.</p>";
      card.innerHTML = head + tabs + '<p class="rc-note muted">Both directions: what ' + esc(C[i].n) +
        "'s page says about others, and what their pages say about " + esc(C[i].n) + ".</p>" +
        '<div class="rc-list">' + list + "</div>";
      card.querySelectorAll(".fm-tab").forEach(function (b) {
        b.addEventListener("click", function () { tab = b.getAttribute("data-t"); render(); });
      });
    }
    input.addEventListener("change", function () {
      var i = byName[input.value.trim().toLowerCase()];
      if (i !== undefined) pick(i);
    });
    root.querySelectorAll(".fm-side .chip[data-pick]").forEach(function (b) {
      b.addEventListener("click", function () {
        var p = b.getAttribute("data-pick"); pick(p === "random" ? "random" : byName[p.toLowerCase()]);
      });
    });
    var qc = new URLSearchParams(location.search).get("c");
    pick(qc && byName[qc.toLowerCase()] !== undefined ? byName[qc.toLowerCase()] : byName["hulk"]);

    /* ---------------- community-crossing bars ---------------- */
    var lab = { foe: "Foe links", ally: "Ally links", family: "Family links" };
    var mx = 0.6;
    document.getElementById("cxBars").innerHTML = ["foe", "ally", "family"].map(function (t) {
      var o = S.cross[t], m = S.null[t], sd = S.nullSd[t];
      return '<div class="cx-row"><div class="cx-lab">' + lab[t] + ' <span class="muted">(' + S.nTyped[t] + ")</span></div>" +
        '<div class="cx-track"><span class="cx-fill" style="width:' + (100 * o / mx) + "%;background:" + TYPE_COL[t] + '"></span>' +
        '<span class="cx-null" style="left:' + (100 * (m - 2 * sd) / mx) + "%;width:" + (100 * 4 * sd / mx) + '%"></span>' +
        '<span class="cx-mean" style="left:' + (100 * m / mx) + '%"></span></div>' +
        '<div class="cx-num"><b>' + Math.round(100 * o) + "%</b> cross</div></div>";
    }).join("") + '<p class="cx-note muted">Bar: observed share of links that join two different communities. Grey band: ±2 standard ' +
      "deviations of 5,000 label shuffles (line: their mean, " + Math.round(100 * S.null.foe) + "%).</p>";

    /* ---------------- the Hulk board ---------------- */
    var hb = data.hostile, top = hb.slice(0, 7), bottom = hb.slice(-4);
    function hrow(r) {
      var n = r[1] + r[2];
      return '<div class="hb-row"><span class="hb-n">' + esc(r[0]) + '</span><span class="hb-bar">' +
        '<span class="f" style="flex:' + r[1] + '">' + (r[1] ? r[1] : "") + "</span>" +
        '<span class="a" style="flex:' + r[2] + '">' + (r[2] ? r[2] : "") + "</span></span>" +
        '<span class="hb-p">' + Math.round(100 * r[1] / n) + "% foe</span></div>";
    }
    document.getElementById("hbBoard").innerHTML = '<div class="hb-h">most fought-with</div>' + top.map(hrow).join("") +
      '<div class="hb-h">…and the friendliest</div>' + bottom.map(hrow).join("") +
      '<div class="hb-key"><span><i class="sw foe"></i>named as a foe</span><span><i class="sw ally"></i>named as an ally</span></div>';

    /* ---------------- validation table ---------------- */
    var V = data.validation;
    function cell(v) { return v ? v[0] + " / " + v[1] + ' <span class="muted">(' + Math.round(100 * v[0] / v[1]) + "%)</span>" : "–"; }
    document.getElementById("valTable").innerHTML = '<table><thead><tr><th></th><th class="num">foe</th><th class="num">ally</th>' +
      '<th class="num">family</th><th class="num">all</th></tr></thead><tbody>' +
      [["Round 1: first word list", V.round1], ["Round 2: fixed rules, fresh links", V.round2]].map(function (r) {
        return "<tr><td>" + r[0] + '</td><td class="num">' + cell(r[1].by.foe) + '</td><td class="num">' + cell(r[1].by.ally) +
          '</td><td class="num">' + cell(r[1].by.family) + '</td><td class="num"><b>' + cell([r[1].ok, r[1].n]) + "</b></td></tr>";
      }).join("") + "</tbody></table>";

    /* ---------------- frenemies ---------------- */
    var REAL = { "Cyclops|Storm": "real: Storm beats Cyclops in a duel for leadership of the X-Men",
                 "Black Widow|Yelena Belova": "real: two Black Widows from the same Red Room" };
    document.getElementById("frList").innerHTML = data.frenemies.map(function (p) {
      var a = p[0], b = p[1], key = [C[a].n, C[b].n].sort().join("|"), verdict = REAL[key];
      var s = [[a, b], [b, a]].map(function (d) {
        var j = out[d[0]].filter(function (k) { return E[k][1] === d[1]; })[0];
        var e = E[j];
        return '<div class="rc ' + e[2] + '"><div class="rc-who">' + esc(C[d[0]].n) + "'s page on <strong>" + esc(C[d[1]].n) +
          "</strong> · labelled " + e[2] + "</div><p>" + highlight(e[3], e[4], e[5]) + "</p></div>";
      }).join("");
      return '<div class="fr ' + (verdict ? "real" : "fake") + '"><div class="fr-h"><b>' + esc(C[a].n) + " &amp; " + esc(C[b].n) +
        '</b><span class="fr-v">' + (verdict ? "✓ " + esc(verdict) : "✗ artefact") + "</span></div>" + s + "</div>";
    }).join("");
  }).catch(function (err) {
    var c = document.getElementById("fmCard");
    if (c) c.innerHTML = '<p class="muted">Could not load week5.json (' + err + ").</p>";
  });
})();
