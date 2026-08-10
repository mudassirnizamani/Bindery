#!/usr/bin/env python3
"""
Copy Page Tool (Merge with previous)
Appends the contents of a specific raw page to the previous page,
and then deletes the specific page to maintain sequence.

Usage:
    python src/copy_page.py <raw_pages_dir> <page_number>
"""

import sys
import argparse
import json
from pathlib import Path

# Import the delete_page logic
from delete_page import delete_page, get_page_filename

def copy_page(raw_pages_dir, page_num):
    if page_num <= 1:
        print("Error: Cannot copy page 1 to a previous page.")
        sys.exit(1)

    raw_pages_path = Path(raw_pages_dir)
    if not raw_pages_path.exists():
        print(f"Error: Directory '{raw_pages_dir}' does not exist.")
        sys.exit(1)

    source_file = raw_pages_path / get_page_filename(page_num)
    target_file = raw_pages_path / get_page_filename(page_num - 1)

    if not source_file.exists():
        print(f"Error: Source page file '{source_file.name}' not found.")
        sys.exit(1)

    if not target_file.exists():
        print(f"Error: Target previous page file '{target_file.name}' not found.")
        sys.exit(1)

    # 1. Read source content
    with open(source_file, 'r', encoding='utf-8') as f:
        source_content = f.read()

    # 2. Get character count of source page from index
    index_path = raw_pages_path.parent / 'pages_index.json'
    source_char_count = len(source_content) # Default fallback
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'pages' in data:
                for p in data['pages']:
                    if p.get('page') == page_num:
                        source_char_count = p.get('char_count', len(source_content))
                        break
        except Exception:
            pass

    # 3. Append to target content
    print(f"Appending content of {source_file.name} to {target_file.name}...")
    with open(target_file, 'a', encoding='utf-8') as f:
        f.write('\n\n')
        f.write(source_content)
        
    # We added 2 newline characters for the empty line
    source_char_count += 2
        
    print(f"  ✓ Content appended.")

    # 4. Call delete_page. This will backup the page and index, and renumber subsequent pages.
    # (It will also subtract source_char_count from total_characters in pages_index.json)
    delete_page(raw_pages_dir, page_num)

    # 5. Fix pages_index.json because delete_page subtracted the characters and didn't add them to target
    if index_path.exists():
        print("Updating pages_index.json with merged character counts...")
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'pages' in data:
                for p in data['pages']:
                    if p.get('page') == page_num - 1:
                        p['char_count'] = p.get('char_count', 0) + source_char_count
                        break
                        
                data['total_characters'] = data.get('total_characters', 0) + source_char_count
                
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
                print("  ✓ pages_index.json updated with merged counts.")
        except Exception as e:
            print(f"  ❌ Failed to adjust pages_index.json: {e}")

    print("\nPage copy (merge) completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Append a page's content to the previous page and delete it.")
    parser.add_argument("raw_pages_dir", help="Path to the raw_pages directory")
    parser.add_argument("page_number", type=int, help="Number of the page to copy and delete (integer)")

    args = parser.parse_args()
    copy_page(args.raw_pages_dir, args.page_number)

if __name__ == "__main__":
    main()
