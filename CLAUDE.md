# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python automation tool that converts PDF whitepapers into LinkedIn social media posts. It extracts charts/figures from PDFs, analyzes them using OpenAI's GPT-4o Vision, and generates LinkedIn posts that are stored in NocoDB for social media scheduling.

## Key Commands

### Setup & Installation
```bash
# Install dependencies using uv
uv pip install -r requirements.lock

# Set up environment variables
cp env_example .env
# Edit .env with your API keys
```

### Main Execution
```bash
# Run in test mode (processes one image at a time)
python whitepaper2li.py --pdf whitepaper.pdf --nocodb-table linkedin --test

# Run in production mode (processes all images)
python whitepaper2li.py --pdf whitepaper.pdf --nocodb-table linkedin
```

## Architecture

The system follows a multi-stage pipeline:

1. **PDF Processing**: Uses `markitdown` CLI to convert PDF to Markdown while preserving figure references
2. **Image Extraction**: Detects embedded raster images >300px wide, assigns sequential indices
3. **State Management**: Uses SQLite (`state.db`) to track processing state by PDF SHA-256 + image_index
4. **Content Generation**: 
   - GPT-4o Vision analyzes charts and extracts insights (JSON format)
   - GPT-4.1 generates two distinct LinkedIn post variations
5. **Persistence**: Stores posts in NocoDB via REST API

## Environment Configuration

Required environment variables (see `env_example`):
- `OPENAI_API_KEY`: GPT-4.1 & GPT-4o access
- `NOCODB_API_KEY`: NocoDB personal token
- `NOCODB_BASE_URL`: NocoDB instance URL
- `NOCODB_TABLE_ID`: NocoDB table identifier
- `NOCODB_BASE_ID`: NocoDB base identifier

## Data Storage

### NocoDB Schema
Posts are stored with these fields:
- `post` (text): LinkedIn post content
- `image` (attachment URL): Chart/figure image
- `date_posted` (nullable DATETIME): Publishing timestamp
- `image_description` (text): Chart analysis
- `image_index` (int): Sequential image identifier

### Local State
- SQLite database (`state.db`) tracks processing progress
- Intermediate Markdown files saved to `/tmp/{slug}.md`
- Fallback CSV output to `/tmp/posts_{date}.csv` if NocoDB fails

## Operating Modes

- **Test mode** (`--test`): Process exactly one unprocessed image for content review
- **Production mode** (default): Process all remaining images in batch

## Input Requirements

- PDF must contain rasterized chart images (not vector graphics)
- Charts should be >300px wide to be detected
- Input PDF placed in project root or specified via `--pdf` flag
- Sample content in `content_inputs/` directory with whitepaper.pdf and extracted images