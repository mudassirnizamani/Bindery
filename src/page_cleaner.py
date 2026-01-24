#!/usr/bin/env python3
"""
Page Cleaner using Azure OpenAI
Iterates over raw pages and uses LLM to clean content.
Output: book_name/cleaned_pages/page_XXX.txt
"""

import sys
import argparse
import time
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from azureOpenAIAPI import AzureClient

# Load environment variables
load_dotenv()

class PageCleaner:
    # When True, always use chunking strategy for cleaning pages.
    # When False, try full-page cleaning first, then fallback to chunking if needed.
    ALWAYS_USE_CHUNKING = True

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

    def sanitize_filename(self, name: str) -> str:
        """Sanitize string to be safe for filename."""
        # Remove invalid chars
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        name = name.replace(' ', '_')
        # Limit length just in case
        return name[:50]

    def identify_heading(self, text: str):
        """
        Uses LLM to identify Part or Chapter headings.
        Returns dict: {"name": "...", "found": bool}
        """
        prompt = f"""You are a metadata extractor.
Analyze the text below and look for a specific Part Number, Part Name, Chapter Number, or Chapter Name at the beginning of the text.

TEXT:
{text[:2000]}

INSTRUCTIONS:
1. Look for explicit headings like "Chapter 1", "Chapter One", "Part I", "Part 1: The Beginning", "1. The Start", or just a chapter title if it's clearly a heading.
2. If found, return the heading name.
3. If NOT found, return empty name.
4. Output must be strictly valid JSON.

OUTPUT FORMAT:
{{
  "name": "Chapter 1",
  "found": true
}}

OR

{{
  "name": "",
  "found": false
}}

JSON OUTPUT:
"""
        response = self.azure_client.generate_content(prompt)
        if not response:
            return {"name": "", "found": False}

        try:
            # Strip markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())
            return data
        except Exception as e:
            print(f"    ⚠ Failed to parse heading JSON: {e}")
            return {"name": "", "found": False}

    def split_text_into_chunks(self, text: str, chunk_size: int = 5000) -> list[str]:
        """
        Splits text into chunks of roughly chunk_size characters.
        Strategy:
        1. Split by double newlines (paragraphs) to maintain structure.
        2. If a paragraph is too large, split by words/tokens (fallback).
        3. Strict order preservation.
        """
        # Split by paragraph separators (2 or more newlines)
        # We capture the separator so we can reconstruct the text perfectly.
        parts = re.split(r'(\n\s*\n)', text)

        chunks = []
        current_chunk = []
        current_length = 0

        for part in parts:
            if not part: continue

            part_len = len(part)

            # If adding this part exceeds chunk size...
            if current_length + part_len > chunk_size:
                # If current buffer is not empty, flush it
                if current_length > 0:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Now we have an empty buffer. Does the part fit on its own?
                if part_len > chunk_size:
                    # Part is huge (e.g. a very long paragraph). Split it deeper.
                    # We use the token-based split logic here.
                    tokens = re.findall(r'\S+|\s+', part)
                    sub_chunk = []
                    sub_len = 0
                    for token in tokens:
                        sub_chunk.append(token)
                        sub_len += len(token)
                        # Split if we cross threshold and end on punctuation
                        if sub_len >= chunk_size and not token.isspace() and token[-1] in '.!?':
                            chunks.append("".join(sub_chunk))
                            sub_chunk = []
                            sub_len = 0

                    if sub_chunk:
                        # Add remainder to current buffer
                        current_chunk = sub_chunk
                        current_length = sub_len
                else:
                    # Part fits in a new empty chunk
                    current_chunk.append(part)
                    current_length += part_len
            else:
                # Fits in current chunk
                current_chunk.append(part)
                current_length += part_len

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def _get_cleaning_prompt(self, text: str) -> str:
        """Returns the standardized prompt for cleaning text."""
        return f"""You are a professional book editor.
Your task is to clean the text below by removing only noise, while STRICTLY PRESERVING all story content and headings.

TEXT TO CLEAN:
{text}

STRICT INSTRUCTIONS:
1. **REMOVE NOISE ONLY**: Remove page numbers, headers, footers, website links, URLs, "Download from..." text, watermarks, and scanning artifacts.
2. **PRESERVE HEADINGS**: You MUST keep all Chapter Headings, Part Headings, Section Titles, and Subtitles exactly as they appear. Do not remove or reformat them.
3. **PRESERVE CONTENT**: You MUST keep 100% of the original story text. Do not summarize, rewrite, shorten, or omit any paragraph or sentence.
4. **OUTPUT FORMAT**: Return ONLY the cleaned text. Do not use markdown code blocks. Do not add comments like "Here is the text".

CLEANED TEXT:
"""

    def clean_page_with_chunking(self, content: str) -> str:
        """
        Fallback method to clean page in chunks.
        Triggered when whole-page cleaning fails (e.g., content filter).
        """
        chunks = self.split_text_into_chunks(content)
        print(f"    ℹ Content Filter/Error detected. Switching to chunking strategy ({len(chunks)} chunks)...")

        cleaned_chunks = []
        for i, chunk in enumerate(chunks):
            prompt = self._get_cleaning_prompt(chunk)
            try:
                chunk_response = self.azure_client.generate_content(prompt)
            except Exception as e:
                print(f"      ⚠ Chunk API call failed: {e}")
                chunk_response = None

            if chunk_response:
                # Strip markdown code blocks
                if chunk_response.startswith("```"):
                     lines = chunk_response.split('\n')
                     if lines[0].startswith("```"):
                         lines = lines[1:]
                     if lines and lines[-1].startswith("```"):
                         lines = lines[:-1]
                     chunk_response = '\n'.join(lines)
                cleaned_chunks.append(chunk_response)
            else:
                print(f"      ⚠ Chunk {i+1} failed/filtered. Using raw text for this chunk.")
                cleaned_chunks.append(chunk) # Fallback Option B: Use raw chunk

            time.sleep(0.5) # Slight delay between chunks

        return "".join(cleaned_chunks)

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
            # Check if already cleaned (checking for any file starting with page_XXX)
            # file_path.stem is typically 'page_001'
            file_stem = file_path.stem
            existing_files = list(cleaned_pages_dir.glob(f"{file_stem}*"))

            if existing_files:
                 print(f"  [{i+1}/{total_files}] Skipping {file_path.name} (Already exists: {existing_files[0].name})", end='\r')
                 continue

            print(f"  [{i+1}/{total_files}] Cleaning: {file_path.name}...", end='', flush=True)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not content.strip():
                    print(" Skipped (Empty)")
                    # Create empty file with basic name
                    output_file = cleaned_pages_dir / f"{file_stem}.txt"
                    output_file.touch()
                    continue

                # Step 1: Clean Content
                final_content = content  # Fallback

                if self.ALWAYS_USE_CHUNKING:
                    # Always use chunking strategy
                    print(f"\n    ℹ Using chunking strategy (ALWAYS_USE_CHUNKING=True)...")
                    cleaned_text = self.clean_page_with_chunking(content)
                else:
                    # Try full-page cleaning first, then fallback to chunking if needed
                    prompt = self._get_cleaning_prompt(content)
                    try:
                        cleaned_text = self.azure_client.generate_content(prompt)
                    except Exception as e:
                        print(f"    ⚠ API call failed: {e}")
                        cleaned_text = None

                    # Strip code blocks from initial attempt to ensure accurate length check
                    if cleaned_text and cleaned_text.startswith("```"):
                         lines = cleaned_text.split('\n')
                         if lines[0].startswith("```"):
                             lines = lines[1:]
                         if lines and lines[-1].startswith("```"):
                             lines = lines[:-1]
                         cleaned_text = '\n'.join(lines)

                    # Check if we need to fallback to chunking (Failure or < 95% retention)
                    if cleaned_text is None:
                        cleaned_text = self.clean_page_with_chunking(content)
                    elif len(content) > 0 and (len(cleaned_text) / len(content)) < 0.95:
                        print(f"    ⚠ Cleaned content is significantly shorter ({len(cleaned_text)}/{len(content)} chars, {int((len(cleaned_text)/len(content))*100)}%). Triggering chunking process...")
                        cleaned_text = self.clean_page_with_chunking(content)

                if cleaned_text:
                    # Check for potential truncation (90% rule)
                    raw_len = len(content)
                    clean_len = len(cleaned_text)
                    print(f"    ℹ Content Length: {int((clean_len/raw_len)*100)}%). Possible truncation. Raw={raw_len}, Cleaned={clean_len}")
                    if raw_len > 0 and (clean_len / raw_len) < 0.9:
                        print(f"    ⚠ WARNING: Cleaned content is significantly shorter ({clean_len}/{raw_len} chars, {int((clean_len/raw_len)*100)}%). Possible truncation.")

                    final_content = cleaned_text
                else:
                    print(" ⚠ Cleaning failed completely. Using raw content fallback.", end='')

                # Step 2: Identify Heading
                heading_data = self.identify_heading(final_content)

                final_filename = f"{file_stem}.txt"
                if heading_data.get("found"):
                    safe_name = self.sanitize_filename(heading_data.get("name", "").strip())
                    if safe_name:
                        final_filename = f"{file_stem}_{safe_name}.txt"
                        print(f" -> Found: {safe_name}", end='')

                output_file = cleaned_pages_dir / final_filename
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(final_content)

                print(" ✓ Done")

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
