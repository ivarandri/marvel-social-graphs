"""
Week-4 post data.  Reads ../data/week4_philosophers_*.tsv, writes ../assets/week4.json:
the "sorting hat" (20 Louvain runs per philosopher), Aristotle's link-community rooms,
the disparity-filter backbone with a fixed layout for the alpha slider, and the numbers
the post quotes.

    cd analysis && python3 week4_post.py        (~3 min: 20 Louvain runs, 10 shuffles, the layout)
"""
import csv
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from networkx.algorithms.community import louvain_communities, modularity
from sklearn.metrics import normalized_mutual_info_score as nmi

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "assets" / "week4.json"
RUNS = 20
ALPHA_MAX = 0.3                          # the slider's range; the layout is of this backbone

nodes = pd.read_csv(DATA / "week4_philosophers_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week4_philosophers_edges.tsv", sep="\t", comment="#")
G = nx.Graph()
G.add_nodes_from(nodes.node_id)
for s, t, w in edges.itertuples(index=False):              # sum both directions
    if G.has_edge(s, t):
        G[s][t]["weight"] += w
    else:
        G.add_edge(s, t, weight=w)
giant = G.subgraph(max(nx.connected_components(G), key=len)).copy()
Gu = nx.Graph(giant.edges())
name = dict(zip(nodes.node_id, nodes.name))
url = dict(zip(nodes.node_id, nodes.url))
era = dict(zip(nodes.node_id, nodes.era))
deg = dict(giant.degree())
strength = dict(giant.degree(weight="weight"))
order = sorted(giant, key=lambda v: -deg[v])
idx = {v: i for i, v in enumerate(order)}
N, M = len(order), giant.number_of_edges()
print(f"giant: {N} philosophers, {M} links")


def labels(parts):
    lab = {v: i for i, c in enumerate(parts) for v in c}
    return [lab[v] for v in order]


def heads(parts):
    """each philosopher -> the highest-degree member of their community (the 'house head')"""
    out = {}
    for c in parts:
        h = max(c, key=lambda v: deg[v])
        for v in c:
            out[v] = h
    return out


# ---------------- the sorting hat: 20 Louvain runs, unweighted (as in the course) ----------------
runs = [louvain_communities(giant, weight=None, seed=s) for s in range(RUNS)]
Qs = [modularity(giant, p, weight=None) for p in runs]
L = [labels(p) for p in runs]
pair_nmi = [nmi(L[a], L[b]) for a, b in combinations(range(RUNS), 2)]
H = [heads(p) for p in runs]
head_count = Counter(h for Hr in H for h in set(Hr.values()))
house_list = [h for h, _ in head_count.most_common()]
hid = {h: i for i, h in enumerate(house_list)}
votes = [[hid[H[r][v]] for r in range(RUNS)] for v in order]


def entropy(vs):
    p = np.array(list(Counter(vs).values())) / len(vs)
    return float(-(p * np.log2(p)).sum())


ent = [entropy(v) for v in votes]
loyal = sum(len(set(v)) == 1 for v in votes)
print(f"Q {min(Qs):.3f}-{max(Qs):.3f}, communities {min(map(len, runs))}-{max(map(len, runs))}, "
      f"NMI {min(pair_nmi):.2f}-{max(pair_nmi):.2f}; loyal {loyal}/{N}; houses: "
      + ", ".join(f"{name[h]} {c}" for h, c in head_count.most_common()))

# weighted Louvain: does the weighted network sort people differently?
wrun = louvain_communities(giant, weight="weight", seed=0)
wH = heads(wrun)
for h in set(wH.values()):
    if h not in hid:
        hid[h] = len(house_list); house_list.append(h)
Qw = modularity(giant, wrun, weight="weight")
nmi_w = nmi(L[0], labels(wrun))
modal = [Counter(v).most_common(1)[0][0] for v in votes]
moved_w = sum(hid[wH[v]] != modal[i] for i, v in enumerate(order))
print(f"weighted: {len(wrun)} communities, Qw {Qw:.3f}, NMI vs unweighted seed 0 {nmi_w:.2f}, "
      f"{moved_w} philosophers land in a different house than their usual one")

