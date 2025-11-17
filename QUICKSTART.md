# Quick Start Guide

## Prerequisites

1. Docker installed and running
2. Anthropic API key

## Step 1: Build the Docker Image

```bash
docker build -t code-mod-agent .
```

## Step 2: Prepare Your Code

Create a directory with your code that you want to modify:

```bash
mkdir my_project
cd my_project
# Add your code files here
```

## Step 3: Run the Agent

### Basic Usage

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_api_key_here \
  code-mod-agent \
  "Change the background color to #ffffff in all CSS files"
```

### Example: Change Background Color

```bash
# Create a test CSS file
echo "body { background-color: #000000; color: white; }" > style.css

# Run agent to change background color
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_api_key_here \
  code-mod-agent \
  "Change background-color to #f0f0f0 in style.css"
```

### Example: Replace API URLs

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_api_key_here \
  code-mod-agent \
  "Replace all occurrences of 'api.old.com' with 'api.new.com' in JavaScript files"
```

### Example: Rename Functions

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_api_key_here \
  code-mod-agent \
  "Rename all instances of 'oldFunction' to 'newFunction' in Python files"
```

## Step 4: Interactive Mode

For multiple commands, use interactive mode:

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ANTHROPIC_API_KEY=your_api_key_here \
  code-mod-agent
```

Then in the Python shell:

```python
from agent import run_agent

# Change background color
result = run_agent("Change background-color to blue in CSS files")

# Replace text
result = run_agent("Replace 'old' with 'new' in all files")

# Search and modify
result = run_agent("Find all instances of 'TODO' and add a comment above them")
```

## Using Docker Compose

1. Create a `.env` file:
```
ANTHROPIC_API_KEY=your_api_key_here
```

2. Update `docker-compose.yml` to point to your code directory:
```yaml
volumes:
  - /path/to/your/code:/workspace
```

3. Run:
```bash
docker-compose run agent "Your instruction here"
```

## Tips

1. **Always use version control**: The agent makes direct file modifications
   ```bash
   git init
   git add .
   git commit -m "Before agent modifications"
   ```

2. **Test in a copy first**: 
   ```bash
   cp -r my_project my_project_backup
   ```

3. **Be specific**: More specific instructions lead to better results
   - ✅ Good: "Change background-color to #ffffff in all CSS files"
   - ❌ Less clear: "Change colors"

4. **Review changes**: Always review the agent's changes before committing

## Troubleshooting

### Agent can't find files
- Make sure you've mounted the correct directory with `-v`
- Check that files exist in the mounted directory

### API key errors
- Ensure `ANTHROPIC_API_KEY` is set correctly
- Check that your API key is valid

### Permission errors
- Ensure Docker has read/write access to the mounted directory
- On Linux/Mac, you may need to adjust file permissions

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [example_usage.py](example_usage.py) for more examples
- Customize tools in [tools.py](tools.py) for your specific needs

