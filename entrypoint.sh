#!/bin/bash

# Entrypoint script for the code modification agent

# If WORKSPACE environment variable is set, use it; otherwise use /workspace
WORKSPACE_DIR=${WORKSPACE:-/workspace}

# Change to workspace directory if it exists
if [ -d "$WORKSPACE_DIR" ]; then
    cd "$WORKSPACE_DIR" || exit 1
else
    echo "Warning: Workspace directory '$WORKSPACE_DIR' does not exist. Using /app"
    cd /app || exit 1
fi

# Set PYTHONPATH to include /app so imports work
export PYTHONPATH=/app:$PYTHONPATH

# If arguments are provided, run the agent with them
if [ $# -gt 0 ]; then
    python /app/agent.py "$@"
else
    # Otherwise, start the interactive CLI
    python /app/cli.py
fi

