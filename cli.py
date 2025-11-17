#!/usr/bin/env python3
"""Interactive CLI for the code modification agent."""

import sys
import os

# Add /app to Python path if running in Docker container
if os.path.exists('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

from agent import run_agent, stream_agent

def print_banner():
    """Print welcome banner."""
    import os
    cwd = os.getcwd()
    print("\n" + "="*80)
    print("Code Modification Agent - Interactive CLI")
    print("="*80)
    print(f"\n📁 Current working directory: {cwd}")
    print(f"   Files created will be saved here")
    print("\nUsage: Type your command (e.g., 'change the color' or 'clin change the color')")
    print("Type 'exit' or 'quit' to exit, 'help' for more info")
    print("="*80 + "\n")

def print_help():
    """Print help information."""
    print("\n" + "-"*80)
    print("HELP")
    print("-"*80)
    print("Commands:")
    print("  - Type any natural language instruction (e.g., 'change the color to blue')")
    print("  - You can prefix with 'clin' or not (both work)")
    print("  - 'help' - Show this help message")
    print("  - 'exit' or 'quit' - Exit the CLI")
    print("\nExamples:")
    print("  > change the background color to #ffffff in all CSS files")
    print("  > clin find all Python files and add error handling")
    print("  > replace 'old_api' with 'new_api' in JavaScript files")
    print("-"*80 + "\n")

def process_command(command: str):
    """Process a single command."""
    # Remove 'clin' prefix if present (case insensitive)
    command = command.strip()
    if command.lower().startswith('clin '):
        command = command[5:].strip()
    
    if not command:
        return
    
    # Handle special commands
    if command.lower() in ['exit', 'quit']:
        print("\nExiting... Goodbye!\n")
        sys.exit(0)
    
    if command.lower() == 'help':
        print_help()
        return
    
    # Run the agent with the command
    try:
        print(f"\n🤖 Processing: {command}\n")
        print("-"*80)
        result = run_agent(command)
        
        # Print results - show all messages including tool calls
        print("\n" + "="*80)
        print("EXECUTION LOG")
        print("="*80)
        
        for i, message in enumerate(result["messages"]):
            msg_type = message.__class__.__name__
            
            # Skip system messages
            if msg_type == 'SystemMessage':
                continue
            
            # Show HumanMessage
            if msg_type == 'HumanMessage':
                if hasattr(message, 'content') and message.content:
                    print(f"\n👤 {msg_type}: {message.content}")
            
            # Show AIMessage with tool calls
            elif msg_type == 'AIMessage':
                print(f"\n🤖 {msg_type}:")
                if hasattr(message, 'content') and message.content:
                    # Check if content is a list (tool calls)
                    if isinstance(message.content, list):
                        for item in message.content:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                tool_name = item.get('name', 'unknown')
                                tool_input = item.get('input', {})
                                print(f"  🔧 Tool Call: {tool_name}")
                                if 'file_path' in tool_input:
                                    print(f"     📁 File: {tool_input['file_path']}")
                                if 'content' in tool_input:
                                    content_preview = str(tool_input['content'])[:100]
                                    print(f"     📝 Content preview: {content_preview}...")
                                elif 'old_string' in tool_input:
                                    print(f"     🔄 Replace operation")
                                elif 'pattern' in tool_input:
                                    print(f"     🔍 Search pattern: {tool_input['pattern']}")
                    else:
                        print(f"  {message.content}")
                # Also show tool_calls if present
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        print(f"  🔧 Tool Call: {tool_call.get('name', 'unknown')}")
                        if 'args' in tool_call:
                            args = tool_call['args']
                            if 'file_path' in args:
                                print(f"     📁 File: {args['file_path']}")
            
            # Show ToolMessage (tool execution results)
            elif msg_type == 'ToolMessage':
                if hasattr(message, 'content') and message.content:
                    content_str = str(message.content)
                    # Truncate very long outputs
                    if len(content_str) > 500:
                        content_str = content_str[:500] + "... (truncated)"
                    print(f"\n✅ Tool Result:")
                    print(f"  {content_str}")
                    # If it's a file operation, show the full path
                    if 'wrote to' in content_str.lower() or 'created' in content_str.lower() or 'wrote' in content_str.lower():
                        import os
                        import re
                        cwd = os.getcwd()
                        # Try to extract filename from the message
                        match = re.search(r"['\"]([^'\"]+)['\"]", content_str)
                        if match:
                            filename = match.group(1)
                            full_path = os.path.join(cwd, filename) if not os.path.isabs(filename) else filename
                            print(f"  📍 Full path: {full_path}")
                        else:
                            print(f"  📍 Working directory: {cwd}")
        
        # Show final summary
        print("\n" + "="*80)
        print("FINAL RESPONSE")
        print("="*80)
        # Get the last AIMessage that's not a tool call
        for message in reversed(result["messages"]):
            if message.__class__.__name__ == 'AIMessage':
                if hasattr(message, 'content') and message.content:
                    if not isinstance(message.content, list):
                        print(f"\n{message.content}\n")
                        break
                    elif not any(isinstance(item, dict) and item.get('type') == 'tool_use' 
                                for item in message.content if isinstance(item, dict)):
                        # It's a text response, not just tool calls
                        text_parts = [item.get('text', '') for item in message.content 
                                     if isinstance(item, dict) and item.get('type') == 'text']
                        if text_parts:
                            print(f"\n{''.join(text_parts)}\n")
                            break
        
        # Display token usage
        print("="*80)
        print("TOKEN USAGE")
        print("="*80)
        token_usage = result.get("token_usage", {})
        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        
        print(f"\n📊 Input Tokens:  {input_tokens:,}")
        print(f"📊 Output Tokens: {output_tokens:,}")
        print(f"📊 Total Tokens:  {total_tokens:,}")
        print("="*80 + "\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Command interrupted by user\n")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")

def main():
    """Main interactive loop."""
    print_banner()
    
    try:
        while True:
            try:
                # Get user input
                command = input("clin> ").strip()
                
                if command:
                    process_command(command)
            except EOFError:
                # Handle Ctrl+D
                print("\n\nExiting... Goodbye!\n")
                sys.exit(0)
            except KeyboardInterrupt:
                # Handle Ctrl+C
                print("\n\nExiting... Goodbye!\n")
                sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}\n")
        sys.exit(1)

if __name__ == "__main__":
    # If arguments provided, run as single command
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        process_command(command)
    else:
        # Otherwise, start interactive mode
        main()

