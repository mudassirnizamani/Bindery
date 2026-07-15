#!/usr/bin/env python3
"""
Improved Bookey Category Scraper with Icon Downloading
Uses the correct API endpoint format to extract all main categories systematically
and downloads all icons for subcategories
"""

import json
import requests
import time
import os
import urllib.parse
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional
from books.book_fetcher import BookeyBookFetcher

class ImprovedBookeyScraper:
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
        
        # All 12 main categories with their IDs and names
        self.main_categories = [
            {'id': '5e3bc389b834740001d35ad8', 'name': 'Personal Development'},
            {'id': '5e3bc443b834740001d35ae0', 'name': 'Psychology & Happiness'},
            {'id': '5e3bc39db834740001d35ad9', 'name': 'Management & Business'},
            {'id': '5e3bc373b834740001d35ad7', 'name': 'Biography & Memoir'},
            {'id': '5e3bc3aeb834740001d35ada', 'name': 'Finance & Investments'},
            {'id': '5e3bc418b834740001d35adf', 'name': 'Society & Culture'},
            {'id': '5e3bc465b834740001d35ae2', 'name': 'Parenting & Education'},
            {'id': '5e3bc455b834740001d35ae1', 'name': 'Art & Creativity'},
            {'id': '5e3bc3beb834740001d35adb', 'name': 'Health & Sports'},
            {'id': '5e3bc3d0b834740001d35adc', 'name': 'Nature & Science'},
            {'id': '5e3bc3f3b834740001d35add', 'name': 'History & Politics'},
            {'id': '5e3bc403b834740001d35ade', 'name': 'Philosophy & Religion'}
        ]
        
        # Create output directories
        self.base_output_dir = Path("../scrapped_data")
        self.categories_dir = self.base_output_dir / "categories"
        
        # Create main directories
        self.categories_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'categories_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_subcategories': 0,
            'total_books': 0,
            'icons_downloaded': 0,
            'icons_failed': 0
        }
        
        # Initialize book fetcher
        self.book_fetcher = BookeyBookFetcher()

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

    def get_file_extension(self, url: str) -> str:
        """Extract file extension from URL"""
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if '.' in path:
            return Path(path).suffix
        return '.png'  # Default to PNG if no extension found

    def download_icon(self, icon_url: str, category_name: str, subcategory_name: str, icon_type: str) -> Optional[str]:
        """Download an icon and return the local file path"""
        if not icon_url or icon_url.strip() == "":
            return None
        
        try:
            # Create safe filenames
            safe_category = self.sanitize_filename(category_name)
            safe_subcategory = self.sanitize_filename(subcategory_name)
            
            # Get file extension
            file_ext = self.get_file_extension(icon_url)
            
            # Create organized folder structure
            category_folder = Path(f"../scrapped_data/icons/{safe_category}")
            category_folder.mkdir(parents=True, exist_ok=True)
            
            # Create filename
            filename = f"{safe_subcategory}_{icon_type}{file_ext}"
            filepath = category_folder / filename
            
            # Download if not already exists
            if filepath.exists():
                print(f"      📁 Icon already exists: {filepath}")
                return str(filepath)
            
            # Download the icon
            print(f"      🔽 Downloading {icon_type}: {icon_url}")
            response = requests.get(icon_url, timeout=90)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                print(f"      ✅ Saved: {filepath}")
                self.stats['icons_downloaded'] += 1
                return str(filepath)
            else:
                print(f"      ❌ Failed to download {icon_type}: HTTP {response.status_code}")
                self.stats['icons_failed'] += 1
                return None
                
        except Exception as e:
            print(f"      ❌ Error downloading {icon_type}: {e}")
            self.stats['icons_failed'] += 1
            return None

    def download_subcategory_icons(self, subcategory: Dict, category_name: str) -> Dict:
        """Download all icons for a subcategory and return updated subcategory data"""
        subcategory_name = subcategory.get('name', 'Unknown')
        print(f"    🎨 Processing icons for: {subcategory_name}")
        
        # Icon types to download
        icon_types = {
            'iconPath': 'icon',
            'darkIconPath': 'dark_icon',
            'watchIconPath': 'watch_icon',
            'miniIconPath': 'mini_icon',
            'warmthIconPath': 'warmth_icon'
        }
        
        # Create updated subcategory data with local icon paths
        # First, copy the subcategory data but exclude unnecessary language fields
        updated_subcategory = subcategory.copy()
        
        # Remove unwanted language fields to keep data clean
        fields_to_remove = ['langName', 'langWarmthDesc', 'langStatus']
        for field in fields_to_remove:
            updated_subcategory.pop(field, None)
        
        local_icon_paths = {}
        
        for url_key, icon_type in icon_types.items():
            icon_url = subcategory.get(url_key, '')
            if icon_url:
                local_path = self.download_icon(icon_url, category_name, subcategory_name, icon_type)
                if local_path:
                    local_icon_paths[f"local_{icon_type}_path"] = local_path
        
        # Add local paths to subcategory data
        updated_subcategory['local_icon_paths'] = local_icon_paths
        
        return updated_subcategory

    def extract_category_data(self, category_id: str, category_name: str) -> Optional[Dict]:
        """Extract data for a specific category using the correct endpoint format"""
        print(f"\n🔍 Extracting: {category_name} (ID: {category_id})")
        
        # Use the correct endpoint format that the app actually uses
        correct_endpoint = f"/book/category/{category_id}/sub?showSubCategoryListBySubType=false"
        url = f"{self.base_url}{correct_endpoint}"
        
        print(f"  🌐 Using endpoint: {correct_endpoint}")
        
        data = self.make_request(url)
        
        if not data or not isinstance(data, dict):
            print(f"  ❌ No valid data returned for {category_name}")
            self.stats['failed_extractions'] += 1
            return None
        
        # Check if we have the expected data structure
        has_subcategories = 'subCategoryList' in data and len(data['subCategoryList']) > 0
        has_books = 'bookList' in data and len(data['bookList']) > 0
        
        if not has_subcategories and not has_books:
            print(f"    ⚠️  No subcategories or books found in response")
            self.stats['failed_extractions'] += 1
            return None
        
        print(f"  ✅ Success!")
        print(f"    📁 Subcategories: {len(data.get('subCategoryList', []))}")
        print(f"    📚 Books: {len(data.get('bookList', []))}")
        
        # Extract and process the data (including icon downloading)
        extracted_data = self.process_category_data(data, category_id, category_name, correct_endpoint)
        
        if extracted_data:
            self.stats['successful_extractions'] += 1
            self.stats['total_subcategories'] += extracted_data['total_subcategories']
            self.stats['total_books'] += extracted_data['total_books']
        
        return extracted_data

    def process_category_data(self, data: Dict, category_id: str, category_name: str, endpoint: str) -> Dict:
        """Process the raw API response into our standard format and download icons"""
        
        # Extract subcategories and download their icons
        subcategories = {}
        subcategories_with_icons = {}
        
        if 'subCategoryList' in data:
            print(f"  🎨 Downloading icons for {len(data['subCategoryList'])} subcategories...")
            
            for subcat in data['subCategoryList']:
                # Store basic subcategory info
                subcategories[subcat['_id']] = subcat['name']
                
                # Download icons and store detailed subcategory info
                updated_subcat = self.download_subcategory_icons(subcat, category_name)
                subcategories_with_icons[subcat['_id']] = updated_subcat
        
        # Extract and group books by subcategory
        subcategory_books = defaultdict(list)
        all_books = []
        
        if 'bookList' in data:
            for book in data['bookList']:
                book_info = {
                    'title': book.get('title', ''),
                    'author': book.get('author', 'Unknown Author'),
                    'subtitle': book.get('subTitle', ''),
                    'id': book.get('_id', ''),
                    'duration': book.get('duration', ''),
                    'free': book.get('free', False),
                    'cover_path': book.get('coverPath', ''),
                    'created_date': book.get('createdDate', '')
                }
                
                all_books.append(book_info)
                
                # Map to subcategories
                category_ids = book.get('categoryId', [])
                for cat_id in category_ids:
                    if cat_id in subcategories:
                        subcat_name = subcategories[cat_id]
                        subcategory_books[subcat_name].append(book_info)
        
        # Prepare final data structure
        extracted_data = {
            'main_category': category_name,
            'main_category_id': category_id,
            'successful_endpoint': endpoint,
            'subcategories': subcategories,
            'subcategories_with_icons': subcategories_with_icons,
            'subcategory_books': dict(subcategory_books),
            'all_books': all_books,
            'total_subcategories': len(subcategories),
            'total_books': len(all_books),
            'extraction_timestamp': int(time.time()),
            'raw_response_size': len(str(data))
        }
        
        print(f"  📊 Processed: {len(subcategories)} subcategories, {len(all_books)} books")
        print(f"  🎨 Icons downloaded: {self.stats['icons_downloaded']}, failed: {self.stats['icons_failed']}")
        
        return extracted_data

    def save_category_data(self, category_data: Dict):
        """Save category data in the new hierarchical structure"""
        category_name = category_data['main_category']
        safe_name = self.sanitize_filename(category_name)
        
        # Create category directory
        category_dir = self.categories_dir / safe_name
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        icons_dir = category_dir / "icons"
        subcategories_dir = category_dir / "subcategories"
        icons_dir.mkdir(exist_ok=True)
        subcategories_dir.mkdir(exist_ok=True)
        
        # Save main category data
        category_file = category_dir / "category_data.json"
        with open(category_file, 'w', encoding='utf-8') as f:
            json.dump({
                'name': category_name,
                'id': category_data['main_category_id'],
                'total_subcategories': category_data['total_subcategories'],
                'total_books': category_data['total_books'],
                'extraction_timestamp': category_data['extraction_timestamp']
            }, f, indent=2, ensure_ascii=False)
        
        # Process and save subcategories
        for subcat_id, subcat_data in category_data.get('subcategories_with_icons', {}).items():
            subcat_name = subcat_data.get('name', 'Unknown')
            safe_subcat_name = self.sanitize_filename(subcat_name)
            
            # Create subcategory directory
            subcat_dir = subcategories_dir / safe_subcat_name
            subcat_dir.mkdir(exist_ok=True)
            
            # Create subcategory icons directory
            subcat_icons_dir = subcat_dir / "icons"
            subcat_icons_dir.mkdir(exist_ok=True)
            
            # Move icons to subcategory icons directory
            local_icons = subcat_data.get('local_icon_paths', {})
            for icon_type, old_path in local_icons.items():
                if old_path and Path(old_path).exists():
                    # Get the icon filename
                    icon_filename = Path(old_path).name
                    # Create new path in subcategory icons directory
                    new_path = subcat_icons_dir / icon_filename
                    # Move the file
                    Path(old_path).rename(new_path)
                    # Update the path in the data
                    local_icons[icon_type] = str(new_path)
            
            # Save subcategory data
            subcat_file = subcat_dir / "subcategory_data.json"
            with open(subcat_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'name': subcat_name,
                    'id': subcat_id,
                    'parent_id': subcat_data.get('parentId'),
                    'type': subcat_data.get('type'),
                    'sort': subcat_data.get('sort'),
                    'status': subcat_data.get('status'),
                    'created_date': subcat_data.get('createdDate'),
                    'local_icon_paths': local_icons,
                    'books': category_data.get('subcategory_books', {}).get(subcat_name, [])
                }, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 Saved category data to: {category_dir}")

    def create_final_summary(self, all_extracted_data: List[Dict]):
        """Create a comprehensive summary of all extracted data including icon information"""
        summary = {
            'extraction_session': {
                'timestamp': int(time.time()),
                'total_categories_attempted': self.stats['categories_processed'],
                'successful_extractions': self.stats['successful_extractions'],
                'failed_extractions': self.stats['failed_extractions'],
                'success_rate': f"{(self.stats['successful_extractions'] / max(self.stats['categories_processed'], 1)) * 100:.1f}%",
                'icons_downloaded': self.stats['icons_downloaded'],
                'icons_failed': self.stats['icons_failed'],
                'total_icons_attempted': self.stats['icons_downloaded'] + self.stats['icons_failed']
            },
            'categories_summary': {},
            'overall_stats': {
                'total_subcategories': 0,
                'total_books': 0,
                'unique_subcategory_names': set(),
                'total_icons_downloaded': self.stats['icons_downloaded']
            },
            'icon_structure': {
                'base_path': str(self.base_output_dir / 'icons'),
                'organization': 'Category folders containing subcategory icons',
                'icon_types': ['icon', 'dark_icon', 'watch_icon', 'mini_icon', 'warmth_icon']
            },
            'all_categories_list': [cat['name'] for cat in self.main_categories]
        }
        
        for data in all_extracted_data:
            cat_name = data['main_category']
            
            # Count icons for this category
            category_icons_count = 0
            subcategories_with_icon_info = {}
            
            for subcat_id, subcat_data in data.get('subcategories_with_icons', {}).items():
                local_icons = subcat_data.get('local_icon_paths', {})
                category_icons_count += len(local_icons)
                
                subcategories_with_icon_info[subcat_data.get('name', 'Unknown')] = {
                    'id': subcat_id,
                    'icons_downloaded': len(local_icons),
                    'available_icons': list(local_icons.keys()),
                    'original_icon_urls': {
                        'iconPath': subcat_data.get('iconPath', ''),
                        'darkIconPath': subcat_data.get('darkIconPath', ''),
                        'watchIconPath': subcat_data.get('watchIconPath', ''),
                        'miniIconPath': subcat_data.get('miniIconPath', ''),
                        'warmthIconPath': subcat_data.get('warmthIconPath', '')
                    }
                }
            
            summary['categories_summary'][cat_name] = {
                'id': data['main_category_id'],
                'successful_endpoint': data['successful_endpoint'],
                'subcategories_count': data['total_subcategories'],
                'books_count': data['total_books'],
                'icons_downloaded': category_icons_count,
                'subcategories': list(data['subcategories'].values()),
                'subcategories_with_icons': subcategories_with_icon_info,
                'sample_books': data['all_books'][:3]  # First 3 books as sample
            }
            
            summary['overall_stats']['total_subcategories'] += data['total_subcategories']
            summary['overall_stats']['total_books'] += data['total_books']
            summary['overall_stats']['unique_subcategory_names'].update(data['subcategories'].values())
        
        # Convert set to sorted list for JSON serialization
        summary['overall_stats']['unique_subcategory_names'] = sorted(list(summary['overall_stats']['unique_subcategory_names']))
        
        # Save summary
        summary_file = self.base_output_dir / "EXTRACTION_SUMMARY.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 Summary saved to: {summary_file}")

    def display_final_stats(self):
        """Display final extraction statistics including icon downloads"""
        print(f"\n🎯 FINAL EXTRACTION STATISTICS")
        print("=" * 50)
        print(f"📊 Categories Processed: {self.stats['categories_processed']}")
        print(f"✅ Successful Extractions: {self.stats['successful_extractions']}")
        print(f"❌ Failed Extractions: {self.stats['failed_extractions']}")
        print(f"📈 Success Rate: {(self.stats['successful_extractions'] / max(self.stats['categories_processed'], 1)) * 100:.1f}%")
        print(f"📁 Total Subcategories: {self.stats['total_subcategories']}")
        print(f"📚 Total Books: {self.stats['total_books']}")
        print(f"🎨 Icons Downloaded: {self.stats['icons_downloaded']}")
        print(f"❌ Icons Failed: {self.stats['icons_failed']}")
        if self.stats['icons_downloaded'] + self.stats['icons_failed'] > 0:
            icon_success_rate = (self.stats['icons_downloaded'] / (self.stats['icons_downloaded'] + self.stats['icons_failed'])) * 100
            print(f"🎯 Icon Success Rate: {icon_success_rate:.1f}%")
        print(f"📁 Data saved in: {self.base_output_dir}/ directory")
        print(f"🎨 Icons saved in: {self.base_output_dir}/icons/ directory")

    def run_systematic_extraction(self, start_from: int = 0, max_categories: int = None):
        """Run systematic extraction for all or specific categories"""
        print("🚀 IMPROVED BOOKEY CATEGORY SCRAPER")
        print("=" * 60)
        print(f"📊 Target: {len(self.main_categories)} main categories")
        print(f"🔄 Starting from category #{start_from + 1}")
        
        if max_categories:
            print(f"📝 Limiting to {max_categories} categories")
        print()
        
        all_extracted_data = []
        categories_to_process = self.main_categories[start_from:]
        
        if max_categories:
            categories_to_process = categories_to_process[:max_categories]
        
        for i, category in enumerate(categories_to_process, start_from + 1):
            print(f"\n{'='*70}")
            print(f"PROCESSING CATEGORY {i}/{len(self.main_categories)}")
            print(f"{'='*70}")
            
            self.stats['categories_processed'] += 1
            
            extracted_data = self.extract_category_data(category['id'], category['name'])
            
            if extracted_data:
                self.save_category_data(extracted_data)
                all_extracted_data.append(extracted_data)
                print(f"  ✅ Successfully extracted {category['name']}")
            else:
                print(f"  ❌ Failed to extract {category['name']}")
            
            # Be respectful to the API
            if i < len(categories_to_process):
                wait_time = 3
                print(f"  ⏳ Waiting {wait_time}s before next category...")
                time.sleep(wait_time)
        
        # Create comprehensive summary
        self.create_final_summary(all_extracted_data)
        
        # Display final statistics
        self.display_final_stats()
        
        return all_extracted_data 