#!/usr/bin/env python3
"""
Standalone Icon Downloader for Bookey Categories
Downloads icons for subcategories from existing extracted JSON files
"""

import json
import requests
import os
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional
import glob

class BookeyIconDownloader:
    def __init__(self):
        self.stats = {
            'icons_downloaded': 0,
            'icons_failed': 0,
            'icons_skipped': 0
        }
        
        # Create icons directory
        os.makedirs('data/icons', exist_ok=True)

    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be used as a filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        while '__' in name:
            name = name.replace('__', '_')
        
        return name.strip('_')

    def get_file_extension(self, url: str) -> str:
        """Extract file extension from URL"""
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if '.' in path:
            return Path(path).suffix
        return '.png'

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
            category_folder = Path(f"data/icons/{safe_category}")
            category_folder.mkdir(parents=True, exist_ok=True)
            
            # Create filename
            filename = f"{safe_subcategory}_{icon_type}{file_ext}"
            filepath = category_folder / filename
            
            # Download if not already exists
            if filepath.exists():
                print(f"      📁 Icon already exists: {filepath}")
                self.stats['icons_skipped'] += 1
                return str(filepath)
            
            # Download the icon
            print(f"      🔽 Downloading {icon_type}: {icon_url}")
            response = requests.get(icon_url, timeout=30)
            
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

    def process_json_file(self, json_file_path: str) -> bool:
        """Process a single JSON file and download icons for its subcategories"""
        try:
            print(f"\n📁 Processing: {json_file_path}")
            
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            category_name = data.get('main_category', 'Unknown Category')
            print(f"  📂 Category: {category_name}")
            
            # Check if icons are already processed
            if 'subcategories_with_icons' in data:
                print("  ✅ Icons already processed for this category")
                return True
            
            # Process subcategories from raw API response or basic subcategories
            subcategories_data = {}
            
            # Try to get subcategory data from the original API response structure
            # This would require access to the original API response
            print("  ⚠️  No detailed subcategory data found in this JSON file")
            print("      This file may need to be re-extracted with the updated scraper")
            return False
            
        except Exception as e:
            print(f"  ❌ Error processing {json_file_path}: {e}")
            return False

    def download_from_api_response(self, api_response_file: str) -> bool:
        """Download icons from a file containing raw API response data"""
        try:
            print(f"\n📡 Processing API response file: {api_response_file}")
            
            with open(api_response_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            category_name = data.get('main_category', 'Unknown Category')
            
            # Look for subcategory list in the raw response
            raw_response = data.get('raw_api_response', {})
            if not raw_response and 'subCategoryList' not in data:
                print("  ⚠️  No subcategory data found")
                return False
            
            subcategories = raw_response.get('subCategoryList', data.get('subCategoryList', []))
            
            if not subcategories:
                print("  ⚠️  No subcategories found")
                return False
            
            print(f"  🎨 Found {len(subcategories)} subcategories to process")
            
            # Download icons for each subcategory
            for subcat in subcategories:
                subcategory_name = subcat.get('name', 'Unknown')
                print(f"    🎯 Processing: {subcategory_name}")
                
                # Icon types to download
                icon_types = {
                    'iconPath': 'icon',
                    'darkIconPath': 'dark_icon',
                    'watchIconPath': 'watch_icon',
                    'miniIconPath': 'mini_icon',
                    'warmthIconPath': 'warmth_icon'
                }
                
                for url_key, icon_type in icon_types.items():
                    icon_url = subcat.get(url_key, '')
                    if icon_url:
                        self.download_icon(icon_url, category_name, subcategory_name, icon_type)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error processing API response file: {e}")
            return False

    def clean_subcategory_data(self, subcategory_data: Dict) -> Dict:
        """Remove unnecessary language fields from subcategory data"""
        cleaned_data = subcategory_data.copy()
        
        # Remove unwanted language fields to keep data clean
        fields_to_remove = ['langName', 'langWarmthDesc', 'langStatus']
        for field in fields_to_remove:
            cleaned_data.pop(field, None)
        
        return cleaned_data

    def process_all_extracted_files(self):
        """Process all extracted JSON files in the directory"""
        print("🎨 BOOKEY ICON DOWNLOADER")
        print("=" * 50)
        
        # Find all extracted JSON files
        json_files = glob.glob('data/*_extracted.json')
        
        if not json_files:
            print("❌ No extracted JSON files found!")
            print("   Please run the main scraper first to extract category data.")
            return
        
        print(f"📁 Found {len(json_files)} JSON files to process")
        
        processed_count = 0
        for json_file in json_files:
            if self.process_json_file(json_file):
                processed_count += 1
        
        self.display_stats()
        
        if processed_count == 0:
            print("\n💡 TIP: Re-run the main scraper with the updated version")
            print("   to get subcategory icon URLs for downloading.")

    def download_specific_icons(self, icon_mapping: Dict[str, Dict[str, str]]):
        """Download icons from a specific mapping"""
        print("🎯 DOWNLOADING SPECIFIC ICONS")
        print("=" * 40)
        
        for category_name, subcategories in icon_mapping.items():
            print(f"\n📂 Processing category: {category_name}")
            
            for subcat_name, icon_urls in subcategories.items():
                print(f"  🎨 Processing subcategory: {subcat_name}")
                
                for icon_type, url in icon_urls.items():
                    if url:
                        self.download_icon(url, category_name, subcat_name, icon_type)
        
        self.display_stats()

    def display_stats(self):
        """Display download statistics"""
        print(f"\n📊 ICON DOWNLOAD STATISTICS")
        print("=" * 40)
        print(f"✅ Icons Downloaded: {self.stats['icons_downloaded']}")
        print(f"📁 Icons Skipped (already exist): {self.stats['icons_skipped']}")
        print(f"❌ Icons Failed: {self.stats['icons_failed']}")
        
        total_attempted = self.stats['icons_downloaded'] + self.stats['icons_failed']
        if total_attempted > 0:
            success_rate = (self.stats['icons_downloaded'] / total_attempted) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print(f"📁 Icons saved in: data/icons/") 