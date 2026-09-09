"""
Week 1 — Marvel Wikipedia network.
Regenerates every figure in posts/week1.html and prints the numbers quoted there.

    cd analysis && python3 week1.py

Reads ../data/week1_{nodes,edges}.tsv (the frozen course snapshot),
writes PNGs into ../assets/.
"""
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
ASSETS = HERE.parent / "assets"
ASSETS.mkdir(exist_ok=True)

INK = "#1a1a1a"
ACCENT = "#e2231a"       # Marvel-ish red, used sparingly
BLUE = "#2f6fb0"
GREY = "#9aa0a6"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "font.size": 11, "axes.titlesize": 12, "axes.edgecolor": "#cccccc",
    "axes.grid": True, "grid.color": "#ececec", "savefig.dpi": 130,
    "savefig.bbox": "tight",
})

# ----------------------------------------------------------------------
# load — every node first, so the 17 isolates survive
# ----------------------------------------------------------------------
nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])

G = nx.DiGraph()
G.add_nodes_from(nodes.node_id)
G.add_edges_from(edges.itertuples(index=False))
name = dict(zip(nodes.node_id, nodes.name))

n = G.number_of_nodes()
m_dir = G.number_of_edges()
UG = G.to_undirected()
m_und = UG.number_of_edges()
reciprocal = sum(G.has_edge(v, u) for u, v in G.edges()) // 2
k_mean = 2 * m_und / n
density = m_und / (n * (n - 1) / 2)

in_deg = dict(G.in_degree())
out_deg = dict(G.out_degree())
in_k = np.array([in_deg[v] for v in G])
out_k = np.array([out_deg[v] for v in G])

comps = sorted(nx.weakly_connected_components(G), key=len, reverse=True)
giant = comps[0]
island = comps[1]
isolates = sorted(nx.isolates(G))

stats = {
    "n": n, "m_directed": m_dir, "m_undirected": m_und, "reciprocal_pairs": reciprocal,
    "avg_degree": round(k_mean, 2), "density": round(density, 4),
    "n_isolates": len(isolates), "giant": len(giant), "island": len(island),
    "top_in": [(name[v], in_deg[v]) for v in sorted(G, key=in_deg.get, reverse=True)[:10]],
    "top_out": [(name[v], out_deg[v]) for v in sorted(G, key=out_deg.get, reverse=True)[:10]],
    "island_members": sorted(name[v] for v in island),
    "isolate_members": sorted(name[v] for v in isolates),
}
(HERE.parent / "assets" / "week1_stats.json").write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))


# ----------------------------------------------------------------------
# graph JSON for the interactive network on the web page
# ----------------------------------------------------------------------
def _short(s):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)",
                " (Marvel Comics character)", " (Morituri)"):
        s = s.replace(suf, "")
    return s

url = dict(zip(nodes.node_id, nodes.url))
comp_of = {v: (0 if v in giant else 1 if v in island else 2) for v in G}

# settled starting positions: force layout on the giant component, island + isolates parked
gpos = nx.spring_layout(G.subgraph(giant), seed=7, k=0.5, iterations=150)
gx = np.array([p[0] for p in gpos.values()]); gy = np.array([p[1] for p in gpos.values()])
gpos = {v: (float((x - gx.min()) / gx.ptp()), float((y - gy.min()) / gy.ptp()))
        for v, (x, y) in gpos.items()}
ipos = nx.spring_layout(G.subgraph(island), seed=2, k=1.0)
pos_xy = {}
for v in G:
    if comp_of[v] == 0:
        pos_xy[v] = gpos[v]
    elif comp_of[v] == 1:
        x, y = ipos[v]
        pos_xy[v] = (-0.28 + 0.16 * x, 0.5 + 0.16 * y)
isos = [v for v in G if comp_of[v] == 2]
for i, v in enumerate(isos):
    pos_xy[v] = (1.18, i / (len(isos) - 1))

