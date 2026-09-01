#!/usr/bin/env python3
"""PostToolUse hook: trim noisy command output before it enters context.

Rationale (measured in the 2026-09-01 token audit): a single verbose Bash
step wrote 6,338 tokens to the cache, and every later turn re-reads them.
Install/build/test output is the worst offender -- thousands of progress
lines whose only load-bearing content is the error near the end.

Policy: keep every line that looks like an error or a test failure, plus the
last N lines (the summary/verdict), plus a small head for context. Drop the
middle and say how much was dropped so the model knows it was truncated
rather than silently short.

Only trims Bash stdout/stderr, only when the command is recognisably noisy
OR the output is large enough that the trim pays for itself. Read/Grep/Glob
results are left alone -- the model asked for those precisely.

Contract: PostToolUse receives the tool payload on stdin as JSON and may
return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
"additionalContext": ...}}. To *replace* output we emit the trimmed text as
additionalContext and let the original through only when we did not trim.
Always exit 0 -- a hook that crashes must never break the turn.
"""

import json
import re
import sys

# Keep the tail (verdict/summary) and a short head (what was invoked).
TAIL_LINES = 30
HEAD_LINES = 5

# Below this, trimming saves nothing worth the indirection.
MIN_LINES_TO_TRIM = 60

# Commands whose output is noisy by nature. Matched anywhere in the command.
NOISY = re.compile(
    r"\b("
    r"npm|pnpm|yarn|bun|npx"
    r"|pip|pip3|poetry|uv|conda"
    r"|cargo|go\s+(build|test|mod)|mvn|gradle|bazel|make|cmake|ninja"
    r"|docker|docker-compose|kubectl|helm"
    r"|pytest|jest|vitest|mocha|tox|nox|rspec|phpunit"
    r"|webpack|vite|rollup|esbuild|tsc|next|turbo"
    r"|apt|apt-get|yum|dnf|brew"
    r"|terraform|ansible"
    r")\b",
    re.IGNORECASE,
)

# Lines worth rescuing from the dropped middle.
ERROR = re.compile(
    r"(?:^|\W)("
    r"error|errors|ERR!|fatal|traceback|exception|panic"
    r"|failed|failure|FAIL|assertion|assert"
    r"|warning:|warn:"
    r"|undefined reference|cannot find|not found|no such file"
    r"|segmentation fault|core dumped"
    r"|E\d{3}\b|TS\d{4}\b|SyntaxError|TypeError|ValueError|KeyError"
    r"|npm ERR|ModuleNotFoundError|ImportError"
    r")",
    re.IGNORECASE,
)

# Progress spam that is never worth keeping even if it matches ERROR.
NOISE = re.compile(
    r"^\s*(\[\s*\d+%\]|Progress|Downloading|Fetching|Resolving|Collecting"
    r"|Requirement already satisfied|added \d+ packages|Compiling |\.{3,}"
    r"|#\d+ \[|=+>|\|=+)",
    re.IGNORECASE,
)

MAX_RESCUED_ERRORS = 40


def trim(text):
    """Return trimmed text, or None if it should pass through untouched."""
    lines = text.splitlines()
    if len(lines) <= MIN_LINES_TO_TRIM:
        return None

    head = lines[:HEAD_LINES]
    tail = lines[-TAIL_LINES:] if TAIL_LINES else []
    middle = lines[HEAD_LINES : len(lines) - len(tail)]
    if not middle:
        return None

    rescued = [
        (i, ln)
        for i, ln in enumerate(middle)
        if ERROR.search(ln) and not NOISE.match(ln) and ln.strip()
    ]
    dropped = len(middle) - len(rescued)
    if dropped <= 0:
        return None

    out = list(head)
    out.append(
        "... [trim-output hook] %d of %d lines dropped; %d error/failure "
        "line(s) preserved below, last %d lines kept verbatim ..."
        % (dropped, len(lines), min(len(rescued), MAX_RESCUED_ERRORS), len(tail))
    )
    if rescued:
        if len(rescued) > MAX_RESCUED_ERRORS:
            keep = rescued[:MAX_RESCUED_ERRORS]
            out.extend(ln for _, ln in keep)
            out.append(
                "... [trim-output hook] %d further error line(s) omitted ..."
                % (len(rescued) - MAX_RESCUED_ERRORS)
            )
        else:
            out.extend(ln for _, ln in rescued)
    out.extend(tail)
    return "\n".join(out)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get("tool_name") != "Bash":
        return

    command = (payload.get("tool_input") or {}).get("command", "") or ""
    response = payload.get("tool_response")

    if isinstance(response, dict):
        text = response.get("stdout") or response.get("output") or ""
        stderr = response.get("stderr") or ""
        if stderr and stderr not in text:
            text = (text + "\n" + stderr) if text else stderr
    elif isinstance(response, str):
        text = response
    else:
        return

    if not text:
        return

    # Trim noisy commands aggressively; anything else only once it is big.
    if not NOISY.search(command) and len(text.splitlines()) < 200:
        return

    trimmed = trim(text)
    if trimmed is None or len(trimmed) >= len(text):
        return

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": trimmed,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
