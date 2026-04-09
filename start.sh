#!/bin/sh
# Load credentials from .env and start the MCP server
set -e
ENV_FILE="$(dirname "$0")/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi
exec node "$(dirname "$0")/dist/index.js"
