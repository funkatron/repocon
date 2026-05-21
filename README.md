# Repocon

`repocon` scans each top-level folder in a source directory and writes a layered brief for every project.

The output is meant to work in two passes:

1. A completely new person can read the opening sections and understand what the project is for.
2. A technical reader can keep going and get a decent picture of stack, history, risks, and likely next steps.

## What The First Version Does

- scans each top-level folder in `~/src` by default
- reads local repo signals such as `README`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, folder structure, and git history
- writes one Markdown brief per project
- generates a summary index, machine-readable JSON export, and structured facts files
- adds simple cross-project similarity matches
- adds heuristic recommendations about next steps, prioritization, and monetization potential

## What It Does Not Do Yet

- it does not read your mind
- it does not inspect private issue trackers, PRs, or business plans
- LLM narration is optional and off by default
- it only knows what the repo visibly signals

That is intentional for v1. It keeps the output explicit and auditable.

## Run It

From this directory:

```bash
PYTHONPATH=src python3 -m repocon ~/src --output ./reports
```

Or install it in editable mode and use the CLI entrypoint:

```bash
python3 -m pip install -e .
repocon ~/src --output ./reports
```

Limit to a few projects while iterating:

```bash
repocon ~/src --limit 3 --output ./reports-sample
```

Scan specific projects only:

```bash
repocon ~/src --project now-playing --project PulseHZ --output ./reports-focused
```

Run the deterministic scan first, but let an LLM rewrite only the extracted facts:

```bash
repocon ~/src --output ./reports-openai --llm-provider openai --llm-model gpt-5-mini --llm-max-projects 5
```

Or use Ollama on nakedsnake via SSH tunnel (recommended on this machine — saves local disk, better models):

```bash
./scripts/repocon-ollama.sh --project now-playing --project PulseHZ --project repocon
```

The helper script tunnels `localhost:11435` to nakedsnake's Ollama server and defaults to `qwen2.5:7b-instruct`. Override with env vars:

```bash
OLLAMA_MODEL=qwen2.5:32b-instruct LLM_MAX_PROJECTS=3 ./scripts/repocon-ollama.sh
```

Manual Ollama flags (local or tunneled):

```bash
repocon ~/src --output ./reports-ollama \
  --llm-provider ollama \
  --llm-model qwen2.5:7b-instruct \
  --llm-base-url http://127.0.0.1:11435 \
  --llm-max-projects 5
```

Start the tunnel in another terminal if you use `--llm-base-url` manually:

```bash
ssh -N -L 11435:127.0.0.1:11434 nakedsnake
```

## Output Shape

- `index.md`: one-page rollup with links to each project brief
- `projects/<name>.md`: full layered brief for one project
- `projects.json`: structured export of all reports
- `facts/<name>.json`: per-project evidence bundle used for optional LLM narration
- `facts.json`: aggregate evidence export for all projects

Generated reports are local working output and should generally stay out of version control. They may contain absolute local paths and project names from your machine.

## Next Obvious Improvements

- summarize key folders more deeply instead of only naming them
- inspect entrypoints and tests more precisely
- detect project families and shared code patterns more intelligently
- add optional LLM-backed narrative generation on top of the deterministic scan

## Planned LLM Handoff

The current scanner is deliberately deterministic first:

- it collects facts from manifests, git, folder structure, likely entrypoints, and likely route files
- it writes those facts into a stable intermediate report
- an LLM can later be asked to rewrite or expand that report, instead of guessing directly from the repo

That means `--llm-provider openai` or `--llm-provider ollama` can be used safely:

- deterministic scan runs first
- the scan output becomes the LLM context
- the model only improves wording, synthesis, comparisons, and recommendations
- if the LLM is unavailable, the base report still exists

That is the direction I would keep. The scanner should gather evidence; the LLM should narrate it.

## LLM Usage Notes

- default mode is still deterministic only
- the LLM sees extracted facts, not raw repo dumps
- `--llm-max-projects` lets you limit spend and runtime
- OpenAI requires `OPENAI_API_KEY`
- Ollama default model is `qwen2.5:7b-instruct` (good JSON compliance for structured briefs)
- Ollama assumes a local server on `http://127.0.0.1:11434` unless you override `--llm-base-url`
- larger Ollama models (`32b`, `70b`) get a 300s timeout per project; smaller models use 120s
- on this machine, prefer `./scripts/repocon-ollama.sh` to reach nakedsnake without installing models locally
