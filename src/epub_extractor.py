#!/usr/bin/env python3
"""
EPUB Content Extractor
Simple extraction: Iterates over the spine and extracts text from each item as a "page".
Output: book_name/raw_pages/page_XXX.txt
"""

import sys
import os
import re
import shutil
import argparse
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup

class EpubExtractor:
    def __init__(self, epub_path: str):
        self.epub_path = Path(epub_path)
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    def _sanitize_filename(self, filename: str) -> str:
        """Removes characters from a string that are not safe for filenames."""
        # Replace tabs and newlines with spaces first
        filename = filename.replace('\t', ' ').replace('\n', ' ')
        # Remove invalid chars
        filename = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
        # Replace multiple spaces with single underscore
        filename = re.sub(r'\s+', '_', filename)
        return filename[:100] # Limit length

    def extract(self, output_dir: str = "extracted_epub"):
        """Main function to process the EPUB."""
        base_output = Path(output_dir)
        base_output.mkdir(parents=True, exist_ok=True)
        
        book_title = self.epub_path.stem
        safe_book_title = self._sanitize_filename(book_title)
        book_output_dir = base_output / safe_book_title
        
        if book_output_dir.exists():
            # Warn user instead of silently deleting? Or just clear it?
            # Instructions imply fresh start.
            shutil.rmtree(book_output_dir)
        book_output_dir.mkdir(parents=True, exist_ok=True)
        
        raw_pages_dir = book_output_dir / "raw_pages"
        raw_pages_dir.mkdir(exist_ok=True)
        
        print(f"\n📂 Extracting: {self.epub_path.name}")
        print(f"   Output: {book_output_dir}")
        
        try:
            book = epub.read_epub(str(self.epub_path))
            
            print(f"\n⚙️  Processing Spine (Internal Files)...")
            
            processed_hrefs = set()
            file_counter = 1
            
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                # Type 9 is 'application/xhtml+xml' usually (document)
                if not item:
                    continue

                # Check media type if get_type() isn't sufficient or if we want to be safe
                # Typically we want XHTML/HTML content.
                # ebooklib item types: ITEM_DOCUMENT = 9
                if item.get_type() != 9:
                    continue
                
                href = item.get_name()
                if href in processed_hrefs:
                    continue
                processed_hrefs.add(href)

                # Parse content
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()
                # Attempt to find the very first prominent heading (h1, h2, h3 or title)
                # We limit the search to the first ~20 tags to ensure we only grab from the top of the document
                heading_text = ""
                for element in soup.find_all(True, limit=20):
                    if element.name in ['h1', 'h2', 'h3', 'title']:
                        if element.get_text(strip=True):
                            heading_text = element.get_text(separator=' - ', strip=True)
                            break
                
                text = soup.get_text(separator='\n', strip=True)
                
                # Prepend the embedded heading if found, to give the AI a strong hint
                if heading_text and not text.startswith(heading_text):
                    text = f"{heading_text}\n\n{text}"
                
                # Save as page
                if text.strip(): # Only save if there is content
                    filename = f"page_{file_counter:03d}.txt"
                    with open(raw_pages_dir / filename, 'w', encoding='utf-8') as f:
                        f.write(text)
                    file_counter += 1

            print(f"  ✓ Extracted {file_counter - 1} raw pages/sections.")
            print(f"\n✨ Extraction complete!")

        except Exception as e:
            print(f"  ❌ Error processing EPUB: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Extract text from EPUB files (Spine -> Raw Pages)")
    parser.add_argument("epub_path", help="Path to EPUB file")
    parser.add_argument("--output", "-o", default="extracted_epub", help="Output directory")
    
    args = parser.parse_args()
    
    extractor = EpubExtractor(args.epub_path)
    extractor.extract(args.output)

if __name__ == "__main__":
    main()
