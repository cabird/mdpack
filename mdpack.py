#!/usr/bin/env python3
"""
mdpack packer — assembles files into a single Markdown bundle.

Usage:
    python mdpack.py <directory>
    python mdpack.py <directory> --check
"""

import sys

if sys.version_info < (3, 11):
    sys.exit("Error: Python 3.11+ required (for tomllib)")

import argparse
import base64
import fnmatch
import hashlib
import re
import tomllib
from pathlib import Path

_PATH_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")

# Header prefix — assembled so it never appears literally in this source.
_HDR = "{o_o}" + " MDPACK >>> ::"

# Frontmatter template embedded directly so mdpack.py is fully self-contained.
# Placeholders: {unpack_dir}, {bootstrap}, {version_line}
_FRONTMATTER = """\
# MDPACK BOOT (do this){version_line}

This bundle is UTF-8 with `\\n` line endings. Read it as UTF-8.

1) Write + run a tiny extractor (Python recommended) that reads THIS file and writes files into `./{unpack_dir}/`.
   If you have been told to extract to a specific directory, use that instead of `./{unpack_dir}/`.
2) Then open `{bootstrap}` (inside the extraction directory) and follow its instructions.

## Header line (starts a file)

The header marker is `""" + _HDR[:-2] + """` followed by 5 fields separated by `::` and ending with `::`.
A header line starts at column 0 and spans the entire line:

    """ + _HDR + """PATH::TYPE::ENC::LEN::HASH::

- PATH = relative file path using `/` only; convert to platform separator when writing
- PATH must not contain `::`, `..` segments, empty components, or be absolute
- TYPE = `text` or `binary` (case-sensitive)
- ENC = text encoding (usually `utf-8`) when TYPE=text, or `base64` when TYPE=binary
- LEN = byte count (base-10 integer) of the final bytes written to disk
- HASH = first 8 lowercase hex characters of the sha256 over the final disk bytes
- Only a line matching the **complete** header format (all fields valid) starts a new section.
  A line that merely begins with the marker prefix but lacks valid fields is ordinary payload.

Python regex for matching a header line:

    ^\\{o_o\\} MDPACK >>> ::.+::(?:text|binary)::.+::\\d+::[0-9a-f]{8}::$

## Payload Details
- Payload begins after the header line and ends immediately before the next header line, or at EOF.
- text: strip leading and trailing whitespace from the raw payload, then append a single `\\n`.
  Encode the result with ENC to get disk bytes; verify len + sha256 (first 8 hex chars); write.
- binary: the payload is standard base64 (with `=` padding); remove ASCII whitespace (`space`, `\\t`, `\\r`, `\\n`),
  then base64-decode to get disk bytes; verify len + sha256 (first 8 hex chars); write.
- If any file fails validation (bad header, decode error, len/sha256 mismatch, unsafe path), abort.

## Write rules
- Create parent directories as needed.
- Write each file under the extraction directory using PATH. Default extraction directory is `./{unpack_dir}/`.
- Reject any PATH that is absolute or contains `..`.
- If the destination file already exists, skip if identical, otherwise abort.
"""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_path(rel: str) -> None:
    if not _PATH_RE.match(rel):
        bad = [c for c in rel if not re.match(r"[a-zA-Z0-9._/\-]", c)]
        sys.exit(f"Error: path '{rel}' has disallowed characters: {bad!r}")
    parts = rel.split("/")
    if rel.startswith("/") or ".." in parts:
        sys.exit(f"Error: path '{rel}' is absolute or contains '..'")
    if any(p == "" for p in parts):
        sys.exit(f"Error: path '{rel}' has empty components")
    if "." in parts:
        sys.exit(f"Error: path '{rel}' contains '.' component")


def parse_metadata(content: str) -> dict:
    """Extract metadata from YAML frontmatter (--- delimited block at file start)."""
    meta: dict = {"title": "", "description": "", "prereqs": []}

    if not content.startswith("---"):
        return meta

    end = content.find("\n---", 3)
    if end == -1:
        return meta

    fm = content[3:end]
    current_list_key = None
    for line in fm.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item
        if stripped.startswith("- ") and current_list_key:
            val = stripped[2:].strip().strip('"').strip("'")
            if current_list_key == "prereqs":
                meta["prereqs"].append(val)
            continue

        # Key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip().lower()
            val = val.strip().strip('"').strip("'")
            current_list_key = None

            if key == "title" and val:
                meta["title"] = val
            elif key == "description" and val:
                meta["description"] = val
            elif key == "prereqs":
                if val and val != "[]":
                    meta["prereqs"] = [
                        p.strip().strip('"').strip("'")
                        for p in val.split(",") if p.strip()
                    ]
                else:
                    current_list_key = "prereqs"
                    meta["prereqs"] = []

    return meta



