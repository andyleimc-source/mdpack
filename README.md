# mdpack

> Convert any directory of docs to clean Markdown, ready for RAG / LLM ingestion.

One CLI. Point it at a folder of DOCX / PPTX / PDF / XLSX / CSV files, get back a mirrored
tree of Markdown — frontmatter-tagged with source path and converter used, inline base64
images stripped, no surprises.

Want it to **auto-sync on every save** instead of running by hand? Use `mdpack watch`.

## Install

```bash
pip install mdpack
```

For DOCX and PPTX, install [pandoc](https://pandoc.org/installing.html):

```bash
brew install pandoc          # macOS
apt install pandoc           # Ubuntu / Debian
```

PDF is optional (Docling pulls ~1GB of torch/transformers) — only install if you need it:

```bash
pip install 'mdpack[pdf]'
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

Input tree is mirrored: `reports/q1/sales.xlsx` → `reports/converted/q1/sales.md`.

### Convert a single file

```bash
mdpack convert proposal.docx -o out/
```

### Options

- `-o, --output PATH` — output directory (default: `<src>/converted` for dirs).
- `--force` — re-convert even if the output is newer than the source.
- `--quiet` — only print errors.

Incremental by default — mdpack skips files whose output is newer than the source.

### Inspect supported formats

```bash
mdpack formats
```

```
Supported formats:
  csv    .csv
  xlsx   .xlsx
  docx   .docx
  pptx   .pptx
  pdf    .pdf
```

---

## Watch mode

**The killer feature.** Instead of running `mdpack convert` every time you save a file,
point `mdpack watch` at a directory and it stays running — every create / modify / delete
/ rename is batched with a 1.5s debounce and applied to the output tree.

```bash
mdpack watch ~/Desktop/reports
# Watches ~/Desktop/reports, keeps ~/Desktop/reports/converted/ in sync. Ctrl-C to stop.
```

Or with a separate output directory:

```bash
mdpack watch ~/Desktop/A -o ~/Desktop/B
```

**What it does on each event**:

| Source change | What happens in output |
|---|---|
| new `.docx` added | corresponding `.md` created |
| `.xlsx` edited | `.md` re-generated |
| `.csv` deleted | `.md` deleted |
| file renamed | old `.md` deleted, new one created |
| file inside the output dir touched | ignored (no infinite loops) |

On startup, `watch` does one incremental sync pass first, so the output is already
aligned when event handling begins. Use `--no-initial-sync` to skip that, or
`--force-initial-sync` to rebuild everything.

### Keeping it running in the background

`mdpack watch` runs in the foreground. Pick whichever background option suits your setup:

**tmux** — simplest, survives terminal close:
```bash
tmux new -d -s mdpack 'mdpack watch ~/Desktop/reports'
tmux attach -t mdpack          # inspect
```

**nohup** — crude but works everywhere:
```bash
nohup mdpack watch ~/Desktop/reports > ~/mdpack.log 2>&1 &
```

**launchd (macOS)** — start on login, auto-restart on crash. Save as
`~/Library/LaunchAgents/com.example.mdpack.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.mdpack</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/mdpack</string>
    <string>watch</string>
    <string>/Users/you/Desktop/reports</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/mdpack.log</string>
  <key>StandardErrorPath</key><string>/tmp/mdpack.log</string>
</dict>
</plist>
```
Load it: `launchctl load ~/Library/LaunchAgents/com.example.mdpack.plist`

**systemd user unit (Linux)** — similar idea, save as `~/.config/systemd/user/mdpack.service`:
```ini
[Unit]
Description=mdpack watch

[Service]
ExecStart=/usr/bin/mdpack watch %h/Desktop/reports
Restart=on-failure

[Install]
WantedBy=default.target
```
Enable: `systemctl --user enable --now mdpack.service`

---

## Pair with mdrag

[mdrag](https://github.com/andyleimc-source/mdrag) is a companion project — a local,
offline Markdown semantic-search MCP server for Claude Code / Cursor / Cline.

**Fully-automatic pipeline** (source changes → Markdown updated → index updated):

```bash
# Terminal 1: keep Markdown in sync with the source dir
mdpack watch ~/Desktop/reports -o ~/Desktop/reports-md

# Terminal 2 (or launched by Claude Code): serve the vault + auto-reindex
mdrag vault add reports ~/Desktop/reports-md     # one-time registration
mdrag serve                                      # watches the vault, re-indexes on change
```

Now edit any `.docx` / `.pptx` / `.xlsx` under `~/Desktop/reports/` — within ~3 seconds,
the matching `.md` is rewritten, mdrag notices and re-embeds it, and your next search from
Claude Code sees the updated content. No manual steps. Both tools are
**loosely coupled** — they don't know about each other, they just both watch the middle
directory.

---

## What the output looks like

Every converted file gets a YAML frontmatter block so downstream tools know where it
came from:

```markdown
---
title: Q1 Sales Review
source: q1/sales.xlsx
converter: xlsx
converter_version: mdpack 0.2.0
converted_at: 2026-04-16T05:30:00Z
---

# sales

## Summary
| Region | Revenue | YoY |
|---|---|---|
| APAC | 4.2M | +12% |
...
```

## Roadmap

Next up (0.3.0): **HTML** and **EPUB** (pandoc), and ready-to-use background scripts
(maybe a `mdpack install-service` that writes the plist / systemd unit for you).

Scanned / image-only PDFs (OCR) remain intentionally out of scope — if you need them,
run [Docling](https://github.com/docling-project/docling) with its OCR pipeline upstream,
or use `tesseract`.

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
