# Whitepaper to LinkedIn Posts

An automated tool that converts PDF whitepapers into engaging LinkedIn social media posts by extracting charts/figures, analyzing them with AI, and generating human-like content.

## Features

- **PDF Processing**: Converts PDFs to markdown while preserving figure references
- **Smart Image Extraction**: Detects and processes charts/figures >300px wide
- **AI Analysis**: Uses GPT-4o Vision to analyze charts and extract insights
- **Content Generation**: Creates 2 unique LinkedIn posts per image with AI-proof prompting
- **Data Storage**: Stores posts in NocoDB with metadata and images
- **PDF Export**: Generates LinkedIn-style PDFs for review and scheduling
- **State Management**: Tracks processing progress with SQLite database

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [markitdown](https://github.com/microsoft/markitdown) CLI tool
- OpenAI API key
- NocoDB instance with API access

### Installation

1. Clone the repository:
```bash
git clone https://github.com/dunctk/whitepaper-to-socials.git
cd whitepaper-to-socials
```

2. Install dependencies:
```bash
uv sync
```

3. Install markitdown CLI:
```bash
pip install markitdown
```

4. Set up environment variables:
```bash
cp env_example .env
# Edit .env with your API keys and NocoDB configuration
```

### Environment Variables

Required variables in `.env`:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-proj-...

# NocoDB Configuration  
NOCODB_API_KEY=your-nocodb-token
NOCODB_BASE_URL=https://your-nocodb-instance.com
NOCODB_TABLE_ID=your-table-id
NOCODB_BASE_ID=your-base-id

# Optional: Custom whitepaper name for posts
WHITEPAPER_NAME="our latest research report"
```

### NocoDB Table Schema

Create a table in NocoDB with these fields:

- `post` (LongText): LinkedIn post content
- `image` (Attachment): Chart/figure image
- `image_description` (LongText): AI analysis of the chart
- `image_index` (Number): Sequential image identifier
- `image_filename` (SingleLineText): Local image filename
- `date_posted` (DateTime, nullable): Publishing timestamp

## Usage

### 1. Prepare Input

Place your PDF whitepaper in the `content_inputs/` directory:

```bash
mkdir -p content_inputs
cp your-whitepaper.pdf content_inputs/whitepaper.pdf
```

### 2. Generate Posts

**Test mode** (process one image):
```bash
uv run whitepaper2li.py --pdf content_inputs/whitepaper.pdf --nocodb-table linkedin --test
```

**Production mode** (process all images):
```bash
uv run whitepaper2li.py --pdf content_inputs/whitepaper.pdf --nocodb-table linkedin
```

### 3. Generate PDF Report

Create a LinkedIn-style PDF with all posts:
```bash
uv run posts_to_pdf.py
```

Optional: specify output filename:
```bash
uv run posts_to_pdf.py --output my-posts.pdf
```

## How It Works

### Processing Pipeline

1. **PDF Conversion**: Uses `markitdown` to convert PDF to Markdown
2. **Image Extraction**: Scans for embedded raster images >300px wide
3. **AI Analysis**: GPT-4o Vision analyzes each chart for insights
4. **Content Generation**: GPT-4.1 creates 2 distinct LinkedIn posts per chart
5. **Storage**: Saves posts to NocoDB with images and metadata
6. **State Tracking**: SQLite database prevents duplicate processing

### AI-Proof Prompting

The system includes sophisticated prompting to avoid AI-sounding language:

- **Banned buzzwords**: Comprehensive list of overused AI terms
- **Date awareness**: Includes current date context to prevent outdated references  
- **Variety enforcement**: Checks recent posts to avoid repetitive openings
- **Human tone**: Explicit instructions for natural, professional language

### Data Storage

- **Local State**: SQLite database (`state.db`) tracks processing by PDF hash + image index
- **NocoDB**: Stores posts with full metadata for scheduling and management
- **Fallback**: CSV export if NocoDB is unavailable
- **Images**: Local filenames stored for reliable PDF generation

## Architecture

```
Input PDF → markitdown → Markdown + Images → GPT-4o Analysis → GPT-4.1 Posts → NocoDB → LinkedIn-style PDF
                ↓                              ↓                    ↓
           Image Extraction              AI Insights         State Tracking
```

## File Structure

```
whitepaper-to-socials/
├── whitepaper2li.py          # Main processing script
├── posts_to_pdf.py           # PDF generation script
├── content_inputs/           # Input PDFs and extracted images
│   ├── images/              # Auto-extracted chart images
│   └── (your-whitepaper.pdf)
├── pdf_outputs/             # Generated LinkedIn-style PDFs
├── state.db                 # Processing state database
├── .env                     # Environment configuration
└── requirements files
```

## Output Examples

### LinkedIn Posts
Each chart generates 2 unique posts with:
- Professional, human-like tone
- Relevant insights from the data
- Proper LinkedIn formatting with line breaks
- Strategic hashtags (max 3)
- Reference to source whitepaper

### PDF Reports
LinkedIn-style layout with:
- One post per A4 page
- Centered content boxes
- Original chart images
- Clean, professional formatting

## Troubleshooting

### Common Issues

**"No valid images found"**
- Ensure PDF contains raster images >300px wide
- Vector graphics won't be detected

**"Missing environment variables"**
- Check all required variables are set in `.env`
- Verify NocoDB API credentials

**"Image download errors"**
- System automatically falls back to local images
- Ensure `content_inputs/images/` directory exists

### Debug Mode

Run with test mode to process one image at a time:
```bash
uv run whitepaper2li.py --pdf your-file.pdf --nocodb-table table-name --test
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Credits

Built with:
- [OpenAI GPT-4](https://openai.com/) for AI analysis and content generation
- [NocoDB](https://nocodb.com/) for data management
- [markitdown](https://github.com/microsoft/markitdown) for PDF processing
- [ReportLab](https://www.reportlab.com/) for PDF generation