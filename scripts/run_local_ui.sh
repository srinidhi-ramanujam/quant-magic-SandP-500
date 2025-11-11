#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_HOST="0.0.0.0"
API_PORT="${API_PORT:-8000}"
UI_HOST="0.0.0.0"
UI_PORT="${UI_PORT:-5173}"
LOG_ROOT="${ROOT_DIR}/.logs"
SESSION_ID="session-$(date +%Y%m%d-%H%M%S)"
SESSION_DIR="${LOG_ROOT}/${SESSION_ID}"
SESSION_LOG_FILE="${SESSION_DIR}/requests.jsonl"

echo "📦 Starting Quant Magic dev stack from ${ROOT_DIR}"

if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  echo "❌ Missing virtual environment (.venv). Run 'python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt' first."
  exit 1
fi

source "${ROOT_DIR}/.venv/bin/activate"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "❌ uvicorn not available in the virtual environment. Run 'pip install -r requirements.txt'."
  exit 1
fi

if [[ ! -d "${ROOT_DIR}/frontend/node_modules" ]]; then
  echo "📥 Installing frontend dependencies..."
  (cd "${ROOT_DIR}/frontend" && npm install)
fi

rm -rf "${LOG_ROOT}"
mkdir -p "${SESSION_DIR}"
export SESSION_LOG_FILE
export SESSION_LOG_DIR="${SESSION_DIR}"

API_LOG="${SESSION_DIR}/api.log"
UI_LOG="${SESSION_DIR}/ui.log"

echo "🗂  Session logs will be stored in ${SESSION_DIR}"

cleanup() {
  echo ""
  echo "🛑 Shutting down dev stack..."
  [[ -n "${API_PID:-}" ]] && kill "${API_PID}" >/dev/null 2>&1 || true
  [[ -n "${UI_PID:-}" ]] && kill "${UI_PID}" >/dev/null 2>&1 || true
  rm -rf "${LOG_ROOT}"
  echo "🧹 Cleared session logs"
}

trap cleanup EXIT INT TERM

echo "🚀 Starting FastAPI server on http://${API_HOST}:${API_PORT}"
(cd "${ROOT_DIR}" && uvicorn src.api.app:app --host "${API_HOST}" --port "${API_PORT}" | tee "${API_LOG}") &
API_PID=$!

echo "💻 Starting Vite dev server on http://localhost:${UI_PORT}"
(cd "${ROOT_DIR}/frontend" && npm run dev -- --host "${UI_HOST}" --port "${UI_PORT}" | tee "${UI_LOG}") &
UI_PID=$!

echo ""
echo "✅ Dev stack is running:"
echo "   API → http://localhost:${API_PORT}"
echo "   UI  → http://localhost:${UI_PORT}"
echo ""
echo "Press Ctrl+C to stop both services."

wait