order = list(G)
idx = {v: i for i, v in enumerate(order)}
graph = {
    "nodes": [{
        "id": idx[v], "name": name[v], "short": _short(name[v]),
        "in": in_deg[v], "out": out_deg[v], "comp": comp_of[v],
        "url": url.get(v, ""),
        "x": round(pos_xy[v][0], 4), "y": round(pos_xy[v][1], 4),
    } for v in order],
    "links": [{"s": idx[u], "t": idx[w]} for u, w in G.edges()],
    "meta": {"n": n, "m": m_dir, "reciprocal": reciprocal},
}
(HERE.parent / "assets" / "marvel.json").write_text(json.dumps(graph, separators=(",", ":")))
print("wrote assets/marvel.json  —", len(graph["nodes"]), "nodes,", len(graph["links"]), "links")


def raw_dist(ks):
    v, c = np.unique(np.asarray(ks), return_counts=True)
    return v, c / len(ks)


def mixed_binned(ks):
    """Course 'Goodies' scheme: u = k+1, width-1 bins for u=1..7, doubling bins
    after, count / bin-width, doubling bins drawn at sqrt(lo*(hi-1))."""
    N = len(ks)
    u = np.asarray(ks) + 1
    mx = int(u.max())
    xs, ys = [], []

    def add(lo, hi):
        c = int(np.sum((u >= lo) & (u < hi)))
        if c:
            xs.append(lo if hi - lo == 1 else np.sqrt(lo * (hi - 1)))
            ys.append(c / N / (hi - lo))

    for lo in range(1, 8):
        if lo <= mx:
            add(lo, lo + 1)
    lo = 8
    while lo <= mx:
        add(lo, 2 * lo)
        lo *= 2
    return np.array(xs), np.array(ys)


# ----------------------------------------------------------------------
# figure 1 — degree distributions
# ----------------------------------------------------------------------
fig, ax = plt.subplots(2, 2, figsize=(10, 7.5))
for row, (ks, lab, col) in enumerate([(in_k, "in-degree", ACCENT), (out_k, "out-degree", BLUE)]):
    kv, pv = raw_dist(ks)
    bx, by = mixed_binned(ks)
    for c, logscale in enumerate([False, True]):
        a = ax[row, c]
        a.scatter(kv + 1, pv, s=26, color=col, alpha=.55, label="raw $P(k)$")
        if logscale:
            a.plot(bx, by, "o-", color=INK, lw=1, ms=4, label="binned")
            a.set_xscale("log"); a.set_yscale("log")
        a.set_title(f"{lab} — {'log–log' if logscale else 'linear'}")
        a.set_xlabel("$k + 1$"); a.set_ylabel("$P(k)$")
        a.legend(frameon=False, fontsize=9)
fig.suptitle("Marvel Wikipedia network — degree distributions  (k+1 keeps the 17 isolates on the log axis)",
             fontsize=12)
fig.tight_layout()
fig.savefig(ASSETS / "fig-degree-dist.png")
plt.close(fig)

# ----------------------------------------------------------------------
# figure 2 — in vs out degree scatter
# ----------------------------------------------------------------------
fig, a = plt.subplots(figsize=(7.5, 6))
xi = out_k + 1
yi = in_k + 1
a.scatter(xi, yi, s=28, color=GREY, alpha=.6, edgecolor="none")
a.plot([1, 130], [1, 130], "--", color="#cccccc", lw=1, label="in = out")
lab_in = sorted(G, key=in_deg.get, reverse=True)[:6]
lab_out = sorted(G, key=out_deg.get, reverse=True)[:6]
def short(s):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)"):
        s = s.replace(suf, "")
    return s

for v in set(lab_in) | set(lab_out):
    right = out_deg[v] > 15
    a.annotate(short(name[v]), (out_deg[v] + 1, in_deg[v] + 1), fontsize=9,
               color=ACCENT if v in lab_in else BLUE,
               ha="right" if right else "left",
               xytext=(-5 if right else 5, 3), textcoords="offset points")
a.set_xscale("log"); a.set_yscale("log")
a.set_xlim(0.9, 200)
a.set_xlabel("out-degree + 1   (links this page makes)")
a.set_ylabel("in-degree + 1   (links this page receives)")
a.set_title("Who is linked to  vs  who links out — almost disjoint sets")
a.legend(frameon=False)
fig.tight_layout()
fig.savefig(ASSETS / "fig-in-vs-out.png")
plt.close(fig)

