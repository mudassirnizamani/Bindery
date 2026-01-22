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

## 2. Page Management (Optional)

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

## 3. Cleaning

Uses Gemini LLM to clean the raw text. It preserves chapter headings but removes artifacts like "Page 22", watermarks, and URLs.

**Usage:** Point it to the `raw_pages` directory created in the previous step.

```bash
# Example for EPUB
python3 page_cleaner.py extracted_epub/book_name/raw_pages

# Example for PDF
python3 page_cleaner.py extracted_google/book_name/raw_pages
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
