#!/usr/bin/env bash
# Run repocon with Ollama on nakedsnake via a local SSH tunnel.
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-nakedsnake}"
OLLAMA_TUNNEL_PORT="${OLLAMA_TUNNEL_PORT:-11435}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b-instruct}"
SOURCE_DIR="${SOURCE_DIR:-$HOME/src}"
OUTPUT_DIR="${OUTPUT_DIR:-./reports-ollama}"
LLM_MAX_PROJECTS="${LLM_MAX_PROJECTS:-5}"

TUNNEL_PID=""

cleanup() {
  if [[ -n "${TUNNEL_PID}" ]] && kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    kill "${TUNNEL_PID}" 2>/dev/null || true
    wait "${TUNNEL_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v repocon >/dev/null 2>&1; then
  REPOCON=(repocon)
else
  REPOCON=(python3 -m repocon)
  export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
fi

export OLLAMA_MODEL

ollama_ready() {
  curl -sf -m 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1
}

if [[ -z "${OLLAMA_BASE_URL:-}" ]]; then
  export OLLAMA_BASE_URL="http://127.0.0.1:${OLLAMA_TUNNEL_PORT}"

  if ! ollama_ready; then
    echo "Starting SSH tunnel: localhost:${OLLAMA_TUNNEL_PORT} -> ${OLLAMA_HOST}:11434"
    ssh -N -L "${OLLAMA_TUNNEL_PORT}:127.0.0.1:11434" "${OLLAMA_HOST}" &
    TUNNEL_PID=$!

    for _ in $(seq 1 20); do
      if ollama_ready; then
        break
      fi
      sleep 0.5
    done

    if ! ollama_ready; then
      echo "error: Ollama not reachable at ${OLLAMA_BASE_URL} after starting tunnel" >&2
      exit 1
    fi
  fi
fi

echo "Using Ollama at ${OLLAMA_BASE_URL} with model ${OLLAMA_MODEL}"

exec "${REPOCON[@]}" "${SOURCE_DIR}" \
  --output "${OUTPUT_DIR}" \
  --llm-provider ollama \
  --llm-max-projects "${LLM_MAX_PROJECTS}" \
  "$@"
