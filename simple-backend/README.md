# Simple Claude Code Backend

A simplified backend server for executing Claude Code tasks. This is a minimal version extracted from the full claude-code-viewer project.

## Features

- Single POST endpoint to execute tasks
- Waits for task completion and returns the result
- No UI dependencies - pure backend API
- Simple HTTP interface

## Prerequisites

- Node.js >= 20.19.0
- Claude Code CLI installed (via `@anthropic-ai/claude-code` package or system PATH)

## Installation

```bash
cd simple-backend
pnpm install
# or
npm install
```

## Usage

### Start the server

```bash
pnpm start
# or
npm start
```

The server will start on `http://localhost:3000` by default (configurable via `PORT` environment variable).

### Execute a task

Send a POST request to `/execute`:

```bash
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a hello world file",
    "cwd": "/path/to/your/project"
  }'
```

### Request Body

```json
{
  "message": "string (required) - The task message to execute",
  "cwd": "string (optional) - Working directory (defaults to process.cwd())",
  "sessionId": "string (optional) - Session ID to resume (for continuing a previous session)"
}
```

### Response

```json
{
  "success": true,
  "sessionId": "session-id-from-execution",
  "result": {
    "type": "result",
    "session_id": "...",
    "result": "..."
  },
  "messageCount": 10,
  "messages": [
    {
      "type": "system",
      "subtype": "init",
      "session_id": "..."
    },
    {
      "type": "assistant",
      "content": "..."
    },
    {
      "type": "result",
      "result": "..."
    }
  ]
}
```

### Health Check

```bash
curl http://localhost:3000/health
```

## Environment Variables

- `PORT` - Server port (default: 3000)
- `CLAUDE_CODE_VIEWER_CC_EXECUTABLE_PATH` - Path to Claude Code executable (optional, will auto-detect)
- `NODE_ENV` - Set to "development" for detailed error stacks

## Example

```bash
# Start server
pnpm start

# In another terminal, execute a task
curl -X POST http://localhost:3000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List all files in the current directory",
    "cwd": "/tmp"
  }'
```

## How it works

1. Receives a POST request with a message
2. Executes the task using Claude Code SDK in the specified working directory
3. Waits for all messages to be processed
4. Returns the final result along with all messages

The backend uses the same Claude Code execution logic as the full application but without the complex state management, UI, and Effect framework dependencies.

