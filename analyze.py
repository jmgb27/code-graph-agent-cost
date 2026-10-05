"""Summarise runs/*.jsonl into results.csv and a per-repo/question/arm table.

Quality proxy: for each question, the "consensus" file set is every source file cited by at least
3 of the question's Opus runs in runs/ (any arm). A run's recall is the share of that set it cites.

Usage: python3 analyze.py [runs-dir]   (default runs/, the Opus sweep)
"""
import csv, json, re, statistics as st, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
RUNS = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "runs"
SIZES = ["flask", "hono", "excalidraw", "django", "sentry", "vscode"]
FILE_RE = re.compile(r"[\w./-]+\.(?:py|tsx?|jsx?|mjs|json|rs|go)\b")


REPO_FILES = {}


def resolve(repo, cited):
    """Map a cited path to the one repo file it ends with; None if unknown or ambiguous."""
    if repo not in REPO_FILES:
        out = subprocess.run(["git", "-C", str(ROOT / "repos" / f"{repo}-ctl"), "ls-files"], capture_output=True, text=True).stdout
        REPO_FILES[repo] = out.split()
    hits = [f for f in REPO_FILES[repo] if f == cited or f.endswith("/" + cited)]
    return hits[0] if len(hits) == 1 else None


def parse(path, save=True):
    events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    result = next((e for e in events if e.get("type") == "result"), None)
    if not result:
        return None
    tools = Counter()
    for e in events:
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c.get("type") == "tool_use":
                    name = c["name"]
                    if name == "Bash" and "codegraph" in c["input"].get("command", ""):
                        name = "Bash(codegraph)"
                    tools[name] += 1
    repo, q, arm, rep = path.stem.split("-")
    u = result.get("usage", {})
    answer = result.get("result", "")
    if save:
        answers = ROOT / RUNS.replace("runs", "answers")
        answers.mkdir(exist_ok=True)
        (answers / f"{path.stem}.md").write_text(answer)
    files = {f for m in FILE_RE.findall(answer) if (f := resolve(repo, m.lstrip("./")))}
    return dict(
        repo=repo, q=q, arm=arm, rep=rep,
        cost=result["total_cost_usd"], turns=result["num_turns"],
        secs=result["duration_ms"] / 1000,
        calls=sum(v for k, v in tools.items() if k != "ToolSearch"),
        graph_calls=tools["mcp__codegraph__codegraph_explore"] + tools["mcp__codegraph__codegraph_node"] + tools["Bash(codegraph)"],
        out_tok=u.get("output_tokens", 0),
        in_tok=u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
        error=result.get("is_error", False), files=files,
    )


rows = [r for p in sorted((ROOT / RUNS).glob("*.jsonl")) if (r := parse(p))]
ref = rows if RUNS == "runs" else [r for p in sorted((ROOT / "runs").glob("*.jsonl")) if (r := parse(p, save=False))]
by_q, ref_q = defaultdict(list), defaultdict(list)
for r in rows:
    by_q[(r["repo"], r["q"])].append(r)
for r in ref:
    ref_q[(r["repo"], r["q"])].append(r)
for key, runs in by_q.items():
    cited = Counter(f for r in ref_q[key] for f in r["files"])
    consensus = {f for f, n in cited.items() if n >= 3}
    for r in runs:
        r["recall"] = len(r["files"] & consensus) / len(consensus) if consensus else 1.0

with open(ROOT / ("results.csv" if RUNS == "runs" else f"results-{RUNS}.csv"), "w", newline="") as fh:
    cols = ["repo", "q", "arm", "rep", "cost", "turns", "secs", "calls", "graph_calls", "in_tok", "out_tok", "recall", "error"]
    w = csv.DictWriter(fh, cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

mean = lambda xs: st.mean(xs) if xs else float("nan")
print(f"{len(rows)} runs\n")
print(f"{'repo':11}{'q':7}" + "".join(f"{a:>32}" for a in ("ctl", "cg", "cgf")))
print(" " * 18 + "   calls  graph  cost$   secs  recall" * 3)
for repo in SIZES:
    for q in ("lookup", "trace", "plan"):
        line = f"{repo:11}{q:7}"
        for arm in ("ctl", "cg", "cgf"):
            rs = [r for r in by_q[(repo, q)] if r["arm"] == arm]
            line += f"{mean([r['calls'] for r in rs]):8.1f}{mean([r['graph_calls'] for r in rs]):7.1f}{mean([r['cost'] for r in rs]):7.2f}{mean([r['secs'] for r in rs]):7.0f}{mean([r['recall'] for r in rs]):8.2f}"
        print(line)
print("\nPer repo totals (calls / cost / recall):")
for repo in SIZES:
    line = f"{repo:11}"
    for arm in ("ctl", "cg", "cgf"):
        rs = [r for r in rows if r["repo"] == repo and r["arm"] == arm]
        line += f"  {arm}: {mean([r['calls'] for r in rs]):5.1f} / ${mean([r['cost'] for r in rs]):.2f} / {mean([r['recall'] for r in rs]):.2f}"
    print(line)
if any(r["error"] for r in rows):
    print("\nerrors:", [f"{r['repo']}-{r['q']}-{r['arm']}-{r['rep']}" for r in rows if r["error"]], file=sys.stderr)
