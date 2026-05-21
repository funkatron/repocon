# Handoff — repocon pause (2026-05-21)

Paste the **Incoming bundle** block below into a new Cursor chat to resume.

---

## TL;DR

Repocon on **`main`** is ready for new-dev onboarding: scan → Bear wiki links → `--export-bear` upsert. User paused after verifying **2 updated** Bear notes on a `--project repocon` run. Next: Bear duplicate cleanup, full `~/src` dogfood, optional CI/incremental scan.

---

## Git truth

| Repo | Branch | HEAD | Remote |
|---|---|---|---|
| repocon | `main` | `5be98f2` | synced |
| infomux | `main` | `dcd3155` | synced (`infomux.bear` from PR #5) |

**Merged PRs:** [repocon #2](https://github.com/funkatron/repocon/pull/2), [infomux #5](https://github.com/funkatron/infomux/pull/5)

---

## Goal (one sentence)

Help a **new developer** orient across `~/src` via repocon briefs in **Bear**, with deterministic scans first and optional LLM enrichment.

---

## Done

- Scan signal quality for onboarding (folder roles, run/test detection, ignore `reports*`)
- Bear `[[Note Title]]` links; `--export-bear` + upsert registry
- Export scoped to current scan; prune stale brief files
- pytest (19 tests), `docs/onboarding-new-dev.md`
- Terminology: **LLM enrichment** / **enrichment**

---

## Not done / next

| Priority | Task |
|---|---|
| User | Trash duplicate Bear notes from pre-fix export (~39 creates) |
| User | Full `uv run repocon ~/src --output ./reports --export-bear` + skim index |
| Eng | CI workflow (pytest) |
| Eng | Incremental rescan by git HEAD |
| Optional | LLM full portfolio run via `./scripts/repocon-ollama.sh` |

---

## Tests last run

```bash
cd ~/src/repocon && uv sync --extra dev && uv run pytest -q
```

→ **19 passed** (2026-05-21)

---

## Blockers

None.

---

## Env / commands

```bash
cd ~/src/repocon && uv sync
uv pip install -e ~/src/infomux   # optional; shared Bear helpers

uv run repocon ~/src --output ./reports --export-bear --no-open
uv run repocon ~/src --project repocon --output ./reports --export-bear --no-open
```

- Tags: `REPOCON_BEAR_TAGS` or `INFOMUX_BEAR_TAGS` (default `repocon,projects`)
- Registry: `reports/.repocon-bear.json` (local; do not commit)
- Ollama: `./scripts/repocon-ollama.sh` → nakedsnake tunnel

---

## Incoming bundle (paste into next chat)

```text
## Handoff
- Repo: ~/src/repocon — branch main @ 5be98f2 — pushed yes
- Related: ~/src/infomux main @ dcd3155 (infomux.bear merged)
- Goal: New-dev onboarding via repocon briefs in Bear; user paused after upsert verified
- Done: PR #2 + onboarding guide + Bear export upsert + export scoping fix
- Not done: Bear duplicate cleanup in app; full ~/src dogfood; CI; incremental scan
- Tests: uv run pytest -q → 19 passed
- Read first: docs/onboarding-new-dev.md, cursorrules/2026-05-21-pause-handoff.md
- Blockers: none
```

---

## Key files

| Path | Role |
|---|---|
| `src/repocon/analyzer.py` | Scan, index, CLI |
| `src/repocon/bear_export.py` | Bear sync + registry |
| `docs/onboarding-new-dev.md` | New dev user guide |
| `scripts/repocon-ollama.sh` | Nakedsnake Ollama helper |
