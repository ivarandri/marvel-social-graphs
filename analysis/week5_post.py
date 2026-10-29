"""
Week-5 post data: friends, foes and family.
For every link A -> B, pull the sentences on A's page that mention B, label the link from
the words near the mention (foe / ally / family), and ask whether foes live in different
network communities than allies.  Reads ../data/week1_*.tsv and ../data/marvel_pages.zip,
writes ../assets/week5.json (and validation_sample.tsv for reading labels by hand).

    cd analysis && python3 week5_post.py        (~20 s)
"""
import csv
import json
import random
import re
import urllib.parse
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from networkx.algorithms.community import louvain_communities

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "assets" / "week5.json"
WINDOW = 12                                     # words either side of the mention

nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])
with zipfile.ZipFile(DATA / "marvel_pages.zip") as z:
    pages = {urllib.parse.unquote(n.split("/")[-1][:-4]): z.read(n).decode("utf-8")
             for n in z.namelist() if n.endswith(".txt") and "README" not in n}
name = dict(zip(nodes.node_id, nodes.name))
url = dict(zip(nodes.node_id, nodes.url))


def short(n):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)", " (Marvel Comics character)"):
        n = n.replace(suf, "")
    return re.sub(r"\s*\(.*?\)\s*$", "", n).strip()


def aliases(v):
    """the page title without its disambiguation, plus real names given in brackets on the first line"""
    al = {short(name[v])}
    first = pages[v].split("\n")[0][:400]
    for m in re.finditer(r"\(([^()]{3,40})\)", first):
        if re.match(r"^[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+$", m.group(1)):
            al.add(m.group(1))
    return al


# ---------------- sentences of the story part of each page ----------------
STOP_SECTIONS = re.compile(r"^(In other media|Reception|Critical reception|Cultural impact|Legacy|Collected editions|"
                           r"See also|References|Bibliography|External links|Notes|Footnotes|Further reading|"
                           r"Merchandise|Accolades|In popular culture)\s*$")


def story_sentences(text):
    out = []
    for para in text.split("\n"):
        if STOP_SECTIONS.match(para.strip()):
            break                                    # the rest is media, critics and references
        if len(para) < 40:                           # headings and list items
            continue
        out += re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", para)
    return out


S = {k: story_sentences(t) for k, t in pages.items()}

# ---------------- the word list ----------------
LEX = {
    "foe": r"enem(?:y|ies)|arch-?enem\w*|nemes(?:is|es)|foes?|rivals?|rivalry|fights?|fought|fighting|battl(?:e|es|ed|ing)|"
           r"defeat(?:s|ed|ing)?|kill(?:s|ed|ing)?|murder\w*|attack(?:s|ed|ing)?|captur\w*|imprison\w*|betray\w*|"
           r"reveng\w*|vengeance|destroy\w*|slay\w*|duel\w*|clash\w*|kidnap\w*|assassinat\w*|tortur\w*|stabb\w*|"
           r"against",
    "ally": r"all(?:y|ies|ied|iance)|teammates?|team(?:s|ed)? up|teamed|partner\w*|friends?|friendship|mentor\w*|"
            r"sidekick\w*|alongside|help(?:s|ed|ing)?|aid(?:s|ed)?|rescu\w*|sav(?:e|es|ed|ing)|protect\w*|recruit\w*|"
            r"join(?:s|ed|ing)?|train(?:s|ed|ing)?|worked with|together",
    "family": r"marri\w*|marry|wedding|wife|husband|spouse|sons?|daughters?|father|mother|parents?|brothers?|sisters?|"
              r"siblings?|twins?|cousins?|niece|nephew|uncle|aunt|grand(?:father|mother|son|daughter)\w*|children|child|"
              r"lovers?|girlfriend|boyfriend|romanc\w*|romantic\w*|dating|kiss\w*|love interest|in love|fianc\w*",
}
LEX_RE = {k: re.compile(r"\b(?:" + v + r")\b", re.I) for k, v in LEX.items()}
FIGHT_ALONGSIDE = re.compile(r"\b(?:fights?|fought|fighting|battl\w+)(?=\s+(?:alongside|together|side by side)\b)", re.I)
# How close a keyword must be to the mention, in words: (before, after). Version 1 used 12 on both sides
# for everything; reading 60 labelled links showed foe and family words usually belonged to someone else.
REACH = {"foe": (5, 2), "ally": (8, 8), "family": (3, 3)}
# every character name, so that keywords hidden inside names ("Black Widow", "Spider-Woman") are masked
ALL_NAMES = re.compile("|".join(sorted({re.escape(a) for v in name for a in aliases(v)}, key=len, reverse=True)))


