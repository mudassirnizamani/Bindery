#!/usr/bin/env python3
"""
EPUB Content Extractor (Two-Stage Pipeline)
Stage 1: Convert EPUB to Markdown using Pandoc (preserves layout/formatting).
Stage 2: Semantic Splitting using Regex to identify chapters.
"""

import sys
import os
import shutil
from pathlib import Path
import argparse
import json
import re
import pypandoc

class EpubExtractor:
    def __init__(self, epub_path: str):
        """
        Initialize EPUB Extractor
        
        Args:
            epub_path: Path to the EPUB file
        """
        self.epub_path = Path(epub_path)
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

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

    def convert_to_markdown(self, output_path: Path) -> str:
        """
        Stage 1: Convert EPUB to Markdown using Pandoc
        Returns the full markdown text.
        """
        print(f"  📖 Stage 1: Converting EPUB to Markdown...")
        try:
            # Convert to markdown_strict or markdown (pandoc's flavor)
            # We use 'markdown' to keep tables and other features
            output = pypandoc.convert_file(str(self.epub_path), 'markdown', outputfile=str(output_path))
            # pypandoc returns empty string if outputfile is specified, so read it back
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"✗ Conversion failed: {e}")
            sys.exit(1)

    def split_chapters(self, markdown_text: str, output_dir: Path) -> list:
        """
        Stage 2: Split Markdown into chapters using Regex
        """
        print(f"  ✂️  Stage 2: Splitting into chapters...")
        
        # Regex to find Chapter headers
        # Matches:
        # # Chapter 1
        # []{#id}Chapter 1
        # Chapter I. Title
        
        # We use a robust pattern that ignores optional Pandoc anchors []{...} and optional #
        # Group 1: Keyword (Chapter/Part/etc)
        # Group 2: Number/Roman
        split_pattern = re.compile(
            r'^(?:\[\]\{.*?\})?\s*(?:#+\s+)?(Chapter|Part|Section|Book)\s+(?:\d+|[IVXLCDM]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)',
            re.IGNORECASE
        )
        
        lines = markdown_text.split('\n')
        chapters = []
        current_chapter_lines = []
        current_title = "Frontmatter"
        chapter_count = 0
        
        for line in lines:
            stripped_line = line.strip()
            
            # Check if line matches the chapter pattern
            # We also check if the line is reasonably short (< 100 chars) to avoid matching sentences in text
            if len(stripped_line) < 100 and split_pattern.match(stripped_line):
                # Save previous chapter
                if current_chapter_lines:
                    chapters.append({
                        'title': current_title,
                        'content': '\n'.join(current_chapter_lines),
                        'number': chapter_count
                    })
                
                # Start new chapter
                chapter_count += 1
                
                # Clean title: remove anchors, #, and whitespace
                # Remove []{...}
                clean_line = re.sub(r'\[\]\{.*?\}', '', line)
                # Remove #
                clean_line = clean_line.replace('#', '').strip()
                
                current_title = clean_line
                current_chapter_lines = [line] # Keep the header in the file
                print(f"    📍 Found: {current_title}")
            else:
                current_chapter_lines.append(line)
                
        # Save final chapter
        if current_chapter_lines:
            chapters.append({
                'title': current_title,
                'content': '\n'.join(current_chapter_lines),
                'number': chapter_count
            })
            
        return chapters

    def extract(self, output_dir: str = "extracted_epub"):
        """
        Execute the pipeline
        """
        # Setup directories
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
        
        print(f"\n📂 Extracting to: {book_output_dir}")
        
        # Stage 1: Conversion
        full_md_path = book_output_dir / "full_book.md"
        markdown_text = self.convert_to_markdown(full_md_path)
        print(f"  ✓ Saved full markdown to: {full_md_path.name}")
        
        # Stage 2: Splitting
        chapters = self.split_chapters(markdown_text, chapters_dir)
        
        # Save Chapters
        structure_data = {"chapters": []}
        
        for ch in chapters:
            safe_title = self._sanitize_filename(ch['title'])
            filename = f"chapter_{ch['number']:02d}_{safe_title}.txt" # Using .txt but content is markdown
            
            # Cleanup content
            # Remove Pandoc anchors []{...}
            content = re.sub(r'\[\]\{.*?\}', '', ch['content'])
            # Fix escaped brackets \[ \] -> [ ]
            content = content.replace('\\[', '[').replace('\\]', ']')
            
            with open(chapters_dir / filename, "w", encoding='utf-8') as f:
                f.write(content)
                
            structure_data["chapters"].append({
                "number": ch['number'],
                "title": ch['title'],
                "file": filename
            })
            
        # Save Structure JSON
        with open(book_output_dir / "structure.json", "w") as f:
            json.dump(structure_data, f, indent=2)
            
        print(f"\n✨ Extraction complete! Saved {len(chapters)} chapters.")


def main():
    parser = argparse.ArgumentParser(description="Extract text from EPUB files (Two-Stage Pipeline)")
    parser.add_argument("epub_path", help="Path to EPUB file")
    parser.add_argument("--output", "-o", default="extracted_epub", help="Output directory")
    
    args = parser.parse_args()
    
    extractor = EpubExtractor(args.epub_path)
    extractor.extract(args.output)

if __name__ == "__main__":
    main()