# null: degree-preserving shuffles (10; the notebook's 20 give 0.222 +- 0.002)
Qnull = []
for r in range(10):
    Hs = Gu.copy()
    nx.double_edge_swap(Hs, nswap=10 * M, max_tries=100 * M, seed=r)
    Qnull.append(modularity(Hs, louvain_communities(Hs, seed=r)))
print(f"shuffled Q {np.mean(Qnull):.3f} +- {np.std(Qnull, ddof=1):.3f}")


# ---------------- link communities (Ahn, Bagrow & Lehmann 2010) ----------------
def link_communities(G):
    E = [tuple(sorted(e)) for e in G.edges()]
    eid = {e: i for i, e in enumerate(E)}
    incl = {v: set(G[v]) | {v} for v in G}
    pairs = []
    for k in G:
        nb = list(G[k])
        for a in range(len(nb)):
            for b in range(a + 1, len(nb)):
                i, j = nb[a], nb[b]
                pairs.append((len(incl[i] & incl[j]) / len(incl[i] | incl[j]),
                              eid[tuple(sorted((i, k)))], eid[tuple(sorted((j, k)))]))
    pairs.sort(key=lambda t: -t[0])
    parent = list(range(len(E)))
    nodes_ = [set(e) for e in E]
    mc = [1] * len(E)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def dens(m, n):
        return 0.0 if n <= 2 else m * (m - (n - 1)) / ((n - 2) * (n - 1))

    total, best, best_s, i = 0.0, 0.0, 1.0, 0
    while i < len(pairs):
        s = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == s:
            _, x, y = pairs[i]; i += 1
            rx, ry = find(x), find(y)
            if rx == ry:
                continue
            if len(nodes_[rx]) < len(nodes_[ry]):
                rx, ry = ry, rx
            total -= dens(mc[rx], len(nodes_[rx])) + dens(mc[ry], len(nodes_[ry]))
            nodes_[rx] |= nodes_[ry]; nodes_[ry] = None
            mc[rx] += mc[ry]; parent[ry] = rx
            total += dens(mc[rx], len(nodes_[rx]))
        if 2 * total / len(E) > best:
            best, best_s = 2 * total / len(E), s
    parent = list(range(len(E)))
    for s, x, y in pairs:
        if s < best_s:
            break
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx
    groups = defaultdict(list)
    for j, e in enumerate(E):
        groups[find(j)].append(e)
    return sorted(groups.values(), key=len, reverse=True), best


lcomms, Dmax = link_communities(Gu)
rooms = defaultdict(set)                     # philosopher -> real (2+ link) rooms
for i, c in enumerate(lcomms):
    if len(c) >= 2:
        for e in c:
            rooms[e[0]].add(i); rooms[e[1]].add(i)
n_rooms = {v: len(rooms[v]) for v in order}
print(f"link communities: D = {Dmax:.4f}, {sum(len(c) >= 2 for c in lcomms)} with 2+ links; "
      f"{sum(n >= 2 for n in n_rooms.values())} philosophers in 2+")

AR = "Aristotle"
ar_rooms = defaultdict(list)
for i, c in enumerate(lcomms):
    for e in c:
        if AR in e:
            ar_rooms[i].append(e[0] if e[1] == AR else e[1])
ar_list = []
for i, nbrs in sorted(ar_rooms.items(), key=lambda t: -len(t[1])):
    members = {v for e in lcomms[i] for v in e} - {AR}
    tops = sorted(members, key=lambda v: -deg[v])[:6]
    ar_list.append({"n": len(nbrs), "size": len(members) + 1, "links": len(lcomms[i]),
                    "nbrs": sorted((idx[v] for v in nbrs), key=lambda j: -deg[order[j]]),
                    "top": [name[v] for v in tops],
                    "houses": []})
    hc = Counter(modal[idx[v]] for v in members)
    ar_list[-1]["houses"] = [[name[house_list[h]], n] for h, n in hc.most_common(4)]
