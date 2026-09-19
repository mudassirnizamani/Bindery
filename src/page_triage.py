#!/usr/bin/env python3
"""
Automated Page Triage & Chapter Compilation using Jev (TypeSafe AI System One)
==============================================================================
Sits between extraction and cleaning in the pipeline.

PURPOSE:
  After OCR/EPUB extraction you have hundreds of individual page files.
  This script uses Jev to:
    1. Identify and remove junk pages (blank, pure ads, legal-only, etc.)
    2. Detect chapter/section boundaries
    3. Merge all pages between boundaries into single chapter files

  The output is a `chapters/` directory with one file per chapter/section,
  ready for the cleaning step.

IMPORTANT:
  Pages with watermarks or ads in their header/footer are NOT junk — those
  are normal book pages. Only pages with ZERO story content get deleted.

MODES:
  Default   → Analyses pages, applies decisions, writes chapter files.
  --dry-run → Prints the chapter map and page assignments without writing.

Usage:
    # Auto mode (writes chapter files)
    python3 src/page_triage.py <raw_pages_dir>

    # Dry-run (preview chapter structure only)
    python3 src/page_triage.py <raw_pages_dir> --dry-run

    # Custom confidence threshold (default 0.85)
    python3 src/page_triage.py <raw_pages_dir> --threshold 0.90

Requirements:
    pip install typesafe-sdk python-dotenv
    TYPESAFE_API_KEY must be set in your .env file or environment.
"""

import os
import sys
import json
import re
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load .env first so TYPESAFE_API_KEY is available
load_dotenv()

try:
    from typesafe_sdk import TypeSafeClient, Choice, Noul
except ImportError:
    print("❌ typesafe-sdk not installed.")
    print("   Run:  pip install typesafe-sdk")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 0.85   # Auto-apply decisions at or above this confidence
MAX_WORKERS       = 8      # Parallel Jev calls
STATE_CHAR_LIMIT  = 3000   # Send first N chars of each page to Jev


# ---------------------------------------------------------------------------
# Jev questions
# ---------------------------------------------------------------------------

JEV_QUESTIONS = {
    "should_delete": Noul(
        instructions=(
            "Should this page be ENTIRELY removed from the book? "
            "IMPORTANT: Most normal content pages will have watermarks, download site "
            "banners, or publisher ads in their header or footer — this alone does NOT "
            "make a page worth deleting. "
            "Only answer YES if the page has ZERO meaningful story, chapter, or "
            "educational content — for example: "
            "(1) a completely blank or near-blank page, "
            "(2) a page that is purely a list of other books by the publisher with no story text, "
            "(3) a page that is only a legal copyright/licensing notice with no story, "
            "(4) a page that is a duplicate of the immediately preceding page, "
            "(5) a page consisting entirely of a download-site splash or ad with no book text. "
            "If the page contains even a paragraph of actual book content, answer NO."
        )
    ),
    "is_chapter_start": Noul(
        instructions=(
            "Does this page BEGIN a new chapter, part, or major section of the book? "
            "Answer YES if the page starts with ANY of the following: "
            "(1) A chapter number (e.g. '1', '2', 'Chapter 3', 'CHAPTER IV'), "
            "(2) A part number or title (e.g. 'I', 'II', 'Part One', 'PART II'), "
            "(3) A major section heading like 'Introduction', 'Prologue', 'Epilogue', "
            "'Conclusion', 'Afterword', 'Preface', 'Foreword', 'Acknowledgments', "
            "'Notes', 'Bibliography', 'Appendix', 'Index', 'Glossary', "
            "(4) A standalone title or heading on the first line that clearly marks "
            "a new major division of the book, "
            "(5) An epigraph page (a page with only a short quote before the chapter). "
            "Answer NO if: "
            "- The page starts mid-sentence (continues from the previous page) "
            "- The page is a continuation of the current chapter's body text "
            "- The page starts with a new paragraph but within the same chapter"
        )
    ),
}


# ---------------------------------------------------------------------------
# Core triage logic
# ---------------------------------------------------------------------------

