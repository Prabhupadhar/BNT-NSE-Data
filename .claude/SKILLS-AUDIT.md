# Skill description audit — 2026-09-01

Skill *descriptions* are preloaded into every session; skill *bodies* are not.
So description length is a per-cold-start tax and body length is free.

## Why these are not applied in-place

Descriptions live in each `SKILL.md` frontmatter, and those files are
re-downloaded from the account on every session start:

    skills_sync_complete {"downloaded": 8, "removed": 0, "duration_ms": 1474}

Editing `~/.claude/skills/synced/**` is overwritten on the next start, and in
a remote container `~/.claude` does not survive at all. The durable edit is in
the claude.ai skill settings for the ones you own. Rewrites below are
paste-ready.

## Rewrites — all reduced to <= 2 sentences

### docx  (1003 -> 244 chars, ~190 tok saved)  [Anthropic-managed: not editable]
Create, read, or edit Word documents (.docx) and templates (.dotx), including
tracked changes, comments, and embedded images. Use when the user names a
.docx/.dotx file or asks for a Word deliverable; not for PDFs, spreadsheets,
or Google Docs.

### pptx  (960 -> 271 chars, ~172 tok saved)  [Anthropic-managed: not editable]
Create, read, or edit PowerPoint files (.pptx, .potx) - slides, layouts,
speaker notes, comments - including extracting text for use elsewhere. Use
whenever a .pptx or .potx file is an input or output; prefer a dedicated
slide-deck artifact when no file format is named.

### xlsx  (948 -> 266 chars, ~170 tok saved)  [Anthropic-managed: not editable]
Create, read, edit, or clean spreadsheet files (.xlsx, .xlsm, .xltx, .csv,
.tsv) - formulas, formatting, charts, messy tabular data. Use when a
spreadsheet file is the primary input or output; not when the deliverable is
a document, HTML report, or database pipeline.

### pdf  (437 -> 164 chars, ~68 tok saved)  [Anthropic-managed: not editable]
Read, extract, merge, split, rotate, watermark, fill, encrypt, or OCR PDF
files, and create new ones. Use whenever the user names a .pdf file or asks
to produce one.

### morning  (339 -> 214 chars, ~31 tok saved)  [EDITABLE - anthropic-example]
Render the user's morning brief as a styled HTML artifact, or set it up as a
recurring weekday task. Use only on an explicit request for the brief or
/morning - not for general questions about their day or calendar.

### prompt-master  (333 -> 205 chars, ~32 tok saved)  [EDITABLE - custom, yours]
Write, fix, improve, or adapt a prompt for a specific AI tool (LLM, Cursor,
Midjourney, image/video AI, coding agents). Use only on an explicit
prompt-engineering request, not for general coding or writing.

### skill-creator  (319 -> 187 chars, ~33 tok saved)  [EDITABLE - anthropic-example]
Create, edit, and optimize skills, including their descriptions for better
triggering. Use for building a skill from scratch, improving one, or running
evals and variance benchmarks on it.

### import-memory  (139 chars, 1 sentence)  [already optimal - no change]

## Removal candidates - NOT REMOVED, listed for your decision

Evidence limitation, stated plainly: you asked for "unused in the last 10
sessions". There is exactly ONE session log on this machine
(`~/.claude/projects/**/*.jsonl`) - this one. This is an ephemeral cloud
container. A true 10-session usage histogram has to be produced on your local
machine, where transcripts accumulate. Everything below is reasoned from this
session plus repository fit (a Python NSE-data project), not from usage counts.

### MCP servers

| Server | Tools | Preload cost | Calls this session | Verdict |
|---|---:|---:|---:|---|
| `Claude_Code_Remote` | 20, all EAGER | ~7,500 tok (~15% of preload) | 2 | **Highest-value target, but do not disable** - it is harness plumbing for the remote session (triggers, repo attach, PR subscriptions). The ask is for these 20 schemas to be *deferred* like GitHub's, not removed. Raise with support. |
| `github` | 55, all DEFERRED | ~550 tok (names only) | 0 | **Keep.** Deferral already makes it nearly free, and this repo has a PR workflow. |
| `ccd_session` | 2, EAGER | ~400 tok | 0 | Minor. Keep. |

### Skills - plausible removals for this repo

| Skill | ~Tokens | Why it is a candidate |
|---|---:|---|
| `pptx` | 240 | No decks in a data repo |
| `docx` | 251 | No Word deliverables |
| `pdf` | 109 | No PDF work |
| `morning` | 85 | Personal brief, unrelated to this repo |
| `import-memory` | 35 | One-time migration tool |
| `design` / `artifact-design` / `artifact-diagramming` / `artifact-capabilities` | ~800 | Only if you never publish artifacts |
| `keybindings-help` | ~40 | One-time setup |
| `session-start-hook` | ~60 | One-time setup |
| `skill-creator` | 80 | Only if you are not authoring skills |

Keep for this repo: `xlsx`, `dataviz`, `code-review`, `simplify`,
`security-review`, `run`, `init`, `update-config`, `fewer-permission-prompts`,
`loop`, `claude-api`, `prompt-master`.

Disabling the top five (`pptx`, `docx`, `pdf`, `morning`, `import-memory`)
saves ~720 tokens per cold start - about $0.014 per session. Real but small.
The description rewrites above save ~696 tokens for free, without losing a
single capability. **Do the rewrites; only disable skills you actually
dislike seeing.**
