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
assets/style.css           shared styles
assets/app.js              shared page interactions + the interactive network (week 1) and
                            friendship-paradox explorer + summary widgets (week 2)
assets/marvel.json         graph data for the week-1 network visualization
assets/week1_stats.json    numbers quoted in the week-1 post
assets/week2.json          per-character + summary numbers quoted in the week-2 post
data/                      the frozen course snapshot (week1_nodes.tsv, week1_edges.tsv) — shared by both weeks
analysis/week1.py          regenerates every figure/stat in the week-1 post
analysis/week2_post.py     regenerates assets/week2.json for the week-2 post
```

## Reproduce

```bash
cd analysis
python3 -m pip install numpy pandas networkx matplotlib   # if needed
python3 week1.py           # writes ../assets/fig-*.png, marvel.json, week1_stats.json
python3 week2_post.py      # writes ../assets/week2.json (matplotlib not required)
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
post (`posts/week1.html`, `posts/week2.html`).
