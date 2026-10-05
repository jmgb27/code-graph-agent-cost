# Code graph agent cost

The scripts, questions, transcripts and results behind this blog post:

**[Code graph in Claude Code: Haiku 27% cheaper on long tasks, Opus no clear gain](https://johnmark.dev/blog/code-graph-agent-cost)**

I gave Claude Code 18 read-only questions about six public codebases (Flask, Hono, Excalidraw, Django, Sentry, VS Code) in three setups, with Opus 5.5 and Haiku 4.5:

- **ctl** (no graph): plain Claude Code.
- **cg** (graph installed): [CodeGraph](https://github.com/colbymchenry/codegraph) 1.6.0 with its defaults, which add an MCP server, a prompt hook and a `CLAUDE.md` note.
- **cgf** (graph + told first): the same, plus a line in each prompt telling the agent to call the graph before grep or reading files.

| Model, task length | Comparisons | Graph installed | Graph + told first |
|---|---|---|---|
| Opus 5.5, short | 31 | 0.99× | 1.28× |
| Opus 5.5, long | 5 | 0.90× | 1.38× |
| Haiku 4.5, short | 12 | 1.19× | 1.40× |
| Haiku 4.5, long | 16 | 0.73× | 0.58× |

Cost relative to no graph. Long means the no-graph run took over 20 tool calls. Cost is Claude Code's own estimate at Anthropic's pay-as-you-go prices.

## Files

| File | What it is |
|---|---|
| `questions.json` | The 18 questions: a lookup, a trace and a plan for each codebase |
| `run.sh` | One headless Claude Code run for a codebase, question, setup and repeat |
| `mcp-codegraph.json` | The MCP config the graph setups use |
| `analyze.py` | Turns transcripts into `results*.csv` and extracts each final answer into `answers*/` |
| `charts/make_charts.py` | The post's charts and the numbers it quotes |
| `runs/`, `runs-haiku/` | Raw stream-json transcripts of every Opus and Haiku run (`.err` holds stderr) |
| `answers/`, `answers-haiku/` | Each run's final answer as Markdown |
| `results.csv`, `results-runs-haiku.csv` | Cost, turns, time, tool calls, graph calls, tokens and file recall per run |
| `logs/` | CodeGraph indexing output per codebase |

## Reproduce

You need [Claude Code](https://claude.com/claude-code), [CodeGraph](https://github.com/colbymchenry/codegraph) 1.6.0, `jq` and Python 3. Each codebase is cloned twice under `repos/`: `<name>` gets CodeGraph, `<name>-ctl` stays plain.

| Codebase | Commit |
|---|---|
| [django/django](https://github.com/django/django) | `9332b163a67eabe5bdbf8066b1c5da394be9aa9c` |
| [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw) | `5a406e51875157bece389b9bc92d41ff241d5f3d` |
| [pallets/flask](https://github.com/pallets/flask) | `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35` |
| [honojs/hono](https://github.com/honojs/hono) | `37ce06904e732d4bc11c9075adf362c76049a594` |
| [getsentry/sentry](https://github.com/getsentry/sentry) | `1c7d16d5d4fcc5e4a665d1b90f29ecee43ea6e4b` |
| [microsoft/vscode](https://github.com/microsoft/vscode) | `4b243603f3c1173d596035e6237cdbc6c23e6a40` |

```bash
git clone https://github.com/pallets/flask repos/flask
git -C repos/flask checkout d73fa1cdcbd8b1465c151db8924ba58b1dd14e35
cp -R repos/flask repos/flask-ctl
(cd repos/flask && codegraph init)           # index plus hook, settings and CLAUDE.md
# repeat for each codebase, then:

./run.sh flask trace cg 0                    # Opus run -> runs/flask-trace-cg-0.jsonl
RUNS=runs-haiku MODEL=claude-haiku-4-5-20251001 ./run.sh flask trace cg 0
python3 analyze.py                           # Opus -> results.csv
python3 analyze.py runs-haiku                # Haiku -> results-runs-haiku.csv
python3 charts/make_charts.py                # SVG charts into charts/
```

`run.sh` unsets `ANTHROPIC_API_KEY` so runs use your Claude subscription login rather than API credit. File recall is measured against the files at least 3 Opus runs cited for the same question, so it's a consensus check, not ground truth.

The Haiku sweep stopped at 99 of 108 runs; the post explains how that's handled.

## Credits

Thanks to [CodeGraph](https://github.com/colbymchenry/codegraph) (MIT) and to the Flask, Hono, Excalidraw, Django, Sentry and VS Code projects. Their code isn't included here; the transcripts quote parts of it.

## License

MIT for the code in this repo.
