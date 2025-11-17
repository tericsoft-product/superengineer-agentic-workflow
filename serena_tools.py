"""Serena tools integration for LangGraph agent.

This module provides integration between Serena tools and LangGraph/LangChain.
It initializes the Serena agent and converts its tools to LangChain-compatible format.
"""

import argparse
import logging
import os
import threading
from pathlib import Path
from typing import Any, List, Optional

# Try importing Serena dependencies, make it optional
try:
    from dotenv import load_dotenv
    from serena.agent import SerenaAgent, Tool
    from serena.config.context_mode import SerenaAgentContext
    from serena.constants import REPO_ROOT
    from serena.util.exception import show_fatal_exception_safe
    from sensai.util.logging import LogTime
    HAS_SERENA = True
except ImportError:
    HAS_SERENA = False

# Try importing LangChain tool decorator and StructuredTool
try:
    from langchain.tools import tool
    from langchain_core.tools import StructuredTool
    import inspect
    HAS_LANGCHAIN_TOOLS = True
except ImportError:
    HAS_LANGCHAIN_TOOLS = False
    StructuredTool = None
    inspect = None

log = logging.getLogger(__name__)


class SerenaAgentProvider:
    """Singleton provider for Serena agent instance."""
    
    _agent: Optional[Any] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_agent(cls, project_file: Optional[str] = None) -> Any:
        """
        Returns the singleton instance of the Serena agent or creates it.
        
        Args:
            project_file: Optional path to the project file (or project.yml file)
        
        Returns:
            SerenaAgent instance
        """
        if not HAS_SERENA:
            raise ImportError(
                "Serena dependencies not available. "
                "Install with: pip install serena (or install required dependencies)"
            )
        
        with cls._lock:
            if cls._agent is not None:
                return cls._agent
            
            # Change to Serena root
            os.chdir(REPO_ROOT)
            load_dotenv()
            
            # Parse project file argument if provided
            if project_file:
                project_file_path = Path(project_file).resolve()
                # If project file path is relative, make it absolute by joining with project root
                if not project_file_path.is_absolute():
                    project_root = Path(REPO_ROOT)
                    project_file_path = project_root / project_file
                # Ensure the path is normalized and absolute
                project_file = str(project_file_path.resolve())
            
            with LogTime("Loading Serena agent"):
                try:
                    serena_agent = SerenaAgent(
                        project_file, 
                        context=SerenaAgentContext.load("agent")
                    )
                except Exception as e:
                    show_fatal_exception_safe(e)
                    raise
            
            cls._agent = serena_agent
            log.info(f"Serena agent instantiated: {serena_agent}")
            
        return cls._agent


def _create_langchain_tool_from_serena(serena_tool: Tool):
    """
    Convert a Serena tool to a LangChain-compatible tool.
    
    Args:
        serena_tool: Serena Tool instance
    
    Returns:
        LangChain tool function
    """
    if not HAS_LANGCHAIN_TOOLS:
        raise ImportError("langchain.tools is required for tool conversion")
    
    # Get the apply function signature
    apply_fn = serena_tool.get_apply_fn()
    tool_name = serena_tool.get_name_from_cls()
    
    def tool_wrapper(**kwargs: Any) -> str:
        """Wrapper function that calls the Serena tool."""
        # Handle kwargs argument if Agno-style kwargs are passed
        if "kwargs" in kwargs:
            kwargs.update(kwargs["kwargs"])
            del kwargs["kwargs"]
        
        log.info(f"Calling Serena tool: {tool_name}")
        try:
            result = serena_tool.apply_ex(
                log_call=True, 
                catch_exceptions=True, 
                **kwargs
            )
            return str(result)
        except Exception as e:
            error_msg = f"Error executing Serena tool {tool_name}: {str(e)}"
            log.error(error_msg)
            return error_msg
    
    # Try to preserve the original function signature
    tool_wrapper.__name__ = tool_name
    tool_doc = getattr(apply_fn, '__doc__', f"Serena tool: {tool_name}")
    tool_wrapper.__doc__ = tool_doc
    
    # Try to use StructuredTool.from_function if we can get the signature
    # Otherwise fall back to @tool decorator
    try:
        if inspect and StructuredTool:
            # Get signature from the original apply function
            sig = inspect.signature(apply_fn)
            # Create tool with explicit signature
            langchain_tool = StructuredTool.from_function(
                func=tool_wrapper,
                name=tool_name,
                description=tool_doc
            )
        else:
            # Fallback to @tool decorator
            langchain_tool = tool(tool_wrapper)
            langchain_tool.name = tool_name
    except Exception as e:
        # If StructuredTool fails, use @tool decorator
        log.warning(f"Could not use StructuredTool for {tool_name}, using @tool decorator: {e}")
        langchain_tool = tool(tool_wrapper)
        langchain_tool.name = tool_name
    
    return langchain_tool


def get_serena_tools(project_file: Optional[str] = None) -> List[Any]:
    """
    Get all Serena tools converted to LangChain format.
    
    Args:
        project_file: Optional path to the project file
    
    Returns:
        List of LangChain-compatible tools
    
    Raises:
        ImportError: If Serena or LangChain dependencies are not available
        RuntimeError: If no tools could be loaded
    """
    if not HAS_SERENA:
        raise ImportError(
            "Serena dependencies are required but not available. "
            "Install with: pip install serena (or install required dependencies)"
        )
    
    if not HAS_LANGCHAIN_TOOLS:
        raise ImportError(
            "LangChain tools are required but not available. "
            "Install with: pip install langchain langchain-core"
        )
    
    try:
        serena_agent = SerenaAgentProvider.get_agent(project_file)
        serena_tool_instances = serena_agent.get_exposed_tool_instances()
        
        if not serena_tool_instances:
            raise RuntimeError(
                "Serena agent has no exposed tools. "
                "Ensure your Serena agent configuration exposes tools."
            )
        
        langchain_tools = []
        for serena_tool in serena_tool_instances:
            try:
                langchain_tool = _create_langchain_tool_from_serena(serena_tool)
                langchain_tools.append(langchain_tool)
                log.info(f"Converted Serena tool: {langchain_tool.name}")
            except Exception as e:
                log.error(f"Failed to convert Serena tool {serena_tool}: {e}")
                # Continue with other tools, but warn
                continue
        
        if not langchain_tools:
            raise RuntimeError(
                "No Serena tools could be converted to LangChain format. "
                "Check tool conversion errors above."
            )
        
        log.info(f"Successfully converted {len(langchain_tools)} Serena tools")
        return langchain_tools
    
    except ImportError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error loading Serena tools: {e}") from e


def get_serena_system_prompt(project_file: Optional[str] = None) -> str:
    """
    Get the system prompt from Serena agent.
    
    Args:
        project_file: Optional path to the project file
    
    Returns:
        System prompt string
    
    Raises:
        ImportError: If Serena dependencies are not available
        RuntimeError: If system prompt could not be retrieved
    """
    if not HAS_SERENA:
        raise ImportError(
            "Serena dependencies are required but not available. "
            "Install with: pip install serena (or install required dependencies)"
        )
    
    try:
        serena_agent = SerenaAgentProvider.get_agent(project_file)
        prompt = serena_agent.create_system_prompt()
        if not prompt:
            raise RuntimeError("Serena agent returned an empty system prompt")
        return prompt
    except ImportError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error getting Serena system prompt: {e}") from e

