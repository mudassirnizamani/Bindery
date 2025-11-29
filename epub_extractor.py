#!/usr/bin/env python3
"""
EPUB Content Extractor (Deterministic Structure + AI Refinement)
Stage 1: Deterministic Extraction using EbookLib (TOC/NCX/Headings).
Stage 2: AI Refinement using Gemini (Cleaning & Renaming).
"""

import sys
import os
import re
import shutil
import argparse
import json
import time
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EpubExtractor:
    def __init__(self, epub_path: str, gemini_api_key: str = None):
        self.epub_path = Path(epub_path)
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

        # Initialize Gemini
        try:
            api_key = gemini_api_key or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("⚠ No Gemini API key found. AI Refinement (Stage 3) will be skipped.")
                self.gemini_model = None
            else:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
                print(f"✓ Gemini initialized (Model: gemini-2.0-flash-exp)")
        except Exception as e:
            print(f"⚠ Failed to initialize Gemini: {e}")
            self.gemini_model = None

    def _sanitize_filename(self, filename: str) -> str:
        """Removes characters from a string that are not safe for filenames."""
        # Replace tabs and newlines with spaces first
        filename = filename.replace('\t', ' ').replace('\n', ' ')
        # Remove invalid chars
        filename = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
        # Replace multiple spaces with single underscore
        filename = re.sub(r'\s+', '_', filename)
        return filename[:100] # Limit length

    def _call_gemini_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Helper to call Gemini with retry logic for rate limits"""
        if not self.gemini_model:
            return None
            
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        print(f"    ⏳ Rate limit hit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                print(f"    ⚠ Gemini call failed: {e}")
                return None
        return None

    def get_toc_structure(self, book):
        """
        Parses the EPUB's Table of Contents to identify parts and chapters.
        Returns a list of tuples: (title, href, level).
        Level 0 = Part, Level 1 = Chapter, etc.
        """
        toc_list = []
        # Use the new navigation document (nav.xhtml) if available (EPUB 3)
        nav_item = book.get_item_with_id('nav')
        if nav_item:
            try:
                soup = BeautifulSoup(nav_item.get_content(), 'html.parser')
                nav_ol = soup.find('nav', {'epub:type': 'toc'})
                if nav_ol:
                    nav_ol = nav_ol.find('ol')
                
                if nav_ol:
                    toc_list = self._parse_toc_ol(nav_ol)
            except Exception as e:
                print(f"  ⚠ Failed to parse nav.xhtml: {e}")
        
        # Fallback to older NCX format if nav parsing fails or is empty (EPUB 2)
        if not toc_list:
            try:
                toc = book.toc
                toc_list = self._parse_ncx_toc(toc)
            except Exception as e:
                print(f"  ⚠ Failed to parse NCX TOC: {e}")
                
        return toc_list

    def _parse_toc_ol(self, ol_element, level=0):
        """Recursively parses a <ol> element from a nav.xhtml file."""
        items = []
        for li in ol_element.find_all('li', recursive=False):
            a_tag = li.find('a')
            if a_tag and a_tag.get('href'):
                title = a_tag.get_text(strip=True)
                href = a_tag['href'] # Keep full href with anchor
                items.append((title, href, level))
            
            nested_ol = li.find('ol')
            if nested_ol:
                items.extend(self._parse_toc_ol(nested_ol, level + 1))
        return items

    def _parse_ncx_toc(self, toc, level=0):
        """Recursively parses the older NCX TOC structure."""
        items = []
        for item in toc:
            # item can be a tuple (section, title, children) or a Link/Section object
            if isinstance(item, tuple) or isinstance(item, list):
                if len(item) >= 2 and hasattr(item[1], 'title'):
                    # (section, title, children) - ebooklib structure
                    # item[1] is the Link object
                    title = item[1].title
                    href = item[1].href # Keep full href
                    items.append((title, href, level))
                    if len(item) > 2 and item[2]:
                        items.extend(self._parse_ncx_toc(item[2], level + 1))
                elif hasattr(item[0], 'title'): # (Link/Section, ...)
                     title = item[0].title
                     href = item[0].href # Keep full href
                     items.append((title, href, level))
            elif hasattr(item, 'title'): # Single Link/Section object
                title = item.title
                href = item.href # Keep full href
                items.append((title, href, level))
        return items

    def refine_chapters(self, chapters_dir: Path):
        """
        Stage 3: AI Refinement
        Iterates through extracted chapters, cleans content, and renames files.
        """
        if not self.gemini_model:
            print("\n⚠ Skipping Stage 3 (AI Refinement) - No API Key")
            return

        print(f"\n🧠 Stage 3: AI Refinement (Cleaning & Renaming)...")
        
        files = sorted([f for f in chapters_dir.iterdir() if f.suffix == '.txt'])
        total_files = len(files)
        
        for i, file_path in enumerate(files):
            print(f"  [{i+1}/{total_files}] Refining: {file_path.name}...", end='', flush=True)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip very small files (likely empty or just title)
            if len(content) < 50:
                print(" Skipped (Too short)")
                continue

            prompt = f"""You are a professional book editor.
