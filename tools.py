"""File operation tools for the code modification agent."""

import os
import re
from pathlib import Path
from typing import List, Optional
from langchain.tools import tool


@tool
def list_files(directory: str = ".", pattern: Optional[str] = None) -> str:
    """List files in a directory, optionally filtered by pattern.
    
    Args:
        directory: Directory path to list files from (default: current directory)
        pattern: Optional glob pattern to filter files (e.g., "*.py", "*.css")
    
    Returns:
        String listing all matching files with their paths
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return f"Error: Directory '{directory}' does not exist"
        
        if pattern:
            files = list(dir_path.rglob(pattern))
        else:
            files = [f for f in dir_path.rglob("*") if f.is_file()]
        
        if not files:
            return f"No files found in '{directory}'"
        
        # Limit to reasonable number for display
        files = sorted(files)[:100]
        result = f"Found {len(files)} files in '{directory}':\n"
        for file in files:
            result += f"  - {file}\n"
        return result
    except Exception as e:
        return f"Error listing files: {str(e)}"


@tool
def search_code(query: str, directory: str = ".", file_pattern: Optional[str] = None) -> str:
    """Search for code patterns using regex or plain text search.
    
    Args:
        query: Search query (can be regex pattern or plain text)
        directory: Directory to search in (default: current directory)
        file_pattern: Optional file pattern to limit search (e.g., "*.py", "*.css", "*.js")
    
    Returns:
        String with matching lines and their file locations
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return f"Error: Directory '{directory}' does not exist"
        
        # Find files to search
        if file_pattern:
            files = list(dir_path.rglob(file_pattern))
        else:
            files = [f for f in dir_path.rglob("*") if f.is_file()]
        
        matches = []
        pattern = re.compile(query, re.IGNORECASE | re.MULTILINE)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            matches.append({
                                'file': str(file_path),
                                'line': line_num,
                                'content': line.strip()
                            })
            except Exception as e:
                continue  # Skip files that can't be read
        
        if not matches:
            return f"No matches found for '{query}' in '{directory}'"
        
        result = f"Found {len(matches)} matches for '{query}':\n\n"
        for match in matches[:50]:  # Limit results
            result += f"{match['file']}:{match['line']}\n  {match['content']}\n\n"
        
        if len(matches) > 50:
            result += f"... and {len(matches) - 50} more matches\n"
        
        return result
    except Exception as e:
        return f"Error searching code: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file.
    
    Args:
        file_path: Path to the file to read
    
    Returns:
        File contents as string
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        if not path.is_file():
            return f"Error: '{file_path}' is not a file"
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return f"Contents of '{file_path}':\n\n{content}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(file_path: str, content: str, mode: str = "replace") -> str:
    """Write content to a file.
    
    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        mode: Write mode - "replace" (overwrite) or "append"
    
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path)
        
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if mode == "append":
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully appended to '{file_path}'"
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to '{file_path}'"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def replace_in_file(file_path: str, old_text: str, new_text: str, count: int = 0) -> str:
    """Replace text in a file.
    
    Args:
        file_path: Path to the file
        old_text: Text to replace (can be regex pattern)
        new_text: Replacement text
        count: Number of replacements to make (0 = all)
    
    Returns:
        Success message with number of replacements made
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Use regex for pattern matching
        pattern = re.compile(old_text, re.MULTILINE)
        matches = pattern.findall(content)
        
        if not matches:
            return f"No matches found for '{old_text}' in '{file_path}'"
        
        if count == 0:
            new_content = pattern.sub(new_text, content)
            replacements = len(matches)
        else:
            new_content = pattern.sub(new_text, content, count=count)
            replacements = min(count, len(matches))
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return f"Successfully replaced {replacements} occurrence(s) in '{file_path}'"
    except Exception as e:
        return f"Error replacing text: {str(e)}"


@tool
def get_file_info(file_path: str) -> str:
    """Get information about a file (size, type, last modified).
    
    Args:
        file_path: Path to the file
    
    Returns:
        File information as string
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        stat = path.stat()
        info = f"File: {file_path}\n"
        info += f"Size: {stat.st_size} bytes\n"
        info += f"Type: {path.suffix or 'no extension'}\n"
        info += f"Last modified: {stat.st_mtime}\n"
        info += f"Is file: {path.is_file()}\n"
        info += f"Is directory: {path.is_dir()}\n"
        
        return info
    except Exception as e:
        return f"Error getting file info: {str(e)}"


@tool
def find_files_by_content(search_text: str, directory: str = ".", file_pattern: Optional[str] = None) -> str:
    """Find files that contain specific text.
    
    Args:
        search_text: Text to search for
        directory: Directory to search in
        file_pattern: Optional file pattern to limit search
    
    Returns:
        List of files containing the search text
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return f"Error: Directory '{directory}' does not exist"
        
        if file_pattern:
            files = list(dir_path.rglob(file_pattern))
        else:
            files = [f for f in dir_path.rglob("*") if f.is_file()]
        
        matching_files = []
        pattern = re.compile(re.escape(search_text), re.IGNORECASE)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    if pattern.search(f.read()):
                        matching_files.append(str(file_path))
            except Exception:
                continue
        
        if not matching_files:
            return f"No files found containing '{search_text}'"
        
        result = f"Found {len(matching_files)} file(s) containing '{search_text}':\n"
        for file in matching_files[:20]:  # Limit results
            result += f"  - {file}\n"
        
        if len(matching_files) > 20:
            result += f"... and {len(matching_files) - 20} more files\n"
        
        return result
    except Exception as e:
        return f"Error finding files: {str(e)}"

