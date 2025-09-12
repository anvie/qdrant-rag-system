#!/usr/bin/env python3
"""
Main CLI entry point for the Qdrant RAG system.

This script provides a unified interface to all CLI tools.
"""

import sys
import argparse
import subprocess
from pathlib import Path


def run_tool(tool_name: str, args: list) -> int:
    """Run a specific CLI tool with the given arguments."""
    script_dir = Path(__file__).parent
    tool_script = script_dir / f"{tool_name}.py"

    if not tool_script.exists():
        print(f"❌ Tool '{tool_name}' not found", file=sys.stderr)
        return 1

    try:
        # Run the tool script with the provided arguments
        cmd = [sys.executable, str(tool_script)] + args
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Error running {tool_name}: {e}", file=sys.stderr)
        return 1


def main():
    """Main CLI dispatcher."""
    parser = argparse.ArgumentParser(
        description="Qdrant RAG System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available tools:
  query    - Search documents with semantic/hybrid search
  index    - Index documents into vector database
  chat     - Interactive RAG chat with LLM

Examples:
  %(prog)s query "machine learning algorithms"
  %(prog)s index --input-path ./documents --collection docs
  %(prog)s chat --interactive

Use '%(prog)s TOOL --help' for tool-specific options.
    """,
    )

    parser.add_argument("tool", choices=["query", "index", "chat"], help="Tool to run")
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="Arguments to pass to the tool"
    )

    # Parse only the tool name, let the individual tools handle their own arguments
    if len(sys.argv) < 2:
        parser.print_help()
        return 1

    tool_name = sys.argv[1]

    if tool_name in ["-h", "--help"]:
        parser.print_help()
        return 0

    if tool_name not in ["query", "index", "chat"]:
        print(f"❌ Unknown tool: {tool_name}")
        print("Available tools: query, index, chat")
        return 1

    # Pass remaining arguments to the specific tool
    tool_args = sys.argv[2:]
    return run_tool(tool_name, tool_args)


if __name__ == "__main__":
    sys.exit(main())
