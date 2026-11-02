"""
Week-6 post data: separated at birth?
Which Marvel pages read alike, and is it the names, the pronouns or the story? TF-IDF + cosine on
the 303 pages in three passes (names kept / names erased / names and pronouns erased); for every page
its five textual twins, their network distance and the words behind each match; plus the
"long-lost twins" we read by hand.  Reads ../data/week1_*.tsv and ../data/marvel_pages.zip,
writes ../assets/week6.json.

    cd analysis && python3 week6_post.py        (~30 s)
"""
import csv
import json
import re
import urllib.parse
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "assets" / "week6.json"
TOP_TWINS, TOP_WORDS = 5, 5
PRONOUNS = {"she", "her", "hers", "herself", "he", "him", "his", "himself"}

nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])
with zipfile.ZipFile(DATA / "marvel_pages.zip") as z:
    pages = {urllib.parse.unquote(n.split("/")[-1][:-4]): z.read(n).decode("utf-8")
             for n in z.namelist() if n.endswith(".txt") and "README" not in n}
ids = list(nodes.node_id)
assert set(ids) == set(pages)
N = len(ids)


def short(n):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)", " (Marvel Comics character)"):
        n = n.replace(suf, "")
    return n


# ---- names: a word capitalised in more than half of its uses (the course's week-6 filter) ----
seen, cap = Counter(), Counter()
for t in pages.values():
    for w in re.findall(r"[A-Za-z]+", t):
        seen[w.lower()] += 1
        cap[w.lower()] += w[0].isupper()
proper = {w for w in seen if cap[w] > seen[w] / 2}

# ---- tokens: lowercase letters, 2+ characters ----
toks = {i: [w for w in re.findall(r"[a-z]+", pages[i].lower()) if len(w) > 1] for i in ids}
pron_counts = {i: Counter(w for w in toks[i] if w in PRONOUNS) for i in ids}
female = {i: (c["she"] + c["her"]) > (c["he"] + c["his"] + c["him"]) for i, c in pron_counts.items()}


def tfidf(drop):
    """the course's definitions: tf = count / |d|, idf = ln(N / df); rows scaled to unit length"""
    docs = {i: [w for w in toks[i] if w not in drop] for i in ids}
    df = Counter(w for d in docs.values() for w in set(d))
    vocab = sorted(df)
    vi = {w: k for k, w in enumerate(vocab)}
    X = np.zeros((N, len(vocab)))
    for r, i in enumerate(ids):
        c, L = Counter(docs[i]), len(docs[i])
        for w, n in c.items():
            X[r, vi[w]] = n / L * np.log(N / df[w])
    return X / np.linalg.norm(X, axis=1, keepdims=True), np.array(vocab)


PASSES = [("kept", set()), ("names", proper), ("story", proper | PRONOUNS)]

# ---- network distance on the undirected week-1 graph (all 303 nodes) ----
G = nx.Graph()
G.add_nodes_from(ids)
G.add_edges_from(edges.itertuples(index=False))
G.remove_edges_from(nx.selfloop_edges(G))
D = dict(nx.all_pairs_shortest_path_length(G))
hops = lambda a, b: D[a].get(b)                                   # None = not connected

iu = np.triu_indices(N, 1)
rand_hops = [hops(ids[a], ids[b]) for a, b in zip(*iu)]
fem_arr = np.array([female[i] for i in ids])

twins, summary, models = {}, {}, {}
for key, drop in PASSES:
    X, vocab = tfidf(drop)
    models[key] = (X, vocab)
    kind = np.array(["n" if w in proper else "p" if w in PRONOUNS else "s" for w in vocab])
    S = X @ X.T
    np.fill_diagonal(S, -1)
    rows, share = [], {"n": [], "p": [], "s": []}
    first = []
    for r, i in enumerate(ids):
        order = np.argsort(-S[r])[:TOP_TWINS]
        lst = []
        for j in order:
            contrib = X[r] * X[j]
            tot = contrib.sum()
            top = np.argsort(-contrib)[:TOP_WORDS]
            words = [[vocab[k], round(float(contrib[k] / tot), 2), kind[k]] for k in top if contrib[k] > 0]
            lst.append([int(j), round(float(S[r, j]), 2), hops(i, ids[j]), words])
            if j == order[0]:
                for t in "nps":
                    share[t].append(float(contrib[kind == t].sum() / tot))
        first.append(order[0])
        rows.append(lst)
    first = np.array(first)
    h = [hops(ids[r], ids[first[r]]) for r in range(N)]
    summary[key] = {
        "share": {t: round(float(np.mean(v)), 3) for t, v in share.items()},
        "linked": round(float(np.mean([x == 1 for x in h])), 3),
        "far": round(float(np.mean([x is None or x >= 3 for x in h])), 3),
        "femTwin": round(float(fem_arr[first][fem_arr].mean()), 4),
    }
    twins[key] = rows

summary["random"] = {
    "linked": round(float(np.mean([x == 1 for x in rand_hops])), 3),
    "far": round(float(np.mean([x is None or x >= 3 for x in rand_hops])), 3),
    "femTwin": round(float(fem_arr.sum() - 1) / (N - 1), 3),
}

