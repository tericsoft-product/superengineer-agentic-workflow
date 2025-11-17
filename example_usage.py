"""Example usage of the code modification agent."""

from agent import run_agent, stream_agent

# Example 1: Change background color in CSS files
print("Example 1: Changing background color")
print("=" * 80)
result = run_agent(
    "Find all CSS files and change any background-color property to #f0f0f0"
)
print("\n")

# Example 2: Stream execution for real-time updates
print("Example 2: Streaming agent execution")
print("=" * 80)
for chunk in stream_agent("List all Python files in the current directory"):
    print(chunk)
    print("\n")

# Example 3: Replace text across files
print("Example 3: Replacing text")
print("=" * 80)
result = run_agent(
    "Replace all occurrences of 'old_api_url' with 'new_api_url' in JavaScript files"
)
print("\n")

# Example 4: Complex modification
print("Example 4: Complex code modification")
print("=" * 80)
result = run_agent(
    """Find all Python files containing 'def old_function_name' 
    and rename it to 'def new_function_name' throughout the codebase"""
)
print("\n")

