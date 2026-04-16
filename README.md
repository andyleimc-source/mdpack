# mdpack

> Convert any directory of docs to clean Markdown, ready for RAG / LLM ingestion.

> 🚧 **WIP.** `0.0.1` is a name placeholder on PyPI — real functionality lands in `0.1.0`.

## What this will be

A single CLI that walks a folder full of mixed-format documents (DOCX, CSV, XLSX, PDF, PPTX, HTML)
and emits clean Markdown, mirroring the source directory structure. Designed to feed downstream
RAG / LLM pipelines — in particular [mdrag](https://github.com/andyleimc-source/mdrag), a local
semantic-search MCP server for Markdown folders.

Why a separate tool? Conversion is a messy, format-specific problem (pandoc for DOCX, Docling for
PDF, openpyxl for XLSX, and so on). Keeping it out of `mdrag` keeps both tools focused: `mdpack`
produces Markdown, `mdrag` indexes Markdown.

## Planned MVP (0.1.0)

| Format | Backend | Status |
|--------|---------|--------|
| DOCX   | pandoc  | planned |
| CSV    | stdlib  | planned |
| XLSX   | openpyxl | planned |

Later (0.2.0+): PDF (Docling, non-OCR), PPTX, HTML, EPUB.

## Install (placeholder)

```bash
pip install mdpack
mdpack --version      # 0.0.1 (placeholder — no conversion yet)
```

## Companion project

- **[mdrag](https://github.com/andyleimc-source/mdrag)** — give any local Markdown folder a
  semantic-search MCP server. Run `mdpack` first to convert mixed-format docs, then point `mdrag`
  at the output directory.

## License

[MIT](./LICENSE)