ar_votes = Counter(votes[idx[AR]])
print(f"Aristotle: {len(ar_rooms)} link communities ({sum(len(c) >= 2 for i, c in enumerate(lcomms) if i in ar_rooms)} real); "
      f"biggest holds {ar_list[0]['n']} of his {deg[AR]} links; Louvain houses {dict(ar_votes)}")


# ---------------- the disparity-filter backbone ----------------
def alpha_star(u, v):
    """smallest alpha at which the link survives: min over both ends of (1 - w/s)^(k-1)"""
    w = giant[u][v]["weight"]
    return min((1 - w / strength[u]) ** (deg[u] - 1), (1 - w / strength[v]) ** (deg[v] - 1))


astar = {tuple(sorted(e)): alpha_star(*e) for e in giant.edges()}
bb_edges = sorted((a, e) for e, a in astar.items() if a < ALPHA_MAX)
print(f"backbone at alpha {ALPHA_MAX}: {len(bb_edges)} links")
for a in (0.05, 0.1, 0.2, 0.3):
    B = nx.Graph([e for x, e in bb_edges if x < a])
    print(f"  alpha {a}: {B.number_of_edges()} links, {B.number_of_nodes()} philosophers, "
          f"giant {len(max(nx.connected_components(B), key=len))}")

# Grow the backbone link by link (increasing alpha*) with union-find, and record every merge.
parent, size = {}, {}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


members_of = {}
merges, curve, big = [], [], 0
for a, (u, v) in bb_edges:
    for x in (u, v):
        if x not in parent:
            parent[x] = x; size[x] = 1; members_of[x] = {x}
    ru, rv = find(u), find(v)
    if ru != rv:
        small, large = sorted((ru, rv), key=lambda r: size[r])
        merges.append((a, u, v, size[small], size[large], set(members_of[small]), set(members_of[large])))
        parent[small] = large; size[large] += size[small]
        members_of[large] |= members_of.pop(small)
    big = max(big, size[find(u)])
    curve.append([round(a, 5), big])
# the break: the merge that joins the two biggest pieces (largest smaller side)
brk = max(merges, key=lambda m: m[3])
a_brk, bu, bv, s_small, s_large, side_small, side_large = brk


def describe(side):
    hc = Counter(modal[idx[v]] for v in side)
    return [[name[house_list[h]], n] for h, n in hc.most_common(4)]


print(f"break: alpha* = {a_brk:.4f}: {name[bu]} - {name[bv]} (w={giant[bu][bv]['weight']}) joins "
      f"{s_small} + {s_large}; small side {describe(side_small)}; large side {describe(side_large)}")
# which end makes it significant?
pu = (1 - giant[bu][bv]['weight'] / strength[bu]) ** (deg[bu] - 1)
pv_ = (1 - giant[bu][bv]['weight'] / strength[bv]) ** (deg[bv] - 1)
print(f"  p at {name[bu]}: {pu:.4f} (k={deg[bu]}, s={strength[bu]}), at {name[bv]}: {pv_:.4f} (k={deg[bv]}, s={strength[bv]})")
top_merges = sorted(merges, key=lambda m: -m[3])[:6]
for m_ in top_merges:
    print(f"  merge at {m_[0]:.4f}: {name[m_[1]]} - {name[m_[2]]}: {m_[3]} + {m_[4]}")