class PageTriage:
    def __init__(self, raw_pages_dir: str, threshold: float = DEFAULT_THRESHOLD, dry_run: bool = False):
        self.raw_pages_dir = Path(raw_pages_dir)
        self.threshold     = threshold
        self.dry_run       = dry_run

        if not self.raw_pages_dir.exists():
            print(f"❌ Directory not found: {raw_pages_dir}")
            sys.exit(1)

        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            print("❌ TYPESAFE_API_KEY is not set.")
            print("   Add it to your .env file or export it:  export TYPESAFE_API_KEY=your-key")
            sys.exit(1)

        self.client = TypeSafeClient()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_sorted_pages(self) -> list[Path]:
        """Return all page_XXX.txt files sorted by page number."""
        files = [
            f for f in self.raw_pages_dir.iterdir()
            if f.is_file() and re.match(r'page_\d+\.txt', f.name)
        ]
        files.sort(key=lambda f: int(re.search(r'\d+', f.name).group()))
        return files

    def _read_page_text(self, page_file: Path) -> str:
        """Read full page text."""
        try:
            return page_file.read_text(encoding='utf-8', errors='replace').strip()
        except Exception:
            return ""

    def _extract_title(self, text: str) -> str:
        """
        Extract a chapter/section title from the beginning of a page.
        Takes the first 1-3 meaningful lines and joins them.
        """
        lines = text.split('\n')
        title_parts = []

        for line in lines[:8]:  # Check first 8 lines
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Stop at page number markers like -3- or -XII-
            if re.match(r'^-\d+-$', stripped) or re.match(r'^-[IVXLCDM]+-$', stripped):
                continue

            # Stop if we hit body text (long paragraph-like line starting lowercase)
            if len(stripped) > 120 and stripped[0].islower():
                break

            # Stop if we've collected enough title parts
            if len(title_parts) >= 3:
                break

            # Stop if this looks like body text after we already have a title
            if title_parts and len(stripped) > 100:
                break

            title_parts.append(stripped)

        if not title_parts:
            return "Untitled"

        title = " — ".join(title_parts)

        # Clean up for filename safety
        return title[:120]

    def _sanitize_filename(self, name: str) -> str:
        """Make a string safe for use as a filename."""
        # Remove invalid chars
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces and special chars with underscores
        name = re.sub(r'[\s,;]+', '_', name)
        # Collapse multiple underscores
        name = re.sub(r'_+', '_', name)
        # Strip leading/trailing underscores
        name = name.strip('_')
        return name[:80]

    def _strip_page_markers(self, text: str) -> str:
        """Remove page number markers like -42- or -XII- from text."""
        # Remove lines that are just page numbers like -42- or -XII-
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'^-\d+-$', stripped) or re.match(r'^-[IVXLCDM]+-$', stripped):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    # ------------------------------------------------------------------
    # Jev calls
    # ------------------------------------------------------------------

    def _call_jev(self, page_file: Path) -> dict:
        """Send one page to Jev and return a result dict."""
        text = self._read_page_text(page_file)
        page_num = int(re.search(r'\d+', page_file.name).group())

        if not text:
            return {
                "file":             page_file.name,
                "page_num":         page_num,
                "should_delete":    0.99,
                "is_chapter_start": 0.0,
                "error":            None,
            }

        state = text[:STATE_CHAR_LIMIT]

        try:
            resp = self.client.system_one(
                state=state,
                questions=JEV_QUESTIONS,
            )
            answers = resp.answers

            return {
                "file":             page_file.name,
                "page_num":         page_num,
                "should_delete":    answers["should_delete"].noul,
                "is_chapter_start": answers["is_chapter_start"].noul,
                "error":            None,
            }
        except Exception as e:
            return {
                "file":             page_file.name,
                "page_num":         page_num,
                "should_delete":    0.0,
                "is_chapter_start": 0.0,
                "error":            str(e),
            }

    # ------------------------------------------------------------------
    # Chapter grouping
    # ------------------------------------------------------------------

    def _build_chapter_map(self, pages: list[Path], results: list[dict]) -> list[dict]:
        """
        Walk pages in order and group them into chapters.
        Returns a list of chapter dicts:
          { "title": str, "pages": [Path, ...], "start_page_num": int }
        """
        # Build a lookup: page_num → result
        result_map = {r["page_num"]: r for r in results}

        chapters = []
        current_chapter = None

        for page_file in pages:
            page_num = int(re.search(r'\d+', page_file.name).group())
            result = result_map.get(page_num)

            if not result:
                continue

            # Skip junk pages
            if result["should_delete"] >= self.threshold:
                continue

            # Skip errored pages — include them in current chapter to be safe
            is_start = False
            if not result["error"]:
                is_start = result["is_chapter_start"] >= self.threshold

            # First non-deleted page is always a chapter start
            if current_chapter is None:
                is_start = True

            if is_start:
                # Extract title from this page's text
                text = self._read_page_text(page_file)
                title = self._extract_title(text)

                current_chapter = {
                    "title": title,
                    "pages": [page_file],
                    "start_page_num": page_num,
                }
                chapters.append(current_chapter)
            else:
                # Append to current chapter
                if current_chapter:
                    current_chapter["pages"].append(page_file)

        return chapters

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self):
        pages = self._get_sorted_pages()
        total = len(pages)

        if total == 0:
            print(f"⚠  No page_XXX.txt files found in {self.raw_pages_dir}")
            return

        mode_label = "DRY-RUN (no files will be written)" if self.dry_run else f"AUTO mode (threshold: {self.threshold:.0%})"
        print(f"\n🤖 Jev Page Triage — {total} pages  [{mode_label}]")
        print("━" * 60)
        print(f"   Sending all pages to Jev in parallel ({MAX_WORKERS} workers)…\n")

        # ---- Parallel Jev calls ----------------------------------------
        results: list[dict] = []
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(self._call_jev, p): p for p in pages}
            done_count = 0
            for future in as_completed(future_map):
                done_count += 1
                print(f"   ✓ {done_count}/{total} analysed", end='\r')
                results.append(future.result())

        elapsed = time.time() - start_time
        print(f"   ✓ All {total} pages analysed in {elapsed:.1f}s{' ' * 20}")

        # Sort results by page number
        results.sort(key=lambda r: r["page_num"])

        # ---- Categorise pages -------------------------------------------
        deleted_pages   = [r for r in results if r["should_delete"] >= self.threshold]
        chapter_starts  = [r for r in results if r["is_chapter_start"] >= self.threshold
                           and r["should_delete"] < self.threshold]
        error_pages     = [r for r in results if r["error"]]

        # ---- Build chapter map ------------------------------------------
        chapters = self._build_chapter_map(pages, results)

        # ---- Print report -----------------------------------------------
        self._print_report(results, deleted_pages, chapter_starts, chapters, error_pages, total)

        # ---- Write chapter files (skip in dry-run) ----------------------
        if not self.dry_run:
            self._write_chapters(chapters)
        else:
            print("\n🔍 DRY-RUN: No files were written.")

        # ---- Save report ------------------------------------------------
        self._save_report(results, deleted_pages, chapters, elapsed, total)

    def _print_report(self, results, deleted_pages, chapter_starts, chapters, error_pages, total):
        """Print a formatted triage report."""
        n_deleted  = len(deleted_pages)
        n_chapters = len(chapters)
        n_kept     = total - n_deleted
        n_errors   = len(error_pages)

        print()

        # DELETED PAGES
        if n_deleted:
            print(f"  🗑  DELETED ({n_deleted} page{'s' if n_deleted != 1 else ''}, conf ≥ {self.threshold:.0%}):")
            for r in deleted_pages:
                print(f"      {r['file']:<20}  ({r['should_delete']:.0%} conf)")

        # ERRORS
        if n_errors:
            print(f"\n  ❌  ERRORS ({n_errors}):")
            for r in error_pages:
                print(f"      {r['file']:<20}  {r['error']}")

        # CHAPTER MAP
        print(f"\n  📖  CHAPTER MAP ({n_chapters} chapters from {n_kept} pages):")
        print(f"  {'─' * 56}")

        for i, ch in enumerate(chapters):
            page_range = f"pages {ch['pages'][0].name}–{ch['pages'][-1].name}" if len(ch['pages']) > 1 else ch['pages'][0].name
            n_pages = len(ch['pages'])
            total_chars = sum(len(self._read_page_text(p)) for p in ch['pages']) if not self.dry_run or n_pages <= 5 else 0
            size_str = f"  ({total_chars:,} chars)" if total_chars else ""

            title_display = ch['title'][:60]
            if len(ch['title']) > 60:
                title_display += "…"

            print(f"      {i+1:3d}. {title_display}")
            print(f"           └─ {n_pages} page{'s' if n_pages != 1 else ''}  ({page_range}){size_str}")

        print(f"\n  Summary: {n_deleted} deleted, {n_kept} pages → {n_chapters} chapters")

    def _write_chapters(self, chapters: list[dict]):
        """Write merged chapter files to the chapters/ directory."""
        book_dir    = self.raw_pages_dir.parent
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)

        print(f"\n  📁 Writing chapters to: {chapters_dir}/\n")

        for i, ch in enumerate(chapters):
            # Build filename
            safe_title = self._sanitize_filename(ch["title"])
            filename = f"{i+1:03d}_{safe_title}.txt"

            # Merge all page texts
            merged_parts = []
            for page_file in ch["pages"]:
                text = self._read_page_text(page_file)
                text = self._strip_page_markers(text)
                if text:
                    merged_parts.append(text)

            merged_text = "\n\n".join(merged_parts)

            # Write chapter file
            output_file = chapters_dir / filename
            output_file.write_text(merged_text, encoding='utf-8')

            n_pages = len(ch['pages'])
            print(f"      ✓ {filename:<60} ({n_pages} page{'s' if n_pages != 1 else ''}, {len(merged_text):,} chars)")

        print(f"\n  ✅ {len(chapters)} chapter files written to: {chapters_dir}/")
        print(f"     Next step — clean with:  python3 src/page_cleaner.py {chapters_dir}")

    def _save_report(self, results, deleted_pages, chapters, elapsed, total):
        """Save a JSON triage report for auditability."""
        book_dir    = self.raw_pages_dir.parent
        report_path = book_dir / "triage_report.json"

        chapter_summary = []
        for i, ch in enumerate(chapters):
            chapter_summary.append({
                "chapter_num":    i + 1,
                "title":          ch["title"],
                "start_page":     ch["start_page_num"],
                "page_count":     len(ch["pages"]),
                "page_files":     [p.name for p in ch["pages"]],
            })

        report = {
            "raw_pages_dir":   str(self.raw_pages_dir),
            "total_pages":     total,
            "threshold":       self.threshold,
            "dry_run":         self.dry_run,
            "elapsed_seconds": round(elapsed, 2),
            "summary": {
                "deleted":  len(deleted_pages),
                "chapters": len(chapters),
            },
            "deleted_pages": [
                {"file": r["file"], "confidence": r["should_delete"]}
                for r in deleted_pages
            ],
            "chapters": chapter_summary,
            "all_results": results,
        }

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n  📄 Triage report saved → {report_path.name}")
        except Exception as e:
            print(f"\n  ⚠  Could not save triage report: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automated page triage & chapter compilation using the Jev System One model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto mode — detect chapters and write merged chapter files
  python3 src/page_triage.py extracted_google/my_book/raw_pages

  # Dry-run — show chapter map without writing files
  python3 src/page_triage.py extracted_google/my_book/raw_pages --dry-run

  # Custom threshold (higher = more conservative boundary detection)
  python3 src/page_triage.py extracted_google/my_book/raw_pages --threshold 0.92
        """
    )
    parser.add_argument(
        "raw_pages_dir",
        help="Path to the raw_pages directory (e.g. extracted_google/my_book/raw_pages)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse pages and print the chapter map, but do NOT write any files."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        metavar="FLOAT",
        help=f"Confidence threshold for decisions (0–1, default: {DEFAULT_THRESHOLD}). "
             "Applies to both delete and chapter-start detection."
    )

    args = parser.parse_args()

    if not (0.0 < args.threshold <= 1.0):
        parser.error("--threshold must be a value between 0.01 and 1.0")

    triage = PageTriage(
        raw_pages_dir=args.raw_pages_dir,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )
    triage.run()


if __name__ == "__main__":
    main()