# ---- the long-lost twins: names and pronouns erased, 3+ hops apart or not connected; read by hand ----
X, vocab = models["story"]
S = X @ X.T
far_pairs = sorted(((S[a, b], a, b) for a, b in zip(*iu)
                    if (lambda x: x is None or x >= 3)(hops(ids[a], ids[b]))), reverse=True)

HALL = [  # (page a, page b, phrase to quote from a, from b, our verdict after reading both pages)
    ("Garrison_Kane", "Yo-Yo_Rodriguez", r"cybernetic arms", r"prosthetic arms", "real",
     "Both lost their arms and got artificial ones: Weapon X grafts cybernetic arms onto Kane, and Yo-Yo's are cut off by "
     "Hydra's Gorgon and replaced. In the link network there is no path between them at all."),
    ("Anole_(character)", "Living_Lightning", r"\bgay\b", r"\bgay\b", "real",
     "Two of Marvel's gay characters, and both pages tell the story of them coming out. Three hops apart and never linked."),
    ("Blue_Eagle_(character)", "Red_Raven_(Marvel_Comics)", r"artificial gravity", r"artificial wings", "real",
     "Two flyers on artificial wings: Blue Eagle falls when Lamprey drains his wings' artificial gravity, and Red Raven's were "
     "a gift from the Bird People. Four hops apart."),
    ("Morbius", "Union_Jack_(Marvel_Comics)", r"Living Vampire", r"\bvampire\b", "real",
     "Morbius is the Living Vampire. Union Jack's page is about World War I and Baron Blood, a vampire who turns out to "
     "be a Falsworth himself. A real shared theme from two different eras."),
    ("Miracleman_(character)", "Shang-Chi", r"\brights\b", r"\brights\b", "meta",
     "Not the stories but the paperwork: both pages tell a rights saga (who owned Miracleman; Marvel wanted Kung Fu, "
     "couldn't get it, and made Shang-Chi instead)."),
    ("Bird-Brain_(Marvel_Comics)", "Brain_Drain_(character)", r"Bird-Brain", r"Brain Drain", "fake",
     "98% of the match is the word brain. Both names contain it, and brain is lowercase often enough elsewhere that our "
     "name filter keeps it. A pun, not a twin."),
    ("Cable_(character)", "Ogre_(Marvel_Comics)", r"techno-organic", r"by Techno\b", "fake",
     "Cable has a techno-organic virus, and Ogre gets knocked out by a villain called Techno. The tokenizer split "
     "techno-organic, and one word glued two unrelated pages together."),
]


def quote(page, pattern, k=200):
    text = re.sub(r"\s+", " ", pages[page])
    for s in re.split(r"(?<=[.!?])\s+", text):
        m = re.search(pattern, s)
        if m and len(s) > 40:
            a = max(0, m.start() - k // 2)
            if a:
                a = s.find(" ", a) + 1                            # start on a word boundary
            return ("…" if a else "") + s[a:a + k] + ("…" if a + k < len(s) else "")
    raise ValueError(f"no quote for {pattern!r} on {page}")


rank = {(ids[a], ids[b]): n + 1 for n, (_, a, b) in enumerate(far_pairs)}
hall = []
for a, b, pa, pb, verdict, note in HALL:
    ia, ib = ids.index(a), ids.index(b)
    r = rank.get((a, b)) or rank.get((b, a))
    hall.append({"a": ia, "b": ib, "cos": round(float(S[ia, ib]), 3), "hops": hops(a, b), "rank": r,
                 "words": [w for w, _, _ in twins["story"][ia][[t[0] for t in twins["story"][ia]].index(ib)][3]]
                 if ib in [t[0] for t in twins["story"][ia]] else
                 [vocab[k] for k in np.argsort(-(X[ia] * X[ib]))[:TOP_WORDS]],
                 "qa": quote(a, pa), "qb": quote(b, pb), "verdict": verdict, "note": note})

chars = [{"n": short(nodes.name[k]), "u": nodes.url[k], "f": bool(female[i])} for k, i in enumerate(ids)]
stats = {"pages": N, "female": int(fem_arr.sum()), "names": len(proper),
         "nameShareKept": summary["kept"]["share"]["n"], "farPairs": len(far_pairs)}
OUT.write_text(json.dumps({"chars": chars, "twins": twins, "summary": summary, "hall": hall, "stats": stats},
                          ensure_ascii=False, separators=(",", ":")))

print(f"{N} pages, {fem_arr.sum()} mostly use she/her; {len(proper):,} name words")
for key, _ in PASSES:
    s = summary[key]
    print(f"{key:>6}: twin match = names {s['share']['n']:.0%} / pronouns {s['share']['p']:.0%} / story {s['share']['s']:.0%};"
          f" twin linked {s['linked']:.0%}, 3+ hops {s['far']:.0%}; women's twin a woman {s['femTwin']:.0%}")
print(f"random: linked {summary['random']['linked']:.0%}, 3+ hops {summary['random']['far']:.0%}, woman {summary['random']['femTwin']:.0%}")
print("hall ranks among far pairs:", [(short(nodes.name[h['a']]), h["rank"], h["hops"]) for h in hall])
i = ids.index("Storm_(Marvel_Comics)")
for key, _ in PASSES:
    j, c, hp, ws = twins[key][i][0]
    print(f"Storm, {key}: {chars[j]['n']} {c} hops={hp} {ws[:3]}")
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
