"""Render the johnmark.dev code-graph post's SVGs from results.csv and results-runs-haiku.csv.

Usage: python3 charts/make_charts.py [out-dir]   (default: charts/)
Numbers printed to stdout are the ones the post quotes.
"""
import csv, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "charts")

BG, INK, MUTED, GRID, BOX, GREY = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1", "#f1f0ec", "#8a8984"
COL = {"ctl": "#eb6834", "cg": "#2a78d6", "cgf": "#174a8b"}  # told first = more of the new side, so a darker shade of its blue (WRITING.md has no third hue)
NAME = {"ctl": "No graph", "cg": "Graph installed", "cgf": "Graph + told first"}
REPOS = ["flask", "hono", "excalidraw", "django", "sentry", "vscode"]
# git ls-files *.py *.ts *.tsx *.js *.jsx *.mjs *.rs *.go | xargs cat | wc -l, at each repo's checked-out commit
LINES = {"flask": 18_345, "hono": 91_044, "excalidraw": 216_411, "django": 556_666, "sentry": 3_300_620, "vscode": 4_456_872}
# CodeGraph's own "N nodes, M edges in X" summary line, logs/index-<repo>.log
CG_TIME = {"flask": "0.3", "hono": "0.6", "excalidraw": "0.7", "django": "2.5", "sentry": "12.5", "vscode": "17.4"}
INDEX = {"flask": (1, "5 MB"), "hono": (2, "26 MB"), "excalidraw": (5, "54 MB"), "django": (9, "165 MB"), "sentry": (60, "951 MB"), "vscode": (107, "1.6 GB")}  # logs/index-summary.txt


def load(name):
    rows = list(csv.DictReader(open(ROOT / name)))
    assert not any(r["error"] == "True" for r in rows), name
    cells = defaultdict(list)
    for r in rows:
        for k in ("cost", "secs", "calls", "graph_calls", "recall"):
            r[k] = float(r[k])
        cells[(r["repo"], r["q"], r["arm"])].append(r)
    return rows, cells


def mean(cells, key, field):
    return st.mean(r[field] for r in cells[key])


def ratio(cells, tasks, arm):
    """Cost of an arm relative to no graph, over the same tasks (sum of per-task means)."""
    return sum(mean(cells, t + (arm,), "cost") for t in tasks) / sum(mean(cells, t + ("ctl",), "cost") for t in tasks)


def crossfit(cells, tasks, arm, limit=20, skip=()):
    """Group tasks by one no-graph run and compare against the other, both ways, pooled.

    Using the same no-graph runs to pick the long tasks and to set their baseline flatters the graph:
    one long, noisy run both qualifies a task and inflates its cost. Returns
    (long ratio, short ratio, long comparisons, short comparisons, distinct long tasks).
    """
    acc = {True: [0.0, 0.0, 0], False: [0.0, 0.0, 0]}
    long_tasks = set()
    for t in tasks:
        if t in skip:
            continue
        ctl = {r["rep"]: r for r in cells[t + ("ctl",)]}
        if len(ctl) < 2:
            continue
        for a, b in (("0", "1"), ("1", "0")):
            is_long = ctl[a]["calls"] > limit
            acc[is_long][0] += mean(cells, t + (arm,), "cost")
            acc[is_long][1] += ctl[b]["cost"]
            acc[is_long][2] += 1
            if is_long:
                long_tasks.add(t)
    return acc[True][0] / acc[True][1], acc[False][0] / acc[False][1], acc[True][2], acc[False][2], len(long_tasks)


def task_mean(cells, tasks, arm, field):
    """Mean over tasks of each task's mean, so arms with missing runs are compared on equal footing."""
    return st.mean(mean(cells, t + (arm,), field) for t in tasks)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=16, fill=INK, anchor="start", weight=400):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>'


def svg(name, w, h, title, subtitle, desc, body):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f"font-family=\"-apple-system, 'Helvetica Neue', Arial, sans-serif\" role=\"img\" aria-labelledby=\"t d\">\n"
            f'<title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>\n<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + text(40, 52, title, 26, weight=600) + "\n" + text(40, 82, subtitle, 16, MUTED) + "\n")
    (OUT / name).write_text(head + "\n".join(body) + "\n</svg>\n")


