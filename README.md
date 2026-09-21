# Bindery

Bindery turns raw PDF and EPUB extractions into clean, structured books. It handles the messy middle step that nobody talks about: going from 300 individual page files down to a coherent, readable document.

The core of it is an automated triage step powered by [Jev](https://typesafe.ai) (TypeSafe's System One model). Jev reads every page and decides what to delete, where chapters start, and where Part divisions begin — without you touching a single file manually.

---

## The Problem

When you extract a PDF or EPUB, you get something like this:

```
raw_pages/
├── page_001.txt   ← might be blank
├── page_002.txt   ← might be a publisher ad
├── page_003.txt   ← might be actual content
...
└── page_297.txt
```

Some pages are junk. Some are real content. Most split mid-sentence across page boundaries. You need to figure out which pages belong to which chapter, delete the noise, and stitch the rest into something readable. Without automation, this is 30-45 minutes of manual work per book.

Bindery does it in under 20 seconds.

---

## How It Works

```
Extract → Triage → Clean → Compile
```

**1. Extract** — Pull raw text from a PDF (via Google Vision OCR) or EPUB.

**2. Triage** (Jev-powered) — Jev reads every page in parallel and answers three questions per page:
- Is this page junk? (blank, publisher ad, pure copyright notice)
- Does this page start a new chapter?
- Does this page start a new Part?

It then deletes junk pages and merges the rest into chapters or parts, applied synchronously in reverse order so file indices never get corrupted.

**Merge strategy is automatic:** if a book has more than 15 chapters and explicit Part divisions, Bindery merges at the Part level. If the book is smaller or has no Parts, it merges at the chapter level. Same command either way.

**3. Clean** — An LLM pass removes residual noise from the merged text: watermarks, page numbers, download banners, scanning artifacts. Book content is left untouched.

**4. Compile** — Joins all cleaned files into a single `book.txt`.

---

## Setup

### Prerequisites

- Python 3.10+
- [Task](https://taskfile.dev) (task runner)
- A [TypeSafe API key](https://console.typesafe.ai) for Jev (triage step)
- An Azure OpenAI key for the cleaning step

### Install

```bash
# Clone the repo
git clone https://github.com/your-username/bindery.git
cd bindery

# Create virtualenv and install dependencies
task install
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required for triage (Jev)
TYPESAFE_API_KEY=your-typesafe-key-here

# Required for cleaning
AZURE_OPENAI_API_KEY=your-azure-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name

# Required for EPUB/PDF extraction
GOOGLE_API_KEY=your-gemini-key-here
GOOGLE_APPLICATION_CREDENTIALS=/path/to/vision-key.json
```

**Get your keys:**
- Jev / TypeSafe: [console.typesafe.ai](https://console.typesafe.ai)
- Azure OpenAI: [portal.azure.com](https://portal.azure.com)
- Google Vision: [console.cloud.google.com](https://console.cloud.google.com) (1,000 pages/month free)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (free)

---

## Usage

### Full Pipeline

```bash
# 1. Extract an EPUB
task epub -- your_book.epub

# 2. Preview what triage will do (no files changed)
task triage -- ./extracted_epub/your_book/raw_pages --dry-run

# 3. Run triage for real
task triage -- ./extracted_epub/your_book/raw_pages

# 4. Clean the merged pages
task clean -- ./extracted_epub/your_book/raw_pages

# 5. Compile into a single book file
# (see book_compiler.py)
```

### Individual Commands

```bash
# Triage with a custom confidence threshold (default: 85%)
task triage -- ./path/to/raw_pages --threshold 0.90

# Manually delete a page and renumber the rest
task delete -- ./path/to/raw_pages 42

# Manually merge a page into the previous one
task copy -- ./path/to/raw_pages 42
```

---

## Triage in Detail

The triage step is the most important part of Bindery. Here is what it does and how.

### Jev Questions

Jev receives the first 3,000 characters of each page and answers three questions simultaneously:

**`should_delete`** — Is this page pure junk with zero book content? Fires on blank pages, publisher book-list pages, pure copyright notices, download-site splash pages. A page with a watermark header but real content underneath is **not** deleted.

**`is_chapter_start`** — Does this page open a new chapter or major section? Fires on chapter numbers, section headings (Introduction, Preface, Epilogue, etc.), and epigraph pages.

**`is_part_start`** — Does this page open a new Part? Only fires when the heading literally contains the word "Part", "Book", or "Volume" followed by a number. Much stricter than chapter detection by design — a typical book has 2-6 Parts, not 37.

### Merge Strategy

After analysis, Bindery picks a merge level automatically:

| Condition | Merges at |
|-----------|-----------|
| ≤ 15 chapters detected | Chapter level |
| > 15 chapters AND Part divisions exist | Part level |
| > 15 chapters but no Parts | Chapter level |

### How Merges Are Applied

Bindery does not rename or move files to a new folder. It merges pages in place inside `raw_pages/`, using the existing `copy_page.py` and `delete_page.py` scripts. Operations run **synchronously in reverse order** (last page first) so that file renumbering never corrupts the index for pages still to be processed. Original individual page files go into `raw_pages/.trash/` for recovery if needed.

---

## Output Structure

After the full pipeline:

```
extracted_epub/your_book/
├── raw_pages/                # Merged chapter/part files (still named page_XXX.txt)
│   └── .trash/              # Original individual pages, safely archived
├── cleaned_pages/           # LLM-cleaned versions of each chapter/part file
├── book.txt                 # Final compiled book
└── triage_report.json       # Full audit trail of every Jev decision
```

---

## Supported Source Formats

| Format | Extraction Method |
|--------|------------------|
| EPUB | Direct extraction (`epub_extractor.py`) |
| PDF | Google Vision OCR (`google_vision_extractor.py`) |
| Markdown | Split into chapters (`markdown_splitter.py`) |

### Supported Languages

- **English** — Full chapter/part detection
- **Urdu (اردو)** — باب and حصہ pattern detection, watermark removal for Urdu book sites
- **Arabic (العربية)** — Right-to-left text support
- **Hindi (हिन्दी)** — Full OCR support

---

## Task Reference

| Command | Description |
|---------|-------------|
| `task install` | Set up virtualenv and install dependencies |
| `task epub -- <file>` | Extract an EPUB to raw pages |
| `task triage -- <dir>` | Run Jev triage on a raw_pages directory |
| `task triage -- <dir> --dry-run` | Preview triage decisions without changing files |
| `task clean -- <dir>` | LLM-clean a directory of pages |
| `task delete -- <dir> <page_num>` | Delete a single page and renumber |
| `task copy -- <dir> <page_num>` | Merge a page into the previous one |

---

## Security

Never commit your `.env` file or credential JSON files to git. The `.gitignore` excludes `.env`, credential files, and all extracted book content (`extracted_epub/`, `extracted_google/`).

---

## License

MIT
