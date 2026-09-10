"""
Week-2 post data.  Reads ../data/week1_*.tsv, writes ../assets/week2.json:
per-character friendship-paradox numbers + the summary blocks the post quotes.

    cd analysis && python3 week2_post.py
"""
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "assets" / "week2.json"


def short(s):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)",
                " (Marvel Comics character)"):
        s = s.replace(suf, "")
    return s


nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])
D = nx.DiGraph(); D.add_nodes_from(nodes.node_id); D.add_edges_from(edges.itertuples(index=False))
M = D.to_undirected()
name = dict(zip(nodes.node_id, nodes.name))
url = dict(zip(nodes.node_id, nodes.url))
deg = dict(M.degree())

# ---------------- per-character friendship paradox ----------------
chars = []
holds = tot = 0
for v in M:
    d = deg[v]
    entry = {"name": name[v], "short": short(name[v]), "deg": d, "url": url.get(v, "")}
    if d == 0:
        entry.update(meanFriend=None, holds=None, topFriend=None, fd=[])
    else:
        fd = sorted((deg[w] for w in M.neighbors(v)), reverse=True)
        mnd = sum(fd) / len(fd)
        tf = max(M.neighbors(v), key=lambda w: deg[w])
        entry.update(meanFriend=round(mnd, 2), holds=bool(mnd >= d),
                     topFriend={"short": short(name[tf]), "deg": deg[tf]},
                     fd=fd)
        holds += mnd >= d
        tot += 1
    chars.append(entry)
chars.sort(key=lambda c: -c["deg"])

# who is out-popularity-ed by nobody: every friend has degree <= yours
never_beaten = [{"short": short(name[v]), "deg": deg[v]}
                for v in M if deg[v] > 0 and all(deg[w] <= deg[v] for w in M.neighbors(v))]
never_beaten.sort(key=lambda c: -c["deg"])

# most often someone's highest-degree friend
pop = Counter()
for v in M:
    if deg[v] == 0:
        continue
    pop[short(name[max(M.neighbors(v), key=lambda w: deg[w])])] += 1
top_friends = [{"short": s, "count": c} for s, c in pop.most_common(6)]

k_pos = np.array([deg[v] for v in M if deg[v] > 0])
edge_mean = sum(deg[u] + deg[v] for u, v in M.edges()) / (2 * M.number_of_edges())

# ---------------- reciprocity + its null ----------------
recip_pairs = sum(D.has_edge(v, u) for u, v in D.edges()) // 2
frac_recip = 2 * recip_pairs / D.number_of_edges()
ind = [d for _, d in D.in_degree()]
outd = [d for _, d in D.out_degree()]
rc = []
for s in range(50):
    g = nx.DiGraph(nx.directed_configuration_model(ind, outd, seed=s))
    g.remove_edges_from(nx.selfloop_edges(g))
    rc.append(2 * (sum(g.has_edge(v, u) for u, v in g.edges()) // 2) / g.number_of_edges())

# ---------------- clustering / transitivity nulls (giant component) ----------------
GC = nx.convert_node_labels_to_integers(
        M.subgraph(max(nx.connected_components(M), key=len)).copy())
seq = [d for _, d in GC.degree()]
n_gc, m_gc = GC.number_of_nodes(), GC.number_of_edges()


def swap_stats(reps=60):
    C, T = [], []
    for s in range(reps):
        g = GC.copy()
        nx.double_edge_swap(g, nswap=10 * m_gc, max_tries=200 * m_gc, seed=s)
        C.append(nx.average_clustering(g)); T.append(nx.transitivity(g))
    return np.array(C), np.array(T)


Cs, Ts = swap_stats()
C_gnm = np.array([nx.average_clustering(nx.gnm_random_graph(n_gc, m_gc, seed=s)) for s in range(60)])

# ---------------- three fake Marvels ----------------
def sm(G):
    g = G.subgraph(max(nx.connected_components(G), key=len))
    return {"C": round(nx.average_clustering(G), 3),
            "d": round(nx.average_shortest_path_length(g), 2),
            "maxk": int(max(d for _, d in G.degree()))}


models = {
    "real": sm(GC),
    "random": sm(nx.gnm_random_graph(n_gc, m_gc, seed=1)),
    "ba": sm(nx.barabasi_albert_graph(n_gc, round(m_gc / n_gc), seed=1)),
    "ws": sm(nx.watts_strogatz_graph(n_gc, round(2 * m_gc / n_gc), 0.2, seed=1)),
}

out = {
    "chars": chars,
    "paradox": {
        "holdsPct": round(100 * holds / tot),
        "nHolds": holds, "nTot": tot,
        "meanDeg": round(k_pos.mean(), 1),
        "friendMean": round(edge_mean, 1),
        "neverBeaten": never_beaten,
        "topFriends": top_friends,
    },
    "reciprocity": {
        "real": round(frac_recip, 3),
        "null": round(float(np.mean(rc)), 3),
        "nullSd": round(float(np.std(rc)), 3),
        "pairs": recip_pairs,
    },
    "shuffle": {
        "gc_n": n_gc, "gc_m": m_gc,
        "C_real": round(nx.average_clustering(GC), 3),
        "C_swap": round(float(Cs.mean()), 3), "C_swap_sd": round(float(Cs.std()), 3),
        "C_gnm": round(float(C_gnm.mean()), 3),
        "T_real": round(nx.transitivity(GC), 3),
        "T_swap": round(float(Ts.mean()), 3),
        "isolates_real": int(sum(1 for _, d in M.degree() if d == 0)),
    },
    "models": models,
}
OUT.write_text(json.dumps(out, separators=(",", ":")))
print("wrote", OUT.name)
print(json.dumps({k: v for k, v in out.items() if k != "chars"}, indent=2))