def hbar(x0, y, w, h, fill):
    if w < 5:
        return f'<rect x="{x0}" y="{y}" width="{max(w, 2):.1f}" height="{h}" fill="{fill}"/>'
    return f'<path d="M{x0} {y} H{x0 + w - 4:.1f} a4 4 0 0 1 4 4 V{y + h - 4} a4 4 0 0 1 -4 4 H{x0} Z" fill="{fill}"/>'


def legend(x, y, arms):
    out = []
    for a in arms:
        out.append(f'<rect x="{x}" y="{y - 12}" width="14" height="14" rx="3" fill="{COL[a]}"/>')
        out.append(text(x + 22, y, NAME[a], 15))
        x += 22 + 7.2 * len(NAME[a]) + 36
    return out


def xgrid(x0, scale, ticks, top, bottom, fmt):
    out = []
    for v in ticks:
        x = x0 + v * scale
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}"/>')
        out.append(text(x, bottom + 24, fmt(v), 14, MUTED, "middle"))
    return out


opus_rows, opus = load("results.csv")
haiku_rows, haiku = load("results-runs-haiku.csv")
tasks = sorted({(r["repo"], r["q"]) for r in opus_rows})
calls = {t: mean(opus, t + ("ctl",), "calls") for t in tasks}
big = [t for t in tasks if calls[t] > 20]
small = [t for t in tasks if calls[t] <= 20]

# ---------------------------------------------------------------- numbers
print(f"Opus runs {len(opus_rows)}, Haiku runs {len(haiku_rows)}")
for label, ts in (("all", tasks), ("over 20", big), ("20 or under", small)):
    print(f"Opus {label} ({len(ts)} tasks): default {ratio(opus, ts, 'cg'):.3f}  forced {ratio(opus, ts, 'cgf'):.3f}")
    for a in ("ctl", "cg", "cgf"):
        print(f"   {a}: calls {st.mean(mean(opus, t + (a,), 'calls') for t in ts):.1f}  secs {st.mean(mean(opus, t + (a,), 'secs') for t in ts):.0f}"
              f"  recall {st.mean(mean(opus, t + (a,), 'recall') for t in ts):.2f}")
htasks = [t for t in tasks if all(haiku[t + (a,)] for a in ("ctl", "cg", "cgf"))]
hcalls = {t: mean(haiku, t + ("ctl",), "calls") for t in htasks}
hbig = [t for t in htasks if hcalls[t] > 20]
for label, ts in (("all", htasks), ("over 20", hbig), ("20 or under", [t for t in htasks if t not in hbig])):
    print(f"Haiku {label} ({len(ts)} tasks): default {ratio(haiku, ts, 'cg'):.3f}  forced {ratio(haiku, ts, 'cgf'):.3f}")
cf = {(m, a): crossfit(c, ts, a) for m, c, ts in (("Opus", opus, tasks), ("Haiku", haiku, htasks)) for a in ("cg", "cgf")}
for k, v in cf.items():
    print(f"cross-fit {k}: long {v[0]:.3f} short {v[1]:.3f}  comparisons {v[2]} long / {v[3]} short, {v[4]} distinct long tasks")
