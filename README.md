# Code Modification Agent

An intelligent agent built with LangGraph that can programmatically modify code files in a containerized environment. The agent uses tool calling to search, read, and modify files based on natural language instructions.

## Features

- **Intelligent Code Search**: Find code patterns using regex or plain text
- **File Operations**: Read, write, and modify files programmatically
- **Context-Aware**: Understands file structure and code context before making changes
- **Containerized**: Runs in Docker for isolated execution
- **Tool-Based Architecture**: Uses LangGraph agent pattern with specialized tools
- **Multi-LLM Support**: Works with both Claude (Anthropic) and Gemini (Google) models
- **Token Tracking**: Monitors input/output tokens for cost tracking

## Architecture

The agent follows the LangGraph agent pattern:
- **Agent Node**: Decides which tools to use based on the task
- **Tool Node**: Executes file operations (search, read, write, replace)
- **Feedback Loop**: Continues until the task is complete

## Available Tools

1. `list_files` - List files in a directory
2. `search_code` - Search for code patterns using regex
3. `read_file` - Read file contents
4. `write_file` - Write content to files
5. `replace_in_file` - Replace text in files
6. `get_file_info` - Get file metadata
7. `find_files_by_content` - Find files containing specific text

## Setup

### Prerequisites

- Docker installed
- API key for your chosen LLM provider:
  - Anthropic API key (for Claude) - Get it from https://console.anthropic.com/
  - Google AI API key (for Gemini) - Get it from https://aistudio.google.com/app/apikey

### Build the Docker Image

```bash
docker build -t code-mod-agent .
```

### Run the Agent

#### Option 1: Direct Command

**Using Claude (default):**
```bash
docker run -it --rm \
  -v /path/to/your/code:/workspace \
  -e ANTHROPIC_API_KEY=your_api_key \
  code-mod-agent \
  "Change the background color to #ffffff in all CSS files"
```

**Using Gemini:**
```bash
docker run -it --rm \
  -v /path/to/your/code:/workspace \
  -e LLM_PROVIDER=gemini \
  -e GOOGLE_API_KEY=your_google_api_key \
  code-mod-agent \
  "Change the background color to #ffffff in all CSS files"
```

#### Option 2: Interactive CLI Mode

**Using Claude (default):**
```bash
docker run -it --rm \
  -v /path/to/your/code:/workspace \
  -e ANTHROPIC_API_KEY=your_api_key \
  code-mod-agent
```

**Using Gemini:**
```bash
docker run -it --rm \
  -v /path/to/your/code:/workspace \
  -e LLM_PROVIDER=gemini \
  -e GOOGLE_API_KEY=your_google_api_key \
  code-mod-agent
```

Once started, you'll see a `clin>` prompt. Simply type your commands:

```
clin> change the color to blue
clin> find all CSS files and update background-color
clin> clin replace 'old_api' with 'new_api'
```

You can prefix commands with `clin` or not - both work! Type `help` for more info, or `exit` to quit.

#### Option 3: Using the Helper Script (Recommended)

To avoid volume mount syntax errors, use the provided helper script:

```bash
# Set your API keys
export LLM_PROVIDER=gemini
export GOOGLE_API_KEY=your_google_api_key

# Run with current directory as workspace
./run_docker.sh

# Or specify a different workspace directory
./run_docker.sh /path/to/your/code
```

The script automatically handles the correct volume mount syntax (`host_path:/workspace`).

#### Option 4: Using docker-compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  agent:
    build: .
    volumes:
      - ./target_code:/workspace
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    stdin_open: true
    tty: true
```

Then run:
```bash
# Single command mode
docker-compose run agent "Your instruction here"

# Interactive CLI mode (no arguments)
docker-compose run agent
```

## Usage Examples

### Example 1: Change Background Color

```bash
docker run -it --rm \
  -v /path/to/project:/workspace \
  -e ANTHROPIC_API_KEY=your_key \
  code-mod-agent \
  "Find all CSS files and change background-color to #f0f0f0"
