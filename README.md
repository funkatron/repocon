# Repocon

`repocon` scans each top-level folder in a source directory and writes a layered brief for every project.

The output is meant to work in two passes:

1. A completely new person can read the opening sections and understand what the project is for.
2. A technical reader can keep going and get a decent picture of stack, history, risks, and likely next steps.

## What The First Version Does

- scans each top-level folder in a source directory you pass on the command line (e.g. `~/src`)
- reads local repo signals such as `README`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, folder structure, and git history
- writes one Markdown brief per project
- generates a summary index, machine-readable JSON export, and structured facts files
- adds simple cross-project similarity matches
- adds heuristic recommendations about next steps, prioritization, and monetization potential

## What It Does Not Do Yet

- it does not read your mind
- it does not inspect private issue trackers, PRs, or business plans
- LLM enrichment is optional and off by default
- it only knows what the repo visibly signals

That is intentional for v1. It keeps the output explicit and auditable.

## Run It

Pass the directory that **contains** your project repos — each subfolder becomes one brief.

From this directory:

```bash
PYTHONPATH=src python3 -m repocon ~/src --output ./reports
```

Or install it in editable mode and use the CLI entrypoint:

```bash
python3 -m pip install -e .
repocon ~/src --output ./reports
```

No enrichment in that command: briefs come from README, manifests, git, and folder layout only.

When the run finishes, repocon offers to open `reports/index.md` in [Marked](https://markedapp.com/) via the [`mk` CLI](https://markedapp.com/help/Command_Line_Utility.html) if installed (`brew install ttscoff/thelab/mk`). The index includes Marked metadata for **GitHub** styling and **CommonMark (GFM)** processing.

By default, links between briefs use **Bear-style** `[[Note Title]]` wiki links (same pattern as infomux `store_bear`). Titles match each brief's `#` heading so [Bear.app](https://bear.app/) can jump between notes. For Marked preview with absolute file paths, pass `--link-style marked`.

Export notes directly into Bear on macOS (uses [infomux](https://github.com/funkatron/infomux) `bear` helpers when installed):

```bash
uv run repocon ~/src --output ./reports --export-bear
```

Tags come from `REPOCON_BEAR_TAGS` (default `repocon,projects`) or `INFOMUX_BEAR_TAGS` if set.

Limit to a few projects while iterating:

```bash
repocon ~/src --limit 3 --output ./reports-sample
```

Scan specific projects only:

```bash
repocon ~/src --project now-playing --project PulseHZ --output ./reports-focused
```

Optional LLM enrichment after the repo scan:

```bash
repocon ~/src --output ./reports-openai --llm-provider openai --llm-model gpt-5-mini
```

Or use Ollama — set the server, then opt in explicitly:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11435
export OLLAMA_MODEL=qwen2.5:7b-instruct   # optional; this is the default
repocon ~/src --output ./reports-ollama --llm-provider ollama
```

`OLLAMA_BASE_URL` (or `OLLAMA_HOST`) picks the server; `--llm-provider ollama` enables the LLM enrichment step. Deterministic-only runs ignore those env vars.

On this machine, use the helper script to reach nakedsnake without managing the tunnel yourself:

```bash
./scripts/repocon-ollama.sh --project now-playing --project PulseHZ --project repocon
```

The helper sets `OLLAMA_BASE_URL` after opening `localhost:11435 -> nakedsnake:11434`. If `OLLAMA_BASE_URL` is already set, it uses that server and skips the tunnel.

```bash
OLLAMA_MODEL=qwen2.5:32b-instruct ./scripts/repocon-ollama.sh
```

Manual tunnel for a remote Ollama server:

```bash
ssh -N -L 11435:127.0.0.1:11434 nakedsnake
export OLLAMA_BASE_URL=http://127.0.0.1:11435
repocon ~/src --output ./reports-ollama --llm-provider ollama
```

For a quick enrichment smoke test without enriching every project:

```bash
repocon ~/src --llm-provider ollama --llm-limit 3 --project now-playing --project PulseHZ --project repocon
```

## Onboarding a new dev

Use this when someone new needs a map of your local project folders before they touch code.

**Assumption:** they have the same source layout you scan (typically `~/src` with one folder per repo).

1. Install and sync:

```bash
cd repocon
uv sync
```

2. Generate briefs on their machine:

```bash
uv run repocon ~/src --output ./reports
```

3. Open `reports/index.md` and skim the summary table first, then open 2–3 project briefs (click `[[Note Title]]` links in Bear, or open the files directly).

4. Optional LLM enrichment after the deterministic scan looks right:

```bash
uv run repocon ~/src --output ./reports --llm-provider ollama --llm-limit 5
```

### How to read a brief

Each `projects/<name>.md` file is layered on purpose:

| Section | Use it for |
|---|---|
| **Start Here** / **Plain-English Summary** | What the project is for |
| **Technical Summary** | Stack, folder roles, likely run commands, test signals, entrypoints |
| **Metadata** | Quick facts pulled from the repo scan |
| **Chronology** | When work started and what changed recently |
| **Current State Evaluation** | Heuristic health read — verify before acting |
| **Recommendations** | Suggested next steps — not authoritative |

Briefs are **evidence-based heuristics**. They read manifests, README, git, and folder layout. They do not read issue trackers, PRs, or private notes.

## Output Shape

- `index.md`: one-page rollup with Bear-style `[[Note Title]]` links to each project brief (use `--link-style marked` for absolute paths)
- `projects/<name>.md`: full layered brief for one project
- `projects.json`: structured export of all reports
- `facts/<name>.json`: per-project evidence bundle used for optional LLM enrichment
- `facts.json`: aggregate evidence export for all projects

Generated reports are local working output and should generally stay out of version control. They may contain absolute local paths and project names from your machine.

## Next Obvious Improvements

- detect project families and shared code patterns more intelligently
- incremental rescans when only some repos changed

## How LLM enrichment works

The scanner reads the repo first:

- it collects facts from manifests, git, folder structure, likely entrypoints, and likely route files
- it writes those facts into a stable intermediate report
- optional enrichment rewrites that report from those facts, instead of guessing directly from the repo

That means `--llm-provider openai` or `--llm-provider ollama` can be used safely:

- the repo scan runs first
- the scan output becomes the enrichment context
- enrichment improves wording, synthesis, comparisons, and recommendations
- if enrichment is unavailable, the base report still exists

The scanner gathers evidence; enrichment improves the brief on top.

## LLM enrichment notes

- by default, briefs use repo files only — no enrichment
- enrichment sees extracted facts, not raw repo dumps
- when you opt in, LLM enrichment runs for every scanned project; use `--llm-limit N` for quick tests
- OpenAI requires `OPENAI_API_KEY`
- Ollama server: set `OLLAMA_BASE_URL` (or `OLLAMA_HOST` as `host:port`); used when `--llm-provider ollama`
- Ollama model: set `OLLAMA_MODEL` or rely on the default `qwen2.5:7b-instruct`
- larger Ollama models (`32b`, `70b`) get a 300s timeout per project; smaller models use 120s
- on this machine, prefer `./scripts/repocon-ollama.sh` to reach nakedsnake without installing models locally
