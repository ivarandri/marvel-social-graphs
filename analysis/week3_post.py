"""
Week-3 post data.  Reads ../data/week1_*.tsv, writes ../assets/week3.json:
adjacency lists for the in-browser "six clicks" BFS, attack curves for the
"break the universe" chart, and the summary numbers the post quotes.

    cd analysis && python3 week3_post.py        (~2 min: the adaptive attacks and 200 shuffles)
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
OUT = HERE.parent / "assets" / "week3.json"
K = 100                                   # how many removals the attack chart covers


def short(s):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)",
                " (Marvel Comics character)", " (Natasha Romanova)"):
        s = s.replace(suf, "")
    return s


nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])
D = nx.DiGraph(); D.add_nodes_from(nodes.node_id); D.add_edges_from(edges.itertuples(index=False))
name = dict(zip(nodes.node_id, nodes.name))
url = dict(zip(nodes.node_id, nodes.url))
M = D.to_undirected()
GC = M.subgraph(max(nx.connected_components(M), key=len)).copy()
order = list(D)
idx = {v: i for i, v in enumerate(order)}
SM = "Spider-Man"

# ---------------- six clicks to Spider-Man ----------------
to_sm = nx.single_source_shortest_path_length(D.reverse(copy=False), SM)    # clicks needed to *reach* him
from_sm = nx.single_source_shortest_path_length(D, SM)                     # clicks needed to get *away*
clicks = {
    "toHist": sorted(Counter(d for v, d in to_sm.items() if v != SM).items()),
    "fromHist": sorted(Counter(d for v, d in from_sm.items() if v != SM).items()),
    "toMax": max(to_sm.values()), "fromMax": max(from_sm.values()),
    "toFarthest": [short(name[v]) for v, d in to_sm.items() if d == max(to_sm.values())],
    "fromFarthest": [short(name[v]) for v, d in from_sm.items() if d == max(from_sm.values())],
    "cantReach": len(D) - len(to_sm),
    "cantReachNonIsolates": [short(name[v]) for v in D if v not in to_sm and D.degree(v) > 0],
}

# ---------------- break the universe ----------------
n_gc = GC.number_of_nodes()


def giant(H):
    return max((len(c) for c in nx.connected_components(H)), default=0)


single = []
for v in GC:
    H = GC.copy(); H.remove_node(v)
    single.append((n_gc - 1 - giant(H), v))
single.sort(reverse=True)


def attack(pick_next):
    H = GC.copy(); sizes, removed = [giant(H)], []
    for _ in range(K):
        v = pick_next(H)
        removed.append(short(name[v])); H.remove_node(v); sizes.append(giant(H))
    return sizes, removed


deg_sizes, deg_order = attack(lambda H: max(H, key=lambda v: (H.degree(v), v)))           # recomputed each step
bet_sizes, bet_order = attack(lambda H: (lambda b: max(H, key=lambda v: (b[v], v)))(nx.betweenness_centrality(H)))
rng = np.random.default_rng(0)
rand_runs = []
for _ in range(100):
    H = GC.copy(); sizes = [giant(H)]
    for v in rng.permutation(list(GC))[:K]:
        H.remove_node(v); sizes.append(giant(H))
    rand_runs.append(sizes)
rand_sizes = np.mean(rand_runs, axis=0)


def halving(sizes):
    return next((k for k, s in enumerate(sizes) if s < n_gc / 2), None)


attack_data = {
    "n": n_gc, "K": K,
    "degree": deg_sizes, "betweenness": bet_sizes, "random": [round(float(x), 1) for x in rand_sizes],
    "degreeOrder": deg_order, "betweennessOrder": bet_order,
    "halve": {"degree": halving(deg_sizes), "betweenness": halving(bet_sizes), "random": halving(rand_sizes)},
    "single": [{"short": short(name[v]), "cut": c} for c, v in single[:5]],
    "spiderLeaves": [short(name[u]) for u in GC.neighbors(SM) if GC.degree(u) == 1],
}

# ---------------- the real broker: betweenness vs degree-preserving shuffles ----------------
bet = nx.betweenness_centrality(GC)
by_name = {v: k for k, v in name.items()}
pick = [by_name[c] for c in ["Spider-Man", "Hercules (Marvel Comics)", "Black Widow (Natasha Romanova)",
                             "U.S. Agent", "Black Cat (Marvel Comics)"]]
null = {v: [] for v in pick}
for s in range(200):
    g = GC.copy()
    nx.connected_double_edge_swap(g, nswap=10 * g.number_of_edges(), seed=s)
    b = nx.betweenness_centrality(g)
    for v in pick:
        null[v].append(b[v])
brokers = [{"short": short(name[v]), "deg": GC.degree(v), "real": round(bet[v], 4),
            "null": round(float(np.mean(null[v])), 4), "sd": round(float(np.std(null[v])), 4),
            "z": round(float((bet[v] - np.mean(null[v])) / np.std(null[v])), 1)} for v in pick]

# ---------------- cliques + a homophily ----------------
eights = [sorted(short(name[v]) for v in c) for c in nx.find_cliques(M) if len(c) == 8]
core = sorted(set.intersection(*(set(c) for c in eights)))
sizes = Counter(len(c) for c in nx.enumerate_all_cliques(M))

debut_csv = HERE.parent.parent / "week3_debut_years.csv"          # made by the Week 3 notebook
homophily = None
if debut_csv.exists():
    debut = pd.read_csv(debut_csv).set_index("node_id")["debut_year"].dropna().astype(int).to_dict()
    era = {v: ("≤1940s" if y < 1950 else "≥2010s" if y >= 2010 else f"{10 * (y // 10)}s") for v, y in debut.items()}
    H = GC.subgraph([v for v in GC if v in era]).copy()
    nx.set_node_attributes(H, era, "era")
    r = nx.attribute_assortativity_coefficient(H, "era")
    lab = list(H); vals = np.array([era[v] for v in lab]); rr = []
    for _ in range(1000):
        nx.set_node_attributes(H, dict(zip(lab, rng.permutation(vals))), "shuf")
        rr.append(nx.attribute_assortativity_coefficient(H, "shuf"))
    same = np.mean([era[u] == era[v] for u, v in H.edges()])
    homophily = {"r": round(r, 3), "null": round(float(np.mean(rr)), 3), "sd": round(float(np.std(rr)), 3),
                 "z": round(float((r - np.mean(rr)) / np.std(rr)), 1), "sameEra": round(float(same), 3)}

out = {
    "chars": [{"short": short(name[v]), "url": url.get(v, "")} for v in order],
    "und": [[idx[u] for u in M.neighbors(v)] for v in order],
    "out": [[idx[u] for u in D.successors(v)] for v in order],
    "spider": idx[SM],
    "clicks": clicks,
    "attack": attack_data,
    "brokers": brokers,
    "cliques": {"clique_number": max(sizes), "n8": len(eights), "core": core, "eights": eights,
                "extras": sorted(set(sum(eights, [])) - set(core)), "counts": dict(sorted(sizes.items()))},
    "homophily": homophily,
}
OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
print("wrote", OUT.name, f"({OUT.stat().st_size // 1024} KB)")
print(json.dumps({k: v for k, v in out.items() if k not in ("chars", "und", "out")}, indent=1, ensure_ascii=False)[:4000])
