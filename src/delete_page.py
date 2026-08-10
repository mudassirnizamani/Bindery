#!/usr/bin/env python3
"""
Page Deletion Tool
Deletes a specific raw page and renumbers subsequent pages to maintain sequence.
Also updates pages_index.json if present.

Usage:
    python src/delete_page.py <raw_pages_dir> <page_number>
"""

import os
import sys
import argparse
import json
import re
import shutil
import time
from pathlib import Path

def get_page_filename(page_num):
    return f"page_{page_num:03d}.txt"

def update_index_file(raw_pages_dir, deleted_page_num):
    """Updates the pages_index.json file if it exists."""
    raw_pages_path = Path(raw_pages_dir)
    # Assuming pages_index.json is in the parent directory of raw_pages
    index_path = raw_pages_path.parent / 'pages_index.json'

    if not index_path.exists():
        print("  ℹ No pages_index.json found to update.")
        return

    print(f"  Updating {index_path}...")
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'pages' not in data:
            print("  ⚠ pages_index.json format not recognized (missing 'pages' list). Skipping update.")
            return

        original_pages = data['pages']
        new_pages = []
        deleted_char_count = 0
        deleted_confidence = 0
        deleted_found = False

        for p in original_pages:
            p_num = p.get('page')
            if p_num == deleted_page_num:
                deleted_found = True
                deleted_char_count = p.get('char_count', 0)
                deleted_confidence = p.get('confidence', 0)
                continue # Skip this page (delete it)

            if p_num > deleted_page_num:
                # Shift down
                p['page'] = p_num - 1
                # Update file path if it matches standard pattern
                if 'file' in p:
                    # simplistic replacement of the filename part
                    # standard format: raw_pages/page_XXX.txt
                    old_filename = get_page_filename(p_num)
                    new_filename = get_page_filename(p_num - 1)
                    p['file'] = p['file'].replace(old_filename, new_filename)

            new_pages.append(p)

        if not deleted_found:
             print(f"  ⚠ Page {deleted_page_num} not found in pages_index.json. Only renumbering logic applied.")

        # Update aggregates
        data['pages'] = new_pages
        data['total_pages'] = len(new_pages)

        # Update total characters
        current_total_chars = data.get('total_characters', 0)
        data['total_characters'] = max(0, current_total_chars - deleted_char_count)

        # Update average confidence
        # We can't easily subtract from average without knowing count, so recalculate from list
        if new_pages:
            total_conf = sum(p.get('confidence', 0) for p in new_pages)
            avg_conf = total_conf / len(new_pages)
            data['avg_confidence'] = f"{avg_conf:.1f}%"
        else:
            data['avg_confidence'] = "0%"

        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("  ✓ pages_index.json updated.")

    except Exception as e:
        print(f"  ❌ Failed to update pages_index.json: {e}")

def save_undo_state(raw_pages_dir, page_num, target_file):
    raw_pages_path = Path(raw_pages_dir)
    trash_dir = raw_pages_path / '.trash'
    trash_dir.mkdir(exist_ok=True)

    timestamp = int(time.time())
    
    # move target file to trash (we copy it so we can still unlink the original or just move it)
    trashed_page = trash_dir / f"page_{page_num:03d}_{timestamp}.txt"
    shutil.copy2(target_file, trashed_page)
    
    index_path = raw_pages_path.parent / 'pages_index.json'
    trashed_index = None
    if index_path.exists():
        trashed_index = trash_dir / f"pages_index_{timestamp}.json"
        shutil.copy2(index_path, trashed_index)
        
    undo_info = {
        "page_num": page_num,
        "trashed_page": str(trashed_page.name),
        "trashed_index": str(trashed_index.name) if trashed_index else None
    }
    with open(trash_dir / 'latest_undo.json', 'w') as f:
        json.dump(undo_info, f)

