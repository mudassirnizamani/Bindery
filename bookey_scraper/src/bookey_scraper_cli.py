#!/usr/bin/env python3
"""

"""

import argparse
from categories.category_scraper import ImprovedBookeyScraper
from categories.icon_downloader import BookeyIconDownloader
from categories.systematic_extraction import run_with_args

def main():
    """Main function with options"""
    parser = argparse.ArgumentParser(description='Bookey Category Scraper')
    parser.add_argument('--fetch-books', action='store_true', help='Fetch all books from extracted categories')
    args = parser.parse_args()

    scraper = ImprovedBookeyScraper()
    
    if args.fetch_books:
        delay = input("Enter delay between requests in seconds (default: 3): ").strip()
        delay = int(delay) if delay.isdigit() else 3
        
        print(f"\n🔍 Will fetch all books with {delay}s delay between requests")
        confirm = input("Continue? (y/n): ").lower().strip()
        
        if confirm == 'y':
            scraper.book_fetcher.fetch_all_books(delay)
        else:
            print("❌ Operation cancelled.")
        return

    print("🔧 EXTRACTION OPTIONS:")
    print("1. Extract all 12 categories")
    print("2. Extract specific range")
    print("3. Test with first 3 categories")
    print("4. Continue from a specific category")
    print("5. Fetch all books from extracted categories")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == "1":
        print("\n🚀 Running FULL extraction on all 12 categories...")
        print("📸 This version includes icon downloading for all subcategories!")
        scraper.run_systematic_extraction(start_from=0, max_categories=None)
    
    elif choice == "2":
        try:
            start = int(input("Enter start category number (1-12): ").strip())
            end = int(input("Enter end category number (1-12): ").strip())
            
            if 1 <= start <= 12 and 1 <= end <= 12 and start <= end:
                print(f"\n🚀 Extracting categories {start} to {end}...")
                scraper.run_systematic_extraction(start_from=start-1, max_categories=end-start+1)
            else:
                print("❌ Invalid range. Please enter numbers between 1 and 12, with start <= end.")
        except ValueError:
            print("❌ Please enter valid numbers.")
    
    elif choice == "3":
        print("\n🧪 Running test extraction on first 3 categories...")
        scraper.run_systematic_extraction(start_from=0, max_categories=3)
    
    elif choice == "4":
        try:
            start = int(input("Enter category number to start from (1-12): ").strip())
            if 1 <= start <= 12:
                print(f"\n🚀 Continuing extraction from category {start}...")
                scraper.run_systematic_extraction(start_from=start-1)
            else:
                print("❌ Invalid category number. Please enter a number between 1 and 12.")
        except ValueError:
            print("❌ Please enter a valid number.")
    
    elif choice == "5":
        delay = input("Enter delay between requests in seconds (default: 3): ").strip()
        delay = int(delay) if delay.isdigit() else 3
        
        print(f"\n🔍 Will fetch all books with {delay}s delay between requests")
        confirm = input("Continue? (y/n): ").lower().strip()
        
        if confirm == 'y':
            scraper.book_fetcher.fetch_all_books(delay)
        else:
            print("❌ Operation cancelled.")
    
    else:
        print("❌ Invalid choice. Please enter a number between 1 and 5.")

if __name__ == "__main__":
    main() 