# Haiku's short-task penalty comes almost entirely from one task; show it without that task too
OUTLIER = ("vscode", "lookup")
cf_skip = {a: crossfit(haiku, htasks, a, skip={OUTLIER}) for a in ("cg", "cgf")}
print("Haiku short tasks without the VS Code lookup:", {a: round(v[1], 3) for a, v in cf_skip.items()}, "comparisons", cf_skip["cg"][3])
assert round(cf[("Opus", "cg")][0], 3) == 0.904 and round(cf[("Haiku", "cg")][0], 3) == 0.734  # checked by hand, 2026-09-30
graph_calls = {(m, a): st.mean(r["graph_calls"] for r in rows if r["arm"] == a) for m, rows in (("Opus", opus_rows), ("Haiku", haiku_rows)) for a in ("cg", "cgf")}
per_run = {(m, a): task_mean(c, ts, a, "calls") for m, c, ts in (("Opus", opus, tasks), ("Haiku", haiku, htasks)) for a in ("ctl", "cg", "cgf")}
recall = {(m, a): task_mean(c, ts, a, "recall") for m, c, ts in (("Opus", opus, tasks), ("Haiku", haiku, htasks)) for a in ("ctl", "cg", "cgf")}
secs = {m: sum(mean(c, t + ("cg",), "secs") for t in ts) / sum(mean(c, t + ("ctl",), "secs") for t in ts) for m, c, ts in (("Opus", opus, tasks), ("Haiku", haiku, htasks))}
print("graph calls per run", {k: round(v, 2) for k, v in graph_calls.items()})
print("tool calls per task", {k: round(v, 1) for k, v in per_run.items()})
print("key files per task", {k: round(v, 3) for k, v in recall.items()})
print("time, default install vs no graph", {k: round(v, 3) for k, v in secs.items()})
in_tok = {a: sum(float(r["in_tok"]) for r in opus_rows if r["arm"] == a) for a in ("ctl", "cg", "cgf")}
print(f"Opus input tokens vs no graph: default {in_tok['cg'] / in_tok['ctl']:.3f}  forced {in_tok['cgf'] / in_tok['ctl']:.3f}")
overall = {(m, a): ratio(c, ts, a) for m, c, ts in (("Opus", opus, tasks), ("Haiku", haiku, htasks)) for a in ("cg", "cgf")}
rspread = {m: st.mean(abs(v[0]["recall"] - v[1]["recall"]) for v in c.values() if len(v) == 2) for m, c in (("Opus", opus), ("Haiku", haiku))}
print("key-file score, mean difference between two runs of the same cell", {k: round(v, 3) for k, v in rspread.items()})
spread = [abs(v[0]["cost"] - v[1]["cost"]) / st.mean(r["cost"] for r in v) for v in opus.values()]
print(f"Opus rep-to-rep cost difference, median {st.median(spread):.0%}")

# ---------------------------------------------------------------- 1. headline (also the og card), 1200x627
W, H, X0, SC = 1200, 627, 400, 440
body = legend(40, 128, ("cg", "cgf"))
body += xgrid(X0, SC, (0, 0.5, 1, 1.5), 150, 540, lambda v: f"{v:g}×")
body.append(f'<line x1="{X0 + SC}" y1="150" x2="{X0 + SC}" y2="540" stroke="{COL["ctl"]}" stroke-width="2" stroke-dasharray="6 5"/>')
body.append(text(X0 + SC + 8, 164, "no graph = 1×", 14, MUTED))
y = 172
desc = []
for m in ("Opus", "Haiku"):
    for i, size in ((1, "Short tasks"), (0, "Long tasks")):
        n = cf[(m, "cg")][2 + i]
        body.append(text(X0 - 16, y + 32, f"{m} {'5.5' if m == 'Opus' else '4.5'}, {size.lower()}", 17, anchor="end", weight=600))
        body.append(text(X0 - 16, y + 54, f"{n} comparisons", 14, MUTED, "end"))
        for a in ("cg", "cgf"):
            v = cf[(m, a)][i]
            body.append(hbar(X0, y + 8, v * SC, 22, COL[a]))
            body.append(f'<rect x="{X0 + v * SC + 6:.1f}" y="{y + 9}" width="48" height="20" fill="{BG}"/>')  # keeps the 1x line off the label
            body.append(text(X0 + v * SC + 10, y + 25, f"{v:.2f}×", 15))
            y += 26
        if m == "Haiku" and i == 1:
            body.append(text(X0 - 16, y + 24, f"{cf_skip['cg'][1]:.2f}× / {cf_skip['cgf'][1]:.2f}× without the VS Code lookup", 14, MUTED, "end"))
        desc.append(f"{m} {size.lower()}: graph installed {cf[(m, 'cg')][i]:.2f}x, graph + told first {cf[(m, 'cgf')][i]:.2f}x")
        y += 40
