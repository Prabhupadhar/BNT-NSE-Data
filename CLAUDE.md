# BNT-NSE-Data

Python project (standard Python `.gitignore`; no source tree committed yet).
Add build/test/lint commands here as they land — one line each, no prose.

---

## Token & cost guard

These rules exist because a 2026-09-01 audit measured a ~50k-token preload
per cold start and one cache miss that cost 28% of a session. Context is the
budget. Spend it deliberately.

### Be concise

- Answer the question asked. No preamble, no recap of what you just did, no
  "great question", no summary of a summary.
- Prefer `sed -n '120,180p' file` over reading a 2,000-line file. Read the
  part you need.
- Never paste a file back into chat to show a change you just made. The diff
  is the record.
- One tool call that answers the question beats three that circle it. Batch
  independent calls into a single message.

### Route mechanical work to a Haiku sub-agent

Delegate to `Agent` with `model: "haiku"` — it runs in its own context
window, so none of its intermediate output touches this session's cache:

- renaming, reformatting, mechanical refactors across many files
- summarizing or extracting from long documents, logs, or transcripts
- scraping, parsing, and reshaping data
- bulk find-and-replace, boilerplate generation, test scaffolding
- any wide search whose only useful product is the conclusion (use `Explore`)

Keep on the main model: architecture, debugging, security-relevant changes,
anything needing the conversation's accumulated context.

Do not spawn a sub-agent for work that costs less than the spawn — a
sub-agent starts cold and re-derives context this session already has.

### Never suggest /compact as a cost-saving measure

`/compact` is not a saving. It re-writes the entire cached prefix at the
1.25x write rate, then the model re-reads files to recover what compaction
dropped. It costs roughly a dollar and buys confusion.

- Autocompact is armed at 80% context. Treat that as a deadline, not a
  safety net.
- The correct move at high context is `/clear` and a fresh session with a
  tight restatement of the goal, or delegating the next chunk to a
  sub-agent.
- Compact only to rescue a session whose state genuinely cannot be
  restated — and say plainly that it is a rescue, not an optimization.

### Cache hygiene

- Pick model and effort once per session. Switching mid-session invalidates
  the prefix and re-pays the full preload.
- The prompt cache lives ~1 hour (5 minutes under rate-limit overage). Long
  idle gaps cost a full re-write; finish a job or `/clear`.
- Commit and push before ending a turn — the `Stop` hook blocks otherwise,
  and each block is a full extra round-trip at current context size.
- Paste text, never PDFs or screenshots. An image of a stack trace costs
  many times the trace itself and cannot be grepped.
