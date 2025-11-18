#!/bin/zsh
# Starter script for Code Modification Agent with Gemini and Serena MCP

# Configuration
WORKSPACE="/Users/saicharan/Documents/GitHub/superengineer-frontend-v3"
LLM_PROVIDER="gemini"
GOOGLE_API_KEY="AIzaSyAFNRUEUIFT0Z7JFKPtJh9gQ5wdeZ7tQDA"

# Serena MCP Configuration
ENABLE_SERENA_MCP="true"
SERENA_CONTEXT="agent"  # Options: agent, ide-assistant, codex
SERENA_PROJECT_DIR="/Users/saicharan/Documents/GitHub/superengineer-frontend-v3"
UVX_PATH="uvx"  # Path to uvx executable (default: uvx)

# Run the Docker container
docker run -it --rm \
  -v "$WORKSPACE:/workspace" \
  -e LLM_PROVIDER="$LLM_PROVIDER" \
  -e GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  -e ENABLE_SERENA_MCP="$ENABLE_SERENA_MCP" \
  -e SERENA_CONTEXT="$SERENA_CONTEXT" \
  -e SERENA_PROJECT_DIR="$SERENA_PROJECT_DIR" \
  -e UVX_PATH="$UVX_PATH" \
  code-mod-agent

