#!/usr/bin/env python3
"""
Detect and erase AI attribution from a git repository.

- Rewrites ALL commit messages, removing lines such as:
    Co-Authored-By: Claude ... <noreply@anthropic.com>
    Generated with [Claude Code](...)
    🤖 Generated with ...
- Scans tracked files for the same patterns and reports any hits (does not edit
  files - review those by hand).

Usage:
    python scripts/strip_ai_attribution.py            # rewrite history + scan files
    python scripts/strip_ai_attribution.py --scan     # scan only, no history rewrite

After a history rewrite you must force-push:  git push --force-with-lease
"""
from __future__ import annotations

import subprocess
import sys

# case-insensitive, extended-regex pattern of attribution lines to drop
PATTERN = (
    r"(co-authored-by:[[:space:]]*.*"
    r"(claude|anthropic|openai|chatgpt|gpt|copilot|gemini|cursor)"
    r"|generated with[[:space:]]*(\[)?(claude|ai\b|gpt|copilot)"
    r"|🤖[[:space:]]*generated"
    r"|assisted by[[:space:]]*(claude|ai\b)"
    r"|via[[:space:]]*claude[[:space:]]*code)"
)


def _run(args, **kw):
    return subprocess.run(args, text=True, capture_output=True, **kw)


def scan_files() -> int:
    r = _run(["git", "grep", "-inE", PATTERN])
    if r.stdout.strip():
        print("Possible AI attribution in tracked files (review manually):")
        print(r.stdout)
        return 1
    print("No AI attribution found in tracked files.")
    return 0


def rewrite_history():
    print("Rewriting commit messages to strip AI attribution...")
    msg_filter = f"grep -viE {_shquote(PATTERN)} || true"
    env = {"FILTER_BRANCH_SQUELCH_WARNING": "1"}
    import os
    full_env = {**os.environ, **env}
    r = subprocess.run(
        ["git", "filter-branch", "-f", "--msg-filter", msg_filter, "--", "--all"],
        text=True, env=full_env)
    if r.returncode != 0:
        print("filter-branch failed.", file=sys.stderr)
        sys.exit(r.returncode)
    print("Done. Verify with:  git log --format='%B'")
    print("Then force-push:     git push --force-with-lease --all")


def _shquote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def main():
    scan_only = "--scan" in sys.argv[1:]
    scan_files()
    if not scan_only:
        rewrite_history()


if __name__ == "__main__":
    main()
