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

SCRIPT_DIR = Path(__file__).parent.resolve()
TEMPLATES_DIR = SCRIPT_DIR

_PATH_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")

# Header prefix — assembled so it never appears literally in this source.
_HDR = "{o_o}" + " MDPACK >>> ::"


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
    meta: dict = {"title": "", "description": "", "prereqs": []}
    for line in content.split("\n")[:10]:
        if line.startswith("Title:"):
            meta["title"] = line[len("Title:"):].strip()
        elif line.startswith("Description:"):
            meta["description"] = line[len("Description:"):].strip()
        elif line.startswith("Prereqs:"):
            raw = line[len("Prereqs:"):].strip()
            meta["prereqs"] = [p.strip() for p in raw.split(",") if p.strip()]
    return meta


def read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.is_file():
        sys.exit(f"Error: template '{name}' not found at {path}")
    return path.read_text(encoding="utf-8")


def load_manifest(src: Path) -> dict:
    mpath = src / "manifest.toml"
    if not mpath.is_file():
        sys.exit(f"Error: manifest.toml not found in '{src}'")
    with open(mpath, "rb") as f:
        manifest = tomllib.load(f)
    required = ["output", "bootstrap", "unpack_dir"]
    missing = [k for k in required if not manifest.get(k)]
    if missing:
        sys.exit(f"Error: manifest.toml missing required fields: {', '.join(missing)}")
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
    fm = read_template("frontmatter.md")
    fm = fm.replace("{unpack_dir}", unpack_dir)
    fm = fm.replace("{bootstrap}", bootstrap)
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
