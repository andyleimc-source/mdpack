# Changelog

## 0.2.1 (2026-04-16)

### Fixes

- **PPTX converter switched from pandoc to `python-pptx`.** Pandoc only gained PPTX
  *input* support in 3.8.3 (released days ago) — most users, including Ubuntu's apt
  packages and many existing Homebrew installs, don't have it. `python-pptx` reads
  the PPTX XML directly and has no sharp version edges. Slides become `## Slide N: <title>`
  sections; tables and bulleted text are preserved; all speaker notes and embedded
  images are skipped.
- CI now only needs Ubuntu's stock pandoc (used for DOCX tests); PPTX tests run
  in-process via `python-pptx`.

## 0.2.0 (2026-04-16)

### New features

- **`mdpack watch <src> [-o OUT]`** — keeps `OUT/` in sync with `src/` as files change.
  File create/modify/delete/move are batched with a 1.5s debounce, then re-converted or
  removed. Ctrl-C to stop. See the README's **Watch mode** section for backgrounding
  (nohup / tmux / launchd) and the recommended setup with `mdrag serve`.
- **PDF support** (optional) — `pip install 'mdpack[pdf]'` pulls [Docling](https://github.com/docling-project/docling).
  Without the extra installed, the converter still lists PDF in `mdpack formats` but raises
  an actionable error on first use pointing to the extras install.
- **PPTX support** — via pandoc, same plumbing as DOCX.
- **`mdpack doctor`** now reports pandoc (explicitly mentions DOCX+PPTX), openpyxl,
  docling (info-level — optional), and watchdog status.

### Refactors

- Extracted `run_pandoc()` into `converters/_pandoc.py`. DOCX and PPTX share the same
  subprocess implementation; adding HTML/EPUB later should be a handful of lines each.
- Moved the private `_run_job()` from `cli.py` into `walker.run_job()` (public) so
  both the `convert` command and the watcher reuse it.

### Infrastructure

- `.github/workflows/ci.yml` — ruff + pytest on Python 3.10/3.11/3.12, pandoc
  pre-installed in the runner so DOCX/PPTX tests execute in CI.

### Notes

- PDF extras (`mdpack[pdf]`) pull torch + transformers (~1GB). Only install if you
  actually need PDF — core install remains lightweight.
- The watcher intentionally refuses to re-convert files it wrote itself. If you point
  `-o` at a subdirectory of the source (e.g. `mdpack watch A -o A/converted`), writes
  under `A/converted/` are filtered out of the event stream.

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
