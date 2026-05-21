# New developer guide

Repocon scans a folder of git repos (usually `~/src`) and writes a brief per project plus an index. This guide is for **someone new to the codebase** and for **the person running repocon** the first time on a team.

**Assumption:** each project is a top-level folder under `~/src` (one repo per folder). Briefs are **heuristic** — they read README, manifests, git, and layout only. Verify before you act on recommendations.

---

## Quickstart

```bash
cd ~/src/repocon
uv sync
uv pip install -e ~/src/infomux   # optional; shared Bear backend on macOS

uv run repocon ~/src --output ./reports --export-bear --no-open
```

Open **Project Briefs** in [Bear.app](https://bear.app/) (or read `reports/index.md`). Skim the index table, then open 2–3 project briefs.

---

## Before you start

| You need | Notes |
|---|---|
| `uv` | Run repocon from the repo: `uv sync` then `uv run repocon …` |
| Access to project repos | Same layout as the team (typically `~/src`) |
| macOS + Bear (optional) | For `--export-bear`; wiki links `[[Note Title]]` work best in Bear |
| infomux (optional) | Editable install from `~/src/infomux` — not on PyPI |

Repocon does **not** need API keys unless you opt into LLM enrichment.

---

## 1. One-time Bear cleanup (macOS)

Do this if Bear already has **duplicate** project notes from an old export (for example a run that synced every file in `reports/projects/` instead of only the current scan).

1. In Bear, search for tag `#repocon` or `#projects` (or whatever you set in `REPOCON_BEAR_TAGS`).
2. For each project name, **keep one note** whose title matches the brief heading (e.g. `repocon`, `now-playing`).
3. Trash duplicates and stray copies of **Project Briefs**.
4. Optional: delete `~/src/repocon/reports/.repocon-bear.json` only if you want repocon to treat the next export as all-new creates. Normally **leave the registry** so the next run **updates** instead of creating again.

After cleanup, a correct run with `--bear-mode upsert` (the default) should report mostly **updated**, not **created**, on the second identical run.

---

## 2. Full portfolio run

Generate briefs for every repo under `~/src` and sync them to Bear.

```bash
cd ~/src/repocon
uv sync

uv run repocon ~/src --output ./reports --export-bear --no-open
```

**What to expect**

| Output | Meaning |
|---|---|
| `Wrote N project briefs` | N folders scanned under `~/src` |
| `Synced M Bear notes (X created, Y updated)` | M = projects + index; first full run is mostly **created** |
| `./reports/index.md` | Landing page with summary table and **Families** |
| `./reports/projects/*.md` | One brief per project |
| `./reports/.repocon-bear.json` | Tracks titles for upsert (do not commit) |

**Second run (sanity check)**

```bash
uv run repocon ~/src --output ./reports --export-bear --no-open
```

You want **`0 created`** (or close) and **`updated`** for projects that did not change. That confirms upsert is working.

**Partial runs** (one project while iterating):

```bash
uv run repocon ~/src --project repocon --output ./reports --export-bear --no-open
```

Only **repocon** and the **Project Briefs** index sync to Bear — not every old file in `reports/projects/`.

**Without Bear** (files only):

```bash
uv run repocon ~/src --output ./reports
```

---

## 3. Skim like a new developer

Read in this order — about 30–45 minutes for a large portfolio.

### Start at the index

Open **Project Briefs** in Bear or `reports/index.md`.

1. Read the caveat: *heuristic scan — verify before acting*.
2. Scan the **Summary table** columns:
   - **One-line read** — what is it?
   - **Current state** — rough health
   - **Run** — likely command to try
   - **Tests** — `yes` / `no` from repo signals
   - **Similar projects** — siblings by local signals
3. Check **Families** — name-prefix clusters (e.g. `draw-things*`). Useful for “what belongs together”.

### Pick 3 briefs to read deeply

Choose one active product, one utility, and one stale or archived repo.

For each `projects/<name>.md`:

| Section | Question to answer |
|---|---|
| **Start Here** / **Plain-English Summary** | What problem does this solve? |
| **Technical Summary** | Stack, folder roles, run commands, test signals, entrypoints |
| **Metadata** | Quick facts |
| **Chronology** | Is it alive? When did work last happen? |
| **Current State Evaluation** | Trust but verify — heuristics, not gospel |
| **Recommendations** | Ideas only — confirm with a human |

Use `[[Note Title]]` links in Bear to jump between related projects.

### What repocon does not know

- Issue trackers, PRs, Slack, roadmaps
- Private or unstated intent
- Runtime behavior without tests or docs

If a brief is wrong, fix the **repo** (README, scripts, tests) and re-run repocon.

---

## 4. Optional LLM enrichment

Run this **after** deterministic briefs look acceptable. Enrichment rewrites wording from extracted facts; it does not read the whole repo.

**Small sample first:**

```bash
uv run repocon ~/src --output ./reports \
  --llm-provider ollama --llm-limit 5 --export-bear --no-open
```

**Remote Ollama on this team’s setup:**

```bash
./scripts/repocon-ollama.sh --llm-limit 5 --export-bear --no-open
```

**Full enrichment** (slow — every project):

```bash
uv run repocon ~/src --output ./reports-ollama \
  --llm-provider ollama --export-bear --no-open
```

OpenAI instead of Ollama:

```bash
export OPENAI_API_KEY=…
uv run repocon ~/src --output ./reports-openai \
  --llm-provider openai --llm-limit 10
```

Re-export to Bear after enrichment so Bear notes match the enriched Markdown.

---

## 5. Your first day (new developer checklist)

You regenerate briefs **on your machine** — nobody emails you a `reports/` zip.

### Setup

```bash
# Clone repocon (and ensure ~/src has the project repos)
cd ~/src/repocon
uv sync

# Optional: shared Bear helpers
uv pip install -e ~/src/infomux
```

**Default:** source directory is `~/src`. If your checkout lives elsewhere, pass that path instead.

### Generate briefs

```bash
uv run repocon ~/src --output ./reports --export-bear --no-open
```

Or without Bear:

```bash
uv run repocon ~/src --output ./reports
```

### Read

- [ ] Open **Project Briefs** (Bear or `reports/index.md`)
- [ ] Skim the summary table and **Families**
- [ ] Read 3 briefs your lead suggested (or pick from active **Run** / **Tests** = yes)
- [ ] Clone one repo and try its **Likely run commands** from the brief
- [ ] Ask your lead where the brief was wrong — that helps everyone

### Optional

```bash
uv run repocon ~/src --output ./reports --llm-provider ollama --llm-limit 5 --export-bear --no-open
```

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `39 created` but you ran `--project one` | Old bug or stale `./reports/projects/` | `git pull` repocon; re-run — should be ~2 notes (project + index) |
| Second run still all **created** | Missing or deleted `.repocon-bear.json` | Normal on first run; second identical run should **update** |
| Duplicate notes in Bear | Past `create` runs or duplicate titles | One-time cleanup (section 1); use default `--bear-mode upsert` |
| `[[links]]` do not jump in Bear | Note title ≠ link text | Note title must match brief `#` heading exactly |
| Brief lists wrong folders | Repo artifacts (old `reports/` in project) | Fix repo layout or ignore; re-scan |
| Marked preview breaks links | Bear wiki links vs file paths | `uv run repocon ~/src --output ./reports --link-style marked` |

---

## Command cheat sheet

| Goal | Command |
|---|---|
| Full scan + Bear sync | `uv run repocon ~/src --output ./reports --export-bear --no-open` |
| One project | `uv run repocon ~/src --project NAME --output ./reports --export-bear --no-open` |
| Files only (no Bear) | `uv run repocon ~/src --output ./reports` |
| LLM sample + Bear | `uv run repocon ~/src --output ./reports --llm-provider ollama --llm-limit 5 --export-bear --no-open` |
| Force new Bear notes | add `--bear-mode create` |
| Marked-friendly links | add `--link-style marked` |

---

## For the person maintaining repocon

- Re-run after meaningful repo changes (README, scripts, new projects).
- Do not commit `reports/` or `.repocon-bear.json`.
- Point new devs at this file: `docs/onboarding-new-dev.md`.
