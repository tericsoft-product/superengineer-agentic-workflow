#!/bin/zsh
# Starter script for Code Modification Agent with Gemini

# Configuration
WORKSPACE="/Users/saicharan/Documents/Cline"
LLM_PROVIDER="gemini"
GOOGLE_API_KEY="AIzaSyBd3ujavpnxET0KCFJhEAVjcXWYcTLw-iw"

# Run the Docker container
docker run -it --rm \
  -v "$WORKSPACE:/workspace" \
  -e LLM_PROVIDER="$LLM_PROVIDER" \
  -e GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  code-mod-agent

