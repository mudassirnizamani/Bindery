# Book Extraction Pipeline Guide

This repository contains a modular pipeline for extracting, cleaning, and compiling text from PDF and EPUB books. The process is divided into three distinct stages to ensure accuracy and flexibility.

## Overview

1.  **Extraction**: Get raw text from the source file.
    *   **PDFs**: Uses Google Cloud Vision API (OCR) to extract text page-by-page.
    *   **EPUBs**: Extracts internal chapters/sections directly as pages.
2.  **Cleaning**: Uses Google Gemini LLM to remove noise (headers, footers, links, watermarks) while preserving content and headings.
3.  **Compilation**: Combines all cleaned pages into a single `book.txt`.

## Prerequisites

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Environment Variables**:
    You need API keys for Google Cloud Vision (OCR) and Google Gemini (LLM). Create a `.env` file or export them:
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/vision-service-account.json"
    export GOOGLE_API_KEY="your-gemini-api-key"
    ```

## 1. Extraction

### For EPUBs
Extracts content based on the book's internal structure (Spine).
```bash
python3 epub_extractor.py book_name.epub
```
*   **Output**: `extracted_epub/book_name/raw_pages/page_XXX.txt`

### For PDFs
Uses Google Vision API for high-accuracy OCR.
```bash
python3 google_vision_extractor.py book_name.pdf
```
*   **Output**: `extracted_google/book_name/raw_pages/page_XXX.txt`

## 2. Page Management (Manual — Optional)

If you need to remove a specific page (e.g., a blank page, an ad, or a duplicate) from the extracted raw pages, you can use the `delete_page.py` tool. This tool will delete the specified page, renumber all subsequent pages to maintain the sequence, and update the `pages_index.json` file.

**Usage:** Provide the path to the `raw_pages` directory and the page number to delete.

```bash
# Syntax
python3 src/delete_page.py <path_to_raw_pages> <page_number>

# Example: Delete page 20
python3 src/delete_page.py extracted_google/book_name/raw_pages 20
```

*   **Result**:
    *   `page_020.txt` is deleted.
    *   `page_021.txt` becomes `page_020.txt`.
    *   `page_022.txt` becomes `page_021.txt`, and so on.
    *   `pages_index.json` is updated with new counts and file references.

## 2.5. Automated Page Triage & Chapter Compilation with Jev (Recommended)

Instead of manually reviewing pages one-by-one, use `page_triage.py` to let the **Jev System One model** automatically:
1. **Delete junk pages** — blank pages, pure publisher book-lists, pure legal notices, download splashes.
2. **Detect chapter boundaries** — identifies where each new chapter, part, or major section begins.
3. **Merge pages into chapters** — if a page is *not* a chapter boundary, it gets merged into the previous page using the `copy_page.py` script.

This happens **synchronously and in reverse order** so that the sequential `page_XXX.txt` filenames are perfectly maintained without index shifts or file corruption. 

> **Important:** Pages with watermarks, banners, or ads in their *header/footer* are **not** deleted. Only pages with **zero** book content are removed.

### Setup

```bash
# Install the Jev SDK
pip install typesafe-sdk

# Add your TypeSafe API key to .env
# Register at: https://console.typesafe.ai
echo "TYPESAFE_API_KEY=your-key-here" >> .env
```

### Usage

```bash
# Auto mode — applies all delete and merge (copy) actions to raw_pages/
python3 src/page_triage.py extracted_google/book_name/raw_pages

# Dry-run — shows what will be merged and deleted without touching files
python3 src/page_triage.py extracted_google/book_name/raw_pages --dry-run

# Custom confidence threshold (default: 0.85 = 85%)
python3 src/page_triage.py extracted_google/book_name/raw_pages --threshold 0.90
```

**Recommended workflow:**
1. Run `--dry-run` first to preview the actions.
2. If it looks correct, run without `--dry-run` to apply the changes to `raw_pages/`.

### Example Output

```
🤖 Jev Page Triage — 351 pages  [AUTO mode (threshold: 85%)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🗑  TO DELETE (4 pages):
      page_004.txt          (delete conf 99%)
      ...

  📖 CHAPTER BOUNDARIES FOUND (18 chapters):
      page_001.txt          (chapter start conf 98%)
      page_004.txt          (chapter start conf 99%)
      ...

  🔗 TO MERGE (329 pages into the above chapters)

  Summary: 4 deleted, 329 merged into 18 chapters.
  
  ⚙️  Applying decisions (synchronously in reverse order to prevent index shifts)...
    🔗  Merging page_351.txt into previous page...
    🔗  Merging page_350.txt into previous page...
    ...
  ✅ Triage complete.
```

**Output:**
```
book_name/
├── raw_pages/           # Contains your new, fully merged chapters (still named page_XXX.txt)
│   └── .trash/          # Safely holds the original pages that were deleted or merged
└── triage_report.json   # Full audit trail
```

## 3. Cleaning

Uses an LLM to clean the text. It preserves chapter headings but removes artifacts like "Page 22", watermarks, and URLs.

**Usage:** Point it to the `raw_pages` directory after the triage step.

```bash
python3 src/page_cleaner.py extracted_google/book_name/raw_pages
```
*   **Output**: `.../book_name/cleaned_pages/page_XXX.txt`


## 4. Compilation

Combines the cleaned pages into a single file in the correct order.

**Usage:** Point it to the `cleaned_pages` directory.

```bash
# Example for EPUB
python3 book_compiler.py extracted_epub/book_name/cleaned_pages

# Example for PDF
python3 book_compiler.py extracted_google/book_name/cleaned_pages
```
*   **Output**: `.../book_name/book.txt`

## Full Workflow Example

**Processing "The Art of War.epub":**

1.  **Extract**:
    ```bash
    python3 epub_extractor.py "The Art of War.epub"
    ```
2.  **Clean**:
    ```bash
    python3 page_cleaner.py "extracted_epub/The Art of War/raw_pages"
    ```
3.  **Compile**:
    ```bash
    python3 book_compiler.py "extracted_epub/The Art of War/cleaned_pages"
    ```
4.  **Result**: You will find the final book text at `extracted_epub/The Art of War/book.txt`.