body.append(text(40, 592, "Long = over 20 searches and file reads (tool calls) in one no-graph run. Comparison = graph cost against the task's other no-graph run.", 14, MUTED))
body.append(text(40, 614, f"Opus 5.5: 108 runs, 18 tasks. Haiku 4.5: {len(haiku_rows)} runs; bars use the 14 tasks with two no-graph runs. Six public codebases.", 14, MUTED))
svg("codegraph-headline.svg", W, H, "Agent cost with a code graph, by task length",
    "Estimated cost at API list prices. 1× = the same task with no graph installed; 0.73× = 27% cheaper.",
    "Cost with a code graph relative to no graph. " + "; ".join(desc) + f". Without the VS Code lookup, Haiku short tasks: graph installed {cf_skip['cg'][1]:.2f}x, graph + told first {cf_skip['cgf'][1]:.2f}x.", body)

# ---------------------------------------------------------------- 2. how each arm works (schematic)
lanes = [("ctl", "No graph", [("Prompt", BOX)] + [("search / read", BOX)] * 5 + [("…", None), ("Answer", BOX)]),
         ("cg", "Graph installed", [("Prompt", BOX), ("Hook adds graph context", "#dbe8f8")] + [("read", BOX)] * 2 + [("…", None), ("Answer", BOX)]),
         ("cgf", "Graph + told first", [("Prompt + “call the graph first”", BOX), ("Hook adds graph context", "#dbe8f8"), ("graph call", "#bcd3f0"), ("graph call", "#bcd3f0"), ("read", BOX), ("…", None), ("Answer", BOX)])]
body = []
y = 130
for arm, label, steps in lanes:
    body.append(f'<rect x="40" y="{y}" width="8" height="60" rx="3" fill="{COL[arm]}"/>')
    body.append(text(60, y + 36, label, 17, weight=600))
    x = 220
    for s, fill in steps:
        w = max(64, 7.6 * len(s) + 24)
        if fill is None:
            body.append(text(x, y + 36, s, 15, MUTED))
            x += w
            continue
        body.append(f'<rect x="{x}" y="{y + 12}" width="{w:.0f}" height="36" rx="6" fill="{fill}" stroke="{GRID}" stroke-width="1.5"/>')
        body.append(text(x + w / 2, y + 35, s, 14, anchor="middle"))
        x += w + 10
    y += 90
body.append(text(40, 420, "Schematic, not to scale. The number of boxes doesn't show real call counts.", 14, MUTED))
body.append(text(40, 444, "The hook runs on every prompt in both graph setups. It pasted in matching source, except on 6 graph-installed tasks where it listed symbol locations only.", 14, MUTED))
svg("codegraph-how.svg", 1240, 470, "What the agent does in each setup",
    "Same question, same codebase, same tools. Only the graph setup changes.",
    "Schematic. With no graph the agent searches and reads files. With the graph installed, a prompt hook adds graph context before the agent starts: matching source, or on 6 of 18 tasks only symbol locations. Graph + told first adds explicit graph calls on top of the hook.", body)

# ---------------------------------------------------------------- 3. the repos (log scale)
X0, SC = 200, 170  # px per decade from 10k
body = xgrid(X0, SC, (0, 1, 2, 3), 110, 400, lambda v: ["10k", "100k", "1M", "10M"][v])
y = 120
for repo in REPOS:
    w = math.log10(LINES[repo] / 10_000) * SC
    body.append(text(X0 - 14, y + 30, repo, 17, anchor="end"))
    body.append(hbar(X0, y + 12, w, 26, GREY))
    n = LINES[repo]
    body.append(text(X0 + w + 12, y + 31, f"{n / 1e6:.1f}M lines" if n >= 1e6 else f"{n / 1e3:.0f}k lines", 16))
    y += 46
