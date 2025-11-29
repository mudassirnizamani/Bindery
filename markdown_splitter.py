#!/usr/bin/env python3
"""
Advanced Markdown Splitter (AI-Powered)
Acts as a human reader:
1. Reads the beginning to understand the book layout (TOC).
2. Reads the rest in chunks to clean text and split based on the understood layout.
"""

import sys
import os
import re
import argparse
import json
import time
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AdvancedMarkdownSplitter:
    def __init__(self, input_path: str, output_dir: str = "split_chapters", api_key: str = None):
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Initialize Gemini
        try:
            key = api_key or os.getenv('GOOGLE_API_KEY')
            if not key:
                raise ValueError("Gemini API key is required for Advanced Mode.")
            genai.configure(api_key=key)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
            print(f"✓ Gemini initialized (Model: gemini-2.5-flash)")
        except Exception as e:
            print(f"❌ Failed to initialize Gemini: {e}")
            sys.exit(1)

        self.layout = {} # Stores the book structure
        self.current_part_folder = None
        self.file_counter = 0

    def _sanitize_filename(self, filename: str) -> str:
        """Removes characters from a string that are not safe for filenames."""
        filename = filename.replace('\t', ' ').replace('\n', ' ')
        filename = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
        filename = re.sub(r'\s+', '_', filename)
        return filename[:100]

    def _call_gemini_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Helper to call Gemini with retry logic"""
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
                return None
        return None

    def analyze_layout(self):
        """Phase 1: Read the beginning of the file to understand the layout."""
        print("\n📖 Phase 1: Analyzing Book Layout...")
        
        # Read first 5000 characters
        with open(self.input_path, 'r', encoding='utf-8') as f:
            preamble = f.read(5000)
        
        prompt = f"""You are analyzing a book to understand its structure.
Read the following beginning of a book (which likely contains a Table of Contents).
Extract the structure of Parts and Chapters.

TEXT:
{preamble}

TASK:
Return a JSON object representing the structure.
Format:
{{
  "parts": [
    {{
      "title": "Part One: The Beginning",
      "chapters": ["Chapter 1", "Chapter 2"]
    }}
  ],
  "chapters_without_part": ["Preface", "Introduction"]
}}
If there are no parts, put all chapters in "chapters_without_part".
"""
        response = self._call_gemini_with_retry(prompt)
        if response:
            try:
                # Clean markdown
                if '```json' in response:
                    response = response.split('```json')[1].split('```')[0]
                elif '```' in response:
                    response = response.split('```')[1].split('```')[0]
                
                self.layout = json.loads(response)
                print("   ✓ Layout detected:")
                print(json.dumps(self.layout, indent=2))
            except Exception as e:
                print(f"   ⚠ Failed to parse layout: {e}")
                self.layout = {"parts": [], "chapters_without_part": []}
        else:
             print("   ⚠ Failed to get layout from AI.")

    def process_book(self):
        """Phase 2: Stream file, clean text, and split based on layout."""
        print("\n🚀 Phase 2: Processing & Splitting...")
        
        # Prepare output dir
        book_name = self.input_path.stem
        book_output_dir = self.output_dir / book_name
        if book_output_dir.exists():
            import shutil
            shutil.rmtree(book_output_dir)
        book_output_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_output_dir = book_output_dir
        self.current_file_path = None
        self.current_content_buffer = []
        self.current_title = "Frontmatter"
        
        # Read file lines
        with open(self.input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        CHUNK_SIZE = 50
        total_lines = len(lines)
        
        for i in range(0, total_lines, CHUNK_SIZE):
            chunk_lines = lines[i : i + CHUNK_SIZE]
            chunk_text = "".join(chunk_lines)
            
            print(f"   Processing lines {i}-{min(i+CHUNK_SIZE, total_lines)}...", end='\r')
            
            # Ask AI to process this chunk
            result = self._process_chunk(chunk_text)
            
            if not result:
                # Fallback: just append raw text if AI fails
                self.current_content_buffer.append(chunk_text)
                continue
            
            # Handle split
            if result.get("new_chapter_detected"):
                # Save previous chapter
                self._save_current_chapter()
                
                # Update context
                new_title = result.get("chapter_title")
                new_part = result.get("part_title")
                
                if new_part:
                    # Create/Switch to Part folder
                    safe_part = self._sanitize_filename(new_part)
                    self.current_output_dir = book_output_dir / safe_part
                    self.current_output_dir.mkdir(exist_ok=True)
                    print(f"\n   📂 Entered Part: {new_part}")
                
                self.current_title = new_title if new_title else "Untitled"
                print(f"\n   🔖 New Chapter: {self.current_title}")
            
            # Append cleaned text
            cleaned_text = result.get("cleaned_text", "")
            if cleaned_text:
                self.current_content_buffer.append(cleaned_text)
        
        # Save final chapter
        self._save_current_chapter()
        print(f"\n✨ Processing complete! Created {self.file_counter} files.")

    def _process_chunk(self, chunk_text):
        """Sends chunk to Gemini for cleaning and header detection."""
        layout_str = json.dumps(self.layout)
        prompt = f"""You are processing a book chunk by chunk.
Your job is to:
1. **Clean the text**: Remove watermarks, page numbers, and artifacts. Keep the story/content EXACTLY as is.
2. **Detect Headers**: Check if this chunk STARTS a new Chapter or Part based on the Book Layout.

BOOK LAYOUT:
{layout_str}

CURRENT CHUNK:
{chunk_text}

RESPONSE FORMAT (JSON ONLY):
{{
  "cleaned_text": "The cleaned content of this chunk...",
  "new_chapter_detected": true/false,
  "chapter_title": "Chapter Name" (if detected, else null),
  "part_title": "Part Name" (if a new part starts here, else null)
}}
"""
        response = self._call_gemini_with_retry(prompt)
        if response:
            try:
                # Clean markdown
                if '```json' in response:
                    response = response.split('```json')[1].split('```')[0]
                elif '```' in response:
                    response = response.split('```')[1].split('```')[0]
                return json.loads(response)
            except:
                return None
        return None

    def _save_current_chapter(self):
        """Saves the buffered content to a file."""
        if not self.current_content_buffer:
            return
            
        text = "".join(self.current_content_buffer)
        if len(text.strip()) < 10:
            self.current_content_buffer = []
            return
            
        safe_title = self._sanitize_filename(self.current_title)
        filename = f"chapter_{self.file_counter:02d}_{safe_title}.txt"
        output_path = self.current_output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        self.file_counter += 1
        self.current_content_buffer = []

def main():
    parser = argparse.ArgumentParser(description="Advanced AI Markdown Splitter")
    parser.add_argument("input_file", help="Path to the .md file")
    parser.add_argument("--output", "-o", default="split_chapters_advanced", help="Output directory")
    parser.add_argument("--key", help="Gemini API Key", required=False)
    
    args = parser.parse_args()
    
    splitter = AdvancedMarkdownSplitter(args.input_file, args.output, api_key=args.key)
    splitter.analyze_layout()
    splitter.process_book()

if __name__ == "__main__":
    main()