def undo_delete(raw_pages_dir):
    raw_pages_path = Path(raw_pages_dir)
    trash_dir = raw_pages_path / '.trash'
    undo_file = trash_dir / 'latest_undo.json'
    
    if not undo_file.exists():
        print("Error: No undo information found.")
        sys.exit(1)
        
    with open(undo_file, 'r') as f:
        undo_info = json.load(f)
        
    page_num = undo_info['page_num']
    trashed_page = trash_dir / undo_info['trashed_page']
    trashed_index = trash_dir / undo_info['trashed_index'] if undo_info.get('trashed_index') else None
    
    if not trashed_page.exists():
        print("Error: Trashed page file missing. Cannot fully undo.")
        sys.exit(1)
        
    # Find files to move back (shift up by 1)
    files_to_move = []
    for entry in raw_pages_path.iterdir():
        if entry.is_file():
            match = re.match(r'page_(\d+)\.txt', entry.name)
            if match:
                curr_num = int(match.group(1))
                if curr_num >= page_num:
                    files_to_move.append(curr_num)
                    
    files_to_move.sort(reverse=True) # Important to sort descending
    
    print(f"Undoing delete for page {page_num}...")
    print(f"Renumbering {len(files_to_move)} subsequent pages back...")
    
    for curr_num in files_to_move:
        old_path = raw_pages_path / get_page_filename(curr_num)
        new_num = curr_num + 1
        new_path = raw_pages_path / get_page_filename(new_num)
        try:
            old_path.rename(new_path)
        except OSError as e:
            print(f"Error renaming {old_path.name} to {new_path.name}: {e}")
            sys.exit(1)
            
    # Restore deleted page
    shutil.copy2(trashed_page, raw_pages_path / get_page_filename(page_num))
    print(f"  ✓ Restored {get_page_filename(page_num)}.")
    
    # Restore index
    if trashed_index and trashed_index.exists():
        index_path = raw_pages_path.parent / 'pages_index.json'
        shutil.copy2(trashed_index, index_path)
        print("  ✓ Restored pages_index.json.")
        
    undo_file.unlink()
    print("\nUndo completed successfully.")

def delete_page(raw_pages_dir, page_num):
    raw_pages_path = Path(raw_pages_dir)

    if not raw_pages_path.exists():
        print(f"Error: Directory '{raw_pages_dir}' does not exist.")
        sys.exit(1)

    target_file = raw_pages_path / get_page_filename(page_num)

    if not target_file.exists():
        print(f"Error: Page file '{target_file.name}' not found in '{raw_pages_dir}'.")
        sys.exit(1)

    print(f"Processing delete operation for page {page_num}...")

    # Save state for undo
    save_undo_state(raw_pages_dir, page_num, target_file)

    # 1. Delete the target file
    try:
        target_file.unlink()
        print(f"  ✓ Deleted {target_file.name}")
    except OSError as e:
        print(f"Error deleting file: {e}")
        sys.exit(1)

    # 2. Rename subsequent pages
    # Find all page files that need renaming
    # We look for page_XXX.txt where XXX > page_num

    files_to_move = []

    for entry in raw_pages_path.iterdir():
        if entry.is_file():
            match = re.match(r'page_(\d+)\.txt', entry.name)
            if match:
                curr_num = int(match.group(1))
                if curr_num > page_num:
                    files_to_move.append(curr_num)

    files_to_move.sort() # Important to sort ascending

    print(f"  Renumbering {len(files_to_move)} subsequent pages...")

    for curr_num in files_to_move:
        old_path = raw_pages_path / get_page_filename(curr_num)
        new_num = curr_num - 1
        new_path = raw_pages_path / get_page_filename(new_num)

        try:
            old_path.rename(new_path)
            # Optional: print verification for debugging, maybe too verbose if many pages
            # print(f"    {old_path.name} -> {new_path.name}")
        except OSError as e:
            print(f"Error renaming {old_path.name} to {new_path.name}: {e}")
            sys.exit(1)

    print(f"  ✓ Renumbering complete.")

    # 3. Update index
    update_index_file(raw_pages_dir, page_num)

    print("\nOperation completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Delete a raw page and renumber subsequent pages.")
    parser.add_argument("raw_pages_dir", help="Path to the raw_pages directory")
    parser.add_argument("page_number", type=int, nargs='?', help="Number of the page to delete (integer)")
    parser.add_argument("--undo", action="store_true", help="Undo the last deletion")

    args = parser.parse_args()

    if args.undo:
        undo_delete(args.raw_pages_dir)
    else:
        if args.page_number is None:
            parser.error("page_number is required unless --undo is specified.")
        delete_page(args.raw_pages_dir, args.page_number)

if __name__ == "__main__":
    main()
