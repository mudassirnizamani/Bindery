#!/usr/bin/env python3
"""
Book Compiler
Combines cleaned pages into a single book.txt file.
"""

import sys
import os
import argparse
import re
from pathlib import Path

class BookCompiler:
    def __init__(self, cleaned_pages_dir: str):
        self.cleaned_pages_dir = Path(cleaned_pages_dir)
        if not self.cleaned_pages_dir.exists():
            raise FileNotFoundError(f"Cleaned pages directory not found: {self.cleaned_pages_dir}")

    def compile(self):
        """Main function to compile the book."""
        book_dir = self.cleaned_pages_dir.parent
        output_file = book_dir / "book.txt"

        print(f"\n📚 Compiling book from: {self.cleaned_pages_dir}")
        print(f"📄 Output: {output_file}")

        # Get list of files
        files = [f for f in self.cleaned_pages_dir.iterdir() if f.suffix == '.txt']

        # Sort files numerically
        # Assumes filenames like "page_001.txt" or "page_1.txt"
        def extract_number(filename):
            match = re.search(r'(\d+)', filename)
            return int(match.group(1)) if match else 0

        files.sort(key=lambda f: extract_number(f.name))

        if not files:
            print("⚠ No text files found to compile.")
            return

        print(f"  Found {len(files)} pages.")

        try:
            with open(output_file, 'w', encoding='utf-8') as outfile:
                for i, file_path in enumerate(files):
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read().strip()

                    if content:
                        outfile.write(content)
                        # Add separator between pages
                        outfile.write("\n\n")

            print(f"✨ Compilation complete! Book saved to: {output_file}")

        except Exception as e:
            print(f"❌ Error compiling book: {e}")

def main():
    parser = argparse.ArgumentParser(description="Compile cleaned pages into a single book.txt")
    parser.add_argument("cleaned_pages_dir", help="Directory containing cleaned text pages")

    args = parser.parse_args()

    compiler = BookCompiler(args.cleaned_pages_dir)
    compiler.compile()

if __name__ == "__main__":
    main()
