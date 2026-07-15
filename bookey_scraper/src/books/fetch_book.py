#!/usr/bin/env python3
"""
Simple utility to fetch a single book by ID
"""

import sys
import json
from pathlib import Path
from book_fetcher import BookeyBookFetcher

def fetch_book(book_id: str, save_locally: bool = True, output_format: str = 'json') -> dict:
    """
    Fetch a single book by its ID
    
    Args:
        book_id (str): The ID of the book to fetch
        save_locally (bool): Whether to save the book data locally
        output_format (str): Output format ('json' or 'summary')
    
    Returns:
        dict: The book data if successful, empty dict otherwise
    """
    fetcher = BookeyBookFetcher()
    book_data = fetcher.fetch_book_by_id(book_id, save_locally)
    
    if book_data:
        if output_format == 'summary':
            print_book_summary(book_data)
        elif output_format == 'json':
            print(json.dumps(book_data, indent=2, ensure_ascii=False))
        return book_data
    else:
        print(f"❌ Failed to fetch book with ID: {book_id}")
        return {}

def print_book_summary(book_data: dict):
    """Print a formatted summary of the book"""
    print("\n" + "="*60)
    print(f"📚 BOOK SUMMARY")
    print("="*60)
    print(f"Title: {book_data.get('title', 'N/A')}")
    if book_data.get('subtitle'):
        print(f"Subtitle: {book_data.get('subtitle')}")
    print(f"Author: {book_data.get('author', 'N/A')}")
    print(f"Language: {book_data.get('langCode', 'N/A')}")
    if book_data.get('categoryName'):
        print(f"Category: {book_data.get('categoryName')}")
    if book_data.get('rating'):
        print(f"Rating: {book_data.get('rating')}")
    if book_data.get('readTime'):
        print(f"Read Time: {book_data.get('readTime')}")
    
    desc = book_data.get('desc', '')
    if desc:
        print(f"\nDescription:")
        print(f"{desc[:200]}{'...' if len(desc) > 200 else ''}")
    
    quotes = book_data.get('quotes', [])
    if quotes:
        print(f"\nSample Quotes ({len(quotes)} total):")
        for i, quote in enumerate(quotes[:3], 1):
            quote_text = quote.get('content', quote.get('text', str(quote)))
            print(f"  {i}. \"{quote_text[:100]}{'...' if len(quote_text) > 100 else ''}\"")
    
    data_list = book_data.get('dataList', [])
    if data_list:
        print(f"\nChapters/Sections: {len(data_list)}")
    
    print("="*60)

def main():
    """Main function for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python fetch_book.py <book_id> [--no-save] [--summary]")
        print("Examples:")
        print("  python fetch_book.py 12345")
        print("  python fetch_book.py 12345 --summary")
        print("  python fetch_book.py 12345 --no-save --summary")
        sys.exit(1)
    
    book_id = sys.argv[1]
    save_locally = '--no-save' not in sys.argv
    output_format = 'summary' if '--summary' in sys.argv else 'json'
    
    fetch_book(book_id, save_locally, output_format)

if __name__ == "__main__":
    main() 