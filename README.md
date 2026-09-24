# Marvel Social Graphs

Group site for **DTU 02805 – Social Graphs and Interactions**. Each week we add one post
that pulls a story out of the Marvel Wikipedia network (the 303 characters in
*Category: Marvel Comics superheroes* and the links between their pages).

Live site: https://ivarandri.github.io/marvel-social-graphs/

## Layout

```
index.html                landing page + post index
posts/week1.html           week 1: degree distributions, network map, the island + isolates
posts/week2.html           week 2: friendship paradox explorer, null-model shuffle test, three fake Marvels
posts/week3.html           week 3: Wikipedia game to Spider-Man, break-the-universe attack chart, brokers, X-Men cliques
posts/week4.html           week 4 (philosophers): Louvain sorting hat, backbone threads, Aristotle's link communities
assets/style.css           shared styles
assets/app.js              shared page interactions + the interactive network (week 1) and
                            friendship-paradox explorer + summary widgets (week 2) and
                            path finder, attack chart, broker bars, clique diagram (week 3) and
                            sorting hat, torn board, backbone canvas, Aristotle's rooms (week 4)
assets/marvel.json         graph data for the week-1 network visualization
assets/week1_stats.json    numbers quoted in the week-1 post
assets/week2.json          per-character + summary numbers quoted in the week-2 post
assets/week3.json          adjacency lists, attack curves and summary numbers for the week-3 post
assets/week4.json          20 Louvain votes per philosopher, backbone links + layout, threads, Aristotle's rooms
data/                      the frozen course snapshots: Marvel (week1_*.tsv, weeks 1–3) and philosophers (week4_philosophers_*.tsv)
analysis/week1.py          regenerates every figure/stat in the week-1 post
analysis/week2_post.py     regenerates assets/week2.json for the week-2 post
analysis/week3_post.py     regenerates assets/week3.json for the week-3 post (~2 min)
analysis/week4_post.py     regenerates assets/week4.json for the week-4 post (~2 min)
```

## Reproduce

```bash
cd analysis
python3 -m pip install numpy pandas networkx matplotlib   # if needed
python3 week1.py           # writes ../assets/fig-*.png, marvel.json, week1_stats.json
python3 week2_post.py      # writes ../assets/week2.json (matplotlib not required)
python3 week3_post.py      # writes ../assets/week3.json (reads ../../week3_debut_years.csv if present)
python3 week4_post.py      # writes ../assets/week4.json (needs scikit-learn for NMI)
```

## Publishing (GitHub Pages)

1. Create an empty repo `marvel-social-graphs` on github.com/ivarandri (no README).
2. From this folder:
   ```bash
   git add -A && git commit -m "Week 1"
   git branch -M main
   git remote add origin https://github.com/ivarandri/marvel-social-graphs.git
   git push -u origin main
   ```
3. Repo → **Settings → Pages** → *Source: Deploy from a branch* → `main` / `/ (root)` → Save.
4. Wait ~1 min, then visit the live URL above.

`.nojekyll` is present so Pages serves the files as-is (no Jekyll build).

## Group

Ívar, Gunnlaugur, Víðir — named on the home page (`index.html`) and in the byline of each
post (`posts/week1.html` … `posts/week4.html`).
