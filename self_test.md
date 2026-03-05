# mdpack self-test

This is an end-to-end test of the mdpack bundle format. The test verifies
that a freshly packed bundle can be unpacked **by an LLM with no prior
context** — which is the whole point of mdpack.

Run these steps in order.

## 1. Clean

Remove any artifacts from previous runs so we start fresh:

- Delete `EXAMPLE.mdpack` if it exists.
- Delete the `example_md_docs/` directory if it exists (this is the
  `unpack_dir` declared in `example/manifest.toml`).
- Check for any scripts in the repo root (other than `mdpack.py`) that
  look like mdpack unpackers/extractors — i.e. they read an `.mdpack`
  file and write out its contents. Read the contents of each `.py` file
  and delete any that are unpacker scripts. The cold subagent must
  write its own from scratch.

## 2. Pack

Run the packer to create a fresh bundle:

```
python mdpack.py example/
```

Confirm that `EXAMPLE.mdpack` was created and is non-empty.

## 3. Cold unpack

This is the core of the test. Spawn a **new subagent with no other
context** and give it exactly this instruction:

> Read the front of EXAMPLE.mdpack and run it.

The subagent must figure out the format, write its own extractor, and
unpack the bundle — all from the boot instructions embedded in the file.

Do **not** give the subagent any hints about mdpack, the expected output
directory, or the file format. The bundle must be fully self-describing.

## 4. Verify

After the subagent finishes, verify the results:

1. The directory `example_md_docs/` exists.
2. Every entry in `example_md_docs/TABLE_OF_CONTENTS.md` corresponds to
   an actual file in the directory.
3. Each file's size in bytes matches the size listed in the table of
   contents.
4. The binary files (`assets/*`) are present and non-empty.
5. `example_md_docs/manifest.toml` exists.

## Pass / fail

- **PASS**: All checks in step 4 succeed.
- **FAIL**: Any missing file, size mismatch, or subagent error.

If the test fails, report which specific checks failed so the problem
can be diagnosed.
