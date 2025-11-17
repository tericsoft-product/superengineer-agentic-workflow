# Serena Tools Integration

This document explains how to use Serena tools with the LangGraph agent.

## Overview

**Serena tools are now mandatory** - the agent requires Serena tools to function. All custom base tools have been removed, and the agent exclusively uses tools provided by your Serena agent configuration.

## Setup

### 1. Install Serena Dependencies

**Required dependencies** must be installed:

```bash
pip install python-dotenv
# Install serena and sensai packages from your source
```

### 2. Configure Environment Variables

Set the following environment variables:

```bash
# Optional: Specify Serena project file
export SERENA_PROJECT_FILE=/path/to/project.yml
```

**Note**: `USE_SERENA_TOOLS` is no longer needed - Serena tools are always loaded.

### 3. Run the Agent

The agent will automatically load Serena tools on startup:

```bash
python agent.py "Your instruction here"
```

Or in Docker:

```bash
docker run -it --rm \
  -v /path/to/your/code:/workspace \
  -e ANTHROPIC_API_KEY=your_api_key \
  -e SERENA_PROJECT_FILE=/path/to/project.yml \
  code-mod-agent \
  "Your instruction here"
```

## How It Works

1. **Tool Loading**: The agent:
   - Initializes the Serena agent (singleton pattern)
   - Retrieves all exposed Serena tool instances
   - Converts each Serena tool to LangChain-compatible format
   - Uses only Serena tools (no base tools)

2. **Tool Execution**: Serena tools are executed through the LangGraph tool node.

3. **System Prompt**: The agent uses Serena's system prompt exclusively (no default fallback).

## Available Tools

On startup, you'll see a message like:
```
✅ Loaded N Serena tools
```

The exact tools available depend entirely on your Serena agent configuration. Only tools exposed by your Serena agent will be available.

## Troubleshooting

### Serena tools not loading

- **Required**: Verify Serena dependencies are installed
- Check that `SERENA_PROJECT_FILE` points to a valid project file (if specified)
- Ensure your Serena agent configuration exposes tools
- Look for error messages in the console output

### Import errors

If you see import errors, ensure all **required** packages are installed:
- `serena`
- `sensai`
- `python-dotenv`

The agent will fail to start if these dependencies are missing.

### Tool execution errors

Serena tools will catch exceptions and return error messages. Check the tool output for details about what went wrong.

### No tools available

If you see "No Serena tools were loaded", ensure:
- Your Serena agent is properly configured
- Your Serena agent exposes tools via `get_exposed_tool_instances()`
- The project file (if specified) is valid

## Code Structure

- `serena_tools.py`: Handles Serena agent initialization and tool conversion
- `agent.py`: Integrates Serena tools into the LangGraph agent workflow

**Important**: The agent requires Serena tools to function. It will fail to start if:
- Serena dependencies are not installed
- No tools can be loaded from the Serena agent
- The system prompt cannot be retrieved from Serena