def load_manifest(src: Path) -> dict:
    mpath = src / "manifest.toml"
    if not mpath.is_file():
        sys.exit(f"Error: manifest.toml not found in '{src}'")
    with open(mpath, "rb") as f:
        manifest = tomllib.load(f)
    required = ["name", "version", "bootstrap", "unpack_dir"]
    missing = [k for k in required if not manifest.get(k)]
    if missing:
        sys.exit(f"Error: manifest.toml missing required fields: {', '.join(missing)}")
    manifest["output"] = f"{manifest['name']}-{manifest['version']}.mdpack"
    return manifest


def discover_text(src: Path, manifest: dict) -> list[str]:
    include = manifest.get("include_text", manifest.get("include_md", None))
    exclude = manifest.get("exclude_text", manifest.get("exclude_md", []))
    if include is not None:
        paths: set[str] = set()
        for pattern in include:
            for p in sorted(src.glob(pattern)):
                if p.is_file():
                    paths.add(p.relative_to(src).as_posix())
    else:
        paths = set()
        for p in sorted(src.rglob("*.md")):
            paths.add(p.relative_to(src).as_posix())

    output_name = manifest["output"]
    paths.discard(output_name)
    paths.discard("TABLE_OF_CONTENTS.md")

    filtered: list[str] = []
    for rel in sorted(paths):
        if rel == "manifest.toml":
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude):
            continue
        filtered.append(rel)
    return filtered


def discover_binary(src: Path, manifest: dict) -> list[str]:
    specs = manifest.get("include_binary", [])
    exclude_pats = manifest.get("exclude_binary", [])
    always_exclude = {"manifest.toml", manifest["output"], "TABLE_OF_CONTENTS.md"}
    paths: set[str] = set()
    for spec in specs:
        for p in sorted(src.glob(spec)):
            rel = p.relative_to(src).as_posix()
            if p.is_file() and rel not in always_exclude:
                paths.add(rel)
    filtered: list[str] = []
    for rel in sorted(paths):
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude_pats):
            continue
        filtered.append(rel)
    return filtered


def emit_header(path: str, ftype: str, enc: str, disk_bytes: bytes) -> str:
    length = len(disk_bytes)
    sha = sha256_hex(disk_bytes)[:8]
    return f"{_HDR}{path}::{ftype}::{enc}::{length}::{sha}::"