body.append(text(X0, 452, "Lines in tracked .py, .ts, .tsx, .js, .jsx, .mjs, .rs and .go files. Log scale.", 14, MUTED))
svg("codegraph-repos.svg", 1240, 480, "Six public codebases, 18k to 4.5M lines of code",
    "Each bar is one codebase at its September 2026 commit. 10k = the left edge of the scale.",
    "Lines of code: flask 18k, hono 91k, excalidraw 216k, django 557k, sentry 3.3M, vscode 4.5M.",
    body)

# ---------------------------------------------------------------- 4. by repo size: no trend
X0, SC = 250, 500
body = legend(40, 128, ("cg", "cgf"))
body += xgrid(X0 - 0.5 * SC, SC, (0.5, 1, 1.5), 150, 470, lambda v: f"{v:g}×")
x1 = X0 + 0.5 * SC
body.append(f'<line x1="{x1}" y1="150" x2="{x1}" y2="470" stroke="{COL["ctl"]}" stroke-width="2" stroke-dasharray="6 5"/>')
body.append(text(x1 + 8, 164, "no graph = 1×", 14, MUTED))
y = 180
desc = []
for repo in REPOS:
    ts = [t for t in tasks if t[0] == repo]
    body.append(text(X0 - 20, y + 5, f"{repo} ({LINES[repo] / 1e6:.1f}M)" if LINES[repo] >= 1e6 else f"{repo} ({LINES[repo] / 1e3:.0f}k)", 16, anchor="end"))
    body.append(f'<line x1="{X0}" y1="{y}" x2="{X0 + SC}" y2="{y}" stroke="{GRID}"/>')
    vals = {a: ratio(opus, ts, a) for a in ("cg", "cgf")}
    for a, v in vals.items():
        cx = X0 + (v - 0.5) * SC
        body.append(f'<circle cx="{cx:.1f}" cy="{y}" r="8" fill="{COL[a]}" stroke="{BG}" stroke-width="2"/>')
    body.append(text(820, y + 5, f"{vals['cg']:.2f}×  /  {vals['cgf']:.2f}×", 15, MUTED))
    desc.append(f"{repo} {vals['cg']:.2f}x / {vals['cgf']:.2f}x")
    y += 52
body.append(text(820, 164, "installed / told first", 14, MUTED))
body.append(text(40, 510, "Opus 5.5, 3 questions × 2 runs per setup per codebase. Codebases in size order, smallest first.", 14, MUTED))
svg("codegraph-size.svg", 1240, 530, "Codebase size doesn't predict the saving",
    "Estimated cost per codebase with a graph. 1× = the same questions with no graph.",
    "Cost with graph installed / graph + told first relative to no graph: " + "; ".join(desc) + ".", body)

# ---------------------------------------------------------------- 5. how noisy "long" is (range plot)
PX0, PX1, PY0, PY1 = 140, 1180, 500, 120  # plot box
xmax, ylo, yhi = 40, 0.6, 1.4
px = lambda v: PX0 + v / xmax * (PX1 - PX0)
py = lambda v: PY0 - (v - ylo) / (yhi - ylo) * (PY0 - PY1)
body = []
for v in range(0, 41, 5):
    body.append(f'<line x1="{px(v):.1f}" y1="{PY1}" x2="{px(v):.1f}" y2="{PY0}" stroke="{GRID}"/>')
    body.append(text(px(v), PY0 + 24, str(v), 14, MUTED, "middle"))
for v in (0.6, 0.8, 1.0, 1.2, 1.4):
    body.append(f'<line x1="{PX0}" y1="{py(v):.1f}" x2="{PX1}" y2="{py(v):.1f}" stroke="{COL["ctl"] if v == 1 else GRID}"'
                + (' stroke-width="2" stroke-dasharray="6 5"' if v == 1 else "") + "/>")
    body.append(text(PX0 - 12, py(v) + 5, f"{v:.1f}×", 14, MUTED, "end"))
