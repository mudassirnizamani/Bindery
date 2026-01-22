#!/usr/bin/env python3
"""
Page Cleaner using Google Gemini
Iterates over raw pages and uses LLM to clean content.
Output: book_name/cleaned_pages/page_XXX.txt
"""

import sys
import os
import argparse
import time
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PageCleaner:
    def __init__(self, raw_pages_dir: str, gemini_api_key: str = None):
        self.raw_pages_dir = Path(raw_pages_dir)
        if not self.raw_pages_dir.exists():
            raise FileNotFoundError(f"Raw pages directory not found: {raw_pages_dir}")

        # Initialize Gemini
        try:
            api_key = gemini_api_key or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("❌ No Gemini API key found. Please set GOOGLE_API_KEY environment variable.")
                sys.exit(1)

            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            print(f"✓ Gemini initialized (Model: gemini-2.0-flash-exp)")
        except Exception as e:
            print(f"❌ Failed to initialize Gemini: {e}")
            sys.exit(1)

    def _call_gemini_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Helper to call Gemini with retry logic for rate limits"""
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"    ⏳ Rate limit hit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                print(f"    ⚠ Gemini call failed: {e}")
                # Wait a bit before retry even for other errors
                time.sleep(2)
        return None

    def clean_pages(self):
        """Main function to clean pages."""
        # Setup output directory
        # Assuming raw_pages_dir is like .../book_name/raw_pages/
        book_dir = self.raw_pages_dir.parent
        cleaned_pages_dir = book_dir / "cleaned_pages"
        cleaned_pages_dir.mkdir(exist_ok=True)

        print(f"\n🧹 Cleaning pages from: {self.raw_pages_dir}")
        print(f"📂 Output: {cleaned_pages_dir}")

        # Get list of files
        files = sorted([f for f in self.raw_pages_dir.iterdir() if f.suffix == '.txt'])
        total_files = len(files)

        if total_files == 0:
            print("⚠ No text files found in raw_pages directory.")
            return

        print(f"  Found {total_files} pages.")

        for i, file_path in enumerate(files):
            # Check if already cleaned
            output_file = cleaned_pages_dir / file_path.name
            if output_file.exists():
                 print(f"  [{i+1}/{total_files}] Skipping {file_path.name} (Already exists)", end='\r')
                 continue

            print(f"  [{i+1}/{total_files}] Cleaning: {file_path.name}...", end='', flush=True)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not content.strip():
                    print(" Skipped (Empty)")
                    # Create empty file to maintain sequence? Or just skip?
                    # Let's create empty file so we know it was processed.
                    output_file.touch()
                    continue

                prompt = f"""You are a professional book editor.
Clean the following page text.

TEXT:
{content}

TASK:
1. Remove all headers and footers (e.g. page numbers, book titles repeated on top/bottom).
2. Remove any website links, URLs, or "Download from..." text.
3. Remove watermarks or scanning artifacts.
4. **IMPORTANT**: PRESERVE all Chapter Headings, Part Headings, and Titles exactly as they are. Do NOT remove them.
5. PRESERVE the original story/content exactly. Do not summarize or rewrite.
6. Return ONLY the cleaned text. Do not add markdown code blocks or "Here is the text" comments.

CLEANED TEXT:
"""
                cleaned_text = self._call_gemini_with_retry(prompt)

                if cleaned_text:
                    # Strip code blocks if model adds them despite instructions
                    if cleaned_text.startswith("```"):
                         lines = cleaned_text.split('\n')
                         if lines[0].startswith("```"):
                             lines = lines[1:]
                         if lines and lines[-1].startswith("```"):
                             lines = lines[:-1]
                         cleaned_text = '\n'.join(lines)

                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(cleaned_text)
                    print(" ✓ Done")
                else:
                    print(" ❌ Failed")

                # Small delay to be nice to API
                time.sleep(1)

            except Exception as e:
                print(f" ❌ Error: {e}")

        print(f"\n✨ Cleaning complete!")

def main():
    parser = argparse.ArgumentParser(description="Clean raw pages using Gemini LLM")
    parser.add_argument("raw_pages_dir", help="Directory containing raw text pages")
    parser.add_argument("--key", help="Gemini API Key", required=False)

    args = parser.parse_args()

    cleaner = PageCleaner(args.raw_pages_dir, gemini_api_key=args.key)
    cleaner.clean_pages()

if __name__ == "__main__":
    main()
