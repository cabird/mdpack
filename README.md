# mdpack

*The world's first LLM-based self-extracting archive format. Like a self-extracting zip except it's not compressed and you need a trillion-parameter model to unpack it. #YoureWelcome*

Contains a production-ready, enterprise-grade, industrial-strength specification for its own extractor implementation. The agent simply reads the spec, writes the extractor, and runs it.

Cross-platform.

Cross-model.

Cross-agent.

Cross-your-fingers.


mdpack packs a directory of files into a single `.mdpack` file — agents, markdown docs, recipes, scripts, binary assets, anything — and makes it self-extracting *and* self-bootstrapping. The bundle includes embedded boot instructions that tell any LLM agent (GitHub Copilot CLI, Claude Code, etc.) how to write the extractor, run that code to extract it, and where to start executing afterward. No prior knowledge of the format required. A vanilla agent just reads the top of the file, writes a small extractor, runs it, and then picks up the bootstrap entry point and gets going.

## Quick start

Pack a directory:

```
python mdpack.py docs/
```

This reads `docs/manifest.toml` and produces a `.mdpack` bundle in the current directory.

If you're too lazy to actually clone the repo (who has the time?), you could also probably just copy-paste this page to an agent then say *"follow this and make me docs.mdpack from what's in the docs directory"*

Once you have an mdpack file, extract it by telling an agent.

*"Read the front of docs.mdpack and follow the instructions."*


## Why?

When you hand a set of documentation files to an LLM agent, it needs to know what to read and in what order. mdpack solves this by bundling everything into one file with:

- **Bootstrap instructions** at the top that tell the agent how to write the extractor and what to read once extraction is complete
- A **table of contents** with file descriptions, reading order, and byte-level integrity checks
- A **manifest** with project configuration
- **SHA-256 checksums** on every file for verification

The agent reads the frontmatter, extracts the rest, and knows exactly where to start.

### Requirements

- Python 3.11+ (uses `tomllib`)

## manifest.toml

The source directory needs a `manifest.toml`:

```toml
# Required
output = "MY_PROJECT.mdpack"    # Output filename
unpack_dir = "my_project_docs"  # Directory the unpacker creates
bootstrap = "getting_started.md" # The file the agent is instructed to read and "run" after extraction

# Optional — file selection
# Any text file can be included, not just .md. By default, all .md files are grabbed.
include_text = ["*.md", "guides/*.md", "script.py"]  # Glob patterns (default: all .md files)
exclude_text = ["drafts/*.md"]                        # Patterns to skip

# Optional — binary assets (base64-encoded in bundle)
# Any file type can be included: images, PDFs, archives, etc.
include_binary = ["assets/*", "images/*.png"]
exclude_binary = ["assets/*.tmp"]

```

### Required fields

| Field | Description |
|-------|-------------|
| `output` | Filename for the generated `.mdpack` bundle |
| `bootstrap` | The first `.md` file an agent should read after unpacking |
| `unpack_dir` | Directory name the extractor writes files into |

## Bundle format

The `.mdpack` file is plain UTF-8 text:

1. **Frontmatter** — human/agent-readable boot instructions
2. **File sections** — each preceded by a header line:

```
{o_o} MDPACK >>> ::path/to/file.md::text::utf-8::1234::abc12345::
```

Text files are stored verbatim. Binary files are base64-encoded. Every file includes its byte count and the first 8 characters of its SHA-256 hash for integrity verification.

## Text file metadata

Text files may optionally start with `Title:` and `Description:` lines in the first 10 lines, which will be put in the table of contents of the bundle and the TABLE_OF_CONTENTS.md after extraction:

```
Title: Getting Started
Description: Quick-start guide for new users
Prereqs: Setup Guide

# Getting Started
...
```

If `Title:` is missing, the file's path is used as the title. If `Description:` is missing, it defaults to empty. `Prereqs` is optional and lists comma-separated prerequisite document titles.

Any text file can be included — `.md`, `.txt`, `.toml`, `.py`, etc. Files without metadata lines are bundled normally; they just won't have a descriptive title or description in the table of contents.

## Testing

Pack the included example and hand the bundle to an agent:

```
python mdpack.py example/
```

For a full end-to-end test, tell an agent like Claude Code or GitHub Copilot CLI the following line and it will build the example bundle, hand it to a subagent to do extraction with zero prior context, and verify that every file is extracted correctly.

```
Read self_test.md and run it
```

## Example

See `example/` for a working source directory with `manifest.toml`, Markdown files, and binary assets.

## License

MIT