body.append(f'<line x1="{px(20):.1f}" y1="{PY1}" x2="{px(20):.1f}" y2="{PY0}" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="3 4"/>')
body.append(text(px(20) + 8, PY1 + 18, "20 calls", 14, MUTED))
placed = []
for t in sorted(tasks, key=lambda t: calls[t]):
    lo, hi = sorted(r["calls"] for r in opus[t + ("ctl",)])
    v = mean(opus, t + ("cg",), "cost") / mean(opus, t + ("ctl",), "cost")
    y = py(v)
    while any(abs(y - q) < 14 and abs(px(calls[t]) - p) < 14 for p, q in placed):  # nudge dots that would overlap
        y += 14
    placed.append((px(calls[t]), y))
    body.append(f'<line x1="{px(lo):.1f}" y1="{y:.1f}" x2="{px(hi):.1f}" y2="{y:.1f}" stroke="{COL["cg"]}" stroke-width="2" opacity="0.5"/>')
    body.append(f'<circle cx="{px(calls[t]):.1f}" cy="{y:.1f}" r="6" fill="{COL["cg"]}" stroke="{BG}" stroke-width="2"/>')
    if hi > 20:
        label = f"{t[0]} {t[1]} ({lo:.0f} and {hi:.0f})"
        lx, ly, anchor = (px(hi) + 10, y + 5, "start") if t == ("vscode", "plan") else (px(calls[t]), y + (24 if t[0] == "excalidraw" else -12), "middle")
        lw = 7.4 * len(label)
        body.append(f'<rect x="{lx - (lw / 2 if anchor == "middle" else 0) - 3:.1f}" y="{ly - 14:.1f}" width="{lw + 6:.1f}" height="19" fill="{BG}"/>')
        if t == ("vscode", "plan"):  # above it sits sentry trace's dot
            body.append(text(px(hi) + 10, y + 5, label, 14, INK))
        else:
            body.append(text(px(calls[t]), y + (24 if t[0] == "excalidraw" else -12), label, 14, INK, "middle"))
body.append(text((PX0 + PX1) / 2, PY0 + 52, "Tool calls per task with no graph: line = the two runs, dot = their mean", 15, MUTED, "middle"))
body.append(text(40, 600, "Opus 5.5, 18 tasks, 2 runs per setup. The y-axis uses the same no-graph runs as the x-axis, which flatters long tasks;", 14, MUTED))
body.append(text(40, 622, "the headline chart compares each long run against the task's other run instead.", 14, MUTED))
svg("codegraph-calls.svg", 1240, 640, "Only one task went over 20 calls in both no-graph runs",
    "Estimated cost with the graph installed per task. 1× = the same task with no graph.",
    "Range plot of 18 tasks. Four tasks went over 20 tool calls in at least one no-graph run: excalidraw plan (23 and 33), excalidraw trace (18 and 35), "
    "sentry plan (13 and 37) and vscode plan (13 and 25). Only excalidraw plan did in both. Cost with the graph installed per task ranges from about 0.7x to 1.3x of no graph.", body)

# ---------------------------------------------------------------- 6. who called the graph
X0, SC = 300, 140
body = xgrid(X0, SC, (0, 1, 2, 3, 4, 5, 6), 110, 390, str)
y = 120
for m in ("Opus", "Haiku"):
    for a in ("cg", "cgf"):
        v = graph_calls[(m, a)]
        body.append(text(X0 - 14, y + 26, f"{m}, {NAME[a].lower()}", 16, anchor="end"))
        body.append(hbar(X0, y + 8, v * SC, 26, COL[a]))
        body.append(text(X0 + v * SC + 12, y + 27, f"{v:.2f}" if v < 1 else f"{v:.1f}", 16))
        y += 62 if a == "cgf" else 46
body.append(text(X0, 444, "Calls to the codegraph_explore tool or the codegraph CLI, mean per run. The prompt hook isn't counted.", 14, MUTED))
svg("codegraph-tool-calls.svg", 1240, 470, "Opus almost never called the graph itself",
    "Explicit graph calls per run. 0 = the agent relied on the hook's context and its own search.",
    f"Graph tool calls per run: Opus graph installed {graph_calls[('Opus', 'cg')]:.2f}, Opus graph + told first {graph_calls[('Opus', 'cgf')]:.1f}, "
    f"Haiku graph installed {graph_calls[('Haiku', 'cg')]:.1f}, Haiku graph + told first {graph_calls[('Haiku', 'cgf')]:.1f}.", body)

