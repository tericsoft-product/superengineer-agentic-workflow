"""Code modification agent using LangGraph."""

import os
import getpass
import asyncio
from typing import Literal, TypedDict, Annotated, Optional, List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages

# Try importing Gemini, but make it optional
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from IPython.display import Image, display
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

# Try importing MCP support, but make it optional
try:
    from mcp_use import MCPClient
    from mcp_use.adapters import LangChainAdapter
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    MCPClient = None
    LangChainAdapter = None

from tools import (
    list_files,
    search_code,
    read_file,
    write_file,
    replace_in_file,
    get_file_info,
    find_files_by_content,
)


# Custom state that includes token usage
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    token_usage: dict


def _set_env(var: str):
    """Set environment variable if not already set."""
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


def initialize_llm():
    """Initialize the LLM based on LLM_PROVIDER environment variable.
    
    Supports:
    - 'claude' or 'anthropic' (default): Uses Claude via ChatAnthropic
    - 'gemini' or 'google': Uses Gemini via ChatGoogleGenerativeAI
    
    Returns:
        Initialized LLM instance
    """
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    
    if provider in ["gemini", "google"]:
        if not HAS_GEMINI:
            raise ImportError(
                "Gemini support requires langchain-google-genai. "
                "Install it with: pip install langchain-google-genai"
            )
        
        # Set up Gemini API key
        _set_env("GOOGLE_API_KEY")
        
        # Get model name from env or use default
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        
        print(f"🤖 Using Gemini model: {model_name}")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            convert_system_message_to_human=True  # Gemini needs this
        )
    
    else:  # Default to Claude
        # Set up Anthropic API key
        _set_env("ANTHROPIC_API_KEY")
        
        # Get model name from env or use default
        model_name = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        
        print(f"🤖 Using Claude model: {model_name}")
        return ChatAnthropic(model=model_name)


# Initialize LLM
llm = initialize_llm()

# Define all available tools
tools = [
    list_files,
    search_code,
    read_file,
    write_file,
    replace_in_file,
    get_file_info,
    find_files_by_content,
]

# MCP client and tools (initialized lazily)
_mcp_client: Optional[MCPClient] = None
_mcp_tools: List = []


async def initialize_serena_mcp():
    """Initialize Serena MCP server and get its tools.
    
    Returns:
        List of LangChain tools from Serena MCP server
    """
    if not HAS_MCP:
        print("⚠️  MCP support not available. Install with: pip install mcp-use")
        return []
    
    try:
        # Check if Serena MCP is enabled (default: True)
        if os.environ.get("ENABLE_SERENA_MCP", "true").lower() == "false":
            print("ℹ️  Serena MCP is disabled (set ENABLE_SERENA_MCP=false to disable)")
            return []
        
        # Get project directory (default: current working directory)
        project_dir = os.environ.get("SERENA_PROJECT_DIR", os.getcwd())
        
        # Get context (default: agent)
        context = os.environ.get("SERENA_CONTEXT", "agent")
        
        # Get uvx path (default: uvx)
        uvx_path = os.environ.get("UVX_PATH", "uvx")
        
        print(f"🔌 Initializing Serena MCP server (context: {context}, project: {project_dir})...")
        
        # Configure Serena MCP server
        config = {
            "mcpServers": {
                "serena": {
                    "command": uvx_path,
                    "args": [
                        "--from",
                        "git+https://github.com/oraios/serena",
                        "serena",
                        "start-mcp-server",
                        "--context",
                        context,
                        "--project",
                        project_dir
                    ],
                    "env": {}
                }
            }
        }
        
        # Create MCP client
        global _mcp_client
        _mcp_client = MCPClient.from_dict(config)
        
        # Create adapter and get tools
        adapter = LangChainAdapter()
        mcp_tools = await adapter.create_tools(_mcp_client)
        
        print(f"✅ Serena MCP initialized with {len(mcp_tools)} tools")
        return mcp_tools
        
    except Exception as e:
        print(f"⚠️  Failed to initialize Serena MCP: {str(e)}")
        print("   Continuing without MCP tools...")
        return []


def get_all_tools():
    """Get all tools including MCP tools if available."""
    return tools + _mcp_tools


# Initialize MCP tools asynchronously (will be done on first use)
async def ensure_mcp_initialized():
    """Ensure MCP tools are initialized."""
    global _mcp_tools
    if not _mcp_tools and HAS_MCP:
        _mcp_tools = await initialize_serena_mcp()
        # Update tool lookup and bind tools to LLM
        global tools_by_name, llm_with_tools
        all_tools = get_all_tools()
        tools_by_name = {tool.name: tool for tool in all_tools}
        llm_with_tools = llm.bind_tools(all_tools)