def label_sentence(sent, spans):
    """keyword hits per category near the mention of the target, other characters' names masked"""
    masked = list(sent)
    for m in ALL_NAMES.finditer(sent):
        if not any(m.start() < b and m.end() > a for a, b in spans):
            masked[m.start():m.end()] = ["#" if c != " " else " " for c in sent[m.start():m.end()]]
    masked = "".join(masked)
    masked = FIGHT_ALONGSIDE.sub(lambda m: "#" * len(m.group(0)), masked)     # "fought alongside X": ally
    starts = [m.start() for m in re.finditer(r"\S+", masked)]
    word_at = lambda pos: max(i for i, st in enumerate(starts) if st <= pos)
    ment = [(word_at(a), word_at(b - 1)) for a, b in spans]
    hits = {}
    for k, r in LEX_RE.items():
        before, after = REACH[k]
        hits[k] = [m.group(0).lower() for m in r.finditer(masked)
                   if any(lo - before <= word_at(m.start()) < lo or hi < word_at(m.start()) <= hi + after
                          for lo, hi in ment)]
    return hits


edge_rows = []
for s, t in edges.itertuples(index=False):
    pats = [re.compile(r"(?<![\w-])" + re.escape(a) + r"(?![\w-])") for a in sorted(aliases(t), key=len, reverse=True)]
    sents = []
    for sent in S[s]:
        spans = [m.span() for p in pats for m in p.finditer(sent)]
        if spans:
            sents.append((sent, spans, label_sentence(sent, spans)))
    score = Counter()
    for _, _, h in sents:
        for k, v in h.items():
            score[k] += len(v)
    if not sents:
        kind = "unmatched"
    elif not score or max(score.values()) == 0:
        kind = "neutral"
    else:
        best = max(score.values())
        tops = [k for k in ("family", "foe", "ally") if score[k] == best]
        kind = tops[0] if len(tops) == 1 else "mixed"
    # the sentence shown in the explorer: the one with most hits for the winning label (else the first)
    show = None
    if sents:
        key = kind if kind in LEX else None
        show = max(sents, key=lambda x: len(x[2][key]) if key else 0)
    edge_rows.append({"s": s, "t": t, "kind": kind, "n_sent": len(sents), "score": dict(score),
                      "sent": show[0] if show else "", "spans": show[1] if show else [],
                      "words": sorted({w for k in LEX for w in (show[2][k] if show else [])})})

E = pd.DataFrame(edge_rows)
# links between two versions of one character (Wolverine -> Ultimate Wolverine) are neither friends nor foes
E.loc[[short(name[s]) == short(name[t]) for s, t in zip(E.s, E.t)], "kind"] = "version"
print(E.kind.value_counts().to_string())

# ---------------- hand-check sample ----------------
# ---------------- hand-checked labels ----------------
# round 1: 60 random typed links labelled by version 1 of the rules (12-word window, no name masking), read by hand;
# round 2: 60 fresh random typed links labelled by the current rules, read by hand. Round 2 is the honest test.
now = {(s, t): k for s, t, k in zip(E.s, E.t, E.kind)}
TYPED = ["foe", "ally", "family"]
val = {}
for rnd, col in [("round1", "label_v1"), ("round2", "label_v2")]:
    r = pd.read_csv(HERE / f"validation_{rnd}.tsv", sep="\t")
    r["ok"] = r[col] == r.truth
    val[rnd] = {"n": len(r), "ok": int(r.ok.sum()),
                "by": {k: [int(g.ok.sum()), len(g)] for k, g in r.groupby(col)}}
    r["now"] = [now[(a, b)] for a, b in zip(r.s, r.t)]
    r["now_ok"] = (r.now == r.truth) | (~r.now.isin(TYPED) & (r.truth == "neutral"))
    print(f"{rnd}: labels right when read {r.ok.mean():.0%} {val[rnd]['by']}; current rules on the same links {r.now_ok.mean():.0%}")
# ---------------- communities (week-4 style Louvain on the undirected giant component) ----------------
U = nx.Graph()
U.add_nodes_from(nodes.node_id)
U.add_edges_from(edges.itertuples(index=False))
U.remove_edges_from(nx.selfloop_edges(U))
GC = U.subgraph(max(nx.connected_components(U), key=len)).copy()
comms = sorted(louvain_communities(GC, seed=0), key=len, reverse=True)
comm = {v: i for i, c in enumerate(comms) for v in c}
deg = dict(GC.degree())
comm_names = [short(name[max(c, key=deg.get)]) for c in comms]
print("communities:", [(comm_names[i], len(c)) for i, c in enumerate(comms)])