# ----------------------------------------------------------------------
# figure 3 — the whole network. Giant component by spring layout; the island
# and the isolates parked deliberately so "disconnected" reads at a glance.
# ----------------------------------------------------------------------
fig, a = plt.subplots(figsize=(12, 8))

giant_g = G.subgraph(giant)
pos = nx.spring_layout(giant_g, seed=7, k=0.5, iterations=150)
xs_ = np.array([p[0] for p in pos.values()])
ys_ = np.array([p[1] for p in pos.values()])
pos = {v: ((x - xs_.min()) / (xs_.ptp()), (y - ys_.min()) / (ys_.ptp()) * 0.85 + 0.12)
       for v, (x, y) in pos.items()}                       # giant -> unit box, upper area

isl = nx.spring_layout(G.subgraph(island), seed=2, k=1.0)
for v, (x, y) in isl.items():                               # island -> small cluster, top-left margin
    pos[v] = (-0.42 + 0.13 * x, 0.72 + 0.13 * y)

for i, v in enumerate(isolates):                            # isolates -> a row along the bottom
    pos[v] = (0.02 + i * (1.0 / (len(isolates) - 1)), -0.08)

col = {v: ("#c9d6e4" if v in giant else ACCENT if v in island else "#efb700") for v in G}
nx.draw_networkx_edges(G, pos, ax=a, alpha=.10, width=.6, arrows=False)
nx.draw_networkx_nodes(G, pos, ax=a, node_color=[col[v] for v in G],
                       node_size=[18 + 10 * in_deg[v] for v in G], linewidths=0)

hubs = sorted(giant, key=in_deg.get, reverse=True)[:6]
cx = np.mean([pos[v][0] for v in giant])
cy = np.mean([pos[v][1] for v in giant])
for v in hubs:
    x, y = pos[v]
    ang = np.arctan2(y - cy, x - cx)
    lx = x + 0.44 * np.cos(ang)
    ly = np.clip(y + 0.30 * np.sin(ang), -0.12, 0.98)         # push outward, keep off the title
    a.annotate(name[v].replace(" (character)", "").replace(" (Marvel Comics)", ""),
               (x, y), (lx, ly), fontsize=10, fontweight="bold",
               ha="center", va="center",
               arrowprops=dict(arrowstyle="-", color="#888", lw=.7),
               bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#ddd", lw=.5))
a.annotate("the island (9)", (-0.36, 0.9), fontsize=9, color=ACCENT, ha="center")
a.annotate("the 17 isolates — in the roster, linked by nobody", (0.5, -0.14),
           fontsize=9, color="#b98a00", ha="center")
a.set_title("303 Marvel characters — one giant blob, one island, 17 loners\n"
            "node size ∝ in-degree; layout: force-directed on the giant component only",
            fontsize=11, pad=16)
a.set_xlim(-0.62, 1.58); a.set_ylim(-0.2, 1.12)
a.axis("off")
fig.tight_layout()
fig.savefig(ASSETS / "fig-network.png")
plt.close(fig)

# ----------------------------------------------------------------------
# figure 4 — the islands: the 9-node component + the isolates
# ----------------------------------------------------------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 5.2), gridspec_kw={"width_ratios": [1.3, 1]})
IS = G.subgraph(island)
p = nx.spring_layout(IS, seed=1, k=1.2)
nx.draw_networkx_edges(IS, p, ax=a1, alpha=.5)
nx.draw_networkx_nodes(IS, p, ax=a1, node_color=ACCENT, node_size=900, linewidths=0)
nx.draw_networkx_labels(IS, p, ax=a1,
                        labels={v: name[v].replace(" (character)", "") for v in IS},
                        font_size=8)
a1.set_title(f"The island — {len(island)} characters, cut off from the other {len(giant)}")
a1.axis("off")

iso_names = sorted(name[v].replace(" (character)", "").replace(" (comics)", "") for v in isolates)
a2.axis("off")
a2.set_title(f"The {len(isolates)} isolates — in the roster, linked by nobody")
a2.text(0.0, 0.95, "\n".join(iso_names), va="top", ha="left", fontsize=9.5, family="monospace")
fig.tight_layout()
fig.savefig(ASSETS / "fig-islands.png")
plt.close(fig)

print("\nwrote:", *(p.name for p in sorted(ASSETS.glob("fig-*.png"))))
