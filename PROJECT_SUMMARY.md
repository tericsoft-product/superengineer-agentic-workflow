# Project Summary: Code Modification Agent

## Overview

A containerized LangGraph-based agent that can programmatically modify code files based on natural language instructions. The agent uses the **Agent Pattern** from LangGraph documentation, implementing a continuous feedback loop with tool calling.

## Architecture

### Agent Pattern Implementation

Following the LangGraph agent pattern:
- **Agent Node**: LLM decides which tools to use
- **Tool Node**: Executes file operations
- **Feedback Loop**: Continues until task completion

```
User Query → Agent Node → Tool Calls → Tool Execution → Agent Node → ... → Final Answer
```

### Core Components

1. **agent.py**: Main agent implementation using LangGraph
   - Uses `MessagesState` for conversation state
   - Implements `agent_node` and `tool_node`
   - Conditional edges for tool calling loop

2. **tools.py**: File operation tools
   - `list_files`: List directory contents
   - `search_code`: Regex/pattern search
   - `read_file`: Read file contents
   - `write_file`: Write to files
   - `replace_in_file`: Replace text in files
   - `get_file_info`: File metadata
   - `find_files_by_content`: Find files containing text

3. **Dockerfile**: Container setup
   - Python 3.11 base image
   - Installs dependencies
   - Sets up workspace directory

4. **entrypoint.sh**: Container entrypoint
   - Handles command-line and interactive modes
   - Manages workspace directory

## Key Features

✅ **Intelligent Search**: Uses regex and pattern matching to find code  
✅ **Context-Aware**: Reads files before modifying  
✅ **Safe Operations**: Can verify changes  
✅ **Containerized**: Isolated execution environment  
✅ **Tool-Based**: Extensible tool architecture  

## Workflow Example: Changing Background Color

1. User: "Change background color to #ffffff in CSS files"
2. Agent searches for CSS files using `find_files_by_content` or `list_files`
3. Agent searches for background-color patterns using `search_code`
4. Agent reads relevant files using `read_file` to understand context
5. Agent replaces background-color values using `replace_in_file`
6. Agent verifies changes (optional)
7. Agent reports completion

## File Structure

```
superengineer/
├── agent.py              # Main agent implementation
├── tools.py              # File operation tools
├── Dockerfile            # Container definition
├── entrypoint.sh         # Container entrypoint
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Docker Compose config
├── README.md             # Full documentation
├── QUICKSTART.md         # Quick start guide
├── example_usage.py      # Usage examples
├── .dockerignore         # Docker ignore patterns
└── .gitignore           # Git ignore patterns
```

## Usage Patterns

### Pattern 1: Direct Command
```bash
docker run -it --rm \
  -v /path/to/code:/workspace \
  -e ANTHROPIC_API_KEY=key \
  code-mod-agent \
  "Change background color to #ffffff"
```

### Pattern 2: Interactive Mode
```bash
docker run -it --rm \
  -v /path/to/code:/workspace \
  -e ANTHROPIC_API_KEY=key \
  code-mod-agent
```

### Pattern 3: Programmatic
```python
from agent import run_agent
result = run_agent("Change background color to blue")
```

## Agent Decision Making

The agent follows this decision process:

1. **Understand Task**: Parse user instruction
2. **Plan Approach**: Decide which tools to use
3. **Search**: Find relevant files and code patterns
4. **Read**: Understand context
5. **Modify**: Make changes
6. **Verify**: Check if task is complete
7. **Respond**: Report results

## Tool Selection Strategy

The agent intelligently selects tools based on the task:

- **Finding files**: `list_files`, `find_files_by_content`
- **Searching code**: `search_code`
- **Understanding context**: `read_file`, `get_file_info`
- **Making changes**: `replace_in_file`, `write_file`

## Extensibility

### Adding New Tools

1. Create tool function in `tools.py`:
```python
@tool
def my_new_tool(param: str) -> str:
    """Tool description."""
    # Implementation
    return result
```

2. Add to tools list in `agent.py`:
```python
tools = [
    # ... existing tools
    my_new_tool,
]
```

### Customizing Agent Behavior

Modify the system message in `agent_node()` function to change agent behavior.

## Best Practices

1. **Version Control**: Always use git before running agent
2. **Test First**: Test on a copy of your code
3. **Be Specific**: Clear instructions = better results
4. **Review Changes**: Always review agent modifications
5. **Iterative**: Break complex tasks into smaller ones

## Performance Considerations

- **Search Optimization**: Agent limits results to prevent overwhelming output
- **File Reading**: Only reads necessary files
- **Parallel Operations**: Can be extended for parallel file operations
- **Caching**: Consider adding caching for large codebases

## Security

- **Container Isolation**: Code runs in isolated container
- **File Permissions**: Respects file system permissions
- **API Key**: Use environment variables, never hardcode
- **Input Validation**: Tools validate file paths

## Future Enhancements

Potential improvements:
- [ ] Add undo/rollback functionality
- [ ] Support for batch operations
- [ ] Progress tracking for large codebases
- [ ] Integration with version control (git)
- [ ] Multi-file refactoring support
- [ ] Code quality checks before/after
- [ ] Backup creation before modifications

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools/)
- [Agent Patterns](https://langchain-ai.github.io/langgraph/how-tos/workflows-agents/)

