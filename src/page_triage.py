#!/usr/bin/env python3
"""
Automated Page Triage using Jev (TypeSafe AI System One)
==============================================================================
Sits between extraction and cleaning in the pipeline.

PURPOSE:
  After OCR/EPUB extraction you have hundreds of individual page files.
  This script uses Jev to:
    1. Identify and remove junk pages (blank, pure ads, legal-only, etc.)
    2. Detect chapter/section boundaries
    3. If a page is NOT a chapter boundary, it merges it into the previous page.

  IMPORTANT: It uses `delete_page.py` and `copy_page.py` internally to apply
  these changes synchronously in reverse order, so the original filenames 
  (page_001.txt, etc.) are maintained and the pages_index.json is updated safely.

MODES:
  Default   → Analyses pages, applies decisions synchronously.
  --dry-run → Prints the plan without modifying files.

Usage:
    # Auto mode
    python3 src/page_triage.py <raw_pages_dir>

    # Dry-run
    python3 src/page_triage.py <raw_pages_dir> --dry-run
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

# Import existing page management tools (delete + merge logic)
# These live in the same src/ directory
sys.path.insert(0, str(Path(__file__).parent))
from delete_page import delete_page
from copy_page import copy_page

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
            "(1) A completely blank or near-blank page. "
            "(2) A page that is purely a list of other books by the publisher with no story text. "
            "(3) A page that is only a legal copyright/licensing notice with no story content. "
            "(4) A page that is an exact duplicate of the immediately preceding page. "
            "(5) A page consisting entirely of a download-site splash or ad with no book text. "
            "CRITICAL: If the page contains even a single paragraph of actual book content, answer NO."
        )
    ),
    "is_chapter_start": Noul(
        instructions=(
            "Does this page BEGIN a new chapter, part, or major section of the book? "
            "Answer YES if the page starts with ANY of the following: "
            "(1) A chapter number (e.g. '1', '2', 'Chapter 3', 'CHAPTER IV'). "
            "(2) A part number or title (e.g. 'I', 'II', 'Part One', 'PART II'). "
            "(3) A major section heading like 'Introduction', 'Prologue', 'Epilogue', "
            "'Conclusion', 'Afterword', 'Preface', 'Foreword', 'Acknowledgments', "
            "'Notes', 'Bibliography', 'Appendix', 'Index', 'Glossary'. "
            "(4) A standalone title or heading on the first line that clearly marks "
            "a new major division of the book. "
            "(5) An epigraph page (a page with only a short quote before the chapter). "
            "Answer NO if: "
            "- The page is just a normal page of continuous text. "
            "- The page starts mid-sentence (continues from the previous page). "
            "- The page starts with a new paragraph but it's just regular body text within the same chapter. "
            "CRITICAL: Only answer YES if the page is explicitly formatted as the start of a new major section or chapter."
        )
    ),
}

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

    def _get_sorted_pages(self) -> list[Path]:
        """Return all page_XXX.txt files sorted by page number."""
        files = [
            f for f in self.raw_pages_dir.iterdir()
            if f.is_file() and re.match(r'page_\d+\.txt', f.name)
        ]
        files.sort(key=lambda f: int(re.search(r'\d+', f.name).group()))
        return files

    def _read_page_text(self, page_file: Path) -> str:
        try:
            return page_file.read_text(encoding='utf-8', errors='replace').strip()
        except Exception:
            return ""

    def _call_jev(self, page_file: Path) -> dict:
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
            resp = self.client.system_one(state=state, questions=JEV_QUESTIONS)
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

    def run(self):
        pages = self._get_sorted_pages()
        total = len(pages)

        if total == 0:
            print(f"⚠  No page_XXX.txt files found in {self.raw_pages_dir}")
            return

        mode_label = "DRY-RUN" if self.dry_run else f"AUTO mode (threshold: {self.threshold:.0%})"
        print(f"\n🤖 Jev Page Triage — {total} pages  [{mode_label}]")
        print("━" * 60)
        print(f"   Sending all pages to Jev in parallel ({MAX_WORKERS} workers)…\n")

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

        # Organize results
        deleted_pages = []
        merged_pages = []
        kept_starts = []
        error_pages = []

        # Sort ascending for the printed report
        results.sort(key=lambda r: r["page_num"])
        
        for r in results:
            if r["error"]:
                error_pages.append(r)
                continue
            if r["should_delete"] >= self.threshold:
                deleted_pages.append(r)
            elif r["is_chapter_start"] < self.threshold and r["page_num"] > 1:
                # Merge into previous page if NOT a chapter start
                merged_pages.append(r)
            else:
                # It IS a chapter start (or it's page 1, which can't be merged backward)
                kept_starts.append(r)

        self._print_report(deleted_pages, merged_pages, kept_starts, error_pages)

        if not self.dry_run:
            print("\n  ⚙️  Applying decisions (synchronously in reverse order to prevent index shifts)...")
            
            # CRITICAL: We must iterate in REVERSE order so that when we copy/delete
            # page N, we don't mess up the indices of page N+1, N+2, etc.
            results.sort(key=lambda r: r["page_num"], reverse=True)
            
            for r in results:
                if r["error"]:
                    continue
                page_num = r["page_num"]
                
                if r["should_delete"] >= self.threshold:
                    print(f"    🗑  Deleting {r['file']}...")
                    delete_page(str(self.raw_pages_dir), page_num)
                elif r["is_chapter_start"] < self.threshold and page_num > 1:
                    print(f"    🔗  Merging {r['file']} into previous page...")
                    copy_page(str(self.raw_pages_dir), page_num)
                    
            print("\n  ✅ Triage complete.")
        else:
            print("\n🔍 DRY-RUN: No files were changed.")

        self._save_report(results, elapsed, total)

    def _print_report(self, deleted_pages, merged_pages, kept_starts, error_pages):
        print()
        if error_pages:
            print(f"  ❌ ERRORS ({len(error_pages)}):")
            for r in error_pages:
                print(f"      {r['file']:<20}  {r['error']}")

        if deleted_pages:
            print(f"  🗑  TO DELETE ({len(deleted_pages)} pages):")
            for r in deleted_pages:
                print(f"      {r['file']:<20}  (delete conf {r['should_delete']:.0%})")

        print(f"\n  📖 CHAPTER BOUNDARIES FOUND ({len(kept_starts)} chapters):")
        for r in kept_starts:
            print(f"      {r['file']:<20}  (chapter start conf {r['is_chapter_start']:.0%})")

        print(f"\n  🔗 TO MERGE ({len(merged_pages)} pages into the above chapters)")
        
        print(f"\n  Summary: {len(deleted_pages)} deleted, {len(merged_pages)} merged into {len(kept_starts)} chapters.")

    def _save_report(self, results, elapsed, total):
        book_dir = self.raw_pages_dir.parent
        report_path = book_dir / "triage_report.json"
        
        report = {
            "raw_pages_dir":   str(self.raw_pages_dir),
            "total_pages":     total,
            "threshold":       self.threshold,
            "dry_run":         self.dry_run,
            "elapsed_seconds": round(elapsed, 2),
            "all_results":     results,
        }
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Automated page triage using Jev.")
    parser.add_argument("raw_pages_dir", help="Path to the raw_pages directory")
    parser.add_argument("--dry-run", action="store_true", help="Print plan but do not modify files.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Confidence threshold")

    args = parser.parse_args()
    if not (0.0 < args.threshold <= 1.0):
        parser.error("--threshold must be between 0.01 and 1.0")

    triage = PageTriage(args.raw_pages_dir, args.threshold, args.dry_run)
    triage.run()

if __name__ == "__main__":
    main()