```

### Example 2: Update API Endpoints

```bash
docker run -it --rm \
  -v /path/to/project:/workspace \
  -e ANTHROPIC_API_KEY=your_key \
  code-mod-agent \
  "Replace all occurrences of 'api.old.com' with 'api.new.com' in JavaScript files"
```

### Example 3: Refactor Function Names

```bash
docker run -it --rm \
  -v /path/to/project:/workspace \
  -e ANTHROPIC_API_KEY=your_key \
  code-mod-agent \
  "Rename all instances of 'oldFunctionName' to 'newFunctionName' in Python files"
```

## How It Works

1. **User provides instruction** (e.g., "Change background color")
2. **Agent searches** for relevant code patterns using `search_code` or `find_files_by_content`
3. **Agent reads files** to understand context using `read_file`
4. **Agent makes changes** using `replace_in_file` or `write_file`
5. **Agent verifies** by reading modified files if needed
6. **Agent responds** with summary of changes made

## Workflow Pattern

The agent uses the **Agent Pattern** from LangGraph:
- Continuous feedback loop
- Tool calling for file operations
- Autonomous decision making
- Context-aware modifications

## Environment Variables

### LLM Provider Selection
- `LLM_PROVIDER`: Optional. Choose the LLM provider (default: "claude")
  - `"claude"` or `"anthropic"`: Use Claude (Anthropic)
  - `"gemini"` or `"google"`: Use Gemini (Google)

### Claude/Anthropic Settings
- `ANTHROPIC_API_KEY`: Required if using Claude. Your Anthropic API key
- `CLAUDE_MODEL`: Optional. Claude model name (default: "claude-sonnet-4-5-20250929")

### Gemini/Google Settings
- `GOOGLE_API_KEY`: Required if using Gemini. Your Google AI API key
- `GEMINI_MODEL`: Optional. Gemini model name (default: "gemini-2.0-flash-exp")

### General Settings
- `WORKSPACE`: Optional. Override default workspace directory (/workspace)

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set API key:
```bash
export ANTHROPIC_API_KEY=your_key
```

3. Run agent:
```bash
# Single command mode
python agent.py "Your instruction"

# Interactive CLI mode
python cli.py

# Or run CLI with a single command
python cli.py "change the color to blue"
```

### Testing

Test the agent with sample code:

```bash
# Create a test directory
mkdir test_project
cd test_project

# Create a sample CSS file
echo "body { background-color: #000000; }" > style.css

# Run agent to change background color
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_key \
  code-mod-agent \
  "Change background-color to #ffffff in style.css"
```

## Troubleshooting

### Docker Build Permission Error

If you see an error like:
```
ERROR: stat /Users/username/.docker/buildx/refs/desktop-linux/desktop-linux: permission denied
```

**Quick Fix**: Build without BuildKit:
```bash
DOCKER_BUILDKIT=0 docker build -t code-mod-agent .
```

Or use the provided build script:
```bash
./build.sh
```

**Proper Fix**: Fix Docker permissions (requires sudo):
```bash
sudo chown -R $(whoami):staff ~/.docker
```

Alternatively, restart Docker Desktop which often resolves permission issues.

### Agent can't find files / Files not persisting
- **CRITICAL**: The volume mount syntax must be `host_path:container_path`
  - ✅ Correct: `-v /path/to/code:/workspace`
  - ❌ Wrong: `-v /path/to/code` (missing container path)
- The container path must be `/workspace` (this is where files are created)
- Make sure you've mounted the correct directory with `-v`
- Check that files exist in the mounted directory

### API key errors
- Ensure `ANTHROPIC_API_KEY` is set correctly
- Check that your API key is valid

### Permission errors
- Ensure Docker has read/write access to the mounted directory
- On Linux/Mac, you may need to adjust file permissions

## Limitations

- The agent works best with text-based files (code, config, etc.)
- Binary files are not supported
- Large codebases may take time to search
- Always review changes before committing

## Safety

- The agent makes direct file modifications
- Always use version control (git) when running the agent
- Test in a separate branch or copy of your code
- Review all changes before deploying

## License

MIT