# The threads: growing the backbone again, record the link that first attaches each big house's head
# to Aristotle's piece. Below that link's alpha*, the tradition is cut off from antiquity.
parent, size = {}, {}
threads = {}
big_heads = [h for h, c in head_count.most_common() if c >= RUNS // 2 and h != AR] + ["Karl_Marx", "John_Locke"]
for a, (u, v) in bb_edges:
    for x in (u, v):
        if x not in parent:
            parent[x] = x; size[x] = 1
    ru, rv = find(u), find(v)
    if ru != rv:
        small, large = sorted((ru, rv), key=lambda r: size[r])
        s_small = size[small]; parent[small] = large; size[large] += size[small]
        if AR in parent:
            for h in big_heads:
                if h not in threads and h in parent and find(h) == find(AR):
                    threads[h] = {"head": name[h], "alpha": round(a, 4), "u": name[u], "v": name[v], "iu": idx[u], "iv": idx[v],
                                  "w": int(giant[u][v]["weight"]), "pieces": [s_small, size[large] - s_small]}
threads = sorted(threads.values(), key=lambda t: t["alpha"])
for t in threads:
    print(f"  {t['head']:20s} joins Aristotle at alpha {t['alpha']}: {t['u']} - {t['v']} (w={t['w']}) {t['pieces']}")
ap = sum(H[r][AR] == H[r]["Plato"] for r in range(RUNS))
print(f"Aristotle and Plato share a house in {ap} of {RUNS} runs")

# a fixed layout of the alpha = 0.3 backbone, so nodes stay put while the slider moves
# (only its largest piece is laid out and drawn: a node outside it at alpha = 0.3 can never rejoin at lower alpha)
B = nx.Graph([e for _, e in bb_edges])
Bg = B.subgraph(max(nx.connected_components(B), key=len)).copy()
pos = nx.forceatlas2_layout(Bg, max_iter=800, seed=4, scaling_ratio=5.0, gravity=0.6, dissuade_hubs=True)
P = np.array([pos[v] for v in Bg])
lo, hi = np.percentile(P, 1, axis=0), np.percentile(P, 99, axis=0)
xy = {v: np.clip((np.asarray(pos[v]) - lo) / (hi - lo), -0.03, 1.03) for v in Bg}

# ---------------- write ----------------
short_house = {h: name[h].replace("Georg Wilhelm Friedrich ", "").replace("Gottfried Wilhelm ", "")
               for h in house_list}
out = {
    "houses": [{"id": name[h], "short": short_house[h], "runs": head_count.get(h, 0)} for h in house_list],
    "p": [{"n": name[v], "u": url[v], "k": deg[v], "s": strength[v], "era": era[v],
           "v": votes[i], "w": hid[wH[v]], "r": n_rooms[v], "e": round(ent[i], 3),
           "xy": [round(float(xy[v][0]), 4), round(float(xy[v][1]), 4)] if v in xy else None}
          for i, v in enumerate(order)],
    "bb": [[idx[u], idx[v], round(a, 5), int(giant[u][v]["weight"])] for a, (u, v) in bb_edges],
    "curve": curve[::5] + [curve[-1]],
    "break": {"alpha": round(a_brk, 4), "u": name[bu], "v": name[bv], "w": int(giant[bu][bv]["weight"]),
              "pu": round(pu, 4), "pv": round(pv_, 4), "small": s_small, "large": s_large,
              "smallSide": describe(side_small), "largeSide": describe(side_large)},
    "threads": threads,
    "aristotle": {"withPlato": ap, "k": deg[AR], "rooms": ar_list, "votes": [[name[house_list[h]], c] for h, c in ar_votes.most_common()]},
    "stats": {"N": N, "M": M, "runs": RUNS, "Qmin": round(min(Qs), 3), "Qmax": round(max(Qs), 3),
              "cmin": min(map(len, runs)), "cmax": max(map(len, runs)),
              "nmiMin": round(min(pair_nmi), 2), "nmiMax": round(max(pair_nmi), 2),
              "Qnull": round(float(np.mean(Qnull)), 3), "QnullSd": round(float(np.std(Qnull, ddof=1)), 3),
              "loyal": loyal, "Qw": round(Qw, 3), "nmiW": round(nmi_w, 2), "movedW": moved_w,
              "D": round(Dmax, 4), "multi": sum(n >= 2 for n in n_rooms.values())},
}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB)")
