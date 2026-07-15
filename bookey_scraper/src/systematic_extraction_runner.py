#!/usr/bin/env python3
"""
Systematic Extraction Runner for Bookey Categories
Provides options to extract all categories or specific ranges
"""

import sys
import argparse
from categories.category_scraper import ImprovedBookeyScraper
from categories.systematic_extraction import run_with_args

def print_categories_menu(scraper):
    """Print available categories with their numbers"""
    print("\n📚 AVAILABLE CATEGORIES:")
    print("=" * 50)
    for i, category in enumerate(scraper.main_categories, 1):
        print(f"{i:2d}. {category['name']}")
    print()

def extract_all_categories():
    """Extract all 12 categories systematically"""
    print("🎯 EXTRACTING ALL CATEGORIES")
    print("=" * 40)
    
    scraper = ImprovedBookeyScraper()
    print_categories_menu(scraper)
    
    confirm = input("⚠️  This will make 12+ API calls. Continue? (y/n): ").lower().strip()
    if confirm != 'y':
        print("❌ Extraction cancelled.")
        return
    
    print("\n🚀 Starting extraction of all categories...")
    scraper.run_systematic_extraction(start_from=0, max_categories=None)

def extract_test_batch():
    """Extract first 3 categories as a test"""
    print("🧪 TEST EXTRACTION (First 3 Categories)")
    print("=" * 40)
    
    scraper = ImprovedBookeyScraper()
    print("Testing with:")
    for i in range(3):
        print(f"  {i+1}. {scraper.main_categories[i]['name']}")
    
    print("\n🚀 Starting test extraction...")
    scraper.run_systematic_extraction(start_from=0, max_categories=3)

def extract_specific_range():
    """Extract a specific range of categories"""
    print("🎯 EXTRACT SPECIFIC RANGE")
    print("=" * 40)
    
    scraper = ImprovedBookeyScraper()
    print_categories_menu(scraper)
    
    try:
        start = int(input("Enter start category number (1-12): ")) - 1
        end = int(input("Enter end category number (1-12): "))
        
        if start < 0 or start >= len(scraper.main_categories):
            print("❌ Invalid start number")
            return
        
        if end <= start or end > len(scraper.main_categories):
            print("❌ Invalid end number")
            return
        
        max_categories = end - start
        
        print(f"\n📋 Will extract categories {start+1} to {end}:")
        for i in range(start, end):
            print(f"  {i+1}. {scraper.main_categories[i]['name']}")
        
        confirm = input(f"\n⚠️  This will make {max_categories}+ API calls. Continue? (y/n): ").lower().strip()
        if confirm != 'y':
            print("❌ Extraction cancelled.")
            return
        
        print("\n🚀 Starting range extraction...")
        scraper.run_systematic_extraction(start_from=start, max_categories=max_categories)
        
    except ValueError:
        print("❌ Please enter valid numbers")

def extract_specific_categories():
    """Extract specific individual categories by selection"""
    print("🎯 EXTRACT SPECIFIC CATEGORIES")
    print("=" * 40)
    
    scraper = ImprovedBookeyScraper()
    print_categories_menu(scraper)
    
    try:
        selection = input("Enter category numbers separated by commas (e.g., 1,3,5): ").strip()
        category_numbers = [int(x.strip()) - 1 for x in selection.split(',')]
        
        # Validate numbers
        for num in category_numbers:
            if num < 0 or num >= len(scraper.main_categories):
                print(f"❌ Invalid category number: {num + 1}")
                return
        
        print(f"\n📋 Will extract {len(category_numbers)} categories:")
        for num in category_numbers:
            print(f"  {num+1}. {scraper.main_categories[num]['name']}")
        
        confirm = input(f"\n⚠️  This will make {len(category_numbers)}+ API calls. Continue? (y/n): ").lower().strip()
        if confirm != 'y':
            print("❌ Extraction cancelled.")
            return
        
        print("\n🚀 Starting selective extraction...")
        
        # Create a custom extraction for selected categories
        selected_categories = [scraper.main_categories[num] for num in category_numbers]
        all_extracted_data = []
        
        for i, category in enumerate(selected_categories, 1):
            print(f"\n{'='*70}")
            print(f"PROCESSING SELECTED CATEGORY {i}/{len(selected_categories)}")
            print(f"{'='*70}")
            
            scraper.stats['categories_processed'] += 1
            
            extracted_data = scraper.extract_category_data(category['id'], category['name'])
            
            if extracted_data:
                scraper.save_category_data(extracted_data)
                all_extracted_data.append(extracted_data)
                print(f"  ✅ Successfully extracted {category['name']}")
            else:
                print(f"  ❌ Failed to extract {category['name']}")
            
            # Be respectful to the API
            if i < len(selected_categories):
                wait_time = 3
                print(f"  ⏳ Waiting {wait_time}s before next category...")
                import time
                time.sleep(wait_time)
        
        # Create summary for selected extractions
        scraper.create_final_summary(all_extracted_data)
        scraper.display_final_stats()
        
    except ValueError:
        print("❌ Please enter valid numbers separated by commas")

def show_already_extracted():
    """Show what categories have already been extracted"""
    import os
    import json
    
    print("📋 ALREADY EXTRACTED CATEGORIES")
    print("=" * 40)
    
    # Check existing extractions
    existing_files = []
    
    # Check data directory
    if os.path.exists('../scrapped_data'):
        for file in os.listdir('../scrapped_data'):
            if file.endswith('_extracted.json'):
                existing_files.append(('../scrapped_data', file))
    
    # Check all_categories_extracted directory
    if os.path.exists('../all_categories_extracted'):
        for file in os.listdir('../all_categories_extracted'):
            if file.endswith('_extracted.json') and 'summary' not in file:
                existing_files.append(('../all_categories_extracted', file))
    
    # Check scrape_categories_list_data directory
    if os.path.exists('../scrape_categories_list_data'):
        for file in os.listdir('../scrape_categories_list_data'):
            if file.endswith('_extracted.json'):
                existing_files.append(('../scrape_categories_list_data', file))
    
    if not existing_files:
        print("❌ No extracted categories found.")
        return
    
    print("✅ Found extracted categories:")
    for directory, filename in existing_files:
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                category_name = data.get('main_category', 'Unknown')
                books_count = data.get('total_books', 0)
                subcats_count = data.get('total_subcategories', 0)
                print(f"  📁 {category_name}: {subcats_count} subcategories, {books_count} books")
                print(f"     └─ File: {filepath}")
        except:
            print(f"  ❌ Error reading: {filepath}")
    
    print()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Bookey Category Scraper')
    parser.add_argument('--test', action='store_true', help='Run test extraction (first 3 categories)')
    parser.add_argument('--all', action='store_true', help='Extract all 12 categories')
    parser.add_argument('--range', help='Extract specific range (e.g., 1-5)')
    parser.add_argument('--select', help='Extract specific categories (e.g., 1,3,5)')
    parser.add_argument('--list', action='store_true', help='Show already extracted categories')
    
    args = parser.parse_args()
    run_with_args(args)

if __name__ == "__main__":
    main() 