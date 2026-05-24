#!/bin/sh
set -e

# Download spaCy model on first run (too large for Docker build layer).
# The check is fast (~0.1s). Download only happens when model is absent.
if ! python -c "import en_core_web_lg" 2>/dev/null; then
    echo "[entrypoint] spaCy model en_core_web_lg not found — downloading (~400MB)..."
    python -m spacy download en_core_web_lg
    echo "[entrypoint] spaCy model ready."
fi

exec "$@"