Clean the following chapter text and extract its metadata.

TEXT:
{content[:30000]}... (truncated)

TASK:
1. **Clean the Text**:
   - Remove "Project Gutenberg" headers/footers.
   - Remove repeated headers/footers (e.g., book title on every page).
   - Remove watermarks or scanning artifacts.
   - Fix broken paragraph breaks if obvious.
   - **PRESERVE** the original story/content exactly. Do not summarize.

2. **Extract Metadata**:
   - Determine the **True Chapter Number** (e.g., "1", "I", "One"). If none, use null.
   - Determine the **True Chapter Title** (e.g., "The Beginning"). If none, use a descriptive title from the first line.

RESPONSE FORMAT (JSON ONLY):
{{
  "chapter_number": "1",
  "chapter_title": "The Beginning",
  "cleaned_content": "The full cleaned text..."
}}
"""
            response_text = self._call_gemini_with_retry(prompt)
            
            if response_text:
                try:
                    # Clean markdown code blocks
                    if '```json' in response_text:
                        response_text = response_text.split('```json')[1].split('```')[0]
                    elif '```' in response_text:
                        response_text = response_text.split('```')[1].split('```')[0]
                    
                    data = json.loads(response_text)
                    
                    new_content = data.get("cleaned_content", content)
                    chapter_num = data.get("chapter_number")
                    chapter_title = data.get("chapter_title", "Untitled")
                    
                    # Save cleaned content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    # Rename file
                    # Pattern: Chapter_[Number]_[Title].txt
                    # If number is null, just [Title].txt
                    # We keep the original file prefix (chapter_XX) to preserve order?
                    # The user wants "proper names to each chapter and thier number".
                    # Let's use the original sort order index + the extracted info.
                    
                    # Extract original index from filename "chapter_01_..."
                    original_idx_match = re.match(r'chapter_(\d+)_', file_path.name)
                    original_idx = original_idx_match.group(1) if original_idx_match else "00"
                    
                    safe_title = self._sanitize_filename(chapter_title)
                    if chapter_num:
                        safe_num = self._sanitize_filename(str(chapter_num))
                        new_name = f"chapter_{original_idx}_Num_{safe_num}_{safe_title}.txt"
                    else:
                        new_name = f"chapter_{original_idx}_{safe_title}.txt"
                    
                    new_path = file_path.parent / new_name
                    if new_path != file_path:
                        os.rename(file_path, new_path)
                        print(f" -> Renamed to: {new_name}")
                    else:
                        print(" -> Cleaned (No rename)")
                        
                except Exception as e:
                    print(f" ⚠ Failed to parse AI response: {e}")
            else:
                print(" ⚠ AI request failed")

    def extract(self, output_dir: str = "extracted_epub"):
        """Main function to process the EPUB."""
        base_output = Path(output_dir)
        base_output.mkdir(parents=True, exist_ok=True)
        
        book_title = self.epub_path.stem
        safe_book_title = self._sanitize_filename(book_title)
        book_output_dir = base_output / safe_book_title
        
        if book_output_dir.exists():
            shutil.rmtree(book_output_dir)
        book_output_dir.mkdir(parents=True, exist_ok=True)
        
        chapters_dir = book_output_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        
        print(f"\n📂 Extracting: {self.epub_path.name}")
        print(f"   Output: {book_output_dir}")
        
        try:
            book = epub.read_epub(str(self.epub_path))
            
            # Stage 1: Deterministic Extraction
            print(f"\n⚙️  Stage 1: Deterministic Structure Extraction...")
            
            # Get Structure
            toc_structure = self.get_toc_structure(book)
            print(f"  ✓ Found {len(toc_structure)} TOC entries.")
            
            # Save structure for reference
            structure_data = []
            for t, h, l in toc_structure:
                structure_data.append({"title": t, "href": h, "level": l})
            with open(book_output_dir / "structure.json", "w") as f:
                json.dump({"toc": structure_data}, f, indent=2)

            # Group TOC entries by file
            file_toc_map = {}
            for title, href, level in toc_structure:
                if '#' in href:
                    filename, anchor = href.split('#', 1)
                else:
                    filename, anchor = href, None
                
                if filename not in file_toc_map:
                    file_toc_map[filename] = []
                file_toc_map[filename].append({'title': title, 'anchor': anchor, 'level': level})

            # Process Spine
            processed_hrefs = set()
            file_counter = 0
            
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                if not item or item.get_type() != 9: 
                    continue
                
                href = item.get_name()
                if href in processed_hrefs:
                    continue
                processed_hrefs.add(href)

                soup = BeautifulSoup(item.get_content(), 'html.parser')
                
                toc_entries = file_toc_map.get(href, [])
                
                if not toc_entries:
                    # Fallback
                    h1 = soup.find('h1')
                    h2 = soup.find('h2')
                    title = "Untitled Section"
                    level = 1
                    if h1:
                        title = h1.get_text(strip=True)
                        level = 0
                    elif h2:
                        title = h2.get_text(strip=True)
                        level = 1
                    
                    if not title:
                        title = f"Section {file_counter}"
                        
                    self._save_chapter(chapters_dir, file_counter, title, level, soup, None)
                    file_counter += 1
                    continue
                
                if len(toc_entries) == 1 and not toc_entries[0]['anchor']:
                     entry = toc_entries[0]
                     self._save_chapter(chapters_dir, file_counter, entry['title'], entry['level'], soup, None)
                     file_counter += 1
                     continue

                # Multi-chapter split logic
                body = soup.find('body') or soup
                top_elements = body.find_all(recursive=False)
                if not top_elements:
                    top_elements = [body]

                anchor_to_entry = {e['anchor']: e for e in toc_entries if e['anchor']}
                
                if not anchor_to_entry and len(toc_entries) > 1:
                     self._save_chapter(chapters_dir, file_counter, toc_entries[0]['title'], toc_entries[0]['level'], soup, None)
                     file_counter += 1
                     continue

                split_indices = []
                for i, elem in enumerate(top_elements):
                    ids = [elem.get('id')] + [e.get('id') for e in elem.find_all(True)]
                    ids = [i for i in ids if i]
                    
                    match = None
                    for id_val in ids:
                        if id_val in anchor_to_entry:
                            match = anchor_to_entry[id_val]
                            break
                    
                    if match:
                        split_indices.append((i, match))
                
                split_indices.sort(key=lambda x: x[0])
                
                unique_splits = []
                seen_indices = set()
                for idx, entry in split_indices:
                    if idx not in seen_indices:
                        unique_splits.append((idx, entry))
                        seen_indices.add(idx)
                
                current_start = 0
                current_entry = toc_entries[0]
                
                for idx, entry in unique_splits:
                    chunk_elements = top_elements[current_start:idx]
                    if chunk_elements:
                        text = self._elements_to_text(chunk_elements)
                        if text.strip():
                             self._save_text(chapters_dir, file_counter, current_entry['title'], current_entry['level'], text)
                             file_counter += 1
                    
                    current_start = idx
                    current_entry = entry
                
                chunk_elements = top_elements[current_start:]
                if chunk_elements:
                    text = self._elements_to_text(chunk_elements)
                    if text.strip():
                        self._save_text(chapters_dir, file_counter, current_entry['title'], current_entry['level'], text)
                        file_counter += 1

            print(f"  ✓ Extracted {file_counter} raw chapters.")
            
            # Stage 3: AI Refinement
            self.refine_chapters(chapters_dir)

            print(f"\n✨ Extraction complete!")

        except Exception as e:
            print(f"  ❌ Error processing EPUB: {e}")
            sys.exit(1)

    def _elements_to_text(self, elements):
        """Convert a list of BS4 elements to text."""
        text_parts = []
        for elem in elements:
            # Remove scripts
            for script in elem(["script", "style"]):
                script.decompose()
            text_parts.append(elem.get_text(separator='\n', strip=True))
        return '\n\n'.join(text_parts)

    def _save_chapter(self, output_dir, number, title, level, soup, anchor):
        """Save a whole soup/element as a chapter."""
        # Remove scripts
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator='\n', strip=True)
        self._save_text(output_dir, number, title, level, text)

    def _save_text(self, output_dir, number, title, level, text):
        """Write text to file."""
        section_type = "Part" if level == 0 else "Chapter"
        safe_title = self._sanitize_filename(title)
        filename = f"chapter_{number:02d}_{section_type}_{safe_title}.txt"
        
        with open(output_dir / filename, 'w', encoding='utf-8') as f:
            f.write(text)

def main():
    parser = argparse.ArgumentParser(description="Extract text from EPUB files (Deterministic + AI Refinement)")
    parser.add_argument("epub_path", help="Path to EPUB file")
    parser.add_argument("--output", "-o", default="extracted_epub", help="Output directory")
    parser.add_argument("--key", help="Gemini API Key", required=False)
    
    args = parser.parse_args()
    
    extractor = EpubExtractor(args.epub_path, gemini_api_key=args.key)
    extractor.extract(args.output)

if __name__ == "__main__":
    main()
