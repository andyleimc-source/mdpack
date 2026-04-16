# mdpack

> Convert any directory of docs to clean Markdown, ready for RAG / LLM ingestion.

One CLI. Point it at a folder of DOCX / XLSX / CSV files, get back a mirrored tree of
Markdown — frontmatter-tagged with source path and converter used, inline base64 images
stripped, no surprises.

## Install

```bash
pip install mdpack
```

For DOCX support, install [pandoc](https://pandoc.org/installing.html) as well:

```bash
brew install pandoc          # macOS
apt install pandoc           # Ubuntu / Debian
```

Check your setup:

```bash
mdpack doctor
```

## Usage

### Convert a whole directory

```bash
mdpack convert ~/Desktop/reports
# Writes Markdown into ~/Desktop/reports/converted/
```

The input directory tree is mirrored: `reports/q1/sales.xlsx` becomes
`reports/converted/q1/sales.md`.

### Convert a single file

```bash
mdpack convert proposal.docx -o out/
```

### Options

- `-o, --output PATH` — output directory (default: `<src>/converted` for dirs, `<src>_md/`
  for a single file).
- `--force` — re-convert even if the output is newer than the source.
- `--quiet` — only print errors.

Incremental by default — mdpack skips files whose output is newer than the source, so
you can safely re-run it over a large folder.

### Inspect supported formats

```bash
mdpack formats
```

```
Supported formats:
  csv    .csv
  xlsx   .xlsx
  docx   .docx
```

## What the output looks like

Every converted file gets a YAML frontmatter block so downstream tools know where it
came from:

```markdown
---
title: Q1 Sales Review
source: q1/sales.xlsx
converter: xlsx
converter_version: mdpack 0.1.0
converted_at: 2026-04-16T05:30:00Z
---

# sales

## Summary
| Region | Revenue | YoY |
|---|---|---|
| APAC | 4.2M | +12% |
...
```

## Pair with mdrag

[mdrag](https://github.com/andyleimc-source/mdrag) is a companion project — a local,
offline Markdown semantic-search MCP server for Claude Code / Cursor / Cline.

Typical workflow:

```bash
# 1. Convert mixed-format docs to Markdown
mdpack convert ~/Desktop/reports

# 2. Point mdrag at the output
mdrag vault add reports ~/Desktop/reports/converted

# 3. Ask Claude Code natural-language questions against the vault
```

## Roadmap

Next up (0.2.0): **PDF** (Docling, non-OCR mode), **PPTX** (pandoc), **HTML / EPUB**
(pandoc). Watch mode to auto-convert on source file change is also planned.

Scanned / image-only PDFs (OCR) are intentionally out of scope — use
[Docling](https://github.com/DS4SD/docling) or `tesseract` upstream if you need them.

## Development

```bash
git clone https://github.com/andyleimc-source/mdpack
cd mdpack
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## License

[MIT](./LICENSE)
