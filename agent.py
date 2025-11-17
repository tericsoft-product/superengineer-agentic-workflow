"""Code modification agent using LangGraph."""

import os
import getpass
from typing import Literal, TypedDict, Annotated

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
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")
        
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

# Create tool lookup dictionary
tools_by_name = {tool.name: tool for tool in tools}

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)


def agent_node(state: AgentState):
    """Agent node that decides which tool to call or provides final answer."""
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


def tool_node(state: AgentState):
    """Execute tool calls from the agent."""
    messages = state["messages"]
    last_message = messages[-1]
    token_usage = state.get("token_usage", {"input_tokens": 0, "output_tokens": 0})
    
    results = []
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        try:
            # Invoke the tool with the provided arguments
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


def run_agent(query: str, show_graph: bool = False):
    """Run the agent with a query.
    
    Args:
        query: User query/instruction
        show_graph: Whether to display the agent graph
    
    Returns:
        Final agent response with token usage
    """
    if show_graph:
        if HAS_IPYTHON:
            try:
                display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
            except Exception:
                print("Could not display graph. Install graphviz for visualization.")
        else:
            print("Graph visualization requires IPython. Install with: pip install ipython")
    
    # Invoke the agent with initial token usage
    messages = [HumanMessage(content=query)]
    result = agent.invoke({
        "messages": messages,
        "token_usage": {"input_tokens": 0, "output_tokens": 0}
    })
    
    return result


def stream_agent(query: str):
    """Stream agent execution for real-time updates.
    
    Args:
        query: User query/instruction
    
    Yields:
        Agent execution steps
    """
    messages = [HumanMessage(content=query)]
    
    for chunk in agent.stream({
        "messages": messages,
        "token_usage": {"input_tokens": 0, "output_tokens": 0}
    }, stream_mode="updates"):
        yield chunk


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

