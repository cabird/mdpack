Title: mdpack Stress Test
Description: End-to-end stress test of mdpack extraction across multiple LLM models

# mdpack Multi-Model Extraction Stress Test

This document walks you through a complete stress test of the mdpack format. You will:

1. Understand the mdpack project by reading its source files
2. Create a test bundle with diverse file types
3. Run extraction tests across every model you can launch sub-agents with
4. Collect reflections and analyze the results

Follow each step in order.

## Step 1: Understand the Project

Read these files to understand what mdpack is and how it works:

- `README.md` — project overview and format description
- `mdpack.py` — the packer implementation
- `frontmatter.md` — the boot instruction template embedded in every bundle

Do not proceed until you have read all three.

## Step 2: Create the Stress Test Source Directory

Create a directory called `stress_test/` containing a realistic set of project documentation files. The goal is to exercise mdpack with a variety of file types, sizes, and nesting depths. Invent plausible content for a fictional software project — the specific content doesn't matter much, but it should be realistic enough to look like real documentation.

### Required structure

```
stress_test/
  manifest.toml
  gen_binaries.py          # Script to generate binary assets (excluded from bundle)
  getting_started.md       # Bootstrap entry point
  architecture.md          # System architecture overview with ASCII diagrams and tables
  api_reference.md         # REST API docs with request/response examples
  changelog.md             # Version history with multiple releases
  analysis.py              # A working Python script (stdlib only) that does something useful
  guides/
    setup.md               # Installation guide
    troubleshooting.md     # Common errors and fixes
    advanced/
      performance_tuning.md  # Advanced tuning guide
      internals/
        wire_protocol.md     # Deep technical spec (tests 3-level nesting)
  assets/                  # Created by gen_binaries.py
    gradient.png
    tone.wav
    sample.db
```

### Content guidelines

- Each markdown file should start with `Title:` and `Description:` metadata lines (and optionally `Prereqs:`) as described in the README. These get picked up by the table of contents.
- Files should be substantive — at least 30-50 lines each. Include markdown tables, code blocks, lists, and other formatting to exercise the format.
- `analysis.py` should be a working Python script using only the standard library. Include `Title:` and `Description:` metadata in a docstring at the top.
- The directory must go at least 3 levels deep (`guides/advanced/internals/`) to test nested path handling.

### manifest.toml

This file must be exact — mdpack reads it to know what to pack:

```toml
name = "STRESS_TEST"
version = "1.0"
unpack_dir = "stress_test_docs"
bootstrap = "getting_started.md"

include_text = [
    "*.md",
    "*.py",
    "guides/*.md",
    "guides/advanced/*.md",
    "guides/advanced/internals/*.md",
]
exclude_text = ["gen_binaries.py"]

include_binary = ["assets/*"]
```

### gen_binaries.py

Write a Python script using **only the standard library** (no external dependencies) that generates three binary files in `stress_test/assets/`:

- `gradient.png` — a small PNG image (e.g., 64×64 color gradient) built manually using `struct` and `zlib` to construct valid PNG chunks
- `tone.wav` — a WAV audio file (~30KB) using the `wave` module. Generate a sine wave tone (e.g., 440Hz, 44100Hz sample rate, 16-bit mono, ~0.35 seconds). This should be the largest binary file in the bundle to stress base64 handling.
- `sample.db` — a SQLite database (~8-12KB) using the `sqlite3` module. Create a few tables with realistic schema and populate them with sample data (enough rows to give the file some heft).

The script should be runnable with `python stress_test/gen_binaries.py` (no `uv run` or virtual environment needed).

## Step 3: Generate Binary Assets and Pack the Bundle

```bash
mkdir -p stress_test/assets
python stress_test/gen_binaries.py
python mdpack.py stress_test/
```

This should produce `STRESS_TEST-1.0.mdpack` in the current directory. Verify it was created and note the file count (should be 12 user files + manifest.toml + TABLE_OF_CONTENTS.md = 14 sections in the bundle).

## Step 4: Discover Available Models

Determine which models you can launch sub-agents with. List all available models. You will run 3 extraction attempts per model.

## Step 5: Set Up the Test Infrastructure

Create the directory and the deferred-reflection instructions file:

```bash
mkdir -p stress_test_runs
```

Write a file called `step2.md` with the content below. You will copy it into each run directory alongside the mdpack file.

```
# Step 2: Reflection

Now that extraction is complete, write a REFLECTION.md file in your working directory with these sections:

- **Strategy**: What was your approach to extracting the mdpack file?
- **What Worked**: What aspects of the format made extraction straightforward?
- **What I Had to Do Differently Than Expected**: Any adaptations you had to make
- **Surprises**: Anything unexpected about the format or the extraction process
- **Suggestions for Format Improvement**: Concrete ideas for making the mdpack format better
- **Tool Calls Made**: List every tool call you made during extraction, with the tool name and parameters (elide source code, just note "wrote extractor script")
```

## Step 6: Run the Extraction Tests

For each model, do 3 runs. Process one model at a time — launch all 3 runs for a model in parallel, wait for all 3 to finish, then move to the next model.

For each run:

1. Create the run directory: `stress_test_runs/{model_id}_run{N}/`
2. Copy the bundle with a neutral filename: `cp STRESS_TEST-1.0.mdpack stress_test_runs/{model_id}_run{N}/PROJECT_DOCS.mdpack`
3. Copy the reflection instructions: `cp step2.md stress_test_runs/{model_id}_run{N}/step2.md`
4. Launch a sub-agent using that model with ONLY this prompt (fill in the absolute path):

```
Your working directory is {absolute_path_to_run_directory}/

Extract the file PROJECT_DOCS.mdpack to the extracted/ directory. Do not read any files outside your working directory.

IMPORTANT: Only after extraction is fully complete — all files written and verified — read the file step2.md in your working directory and follow its instructions. Do NOT read step2.md before extraction is finished.
```

## Step 7: Verify and Analyze Results

After all runs are complete:

1. **Verify extraction completeness**: Check that every run directory has exactly 14 files in its `extracted/` subdirectory. Report any failures.

2. **Read all REFLECTION.md files** and produce a summary report with:
   - **Per-model summary**: For each model, what was the common strategy? How many tool calls on average? Any failures or mistakes?
   - **Cross-model comparison**: Which models were most/least efficient (fewest tool calls)? Did any models cheat (read files outside their directory, copy extractors from sibling runs)? Did any models make wrong initial assumptions about the format?
   - **Format feedback**: What format improvement suggestions came up most frequently across all models? List them ranked by how many independent agents mentioned them.
   - **Behavioral observations**: Any notable differences in how models approached the task — did some read the spec more carefully? Did some write more defensive code? Did any try to execute the file directly?

Report these results clearly so they can be compared across different runs of this stress test.
