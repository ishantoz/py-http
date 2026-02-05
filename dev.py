#!/usr/bin/env python3
"""Run the server with hot reload."""
import subprocess
import sys

def main():
    try:
        subprocess.run(["uv", "run", "watchfiles", "uv run python main.py"])
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
