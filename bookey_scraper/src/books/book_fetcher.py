#!/usr/bin/env python3
"""
Bookey Book Fetcher
A dedicated class for fetching book details from the Bookey API
"""

import json
import requests
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

class BookeyBookFetcher:
    def __init__(self):
        self.base_url = "https://api.bookey.app"
        
        # Headers from successful API calls
        self.headers = {
            'Accept-Encoding': 'gzip',
            'app_code': '513',
            'app_language': 'en-US',
            'app_os': 'android',
            'app_theme': 'dark',
            'app_time_zone': 'Asia/Karachi',
            'app_version': '5.1.3',
            'Connection': 'Keep-Alive',
            'content_lang_code': 'en',
            'Domain-Name': 'book',
            'Host': 'api.bookey.app',
            'interface_lang_code': 'en',
            'token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjVkMTJhYjc4MmNiNjA5NjI4NWY2OWU0OGFlYTk5MDc5YmI1OWNiODYiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiI1MDAwMDE2Njg4NTItMzBsY3RqNTliYXM4cWZta3I2N29pdnA2MGtvMmNudmouYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJhdWQiOiI1MDAwMDE2Njg4NTItNG9pbzVvbTRtcWI5cHJ0MG44YmJwajFxZjhqN25rc2kuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJzdWIiOiIxMTA4MDkyNzA1Njg1Njg0MDEwOTciLCJlbWFpbCI6Im11ZGFzc2lybXVqaGVyaUBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwibmFtZSI6Ik11ZGFzc2lyIE5pemFtYW5pIiwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0lkcENCOEswN2xzaDBjMDJvX3BfS2RkenZGalNEZW1VRU1KcGRiV0VfZW5iVE1Zdkk9czk2LWMiLCJnaXZlbl9uYW1lIjoiTXVkYXNzaXIiLCJmYW1pbHlfbmFtZSI6Ik5pemFtYW5pIiwiaWF0IjoxNzM5OTczNzg4LCJleHAiOjE3Mzk5NzczODh9.fOsNprZoYvKQBhf44OYKZKyqQHROaM2T6xHsBG3iohctgLSMtdyQwJYiCB0qKwxNCjiHi_qtvnGX-fRrYKCh3hL7NMyeaU95dO83PEhdegpNVPDExjGJsQ-BPF9782bQIBflajTXd6Q23AKsIgPiwNesjy_bslyQiDi97FWZVYJWgXX0Bhx7bgGpBWPWIgYUtFG6T1XkEq1toRDPrBVNHFByPNycySoNHk9k_FoxeZXk_nhe0RNAGDGkb9YpIMYpBjLogVCC6Kcf9Dhc5NcCqTsI_2ukFV-QDay4mvUROzifn9N1Lpuryqfb2sxU1bPlwC-wQvKXITpuGEZpyz_HMQ',
            'tokentype': 'google',
            'User-Agent': 'okhttp/4.9.0',
            'USER_ID': 'Google_110809270568568401097'
        }
        
        # Create output directories
        self.base_output_dir = Path("../scrapped_data")  # Points to bookey_scraper/data
        self.books_dir = self.base_output_dir / "books"
        self.books_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'books_processed': 0,
            'successful_fetches': 0,
            'failed_fetches': 0
        }

    def update_app_time(self):
        """Update the app_time header with current timestamp"""
        self.headers['app_time'] = str(int(time.time() * 1000))

    def make_request(self, url: str, retries: int = 3) -> Optional[Dict]:
        """Make a request to the API with proper error handling and retries"""
        self.update_app_time()
        
        for attempt in range(retries):
            try:
                print(f"🌐 Fetching {url}")
                response = requests.get(url, headers=self.headers, timeout=60)
                response.raise_for_status()
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"    ✅ Success! Response size: {len(str(data))} chars")
                        return data
                    except json.JSONDecodeError as e:
                        print(f"    ❌ JSON decode error: {e}")
                        return None
                else:
                    print(f"    ❌ HTTP {response.status_code}: {response.text[:100]}...")
                    
            except requests.exceptions.RequestException as e:
                print(f"    ❌ Request error: {e}")
                
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"    ⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        print(f"    ❌ All attempts failed for {url}")
        return None

    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be used as a filename"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Remove multiple underscores and trim
        while '__' in name:
            name = name.replace('__', '_')
        
        return name.strip('_')

    def save_book_data(self, book_data: Dict, book_id: str):
        """Save book data in the new hierarchical structure"""
        # Create book directory using ID and title
        title = book_data.get('title', 'Unknown Title')
        safe_title = self.sanitize_filename(title)
        book_dir = self.books_dir / f"{book_id}_{safe_title}"
        book_dir.mkdir(parents=True, exist_ok=True)
        
        # Create icons directory
        icons_dir = book_dir / "icons"
        icons_dir.mkdir(exist_ok=True)
        
        # Save book data with title in filename
        book_file = book_dir / f"{safe_title}_book_data.json"
        with open(book_file, 'w', encoding='utf-8') as f:
            json.dump(book_data, f, indent=2, ensure_ascii=False)
        
        # Download and save cover image if available
        cover_path = book_data.get('coverPath')
        if cover_path:
            try:
                response = requests.get(cover_path, timeout=30)
                if response.status_code == 200:
                    cover_file = icons_dir / "cover.jpg"
                    with open(cover_file, 'wb') as f:
                        f.write(response.content)
                    print(f"  🖼️  Saved cover image to: {cover_file}")
            except Exception as e:
                print(f"  ❌ Error downloading cover image: {e}")
        
        print(f"  💾 Saved book data to: {book_dir}")

    def fetch_book_details(self, book_id: str) -> Optional[Dict]:
        """Fetch detailed information for a specific book by ID"""
        print(f"\n📚 Fetching book details for ID: {book_id}")
        
        # First check if book data exists locally
        for book_dir in self.books_dir.glob(f"{book_id}_*"):
            if book_dir.is_dir():
                # Look for the book data JSON file
                book_files = list(book_dir.glob("*_book_data.json"))
                if book_files:
                    try:
                        with open(book_files[0], 'r', encoding='utf-8') as f:
                            book_data = json.load(f)
                        print(f"  📂 Found book data locally in: {book_dir}")
                        self.stats['successful_fetches'] += 1
                        return book_data
                    except Exception as e:
                        print(f"  ⚠️ Error reading local book data: {e}")
                        break
        
        # If we get here, we need to fetch from API
        url = f"{self.base_url}/book/{book_id}"
        data = self.make_request(url)
        
        if not data or not isinstance(data, dict):
            print(f"  ❌ No valid data returned for book {book_id}")
            self.stats['failed_fetches'] += 1
            return None
        
        # Extract only the required fields
        book_details = {
            'title': data.get('title', ''),
            'subtitle': data.get('subTitle', ''),
            'author': data.get('author', ''),
            'authorInfo': data.get('authorInfo', ''),
            'desc': data.get('desc', ''),
            'quizList': data.get('quizList', []),
            'mindMapPath': data.get('mindMapPath', ''),
            'coverPath': data.get('coverPath', ''),
            'langCode': data.get('langCode', ''),
            'dataList': data.get('dataList', []),
            'quotes': data.get('quotes', [])
        }
        
        # Save using new structure
        self.save_book_data(book_details, book_id)
        
        self.stats['successful_fetches'] += 1
        return book_details

    def extract_book_ids_from_category(self, category_data: Dict) -> List[str]:
        """Extract all book IDs from a category's data"""
        book_ids = set()
        
        # Extract from subcategory_books
        for subcategory, books in category_data.get('subcategory_books', {}).items():
            for book in books:
                if 'id' in book:
                    book_ids.add(book['id'])
        
        # Extract from all_books
        for book in category_data.get('all_books', []):
            if 'id' in book:
                book_ids.add(book['id'])
        
        return list(book_ids)

    def fetch_books_from_category(self, category_data: Dict, delay: int = 3):
        """Fetch all books from a category's data"""
        book_ids = self.extract_book_ids_from_category(category_data)
        
        if not book_ids:
            print(f"  ⚠️  No book IDs found in category: {category_data.get('main_category', 'Unknown')}")
            return
        
        print(f"\n📚 Found {len(book_ids)} books in category: {category_data.get('main_category', 'Unknown')}")
        print("=" * 50)
        
        self.fetch_multiple_books(book_ids, delay)

    def fetch_multiple_books(self, book_ids: List[str], delay: int = 3):
        """Fetch details for multiple books by their IDs"""
        print(f"\n📚 FETCHING {len(book_ids)} BOOKS")
        print("=" * 50)
        
        self.stats['books_processed'] = len(book_ids)
        
        for i, book_id in enumerate(book_ids, 1):
            print(f"\n[{i}/{len(book_ids)}] Processing book ID: {book_id}")
            
            book_data = self.fetch_book_details(book_id)
            if book_data:
                title = book_data.get('title', 'Unknown Title')
                print(f"  📖 Book: {title}")
            
            # Be respectful to the API
            if i < len(book_ids):
                print(f"  ⏳ Waiting {delay}s before next book...")
                time.sleep(delay)
        
        self.display_final_stats()

    def fetch_all_books(self, delay: int = 3):
        """Fetch all books from all extracted categories"""
        print("\n📚 FETCHING ALL BOOKS FROM CATEGORIES")
        print("=" * 50)
        
        # Reset stats
        self.stats = {
            'books_processed': 0,
            'successful_fetches': 0,
            'failed_fetches': 0
        }
        
        # Get all category_data.json files in the categories directory
        categories_dir = Path("../scrapped_data/categories")  # Points to bookey_scraper/data/categories
        category_files = list(categories_dir.glob("**/category_data.json"))  # Search recursively for category_data.json files
        
        if not category_files:
            print("❌ No category data files found!")
            print(f"  Looking in: {categories_dir.absolute()}")
            return
        
        print(f"📁 Found {len(category_files)} category files")
        
        for i, file_path in enumerate(category_files, 1):
            print(f"\n[{i}/{len(category_files)}] Processing category: {file_path.parent.name}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    category_data = json.load(f)
                
                # Get all subcategory_data.json files for this category
                subcategory_files = list(file_path.parent.glob("subcategories/*/subcategory_data.json"))
                
                if not subcategory_files:
                    print(f"  ⚠️  No subcategory data found in {file_path.parent.name}")
                    continue
                
                print(f"  📁 Found {len(subcategory_files)} subcategories")
                
                # Process each subcategory
                for subcat_file in subcategory_files:
                    try:
                        with open(subcat_file, 'r', encoding='utf-8') as f:
                            subcat_data = json.load(f)
                        
                        # Extract book IDs from the subcategory data
                        book_ids = []
                        for book in subcat_data.get('books', []):
                            if 'id' in book:
                                book_ids.append(book['id'])
                        
                        if book_ids:
                            print(f"    📚 Found {len(book_ids)} books in {subcat_file.parent.name}")
                            self.fetch_multiple_books(book_ids, delay)
                        else:
                            print(f"    ⚠️  No books found in {subcat_file.parent.name}")
                            
                    except Exception as e:
                        print(f"    ❌ Error processing subcategory {subcat_file.parent.name}: {e}")
                        continue
                
            except Exception as e:
                print(f"  ❌ Error processing category {file_path.parent.name}: {e}")
                continue

    def display_final_stats(self):
        """Display final fetching statistics"""
        print(f"\n📊 FETCH RESULTS")
        print("=" * 50)
        print(f"📚 Total Books Processed: {self.stats['books_processed']}")
        print(f"✅ Successfully fetched: {self.stats['successful_fetches']}")
        print(f"❌ Failed to fetch: {self.stats['failed_fetches']}")
        if self.stats['books_processed'] > 0:
            success_rate = (self.stats['successful_fetches'] / self.stats['books_processed']) * 100
            print(f"🎯 Success Rate: {success_rate:.1f}%")
        print(f"📁 Books saved in: {self.books_dir}/")

    def fetch_book_by_id(self, book_id: str, save_locally: bool = True) -> Optional[Dict]:
        """
        Simple method to fetch a book by its ID
        
        Args:
            book_id (str): The ID of the book to fetch
            save_locally (bool): Whether to save the book data locally (default: True)
            
        Returns:
            Optional[Dict]: The book data if successful, None otherwise
        """
        if not book_id or not book_id.strip():
            print("❌ Invalid book ID provided")
            return None
            
        book_id = book_id.strip()
        print(f"📚 Fetching book with ID: {book_id}")
        
        # Check local cache first
        if save_locally:
            local_data = self._get_local_book_data(book_id)
            if local_data:
                print(f"✅ Found book locally: {local_data.get('title', 'Unknown Title')}")
                return local_data
        
        # Fetch from API
        url = f"{self.base_url}/book/{book_id}"
        print(f"🌐 Fetching from API: {url}")
        
        try:
            self.update_app_time()
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract book details
            book_details = self._extract_book_details(data)
            
            if not book_details:
                print("❌ No valid book data received")
                return None
                
            print(f"✅ Successfully fetched: {book_details.get('title', 'Unknown Title')}")
            
            # Save locally if requested
            if save_locally:
                self.save_book_data(book_details, book_id)
                
            return book_details
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None

    def _get_local_book_data(self, book_id: str) -> Optional[Dict]:
        """Check if book data exists locally and return it"""
        for book_dir in self.books_dir.glob(f"{book_id}_*"):
            if book_dir.is_dir():
                book_files = list(book_dir.glob("*_book_data.json"))
                if book_files:
                    try:
                        with open(book_files[0], 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception as e:
                        print(f"⚠️ Error reading local data: {e}")
                        break
        return None

    def _extract_book_details(self, data: Dict) -> Optional[Dict]:
        """Extract relevant book details from API response"""
        if not data or not isinstance(data, dict):
            return None
            
        return {
            'id': data.get('id', ''),
            'title': data.get('title', ''),
            'subtitle': data.get('subTitle', ''),
            'author': data.get('author', ''),
            'authorInfo': data.get('authorInfo', ''),
            'desc': data.get('desc', ''),
            'quizList': data.get('quizList', []),
            'mindMapPath': data.get('mindMapPath', ''),
            'coverPath': data.get('coverPath', ''),
            'langCode': data.get('langCode', ''),
            'dataList': data.get('dataList', []),
            'quotes': data.get('quotes', []),
            'categoryName': data.get('categoryName', ''),
            'publishTime': data.get('publishTime', ''),
            'readTime': data.get('readTime', ''),
            'rating': data.get('rating', ''),
            'tags': data.get('tags', [])
        }

def main():
    """Main function for book fetching"""
    fetcher = BookeyBookFetcher()
    
    print("📚 BOOKEY BOOK FETCHER")
    print("=" * 50)
    print("1. Fetch specific books by ID")
    print("2. Fetch all books from categories")
    
    choice = input("\nEnter your choice (1-2): ").strip()
    
    if choice == "1":
        book_ids = input("Enter book IDs separated by commas: ").strip().split(',')
        book_ids = [id.strip() for id in book_ids if id.strip()]
        
        if book_ids:
            delay = input("Enter delay between requests in seconds (default: 3): ").strip()
            delay = int(delay) if delay.isdigit() else 3
            
            print(f"\n🔍 Will fetch {len(book_ids)} books with {delay}s delay between requests")
            confirm = input("Continue? (y/n): ").lower().strip()
            
            if confirm == 'y':
                fetcher.fetch_multiple_books(book_ids, delay)
            else:
                print("❌ Operation cancelled.")
        else:
            print("❌ No valid book IDs provided.")
    
    elif choice == "2":
        delay = input("Enter delay between requests in seconds (default: 3): ").strip()
        delay = int(delay) if delay.isdigit() else 3
        
        print(f"\n🔍 Will fetch all books with {delay}s delay between requests")
        confirm = input("Continue? (y/n): ").lower().strip()
        
        if confirm == 'y':
            fetcher.fetch_all_books(delay)
        else:
            print("❌ Operation cancelled.")
    
    else:
        print("❌ Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main()