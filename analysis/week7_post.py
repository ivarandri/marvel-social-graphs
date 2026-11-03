"""
Week-7 post data: whose page is it anyway?
On every one of the 303 hero pages, count how often the page's own subject is named and how often every OTHER
character is named, and ask who lives in someone else's shadow.  Character mentions come from spaCy's
en_core_web_sm (the raw tagger output is kept in ../data/week7_ner_mentions.csv.gz, one row per span, exactly as the
model produced it) plus the alias resolution from exercise 7.8; the subject is counted by its own names in the raw text.
Reads ../data/week1_*.tsv, ../data/marvel_pages.zip and the mentions file, writes ../assets/week7.json.

    cd analysis && python3 week7_post.py        (~15 s; regenerating the mentions with spaCy takes ~4 min, see bottom)
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

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE.parent / "assets" / "week7.json"
SHADOW = 0.5                 # "in someone's shadow": the most-named other character gets >= half as many mentions
MIN_NAMED = 5                # pages naming their own subject fewer times than this are too thin to judge

nodes = pd.read_csv(DATA / "week1_nodes.tsv", sep="\t", comment="#", quoting=csv.QUOTE_NONE)
edges = pd.read_csv(DATA / "week1_edges.tsv", sep="\t", comment="#", names=["source", "target"])
with zipfile.ZipFile(DATA / "marvel_pages.zip") as z:
    pages = {urllib.parse.unquote(n.split("/")[-1][:-4]): z.read(n).decode("utf-8")
             for n in sorted(z.namelist()) if n.endswith(".txt") and "README" not in n}
ids = list(nodes.node_id)
assert set(ids) == set(pages)
links = set(map(tuple, edges.values))
mentions = pd.read_csv(DATA / "week7_ner_mentions.csv.gz", keep_default_na=False)


def short(n):
    for suf in (" (character)", " (characters)", " (comics)", " (Marvel Comics)", " (Marvel Comics character)"):
        n = n.replace(suf, "")
    return n


# ---------------- paragraphs and sentences (exercise 7.8: paragraph = non-empty line) ----------------
paras = {(pg, p): l.strip() for pg, text in pages.items() for p, l in enumerate(x for x in text.split("\n") if x.strip())}
SPLIT = r"(?<=[.!?])\s+(?=[\"“A-Z0-9])"
sent_start = {}
for k, para in paras.items():
    starts, pos = [], 0
    for piece in re.split(SPLIT, para):
        pos = para.index(piece, pos); starts.append(pos); pos += len(piece)
    sent_start[k] = np.array(starts)


def sentence_at(pg, p, char):
    st = sent_start[(pg, p)]
    i = int(np.searchsorted(st, char, side="right") - 1)
    return paras[(pg, p)][st[i]: st[i + 1] if i + 1 < len(st) else None].strip()


# ---------------- alias resolution: the same steps and table as exercise 7.8 ----------------
ALIAS = {
    "Spider-Man": ["Spider-Man", "Peter Parker", "Spidey"], "Wolverine": ["Wolverine", "Logan", "James Howlett"],
    "Jean Grey": ["Jean Grey", "Jean Gray", "Marvel Girl", "Jean Grey-Summers"], "Hulk": ["Hulk", "Bruce Banner", "Banner"],
    "She-Hulk": ["She-Hulk", "Jennifer Walters"], "Iron Man": ["Iron Man", "Tony Stark", "Anthony Stark"],
    "Captain America": ["Captain America", "Steve Rogers"], "Black Panther": ["Black Panther", "T'Challa"],
    "Storm": ["Storm", "Ororo Munroe", "Ororo"], "Emma Frost": ["Emma Frost", "White Queen"],
    "Scarlet Witch": ["Scarlet Witch", "Wanda Maximoff", "Wanda"], "Quicksilver": ["Quicksilver", "Pietro Maximoff", "Pietro"],
    "Betsy Braddock": ["Betsy Braddock", "Psylocke", "Betsy"], "Cyclops": ["Cyclops", "Scott Summers"],
    "Professor X": ["Professor X", "Charles Xavier", "Xavier", "Professor Xavier"], "Magneto": ["Magneto", "Erik Lehnsherr"],
    "Doctor Doom": ["Doctor Doom", "Victor von Doom", "Victor Von Doom"], "Thor": ["Thor", "Thor Odinson"],
    "Moon Knight": ["Moon Knight", "Marc Spector"], "Luke Cage": ["Luke Cage", "Power Man"],
    "Mary Jane Watson": ["Mary Jane", "Mary Jane Watson", "MJ"], "Venom": ["Venom"], "Shang-Chi": ["Shang-Chi"],
    "Deadpool": ["Deadpool", "Wade Wilson"], "Morbius": ["Morbius"], "Doctor Strange": ["Doctor Strange", "Stephen Strange"],
    "Daredevil": ["Daredevil", "Matt Murdock"], "Beta Ray Bill": ["Beta Ray Bill", "Ray Bill"],
}
ALIAS_EXCEPT = {("Storm", "Human_Torch")}
NOT_CHAR = {"Marvel", "Avengers", "Hydra", "America", "Universe", "Appendix", "X-Men", "Marvel Comics", "Comics"}
alias_of = {a: c for c, al in ALIAS.items() for a in al}


def normalise(t):
    t = re.sub(r"[’']s$", "", t.strip()).split(" / ")[0].strip()
    return None if re.search(r"\d|\bTPB\b|\bvol\b", t, re.I) else t


mentions["norm"] = mentions.text.map(normalise)
per = mentions[(mentions.label == "PERSON") & mentions.norm.notna()]
multi = per[per.norm.str.match(r"^(?:[A-Z][\w'’-]*)(?: [A-Z][\w'’-]*){1,2}$") & ~per.norm.str.contains(r" (?:I|II|III|IV|V)$")] \
    .groupby(["page", "norm"]).size()
multi = multi[multi >= 2]


def expand(page, t):
    if t is None or " " in t or t in alias_of or t in NOT_CHAR or page not in multi.index.get_level_values(0):
        return t
    c = multi[page][[f.split()[0] == t or f.split()[-1] == t for f in multi[page].index]]
    return c.idxmax() if len(c) else t


def resolve(pg, t, l):
    if t is None:
        return None
    if t in alias_of and (t, pg) not in ALIAS_EXCEPT:
        return alias_of[t]
    return t if l == "PERSON" else None


mentions["expanded"] = [expand(pg, t) if l == "PERSON" else t for pg, t, l in zip(mentions.page, mentions.norm, mentions.label)]
mentions["resolved"] = [resolve(pg, t, l) for pg, t, l in zip(mentions.page, mentions.expanded, mentions.label)]
mentions["sentence"] = [sentence_at(pg, p, s) for pg, p, s in zip(mentions.page, mentions.para, mentions.start)]
CREATION = r"\b(?:creat\w*|writer|written|artist|drawn|penciler|penciller|inker|editor|illustrat\w*|voiced|portrayed|played by|actor|actress|cast)\b"
cs = mentions[mentions.label == "PERSON"].assign(c=mentions.sentence.str.contains(CREATION, case=False)).groupby("resolved").c.agg(["mean", "size"])
REAL = set(cs[(cs["mean"] >= 0.5) & (cs["size"] >= 3)].index) - set(ALIAS)

# new for this post: a character name directly followed by an issue number / volume is a comic TITLE, not the character
# ("first appeared in Iron Man #43"), and is dropped
TITLE_NEXT = (r"\s*(?:#|vol\b|Vol\b|\(vol|Annual\b|Comics\b|comics?\b|stor(?:y|ies|yline)\b|series\b|title\b|book\b|run\b|strip\b"
              r"|:\s+[A-Z]|\(\d{4}\))")              # "Venom: Sinner Takes All", "Venom (2018)" are titles too
after = [paras[(pg, p)][e:e + 14] for pg, p, e in zip(mentions.page, mentions.para, mentions.end)]
mentions["title_use"] = [bool(re.match(TITLE_NEXT, a)) for a in after]
ARTEFACT = {"Glenn", "Brasfield"}     # citation authors on Illuminator's page ("Herdling, Glenn; Brasfield, E.") the creator rule missed
mentions["kind"] = np.select(
    [mentions.resolved.isna(), mentions.resolved.isin(NOT_CHAR), mentions.resolved.isin(REAL), mentions.resolved.isin(ARTEFACT),
     mentions.title_use], ["not a person span", "not a character", "real person", "citation", "comic title"], "character")

# ---------------- the subject's own names (counted in the raw text, so the tagger can't lose them) ----------------
SKIP = re.compile(r"character|comics|Marvel|film|series|Universe|Inhuman|Heroes for Hire|Morituri|Mangaverse|New Universe", re.I)
PREFIX = ("Captain", "Doctor", "Mister", "Miss", "Ms.", "Iron", "Black", "White", "Blue", "Red", "The", "Princess")
# read by hand: names of the SAME character the automatic rule missed (found while reading the lead of every flagged page)
EXTRA = {
    "Black_Jack_Tarr": ["Jack Tarr", "Tarr"], "Blue_Bullet": ["Johann Goldstein", "Johann", "John Goldstein", "John"],
    "Mania_(character)": ["Venom", "Maniac"], "Steel_Spider": ["Ollie Osnick", "Oliver Osnick", "Ollie", "Kid Ock"],
    "Jericho_Drumm": ["Brother Voodoo", "Doctor Voodoo"], "Oya_(comics)": ["Idie Okonkwo", "Idie", "Temper"],
    "Doctor_Druid": ["Anthony Droom", "Anthony Druid", "Droom", "Druid"], "Speed_(character)": ["Tommy Maximoff", "Tommy Shepherd", "Tommy", "Thomas Shepherd"],
    "Genis-Vell": ["Genis"], "Robbie_Baldwin": ["Speedball", "Penance"], "Blackwulf": ["Lucian"],
    "Black_Cat_(Marvel_Comics)": ["Felicia Hardy", "Felicia"], "Doom_2099": ["Victor Von Doom", "Doom"],
    "Kismet_(Marvel_Comics)": ["Ayesha", "Paragon", "Her"], "Silk_(character)": ["Cindy Moon", "Cindy"],
    "Kristoff_Vernard": ["Kristoff von Doom"], "Dogpool": [], "Anne_Weying": ["She-Venom"],
    "Mayday_Parker": ["Spider-Girl", "May Parker"], "Sean_and_Chris": ["Sean Daniels", "Chris Daniels"],
    "Agent_X_(Marvel_Comics)": ["Alex Hayden"], "Jeffrey_Mace": ["Patriot"], "Synapse_(character)": ["Emily Guerrero", "Emily"],
    "Jack_Monroe_(character)": ["Nomad"], "Nightmask": ["Keith Remsen", "Keith"],
    "War_Machine": ["James Rhodes", "James Rupert Rhodes", "Rhodes", "Rhodey", "Iron Patriot"],
}
# pages about a CODENAME held by several characters: every holder named in the lead counts as the subject
MANTLE = {
    "Turbo_(comics)": ["Mickey", "Michiko Musashi", "Mike Jeffries", "Mike"], "Thunderbolt_(Marvel_Comics)": ["William Carver", "Luis Barrett"],
    "Guardsman_(character)": ["Kevin O'Brien", "Michael O'Brien"], "Nomad_(Marvel_Comics)": ["Captain America", "Steve Rogers", "Edward Ferbel", "Jack Monroe"],
    "Red_Guardian": ["Shostakov", "Alexei Shostakov", "Aleksey Lebedev", "Tania Belinsky", "Josef Petkus", "Anton Ivanov"],
    "Magician_(Marvel_Comics)": ["Elliot Boggs", "Lee Guardineer"], "Radioactive_Man_(comics)": ["Chen Lu", "Igor Stancheck"],
    "Scarlet_Scarab": ["Abdul Faoul", "Mehemet Faoul"], "Moonglow_(comics)": ["Melissa Hanover", "Arcanna"],
    "Captain_Marvel_(Marvel_Comics)": ["Carol Danvers", "Mar-Vell", "Monica Rambeau", "Genis-Vell", "Phyla-Vell", "Noh-Varr"],
    "William_Burnside_(character)": ["Captain America"], "Dargo_Ktor": ["Thor"], "Scarlet_Spider": ["Ben Reilly", "Kaine"],
    "Ricochet_(comics)": ["Spider-Man", "Peter Parker", "Johnny Gallo"], "Bucky_(Marvel_Comics)": ["Bucky Barnes", "Jack Monroe", "Rikki Barnes", "Lemar Hoskins"],
    "Black_Knight_(Marvel_Comics)": ["Dane Whitman", "Nathan Garrett", "Percy"], "Quasar_(character)": ["Avril Kincaid", "Wendell Vaughn", "Phyla-Vell"],
    "The_Witness_(character)": ["Nelson Kohler"], "Dusk_(comics)": ["Spider-Man", "Peter Parker", "Cassie St. Commons", "Cassie"],
    "Isaiah_Bradley": ["Captain America"],        # "one of the superheroes to hold the title of Captain America"
    "Ms._Marvel": ["Carol Danvers", "Sharon Ventura", "Karla Sofen", "Kamala Khan"],
    "Shuri_(character)": ["Black Panther"],       # "Shuri is tested and found suitable for the role of Black Panther"
}


def variants(page, extra=True, mantle=True):
    text = pages[page]
    t = re.sub(r"\s*\(.*\)$", "", page.replace("_", " "))
    v = {t}
    m = re.search(r"\(([^)]*)\)$", page.replace("_", " "))
    if m and not SKIP.search(m.group(1)) and re.fullmatch(r"[A-Z][\w'.-]*(?: [A-Z][\w'.-]*){0,3}", m.group(1)):
        v.add(m.group(1))
    lead = re.sub(r"\s+", " ", text.split("\n")[0])[:1500]
    for g in re.findall(r"\(([A-Z][\w'’.-]+(?: [A-Z][\w'’.\"-]+){1,3})[;),]", lead):
        if not SKIP.search(g):
            v.add(g.replace('"', "").strip())
    for g in re.findall(r"(?:real name|alias of|alter ego of|secret identity of|identity of|known as)\s+([A-Z][\w'’.-]+(?: [A-Z][\w'’.-]+){1,2})", lead):
        if not SKIP.search(g):
            v.add(g)
    for full in list(v):
        parts = full.split()
        if len(parts) >= 2 and not re.search(r"\d", full) and not full.startswith(PREFIX):
            v.update((parts[0], parts[-1]))
    if extra:
        v |= set(EXTRA.get(page, []))
    if mantle:
        v |= set(MANTLE.get(page, []))
    return {x for x in v if len(x) > 2}


def is_subject(node, vs):
    return node in vs or any(x in node.split() or (" " in x and x in node) for x in vs) or any(node in x for x in vs if " " in x)


def count_subject(page, vs, titles=True):
    tail = "(?!" + TITLE_NEXT + ")" if titles else ""
    pat = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(x) for x in sorted(vs, key=len, reverse=True)) + r")(?![\w-])" + tail)
    return len(pat.findall(pages[page]))


# the audit: the naive measure first, then each fix in turn; a page "cleared" by a fix drops below the shadow line there
STEPS = [("naive", {}), ("same hero, another name", dict(extra=True)), ("shared codename", dict(extra=True, mantle=True)),
         ("comic title, not a character", dict(extra=True, mantle=True, titles=True)),
         ("citation author", dict(extra=True, mantle=True, titles=True, citations=True))]
by_page = {pg: g for pg, g in mentions[mentions.kind.isin(["character", "comic title", "citation"])].groupby("page")}


def shadow(pg, extra=False, mantle=False, titles=False, citations=False):
    vs = variants(pg, extra, mantle)
    S = count_subject(pg, vs, titles)
    on = by_page.get(pg, mentions.iloc[:0])
    keep = on.kind.eq("character") | (~on.kind.eq("comic title") if not titles else False) & on.kind.ne("citation") \
        | (on.kind.eq("citation") if not citations else False)
    on = on[keep]
    oth = Counter(r for r in on.resolved if not is_subject(r, vs))
    return S, oth, on, vs


audit = {}
for pg in ids:
    path, named, naive_caster = [], 0, None
    for name, kw in STEPS:
        S, oth, _, _ = shadow(pg, **kw)
        path.append(oth.most_common(1)[0][1] / max(S, 1) if oth else 0.0); named = S
        if naive_caster is None:
            naive_caster = oth.most_common(1)[0][0] if oth else ""
    if max(path) >= SHADOW:
        if named < MIN_NAMED:
            verdict = "too thin to judge"
        elif path[-1] >= SHADOW:
            verdict = "real shadow"
        else:                                   # the fix that pushed it below the line the last time
            last = max(i for i, x in enumerate(path) if x >= SHADOW)
            verdict = STEPS[last + 1][0]
        audit[pg] = (verdict, [round(x, 2) for x in path], naive_caster)


# ---------------- per page: who gets named ----------------
link_target = {}                     # character node -> its own page among the 303 (variant pages like "Ultimate" don't count)
GENERIC = re.compile(r"^(?:character|characters|comics|Marvel Comics|Marvel Comics character)$")
for pg in ids:
    m = re.match(r"^(.*?)(?:_\((.*)\))?$", pg)
    if m.group(2) is None or GENERIC.match(m.group(2).replace("_", " ")):
        link_target.setdefault(m.group(1).replace("_", " "), pg)
for node, al in ALIAS.items():
    for a in al:
        if a in link_target:
            link_target.setdefault(node, link_target[a])


def gender(text):
    c = Counter(re.findall(r"[a-z]+", text.lower()))
    return "f" if c["she"] + c["her"] > c["he"] + c["his"] + c["him"] else "m"


# what we found when we read each page that is still in a shadow after every fix
REAL_NOTE = {
    "Bob,_Agent_of_Hydra": "Deadpool's sidekick. The lead says it outright: \"a sidekick of Deadpool\".",
    "War_Machine": "Created \"as a supporting character for Iron Man\": Rhodey works for Tony Stark, takes his place, then gets his own armor from him.",
    "Guardsman_(character)": "Kevin O'Brien is a Stark Industries engineer and Tony Stark's close friend, so his story is told through Stark's.",
    "Sean_and_Chris": "The page opens with their father, \"the twin sons of Gabriel and Thea\", and his betrayal sets their story in motion.",
    "Quicksilver_(Marvel_Comics)": "Introduced \"alongside his twin sister, Scarlet Witch\". The twins are written as a pair almost everywhere.",
    "Dogpool": "\"A dog counterpart of Deadpool\". The whole page is a Deadpool joke with its own article.",
    "Anne_Weying": "Eddie Brock's ex-wife. Her story runs through Venom, who later bonds with her and makes her She-Venom.",
    "Black_Jack_Tarr": "Nayland Smith's aide in Master of Kung Fu, so his adventures are Shang-Chi's adventures.",
    "Agent_X_(Marvel_Comics)": "Spun out of the Deadpool series (\"born out of experiments with … Deadpool\"), and still orbiting him.",
    "Bucky_(Marvel_Comics)": "\"Usually as a sidekick to Captain America\". And Cap doesn't even have a page among our 303.",
    "Blue_Bullet": "The shadow is family: his older brother Jacob, captured by the Nazis to blackmail him.",
}

rows = []
for pg in ids:
    S, oth, on, vs = shadow(pg, **STEPS[-1][1])
    top = oth.most_common(6)
    caster, cn = top[0] if top else ("", 0)
    receipts = []
    if caster:
        seen = set()
        for s in on[on.resolved == caster].sentence:
            if s not in seen and len(receipts) < 3:
                seen.add(s); receipts.append(s[:320] + ("…" if len(s) > 320 else ""))
    tp = link_target.get(caster)
    rows.append(dict(page=pg, n=short(pg.replace("_", " ")), u=nodes.url[ids.index(pg)], g=gender(pages[pg]),
                     subject=S, others=int(sum(oth.values())), top=[[a, int(b)] for a, b in top],
                     caster=caster, cn=int(cn), ratio=round(cn / max(S, 1), 3),
                     linked=bool(tp and ((pg, tp) in links)), caster_page=tp, receipts=receipts,
                     audit=audit.get(pg, [None])[0], path=audit.get(pg, [None, None])[1],
                     naive=audit.get(pg, [None, None, None])[2], note=REAL_NOTE.get(pg, "")))
df = pd.DataFrame(rows)
shadowed = df[(df.ratio >= SHADOW) & (df.subject >= MIN_NAMED)].sort_values("ratio", ascending=False)

# hand-labelled gender of every character who casts a shadow (most have no page of their own in the 303)
CASTER_G = {}
for c in shadowed.caster.unique():
    p = link_target.get(c)
    CASTER_G[c] = gender(pages[p]) if p else None
CASTER_G.update({"Captain America": "m", "Iron Man": "m", "Thor": "m", "Adam Warlock": "m", "Nayland Smith": "m",
                 "Jacob": "m", "Gabriel": "m", "Patriot": "m"})
print("casters without a gender:", [c for c, g in CASTER_G.items() if g is None])

stats = {
    "pages": len(df), "shadowed": int(len(shadowed)), "eclipsed": int(((df.ratio >= 1) & (df.subject >= MIN_NAMED)).sum()),
    "suspects": len(audit), "auditCounts": dict(Counter(v[0] for v in audit.values())),
    "titleDropped": int((mentions.kind == "comic title").sum()),
    "women": int((df.g == "f").sum()),
    "shadowedWomen": round(float((shadowed.g == "f").mean()), 3), "womenAll": round(float((df.g == "f").mean()), 3),
    "ratioMedianW": round(float(df[df.g == "f"].ratio.median()), 3), "ratioMedianM": round(float(df[df.g == "m"].ratio.median()), 3),
    "castersMaleOnWomen": round(float(np.mean([CASTER_G[c] == "m" for c in shadowed[shadowed.g == "f"].caster])), 3) if (shadowed.g == "f").any() else None,
    "castersMaleOnMen": round(float(np.mean([CASTER_G[c] == "m" for c in shadowed[shadowed.g == "m"].caster])), 3),
    "linkedShadowed": round(float(shadowed.linked.mean()), 3),
}
thieves = Counter(shadowed.caster)
OUT.write_text(json.dumps({"pages": rows, "stats": stats, "casterGender": CASTER_G, "alias": ALIAS,
                           "thieves": thieves.most_common(12)}, ensure_ascii=False, separators=(",", ":")))

print("audit:", Counter(v[0] for v in audit.values()))
for pg, (c, path, nc) in sorted(audit.items(), key=lambda x: -x[1][1][0]):
    print(f"   {pg:<34} {c:<30} {path} naive caster: {nc}")
print(f"{len(df)} pages; {len(shadowed)} with a shadow >= {SHADOW}, {stats['eclipsed']} eclipsed (>= 1)")
print("thieves:", thieves.most_common(10))
for r in shadowed.itertuples():
    print(f"  {r.ratio:5.2f} {r.n:<32} ({r.g}) <- {r.caster} {r.cn} vs {r.subject}  linked={r.linked} {r.audit}")
print(json.dumps(stats, indent=1))
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
