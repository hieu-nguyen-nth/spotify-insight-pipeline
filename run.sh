#!/bin/sh
set -eu
pipeline_python="${SPOTIFY_PYTHON:-python3}"
if [ -z "${SPOTIFY_PYTHON:-}" ] && [ -x "$(dirname "$0")/.venv/bin/python" ]; then
  pipeline_python="$(dirname "$0")/.venv/bin/python"
fi
if ! "$pipeline_python" -c 'import sys; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Set SPOTIFY_PYTHON to its executable path." >&2
  exit 1
fi
exec "$pipeline_python" "$(dirname "$0")/pipeline.py" "$@"
