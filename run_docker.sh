#!/bin/bash
# Helper script to run the code modification agent in Docker

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default to script directory as workspace
WORKSPACE_DIR="${1:-$SCRIPT_DIR}"

# Check if workspace directory exists
if [ ! -d "$WORKSPACE_DIR" ]; then
    echo "Error: Workspace directory '$WORKSPACE_DIR' does not exist"
    exit 1
fi

# Get absolute path
WORKSPACE_DIR="$(cd "$WORKSPACE_DIR" && pwd)"

echo "🚀 Starting Code Modification Agent"
echo "📁 Workspace: $WORKSPACE_DIR"
echo ""

# Check for API keys
if [ -z "$LLM_PROVIDER" ] || [ "$LLM_PROVIDER" = "claude" ] || [ -z "$LLM_PROVIDER" ]; then
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "⚠️  Warning: ANTHROPIC_API_KEY not set. Set it with:"
        echo "   export ANTHROPIC_API_KEY=your_key"
        echo ""
    fi
fi

if [ "$LLM_PROVIDER" = "gemini" ] || [ "$LLM_PROVIDER" = "google" ]; then
    if [ -z "$GOOGLE_API_KEY" ]; then
        echo "⚠️  Warning: GOOGLE_API_KEY not set. Set it with:"
        echo "   export GOOGLE_API_KEY=your_key"
        echo ""
    fi
fi

# Build docker command
DOCKER_CMD="docker run -it --rm"

# Mount workspace volume (CRITICAL: must include :/workspace)
DOCKER_CMD="$DOCKER_CMD -v $WORKSPACE_DIR:/workspace"

# Add environment variables
if [ -n "$ANTHROPIC_API_KEY" ]; then
    DOCKER_CMD="$DOCKER_CMD -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
fi

if [ -n "$LLM_PROVIDER" ]; then
    DOCKER_CMD="$DOCKER_CMD -e LLM_PROVIDER=$LLM_PROVIDER"
fi

if [ -n "$GOOGLE_API_KEY" ]; then
    DOCKER_CMD="$DOCKER_CMD -e GOOGLE_API_KEY=$GOOGLE_API_KEY"
fi

# Add image name
DOCKER_CMD="$DOCKER_CMD code-mod-agent"

# Add any additional arguments (for passing commands directly)
if [ $# -gt 1 ]; then
    shift
    DOCKER_CMD="$DOCKER_CMD \"$@\""
fi

# Execute the command
eval $DOCKER_CMD

