#!/usr/bin/env python3
"""
Page Cleaner using Azure OpenAI
Iterates over raw pages and uses LLM to clean content.
Output: book_name/cleaned_pages/page_XXX.txt
"""

import sys
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv
from azureOpenAIAPI import AzureClient

# Load environment variables
load_dotenv()

class PageCleaner:
    def __init__(self, raw_pages_dir: str):
        self.raw_pages_dir = Path(raw_pages_dir)
        if not self.raw_pages_dir.exists():
            raise FileNotFoundError(f"Raw pages directory not found: {raw_pages_dir}")

        # Initialize Azure Client
        try:
            self.azure_client = AzureClient()
        except Exception as e:
            print(f"❌ Failed to initialize Azure Client: {e}")
            sys.exit(1)

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
                    output_file.touch()
                    continue

                prompt = f"""You are a professional book editor.
Your task is to clean the text below by removing only noise, while STRICTLY PRESERVING all story content and headings.

TEXT TO CLEAN:
{content}

STRICT INSTRUCTIONS:
1. **REMOVE NOISE ONLY**: Remove page numbers, headers, footers, website links, URLs, "Download from..." text, watermarks, and scanning artifacts.
2. **PRESERVE HEADINGS**: You MUST keep all Chapter Headings, Part Headings, Section Titles, and Subtitles exactly as they appear. Do not remove or reformat them.
3. **PRESERVE CONTENT**: You MUST keep 100% of the original story text. Do not summarize, rewrite, shorten, or omit any paragraph or sentence.
4. **OUTPUT FORMAT**: Return ONLY the cleaned text. Do not use markdown code blocks. Do not add comments like "Here is the text".

CLEANED TEXT:
"""
                cleaned_text = self.azure_client.generate_content(prompt)

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
    parser = argparse.ArgumentParser(description="Clean raw pages using Azure OpenAI")
    parser.add_argument("raw_pages_dir", help="Directory containing raw text pages")

    args = parser.parse_args()

    cleaner = PageCleaner(args.raw_pages_dir)
    cleaner.clean_pages()

if __name__ == "__main__":
    main()