# Initialize MCP tools synchronously for immediate use
# This will run in a new event loop if needed
def sync_ensure_mcp_initialized():
    """Synchronously ensure MCP tools are initialized."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, we can't use it
            # MCP tools will be initialized on first async call
            return
    except RuntimeError:
        # No event loop exists, create one
        pass
    
    try:
        asyncio.run(ensure_mcp_initialized())
    except Exception as e:
        print(f"⚠️  Could not initialize MCP tools synchronously: {e}")


# Create tool lookup dictionary
tools_by_name = {tool.name: tool for tool in tools}

# Bind tools to LLM (will be updated when MCP tools are loaded)
llm_with_tools = llm.bind_tools(tools)


async def agent_node(state: AgentState):
    """Agent node that decides which tool to call or provides final answer."""
    # Ensure MCP tools are initialized before using LLM
    await ensure_mcp_initialized()
    
    messages = state["messages"]
    
    # Track token usage
    token_usage = state.get("token_usage", {"input_tokens": 0, "output_tokens": 0})
    
    # Add system message if it's the first message
    if len(messages) == 1 and isinstance(messages[0], HumanMessage):
        system_msg = SystemMessage(
            content="""You are a helpful code modification agent. Your task is to:
1. Understand user requests for code changes
2. Search for relevant code patterns using the available tools
3. Read files to understand context
4. Make precise modifications to files
5. Verify changes when appropriate

When modifying code:
- Always search first to find all relevant occurrences
- Read files to understand context before making changes
- Make precise replacements that preserve code structure
- Consider file types (CSS, JS, Python, etc.) when searching

Be thorough and methodical. Always search before making changes."""
        )
        response = llm_with_tools.invoke([system_msg] + messages)
    else:
        response = llm_with_tools.invoke(messages)
    
    # Extract token usage from response
    # Different providers structure token usage differently
    usage = None
    
    # Method 1: Check response_metadata (Claude and some Gemini versions)
    if hasattr(response, 'response_metadata') and response.response_metadata:
        usage = response.response_metadata.get('usage', {})
    
    # Method 2: Check usage_metadata (Gemini)
    if not usage and hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
    
    # Method 3: Check if usage is directly on response
    if not usage and hasattr(response, 'usage'):
        usage = response.usage
    
    # Extract tokens if we found usage info
    if usage:
        if isinstance(usage, dict):
            # Handle different token naming conventions
            # Claude: input_tokens, output_tokens
            # Gemini: prompt_token_count, candidates_token_count
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("prompt_token_count", 0)
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("candidates_token_count", 0)
            
            token_usage["input_tokens"] += input_tokens
            token_usage["output_tokens"] += output_tokens
        elif hasattr(usage, 'input_tokens'):
            token_usage["input_tokens"] += getattr(usage, 'input_tokens', 0)
            token_usage["output_tokens"] += getattr(usage, 'output_tokens', 0)
        elif hasattr(usage, 'prompt_token_count'):
            # Gemini format
            token_usage["input_tokens"] += getattr(usage, 'prompt_token_count', 0)
            token_usage["output_tokens"] += getattr(usage, 'candidates_token_count', 0)
    
    return {"messages": [response], "token_usage": token_usage}


async def tool_node(state: AgentState):
    """Execute tool calls from the agent (supports both sync and async tools)."""
    # Ensure MCP tools are initialized
    await ensure_mcp_initialized()
    
    messages = state["messages"]
    last_message = messages[-1]
    token_usage = state.get("token_usage", {"input_tokens": 0, "output_tokens": 0})
    
    results = []
    for tool_call in last_message.tool_calls:
        tool = tools_by_name.get(tool_call["name"])
        if not tool:
            results.append(
                ToolMessage(
                    content=f"Error: Tool '{tool_call['name']}' not found",
                    tool_call_id=tool_call["id"]
                )
            )
            continue
        
        try:
            # Prefer ainvoke (standard LangChain async interface)
            if hasattr(tool, 'ainvoke'):
                # LangChain async invoke - pass args as dict
                observation = await tool.ainvoke(tool_call["args"])
            elif hasattr(tool, 'arun'):
                # Alternative async method (some tools use arun instead of ainvoke)
                observation = await tool.arun(**tool_call["args"])
            elif hasattr(tool, '_arun'):
                # Internal async method - requires config parameter
                # Try with config=None first
                try:
                    observation = await tool._arun(**tool_call["args"], config=None)
                except TypeError:
                    # If that fails, try without config (some tools don't need it)
                    observation = await tool._arun(**tool_call["args"])
            else:
                # Sync tool - use invoke
                observation = tool.invoke(tool_call["args"])
            
            results.append(
                ToolMessage(
                    content=str(observation),
                    tool_call_id=tool_call["id"]
                )
            )
        except Exception as e:
            results.append(
                ToolMessage(
                    content=f"Error executing tool: {str(e)}",
                    tool_call_id=tool_call["id"]
                )
            )
    
    return {"messages": results, "token_usage": token_usage}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Decide whether to continue with tool calls or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the LLM makes a tool call, continue to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Otherwise, end (agent has provided final answer)
    return END


# Build the agent graph
def create_agent():
    """Create and compile the code modification agent."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    workflow.add_edge("tools", "agent")
    
    # Compile the agent
    return workflow.compile()