# ---------------------------------------------------------------- 7. Haiku: fewer calls, same answers (two panels)
body = legend(40, 128, ("ctl", "cg", "cgf"))
panels = ((40, "Tool calls per task", "calls", per_run, 30, (0, 10, 20, 30), str),
          (650, "Share of key files found", "recall", recall, 1.0, (0, 0.5, 1), lambda v: f"{v:.0%}"))
for px0, head, _, data, vmax, ticks, fmt in panels:
    X0, SC = px0 + 90, 440 / vmax
    body.append(text(px0, 172, head, 18, weight=600))
    body += xgrid(X0, SC, ticks, 190, 486, fmt)
    y = 196
    for m in ("Opus", "Haiku"):
        body.append(text(X0 - 12, y + 44, m, 16, anchor="end", weight=600))
        for a in ("ctl", "cg", "cgf"):
            v = data[(m, a)]
            body.append(hbar(X0, y + 8, v * SC, 24, COL[a]))
            body.append(text(X0 + v * SC + 10, y + 26, f"{v:.0%}" if vmax == 1 else f"{v:.1f}", 15))
            y += 30
        y += 50
body.append(text(40, 540, f"Mean of per-task means. Opus 5.5: 108 runs. Haiku 4.5: {len(haiku_rows)} of 108 planned runs. Key files = files cited by at least 3 of the 6 Opus runs.", 14, MUTED))
svg("codegraph-haiku.svg", 1240, 566, "Haiku made two thirds fewer calls with a graph; key files found moved within noise",
    "Left: tool calls per task. Right: share of each question's key files the answer cited. Orange = no graph.",
    f"Tool calls per task, no graph / graph installed / graph + told first: Opus {per_run[('Opus', 'ctl')]:.1f} / {per_run[('Opus', 'cg')]:.1f} / {per_run[('Opus', 'cgf')]:.1f}; "
    f"Haiku {per_run[('Haiku', 'ctl')]:.1f} / {per_run[('Haiku', 'cg')]:.1f} / {per_run[('Haiku', 'cgf')]:.1f}. Key files found: Opus "
    f"{recall[('Opus', 'ctl')]:.0%} / {recall[('Opus', 'cg')]:.0%} / {recall[('Opus', 'cgf')]:.0%}; Haiku {recall[('Haiku', 'ctl')]:.0%} / {recall[('Haiku', 'cg')]:.0%} / {recall[('Haiku', 'cgf')]:.0%}.",
    body)

# ---------------------------------------------------------------- 8. the index is the price of entry
X0, SC = 200, 7.5
body = xgrid(X0, SC, (0, 30, 60, 90, 120), 110, 400, lambda v: f"{v} s")
y = 120
for repo in REPOS:
    s, size = INDEX[repo]
    body.append(text(X0 - 14, y + 30, repo, 17, anchor="end"))
    body.append(hbar(X0, y + 12, s * SC, 26, GREY))
    body.append(text(X0 + s * SC + 12, y + 31, f"{s} s, {size} on disk", 16))
    y += 46
body.append(text(X0, 456, "CodeGraph's own summary line reports less, for its graph step: " + ", ".join(f"{CG_TIME[r]} s" for r in REPOS) + ".", 14, MUTED))
body.append(text(X0, 478, "One index build per codebase, CodeGraph 1.6.0. Bars in grey: a cost of the graph itself, not a setup.", 14, MUTED))
svg("codegraph-index.svg", 1240, 500, "Building the index: seconds for most codebases, two minutes for the biggest",
    "Wall clock from install command to finished index, whole seconds. 0 s = no index.",
    "Wall-clock time from install to finished index, and index size: Flask 1 s, 5 MB; Hono 2 s, 26 MB; Excalidraw 5 s, 54 MB; Django 9 s, 165 MB; Sentry 60 s, 951 MB; VS Code 107 s, 1.6 GB. CodeGraph's own summary line reports 0.3 s to 17.4 s for its graph step.", body)

print("wrote", OUT)
