# Changelog

## 0.1.0 (2026-04-16)

First functional release.

### Features

- `mdpack convert <src> [-o OUT] [--force] [--quiet]` — walks a file or directory,
  converts supported formats to Markdown, mirrors the input structure, skips files
  whose output is newer than the source (incremental).
- `mdpack formats` — list supported formats and their backends.
- `mdpack doctor` — report Python version, pandoc availability, openpyxl version,
  and supported extensions; exits non-zero if anything needed is missing.
- Supported formats:
  - **DOCX** via `pandoc` (→ GFM, `--wrap=none`)
  - **XLSX** via `openpyxl` (one `## <sheet>` section per non-empty sheet)
  - **CSV** via stdlib `csv` (auto-detects delimiter: `,;\t|`)
- YAML frontmatter injected on every output file: `title`, `source`, `converter`,
  `converter_version`, `converted_at` — downstream tools (e.g. [mdrag](https://github.com/andyleimc-source/mdrag))
  can trace back to the original file.
- Inline base64 images in DOCX output are stripped to `<!-- image -->` to keep
  Markdown chunk-friendly (a single image can otherwise blow a file past multi-MB).

### Design choices

- Conversion failures on one file do **not** abort the batch — they are reported
  and counted in the final summary. Exit code is `2` if anything failed.
- Each converter is independent; missing `pandoc` surfaces an actionable error
  (with `brew install pandoc` hint) only when a DOCX is actually encountered.

## 0.0.1 (2026-04-16)

Placeholder release to reserve the `mdpack` name on PyPI. No functional code.