def render_toc(entries: list[dict], manifest: dict) -> str:
    """Generate a table-of-contents markdown file."""
    lines = ["# Table of Contents", ""]
    bootstrap = manifest.get("bootstrap", "")
    if bootstrap:
        lines.append(f"**Start here:** {bootstrap}")
        lines.append("")
    lines.append("| Path | Title | Description | Prereqs | Type | Bytes |")
    lines.append("|------|-------|-------------|---------|------|-------|")
    for e in entries:
        meta = e.get("meta", {})
        title = meta.get("title", e["path"])
        desc = meta.get("description", "")
        prereqs = ", ".join(meta.get("prereqs", []))
        lines.append(
            f"| {e['path']} | {title} | {desc} "
            f"| {prereqs} | {e['type']} | {len(e['disk_bytes']):,} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_bundle(entries: list[dict], manifest: dict, src_dir: Path) -> str:
    parts: list[str] = []
    unpack_dir = manifest.get("unpack_dir", "md_docs")
    bootstrap = manifest.get("bootstrap", "")

    # Frontmatter
    fm = _FRONTMATTER
    fm = fm.replace("{unpack_dir}", unpack_dir)
    fm = fm.replace("{bootstrap}", bootstrap)
    version = manifest.get("version", "")
    fm = fm.replace("{version_line}", f"\n**Version {version}**" if version else "")
    parts.append(fm.rstrip("\n") + "\n\n")

    # Build manifest entry
    manifest_text = (src_dir / "manifest.toml").read_text(encoding="utf-8").strip() + "\n"
    manifest_bytes = manifest_text.encode("utf-8")
    manifest_entry = {
        "path": "manifest.toml",
        "type": "text",
        "enc": "utf-8",
        "disk_bytes": manifest_bytes,
        "payload": manifest_text,
        "meta": {"title": "manifest.toml", "description": "Bundle configuration", "prereqs": []},
    }

    # Sort user entries: text alpha, then binary alpha
    # (already sorted by pack(), but ensure consistency)

    # Build TOC with manifest first, then user entries
    toc_entries = [manifest_entry] + entries
    toc_text = render_toc(toc_entries, manifest).strip() + "\n"
    toc_bytes = toc_text.encode("utf-8")
    toc_entry = {
        "path": "TABLE_OF_CONTENTS.md",
        "type": "text",
        "enc": "utf-8",
        "disk_bytes": toc_bytes,
        "payload": toc_text,
        "meta": {"title": "Table of Contents", "description": "Index of all bundled files", "prereqs": []},
    }

    # Final order: manifest, TOC, then user entries (text alpha, binary alpha)
    all_entries = [manifest_entry, toc_entry] + entries
    for e in all_entries:
        parts.append(emit_header(e["path"], e["type"], e["enc"], e["disk_bytes"]) + "\n")
        parts.append(e["payload"])

    return "".join(parts)


def pack(src_dir: Path, *, check_only: bool = False) -> str | None:
    manifest = load_manifest(src_dir)
    md_files = discover_text(src_dir, manifest)
    bin_files = discover_binary(src_dir, manifest)
    all_paths = md_files + bin_files

    if not all_paths:
        sys.exit("Error: no files found to bundle")

    if len(all_paths) != len(set(all_paths)):
        dupes = [p for p in all_paths if all_paths.count(p) > 1]
        sys.exit(f"Error: duplicate paths: {sorted(set(dupes))}")

    bootstrap = manifest["bootstrap"]
    if bootstrap not in all_paths:
        sys.exit(f"Error: bootstrap file '{bootstrap}' not found in source files")

    for rel in all_paths:
        validate_path(rel)

    # Bundle recursion detection — only reject files containing a complete valid header
    _HEADER_RE = re.compile(r"^\{o_o\} MDPACK >>> ::.+::(?:text|binary)::.+::\d+::[0-9a-f]{8}::$", re.MULTILINE)
    entries: list[dict] = []

    for rel in md_files:
        content = (src_dir / rel).read_text(encoding="utf-8")
        if _HEADER_RE.search(content):
            sys.exit(f"Error: '{rel}' contains an mdpack header — refusing to pack")
        meta = parse_metadata(content)
        if not meta["title"]:
            meta["title"] = rel
        if not meta["description"]:
            meta["description"] = ""

        content = content.strip() + "\n"
        disk_bytes = content.encode("utf-8")
        entries.append({
            "path": rel,
            "type": "text",
            "enc": "utf-8",
            "disk_bytes": disk_bytes,
            "payload": content,
            "meta": meta,
        })

    for rel in bin_files:
        disk_bytes = (src_dir / rel).read_bytes()
        b64 = base64.b64encode(disk_bytes).decode("ascii")
        b64_wrapped = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
        if not b64_wrapped.endswith("\n"):
            b64_wrapped += "\n"
        entries.append({
            "path": rel,
            "type": "binary",
            "enc": "base64",
            "disk_bytes": disk_bytes,
            "payload": b64_wrapped,
            "meta": {"title": Path(rel).name, "description": "(binary)", "prereqs": []},
        })

    # Sort entries: text files alphabetically, then binary files alphabetically
    # This matches the TOC order
    entries.sort(key=lambda e: (0 if e["type"] == "text" else 1, e["path"]))

    if check_only:
        print(f"\nValidation passed: {len(entries)} file(s)")
        for e in entries:
            tag = f" [{e['type']}]" if e["type"] != "text" else ""
            print(f"  {e['path']}{tag}  ({len(e['disk_bytes']):,} bytes)")
        return None

    bundle_text = build_bundle(entries, manifest, src_dir)

    output_name = manifest["output"]
    output_path = Path.cwd() / output_name
    output_path.write_text(bundle_text, encoding="utf-8", newline="\n")

    print(f"\nBundle written: {output_path}")
    print(f"  Files:  {len(entries)} (+ manifest.toml)")
    print(f"  Size:   {len(bundle_text.encode('utf-8')):,} bytes")
    bootstrap = manifest.get("bootstrap", "")
    if bootstrap:
        print(f"  Boot:   {bootstrap}")
    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="mdpack — pack files into a Markdown bundle")
    parser.add_argument("directory", help="Source directory containing manifest.toml")
    parser.add_argument("--check", action="store_true", help="Validate only")
    args = parser.parse_args()

    src = Path(args.directory).resolve()
    if not src.is_dir():
        sys.exit(f"Error: '{args.directory}' is not a directory")

    pack(src, check_only=args.check)


if __name__ == "__main__":
    main()