# Create the agent instance
agent = create_agent()


async def run_agent_async(query: str, show_graph: bool = False):
    """Run the agent with a query (async version).
    
    Args:
        query: User query/instruction
        show_graph: Whether to display the agent graph
    
    Returns:
        Final agent response with token usage
    """
    # Initialize MCP tools before running
    await ensure_mcp_initialized()
    
    if show_graph:
        if HAS_IPYTHON:
            try:
                display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
            except Exception:
                print("Could not display graph. Install graphviz for visualization.")
        else:
            print("Graph visualization requires IPython. Install with: pip install ipython")
    
    # Invoke the agent with initial token usage (async)
    messages = [HumanMessage(content=query)]
    result = await agent.ainvoke({
        "messages": messages,
        "token_usage": {"input_tokens": 0, "output_tokens": 0}
    })
    
    return result


def run_agent(query: str, show_graph: bool = False):
    """Run the agent with a query (synchronous wrapper).
    
    Args:
        query: User query/instruction
        show_graph: Whether to display the agent graph
    
    Returns:
        Final agent response with token usage
    """
    # Use asyncio.run to execute the async function
    # This works even if there's no event loop or if we're in a sync context
    try:
        # Try to get existing loop
        loop = asyncio.get_running_loop()
        # If we get here, there's a running loop - we need to create a task
        # This shouldn't happen in normal usage, but handle it gracefully
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, run_agent_async(query, show_graph))
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(run_agent_async(query, show_graph))


async def stream_agent_async(query: str):
    """Stream agent execution for real-time updates (async version).
    
    Args:
        query: User query/instruction
    
    Yields:
        Agent execution steps
    """
    # Initialize MCP tools before streaming
    await ensure_mcp_initialized()
    
    messages = [HumanMessage(content=query)]
    
    async for chunk in agent.astream({
        "messages": messages,
        "token_usage": {"input_tokens": 0, "output_tokens": 0}
    }, stream_mode="updates"):
        yield chunk


def stream_agent(query: str):
    """Stream agent execution for real-time updates (synchronous wrapper).
    
    Args:
        query: User query/instruction
    
    Yields:
        Agent execution steps
    """
    # Create a new event loop for streaming
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async_gen = stream_agent_async(query)
        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
    finally:
        loop.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = run_agent(query)
        
        # Print final messages
        print("\n" + "="*80)
        print("AGENT EXECUTION COMPLETE")
        print("="*80 + "\n")
        
        for message in result["messages"]:
            if hasattr(message, 'content') and message.content:
                print(f"{type(message).__name__}:")
                print(message.content)
                print("\n" + "-"*80 + "\n")
        
        # Display token usage
        token_usage = result.get("token_usage", {})
        if token_usage:
            input_tokens = token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            print("="*80)
            print("TOKEN USAGE")
            print("="*80)
            print(f"Input Tokens:  {input_tokens:,}")
            print(f"Output Tokens: {output_tokens:,}")
            print(f"Total Tokens:  {total_tokens:,}")
            print("="*80 + "\n")
    else:
        print("Code Modification Agent")
        print("="*80)
        print("Usage: python agent.py '<your instruction>'")
        print("\nExample: python agent.py 'Change the background color to #ffffff in all CSS files'")
        print("\nOr use interactively:")
        print("  from agent import run_agent")
        print("  result = run_agent('Change background color to blue')")

