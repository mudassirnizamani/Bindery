#!/usr/bin/env python3
"""
EPUB Content Extractor
Extracts text from EPUB files and organizes it into a folder structure.
"""

import sys
import os
import shutil
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re
import argparse
import json
import time
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EpubExtractor:
    def __init__(self, epub_path: str, gemini_api_key: str = None):
        """
        Initialize EPUB Extractor
        
        Args:
            epub_path: Path to the EPUB file
            gemini_api_key: Google AI API key
        """
        self.epub_path = Path(epub_path)
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")
            
        # Initialize Gemini
        try:
            api_key = gemini_api_key or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("✗ No Gemini API key found. Set GOOGLE_API_KEY env var.")
                sys.exit(1)

            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-flash-lite-latest')
            print(f"✓ Gemini initialized")
        except Exception as e:
            print(f"✗ Failed to initialize Gemini: {e}")
            sys.exit(1)

        try:
            self.book = epub.read_epub(self.epub_path)
            print(f"✓ Loaded EPUB: {self.epub_path.name}")
            print(f"  Title: {self.book.get_metadata('DC', 'title')[0][0] if self.book.get_metadata('DC', 'title') else 'Unknown'}")
        except Exception as e:
            print(f"✗ Failed to load EPUB: {e}")
            sys.exit(1)
            
        self.book_structure = None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename"""
        # Replace tabs and newlines with spaces first
        name = name.replace('\t', ' ').replace('\n', ' ')
        # Remove invalid chars
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace multiple spaces with single underscore
        name = re.sub(r'\s+', '_', name)
        # Limit length
        return name[:50]

    def _clean_html(self, html_content: bytes) -> str:
        """Convert HTML content to clean text"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text
        text = soup.get_text()
        
        # Basic whitespace normalization
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Drop blank lines
        text = '\n'.join(line for line in lines if line)
        
        return text

    def _refine_content_with_llm(self, text: str) -> str:
        """Refine text content using Gemini to fix formatting"""
        if not text or len(text) < 50:
            return text
            
        # Process in chunks if too large (Gemini limit)
        # But for now, let's try to process the whole chapter or chunks of it
        # A chapter can be long. 
        
        prompt = f"""You are a professional book editor. Format the following text to look like a proper book page.

TEXT TO FORMAT:
{text[:30000]}... (truncated if too long)

TASK:
1. Remove multiple spaces, tabs, and weird indentation.
2. Fix broken line breaks (join sentences that are split across lines).
3. Preserve paragraph structure (keep empty lines between paragraphs).
4. Remove any remaining artifacts like "[Page 12]" or headers/footers.
5. Return ONLY the formatted text.

IMPORTANT: Do not summarize. Do not change the words. Just fix the formatting."""

        try:
            # We might need to handle long texts by splitting them.
            # For now, let's assume chapters fit in context window (1M tokens for Gemini 1.5 Flash)
            # But we are using flash-lite which might have smaller limits? 
            # The code uses 'gemini-flash-lite-latest'.
            
            # Let's use a simpler prompt for safety and speed
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"  ⚠ Text refinement failed: {e}")
            return text

    def _get_toc_content(self) -> str:
        """Get text content from the beginning of the book for structure analysis"""
        toc_content = ""
        # Get first 5 items from spine or until we have enough text
        spine_ids = [item[0] for item in self.book.spine]
        
        for i, item_id in enumerate(spine_ids[:10]): # Check first 10 items
            item = self.book.get_item_with_id(item_id)
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
                
            text = self._clean_html(item.get_content())
            if len(text) > 100:
                toc_content += f"\n\n--- SECTION {i+1} ---\n"
                toc_content += text[:2000] # Limit per section
                
            if len(toc_content) > 10000: # Limit total context
                break
                
        return toc_content

    def _extract_structure_with_llm(self) -> dict:
        """Extract book structure using Gemini"""
        print("  🔍 Analyzing book structure...")
        toc_content = self._get_toc_content()
        
        prompt = f"""You are analyzing the beginning of a book to extract its structure.

BOOK CONTENT (First few sections):
{toc_content}

TASK:
Analyze these sections and extract the book's structure (table of contents).
Look for Parts and Chapters.

RESPOND IN JSON FORMAT:
{{
  "has_parts": true/false,
  "parts": [
    {{
      "number": 1,
      "title": "Part One: The Beginning",
      "chapters": [
         {{ "number": 1, "title": "Chapter 1 Title" }},
         {{ "number": 2, "title": "Chapter 2 Title" }}
      ]
    }}
  ],
  "chapters": [
    {{
      "number": 1,
      "title": "Chapter 1 Title",
      "part_number": 1
    }}
  ]
}}

RULES:
- If no parts, set has_parts=false and part_number=null
- Extract EXACT titles
- Return ONLY valid JSON"""

        try:
            response = self.gemini_model.generate_content(prompt)
            text = response.text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
                
            structure = json.loads(text)
            print(f"  ✓ Structure detected: {len(structure.get('chapters', []))} chapters")
            return structure
        except Exception as e:
            print(f"  ⚠ Structure extraction failed: {e}")
            return None

    def _process_content_with_llm(self, content: str, structure: dict) -> dict:
        """Process content with Gemini to clean and identify chapter"""
        # Create a simplified structure context
        chapters_context = ""
        if structure:
            for ch in structure.get('chapters', [])[:50]: # Limit context
                chapters_context += f"- Chapter {ch.get('number')}: {ch.get('title')}\n"
        
        prompt = f"""You are cleaning text from an EPUB file.
        
CONTENT:
{content[:10000]}... (truncated)

BOOK STRUCTURE:
{chapters_context}

TASK:
1. Clean the text (remove headers, footers, page numbers, HTML noise).
2. Identify which chapter this content belongs to based on the structure.
3. If it's a new chapter start, extract the title.

RESPOND IN JSON:
{{
  "cleaned_text": "The clean text...",
  "is_chapter_start": true/false,
  "chapter_number": 1,
  "chapter_title": "The Title",
  "part_number": 1 (or null)
}}

RULES:
- Return ONLY valid JSON
- If content matches a chapter in the structure, use that number/title.
"""
        try:
            # Use a faster/cheaper model call or lower token limit if possible
            response = self.gemini_model.generate_content(prompt)
            text = response.text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            return json.loads(text)
        except Exception as e:
            print(f"  ⚠ Content processing failed: {e}")
            return {"cleaned_text": content, "is_chapter_start": False}

    def extract(self, output_dir: str = "extracted_epub"):
        """
        Extract content from EPUB
        
        Args:
            output_dir: Base directory to save extracted content
        """
        # Create base output directory
        base_output = Path(output_dir)
        base_output.mkdir(parents=True, exist_ok=True)
        
        # Create book-specific directory
        book_title = self.book.get_metadata('DC', 'title')[0][0] if self.book.get_metadata('DC', 'title') else self.epub_path.stem
        safe_book_title = self._sanitize_filename(book_title)
        book_output_dir = base_output / safe_book_title
        
        if book_output_dir.exists():
            shutil.rmtree(book_output_dir)
        book_output_dir.mkdir(parents=True, exist_ok=True)
        
        chapters_dir = book_output_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        
        # 1. Extract Structure
        self.book_structure = self._extract_structure_with_llm()
        
        # Save structure
        if self.book_structure:
            with open(book_output_dir / "structure.json", "w") as f:
                json.dump(self.book_structure, f, indent=2)
        
        print(f"\n📂 Extracting to: {book_output_dir}")
        
        # 2. Get ALL Content
        print("  📖 Reading all book content...")
        full_text = ""
        spine_ids = [item[0] for item in self.book.spine]
        
        for i, item_id in enumerate(spine_ids):
            item = self.book.get_item_with_id(item_id)
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            
            # Add a marker to help separation if needed, but mainly we rely on titles
            text = self._clean_html(item.get_content())
            if text:
                full_text += text + "\n\n"
                
        print(f"  ✓ Loaded {len(full_text):,} characters")
        
        # Normalize whitespace for searching
        # This handles tabs, newlines, and multiple spaces that break simple string matching
        search_text = re.sub(r'\s+', ' ', full_text).lower()
        print(f"  ✓ Normalized text for searching")
        
        # 3. Split by Structure
        if not self.book_structure or not self.book_structure.get('chapters'):
            print("  ⚠ No structure to split by. Saving as single file.")
            with open(chapters_dir / "full_text.txt", "w", encoding='utf-8') as f:
                f.write(full_text)
            return

        chapters = self.book_structure['chapters']
        # Sort by number just in case
        chapters.sort(key=lambda x: x.get('number', 0))
        
        # Find start positions of each chapter
        # We look for the Title in the text
        chapter_positions = []
        
        search_start_pos = 0
        
        for i, chapter in enumerate(chapters):
            title = chapter.get('title', '').strip()
            if not title:
                continue
            
            # Normalize title for regex
            clean_title = re.escape(title)
            # Allow flexible whitespace
            title_pattern = re.compile(clean_title.replace(r'\ ', r'\s+'), re.IGNORECASE)
            
            current_pos = search_start_pos
            found_valid = False
            
            while True:
                match = title_pattern.search(full_text, current_pos)
                if not match:
                    break
                
                pos = match.start()
                
                # Check if this looks like a TOC entry
                if i + 1 < len(chapters):
                    next_title = chapters[i+1].get('title', '').strip()
                    if next_title:
                        clean_next = re.escape(next_title)
                        next_pattern = re.compile(clean_next.replace(r'\ ', r'\s+'), re.IGNORECASE)
                        
                        next_match = next_pattern.search(full_text, pos + len(title))
                        if next_match and (next_match.start() - pos) < 500:
                            # Too close -> likely TOC
                            current_pos = pos + 1
                            continue
                            
                chapter_positions.append({
                    'chapter': chapter,
                    'pos': pos,
                    'title': title
                })
                print(f"  📍 Found start of '{title}' at index {pos}")
                search_start_pos = pos + 1
                found_valid = True
                break
            
            if not found_valid:
                print(f"  ⚠ Could not find valid start of '{title}' in text")
        
        # 4. Save Chapters
        print(f"\n  ✨ Refining content with AI...")
        for i, entry in enumerate(chapter_positions):
            chapter = entry['chapter']
            start_pos = entry['pos']
            
            # End is start of next chapter, or end of text
            if i + 1 < len(chapter_positions):
                end_pos = chapter_positions[i+1]['pos']
            else:
                end_pos = len(full_text)
                
            content = full_text[start_pos:end_pos].strip()
            
            # Refine content with AI
            print(f"  Processing: {chapter['title']}...", end='\r')
            refined_content = self._refine_content_with_llm(content)
            
            # Determine folder
            part_num = chapter.get('part_number')
            if part_num:
                part_folder = chapters_dir / f"part_{part_num:02d}"
                part_folder.mkdir(exist_ok=True)
                target_dir = part_folder
            else:
                target_dir = chapters_dir
                
            # Filename
            chapter_num = chapter.get('number', i+1)
            safe_title = self._sanitize_filename(chapter['title'])
            filename = f"chapter_{chapter_num:02d}_{safe_title}.txt"
            
            with open(target_dir / filename, "w", encoding='utf-8') as f:
                f.write(f"{chapter['title']}\n")
                f.write("=" * 40 + "\n\n")
                f.write(refined_content)
                
            print(f"  ✓ Saved: {filename} ({len(refined_content):,} chars)")

        print(f"\n✨ Extraction complete! Saved {len(chapter_positions)} chapters.")

def main():
    parser = argparse.ArgumentParser(description="Extract text from EPUB files")
    parser.add_argument("epub_path", help="Path to EPUB file")
    parser.add_argument("--output", "-o", default="extracted_epub", help="Output directory")
    parser.add_argument("--key", help="Gemini API Key")
    
    args = parser.parse_args()
    
    extractor = EpubExtractor(args.epub_path, gemini_api_key=args.key)
    extractor.extract(args.output)

if __name__ == "__main__":
    main()