E["in_gc"] = E.s.isin(comm) & E.t.isin(comm)
E["cross"] = [comm.get(s) != comm.get(t) for s, t in zip(E.s, E.t)]
typed = E[E.in_gc & E.kind.isin(TYPED)].copy()
cross = typed.groupby("kind").cross.mean()
n_kind = typed.kind.value_counts()
print("share of links that cross communities:", cross.round(3).to_dict(), n_kind.to_dict())
# null: shuffle the labels among the typed links (keeps how many of each type, and which links are typed)
rng = np.random.default_rng(0)
labels, crosses = typed.kind.values, typed.cross.values
null = defaultdict(list)
for _ in range(5000):
    perm = rng.permutation(labels)
    for k in ("foe", "ally", "family"):
        null[k].append(crosses[perm == k].mean())
zs = {k: (cross[k] - np.mean(null[k])) / np.std(null[k]) for k in null}
p_foe = np.mean(np.array(null["foe"]) >= cross["foe"])
print("null mean cross share:", {k: round(float(np.mean(v)), 3) for k, v in null.items()},
      "z:", {k: round(float(z), 2) for k, z in zs.items()}, "p(foe >= observed):", p_foe)
overall_cross = E[E.in_gc].cross.mean()

# ---------------- display names (unique: there are several Ghost Riders and Human Torches) ----------------
groups = defaultdict(list)
for v in name:
    groups[short(name[v])].append(v)
disp = {}
for sh, vs in groups.items():                       # the most-linked one keeps the short name, the others the full title
    vs = sorted(vs, key=lambda v: -U.degree(v))
    disp[vs[0]] = sh
    for v in vs[1:]:
        disp[v] = name[v]

# ---------------- leaderboards ----------------
inc = {k: Counter(E[E.kind == k].t) for k in TYPED}
for k in inc:
    print(k, "most often named as one:", [(disp[v], n) for v, n in inc[k].most_common(5)])
hostile = []
for v in name:
    f, a = inc["foe"][v], inc["ally"][v]
    if f + a >= 8:
        hostile.append((f / (f + a), f, a, v))
hostile.sort(reverse=True)
print("most fought-with (share of foe among foe+ally mentions, 8+):", [(disp[v], f, a) for _, f, a, v in hostile[:6]])
print("friendliest:", [(disp[v], f, a) for _, f, a, v in hostile[-6:]])
kind_of = {(s, t): k for s, t, k in zip(E.s, E.t, E.kind)}
fren = sorted({tuple(sorted((s, t))) for (s, t), k in kind_of.items() if k == "foe" and kind_of.get((t, s)) == "ally"})
print("frenemy pairs:", len(fren), [(disp[a], disp[b]) for a, b in fren])

# ---------------- a layout grouped by community ----------------
# each community is laid out on its own and placed around a circle, so a link between two communities is a long
# line across the middle and a link inside one is a short line inside its cluster
xy = {}
R = 0.36
for i, c in enumerate(comms):
    ang = 2 * np.pi * i / len(comms) - np.pi / 2
    cx, cy = 0.5 + R * np.cos(ang), 0.5 + R * np.sin(ang)
    sub = GC.subgraph(c)
    p = nx.spring_layout(sub, seed=1, k=1.6 / np.sqrt(len(c)), iterations=200)
    P = np.array(list(p.values()))
    P = (P - P.mean(axis=0)) / (np.abs(P - P.mean(axis=0)).max() + 1e-9)
    rad = 0.06 + 0.012 * np.sqrt(len(c))
    for v, q in zip(p, P):
        xy[v] = np.array([cx + rad * q[0], cy + rad * q[1] * 1.0])

# ---------------- write ----------------
order = sorted(name, key=lambda v: disp[v].lower())
idx = {v: i for i, v in enumerate(order)}
out = {
    "chars": [{"n": disp[v], "u": url[v], "c": comm.get(v, -1), "k": deg.get(v, 0),
               "xy": [round(float(xy[v][0]), 4), round(float(xy[v][1]), 4)] if v in xy else None} for v in order],
    "comms": [{"name": comm_names[i], "size": len(c)} for i, c in enumerate(comms)],
    "edges": [[idx[r.s], idx[r.t], r.kind, r.sent, r.spans, r.words] for r in E.itertuples()],
    "stats": {"edges": len(E), "matched": int((E.kind != "unmatched").sum()),
              "kinds": {k: int(v) for k, v in E.kind.value_counts().items()},
              "cross": {k: round(float(v), 3) for k, v in cross.items()},
              "crossAll": round(float(overall_cross), 3),
              "null": {k: round(float(np.mean(v)), 3) for k, v in null.items()},
              "nullSd": {k: round(float(np.std(v)), 3) for k, v in null.items()},
              "z": {k: round(float(z), 2) for k, z in zs.items()}, "pFoe": round(float(p_foe), 3),
              "nTyped": {k: int(v) for k, v in n_kind.items()}},
    "validation": val,
    "top": {k: [[disp[v], n] for v, n in inc[k].most_common(8)] for k in inc},
    "hostile": [[disp[v], f, a] for _, f, a, v in hostile],
    "frenemies": [[idx[a], idx[b]] for a, b in fren],
}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB)")
