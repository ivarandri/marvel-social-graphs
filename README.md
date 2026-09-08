# Marvel Social Graphs

Group site for **DTU 02805 – Social Graphs and Interactions**. Each week we add one post
that pulls a story out of the Marvel Wikipedia network (the 303 characters in
*Category: Marvel Comics superheroes* and the links between their pages).

Live site: https://ivarandri.github.io/marvel-social-graphs/

## Layout

```
index.html          landing page + post index
posts/week1.html    the weekly write-ups
assets/             style.css + generated figures (fig-*.png) + week1_stats.json
data/               the frozen course snapshot (week1_nodes.tsv, week1_edges.tsv)
analysis/week1.py   regenerates every figure and stat in the week-1 post
```

## Reproduce the figures

```bash
cd analysis
python3 -m pip install numpy pandas networkx matplotlib   # if needed
python3 week1.py                                          # writes ../assets/fig-*.png
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

## Editing group identity

Group name and members are marked with `EDIT THIS BLOCK` comments in `index.html`
and appear as "Group N" in `posts/week1.html`.
