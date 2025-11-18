#!/bin/bash

# Example script to test the simple backend

# Health check
echo "=== Health Check ==="
curl http://localhost:3000/health
echo -e "\n\n"

# Execute a simple task
echo "=== Executing Task ==="
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all files in the current directory",
    "cwd": "/tmp"
  }' | jq '.'

echo -e "\n\n"

# Example with session continuation (replace SESSION_ID with actual session ID from previous response)
# echo "=== Continuing Session ==="
# curl -X POST http://localhost:3000/execute \
#   -H "Content-Type: application/json" \
#   -d '{
#     "message": "Now create a test file",
#     "cwd": "/tmp",
#     "sessionId": "SESSION_ID"
#   }' | jq '.'

