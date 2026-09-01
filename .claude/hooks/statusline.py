#!/usr/bin/env python3
"""Status line: model | effort | context % | session cost.

Claude Code pipes a JSON blob on stdin (model, workspace, session_id,
transcript_path, cost, ...). Cost is taken from the harness when it supplies
it and otherwise priced from the transcript's own usage records, so the
number is real rather than a guess.

Context % is what matters most here: autocompact fires at 80% and rewrites
the whole cached prefix, which the token audit measured at roughly a dollar
per fire. Seeing the bar climb is the whole point -- /clear before it hits
80%, not after.
"""

import json
import os
import sys

CONTEXT_WINDOW = 200_000
AUTOCOMPACT_PCT = float(os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", 80))

# USD per million tokens: (input, output, cache-write, cache-read)
PRICES = {
    "opus": (15.0, 75.0, 18.75, 1.50),
    "sonnet": (3.0, 15.0, 3.75, 0.30),
    "haiku": (0.80, 4.0, 1.0, 0.08),
    "fable": (3.0, 15.0, 3.75, 0.30),
}

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"


def price_for(model_id):
    m = (model_id or "").lower()
    for key, p in PRICES.items():
        if key in m:
            return p
    return PRICES["opus"]


def read_transcript(path):
    """Return (last_context_tokens, total_cost_usd) from a transcript."""
    if not path or not os.path.exists(path):
        return 0, 0.0
    last_ctx, cost, seen = 0, 0.0, set()
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue
                key = rec.get("requestId") or msg.get("id")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                i = usage.get("input_tokens") or 0
                o = usage.get("output_tokens") or 0
                cr = usage.get("cache_read_input_tokens") or 0
                cw = usage.get("cache_creation_input_tokens") or 0
                pi, po, pcw, pcr = price_for(msg.get("model"))
                cost += (i * pi + o * po + cw * pcw + cr * pcr) / 1e6
                last_ctx = i + cr + cw + o
    except Exception:
        pass
    return last_ctx, cost


def bar(pct, width=10):
    filled = min(width, int(round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    model = data.get("model") or {}
    name = model.get("display_name") or model.get("id") or "claude"
    model_id = model.get("id") or name

    effort = (
        os.environ.get("CLAUDE_EFFORT")
        or data.get("effort_level")
        or (data.get("session_context") or {}).get("effort_level")
        or ""
    )

    ctx_tokens, derived_cost = read_transcript(data.get("transcript_path"))

    cost = (data.get("cost") or {}).get("total_cost_usd")
    if not isinstance(cost, (int, float)):
        cost = derived_cost

    window = CONTEXT_WINDOW
    if data.get("exceeds_200k_tokens"):
        window = 1_000_000
    pct = min(100.0, 100.0 * ctx_tokens / window) if ctx_tokens else 0.0

    if pct >= AUTOCOMPACT_PCT:
        colour, flag = RED, "  ⚠ AUTOCOMPACT"
    elif pct >= AUTOCOMPACT_PCT * 0.75:
        colour, flag = YELLOW, ""
    else:
        colour, flag = GREEN, ""

    parts = [f"{BOLD}{CYAN}{name}{RESET}"]
    if effort:
        parts.append(f"{DIM}{effort}{RESET}")
    parts.append(
        f"{colour}{bar(pct)} {pct:4.1f}%{RESET} "
        f"{DIM}{ctx_tokens // 1000}k/{window // 1000}k{RESET}"
    )
    parts.append(f"{BOLD}${cost:.2f}{RESET}")

    sys.stdout.write(f"{DIM} | {RESET}".join(parts) + flag)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write("claude")
    sys.exit(0)
