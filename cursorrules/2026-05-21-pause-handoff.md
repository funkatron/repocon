# Pause handoff — 2026-05-21

## State

- **Branch:** `main` @ `5be98f2` — synced with `origin/main`
- **Working tree:** clean (local `reports/` is generated output; not committed)

## Shipped this arc

- Onboarding scan quality (folder roles, test/run signals, artifact ignore, pytest)
- Bear-style `[[Note Title]]` links; `--link-style marked` for Marked
- `--export-bear` with `--bear-mode upsert|create|update` and `reports/.repocon-bear.json`
- Index **Families** + Run/Tests columns
- Fix: Bear export scoped to **current scan only**; stale `projects/*.md` pruned on write
- **docs/onboarding-new-dev.md** — new dev guide (Bear cleanup → full run → skim → LLM → first day)

## Related repos

- **infomux** `main` @ `dcd3155` — `infomux.bear` (`create_note`, `replace_note`) merged in PR #5
- Repocon uses `infomux.bear` when installed editable; no PyPI

## Verified

```bash
cd ~/src/repocon && uv sync --extra dev && uv run pytest -q   # 19 passed
uv run repocon ~/src --project repocon --output ./reports --export-bear --no-open
# → Synced 2 Bear notes (0 created, 2 updated) on repeat run
```

## Not done / next when resuming

1. One-time **Bear duplicate cleanup** in Bear.app (bad 39-note run before export scoping fix)
2. Full **`~/src` portfolio run** + skim as new dev (guide section 2)
3. Optional **LLM enrichment** sample then full run
4. **CI** — GitHub Actions `uv sync --extra dev && uv run pytest -q`
5. **Incremental rescan** (only repos whose git HEAD changed)
6. infomux: SDXL WIP may still be on `feature/sdxl-image-generation-step` with stash `wip-sdxl` (separate repo)

## Key commands

```bash
uv run repocon ~/src --output ./reports --export-bear --no-open
uv pip install -e ~/src/infomux   # optional Bear backend
```

Guide: `docs/onboarding-new-dev.md`

Delivery handoff: `docs/delivery/2026-05-21-pause-handoff.md`
