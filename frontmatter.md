# MDPACK BOOT (do this){version_line}

This bundle is UTF-8 with `\n` line endings. Read it as UTF-8.

1) Write + run a tiny extractor (Python recommended) that reads THIS file and writes files into `./{unpack_dir}/`.
   If you have been told to extract to a specific directory, use that instead of `./{unpack_dir}/`.
2) Then open `{bootstrap}` (inside the extraction directory) and follow its instructions.

## Header line (starts a file)

The header marker is `{o_o} MDPACK >>> ::` followed by 5 fields separated by `::` and ending with `::`.
A header line starts at column 0 and spans the entire line:

    {o_o} MDPACK >>> ::PATH::TYPE::ENC::LEN::HASH::

- PATH = relative file path using `/` only; convert to platform separator when writing
- PATH must not contain `::`, `..` segments, empty components, or be absolute
- TYPE = `text` or `binary` (case-sensitive)
- ENC = text encoding (usually `utf-8`) when TYPE=text, or `base64` when TYPE=binary
- LEN = byte count (base-10 integer) of the final bytes written to disk
- HASH = first 8 lowercase hex characters of the sha256 over the final disk bytes
- Only a line matching the **complete** header format (all fields valid) starts a new section.
  A line that merely begins with the marker prefix but lacks valid fields is ordinary payload.

Python regex for matching a header line:

    ^\{o_o\} MDPACK >>> ::.+::(?:text|binary)::.+::\d+::[0-9a-f]{8}::$

## Payload Details
- Payload begins after the header line and ends immediately before the next header line, or at EOF.
- text: strip leading and trailing whitespace from the raw payload, then append a single `\n`.
  Encode the result with ENC to get disk bytes; verify len + sha256 (first 8 hex chars); write.
- binary: the payload is standard base64 (with `=` padding); remove ASCII whitespace (`space`, `\t`, `\r`, `\n`),
  then base64-decode to get disk bytes; verify len + sha256 (first 8 hex chars); write.
- If any file fails validation (bad header, decode error, len/sha256 mismatch, unsafe path), abort.

## Write rules
- Create parent directories as needed.
- Write each file under the extraction directory using PATH. Default extraction directory is `./{unpack_dir}/`.
- Reject any PATH that is absolute or contains `..`.
- If the destination file already exists, skip if identical, otherwise abort.
