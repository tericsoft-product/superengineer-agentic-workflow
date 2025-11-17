#!/bin/bash
# Build script that works around Docker permission issues

# Build without BuildKit to avoid permission issues
DOCKER_BUILDKIT=0 docker build -t code-mod-agent .

