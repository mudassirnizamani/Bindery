# Bookey API Scraper with Icon Downloading

This directory contains all the tools and scripts for scraping data from the Bookey API, including automatic icon downloading for subcategories.

## 📁 Directory Structure

### Core Scripts
- `improved_category_scraper.py` - **Latest enhanced scraper** with icon downloading support
- `icon_downloader.py` - **Standalone icon downloader** for existing data
- `systematic_extraction_runner.py` - **Systematic extraction runner** for batch processing
- `enhanced_bookey_scraper.py` - Enhanced scraper engine with database storage
- `run_full_scrape.py` - Full automation script to run complete scraping
- `discover_categories.py` - Category discovery tool to find all available category IDs
- `test_specific_endpoints.py` - Test script for the 3 specific provided endpoints
- `bookey_scraper.py` - Original scraper with basic functionality

### Configuration & Dependencies
- `requirements.txt` - Python package dependencies
- `SCRAPING_RESULTS.md` - Comprehensive documentation of scraping results and insights

### Data Directories
- `improved_extracted_data/` - **NEW**: Output from improved scraper with icons
  - `icons/` - **Downloaded subcategory icons** organized by category
  - `*_extracted.json` - Category data with icon information
  - `IMPROVED_EXTRACTION_SUMMARY.json` - Complete extraction summary
- `enhanced_scraped_data/` - Output from enhanced scraper (SQLite DB, CSV reports, JSON files)
- `scrape_categories_list_data/` - Raw category discovery data

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd bookey_scraper
pip install -r requirements.txt
```

### 2. Run Improved Scraper with Icon Downloading
```bash
python improved_category_scraper.py
```

This will:
- Extract all category and subcategory data
- **Download all subcategory icons** (icon, dark_icon, mini_icon, watch_icon, warmth_icon)
- Organize icons in `improved_extracted_data/icons/CategoryName/` folders
- Create comprehensive JSON files with local icon paths

### 3. Alternative: Use Standalone Icon Downloader
```bash
python icon_downloader.py
```

### 4. Test API Connectivity (Optional)
```bash
python test_specific_endpoints.py
```

## 🎨 Icon Downloading Features

### Automatic Icon Organization
```
improved_extracted_data/icons/
├── Finance_and_Investments/
│   ├── Economics_icon.png
│   ├── Economics_dark_icon.png
│   ├── Economics_mini_icon.png
│   ├── Investment_icon.png
│   └── ...
├── Personal_Development/
│   ├── Self_Help_icon.png
│   ├── Self_Help_dark_icon.png
│   └── ...
└── ...
```

### Icon Types Downloaded
- **`iconPath`** → `*_icon.png` - Main category icon
- **`darkIconPath`** → `*_dark_icon.png` - Dark theme icon
- **`miniIconPath`** → `*_mini_icon.png` - Small/mini icon
- **`watchIconPath`** → `*_watch_icon.png` - Watch interface icon
- **`warmthIconPath`** → `*_warmth_icon.png` - Warmth/emotion icon

### Icon Data Structure
Each subcategory now includes:
```json
{
  "name": "Economics",
  "iconPath": "https://cdn.bookey.app/_category/20210722192147650.png",
  "darkIconPath": "https://cdn.bookey.app/_category/20220919113804852.png",
  "local_icon_paths": {
    "local_icon_path": "improved_extracted_data/icons/Finance_and_Investments/Economics_icon.png",
    "local_dark_icon_path": "improved_extracted_data/icons/Finance_and_Investments/Economics_dark_icon.png",
    "local_mini_icon_path": "improved_extracted_data/icons/Finance_and_Investments/Economics_mini_icon.png"
  }
}
```

## 📊 What You Get

### Complete Data Package
- **📁 Category Data**: Complete subcategory and book information
- **🎨 Icons**: All subcategory icons downloaded and organized
- **📊 Statistics**: Comprehensive extraction and download statistics
- **🔗 Local Paths**: Direct links to downloaded icons in your data structure

### Output Files
- **JSON Data**: `improved_extracted_data/*_extracted.json`
- **Summary**: `improved_extracted_data/IMPROVED_EXTRACTION_SUMMARY.json`
- **Icons**: `improved_extracted_data/icons/CategoryName/`
- **SQLite Database**: `enhanced_scraped_data/bookey_enhanced.db` (from enhanced scraper)

## 🔧 Usage Options

### 1. Improved Scraper (Latest - Recommended)
```python
from improved_category_scraper import ImprovedBookeyScraper
scraper = ImprovedBookeyScraper()
scraper.run_systematic_extraction(start_from=0, max_categories=3)  # Test run
scraper.run_systematic_extraction()  # Full extraction
```

### 2. Standalone Icon Downloader
```python
from icon_downloader import BookeyIconDownloader
downloader = BookeyIconDownloader()
downloader.process_all_extracted_files()  # Process existing JSON files

# Or download specific icons
icon_mapping = {
    "Finance & Investments": {
        "Economics": {
            "icon": "https://cdn.bookey.app/_category/20210722192147650.png",
            "dark_icon": "https://cdn.bookey.app/_category/20220919113804852.png"
        }
    }
}
downloader.download_specific_icons(icon_mapping)
```

### 3. Enhanced Scraper (Previous Version)
```python
from enhanced_bookey_scraper import EnhancedBookeyScraper
scraper = EnhancedBookeyScraper()
scraper.run_enhanced_scrape(max_categories=20)
```

## 📈 Results Summary

### Data Extraction
From test runs:
- **📚 2,360+ books** extracted
- **🏷️ 129+ subcategories** found  
- **🔗 3,347+ relationships** mapped
- **🎨 500+ icons** downloaded
- **❌ Near 0% error rate**

### Icon Statistics
- **✅ High success rate** for icon downloads
- **📁 Organized storage** by category
- **🔄 Smart caching** - skips already downloaded icons
- **🛡️ Error handling** for failed downloads

## 🔐 Authentication

The JWT token in the headers will expire. When it does, you'll need to:
1. Update the `token` field in the headers in `improved_category_scraper.py`
2. Ensure the `USER_ID` matches your Google account

## 🎯 Integration

The scraped data with icons is designed for easy integration into SmartFM:
- **Local icon paths** ready for direct use
- **Organized folder structure** matching categories
- **Complete metadata** linking categories to their visual assets
- **JSON format** for easy parsing and integration

## 🚀 Advanced Usage

### Custom Icon Processing
```python
# Download icons for specific categories only
scraper = ImprovedBookeyScraper()
finance_data = scraper.extract_category_data('5e3bc3aeb834740001d35ada', 'Finance & Investments')

# Process existing data to add missing icons
downloader = BookeyIconDownloader()
downloader.process_all_extracted_files()
```

### Batch Processing
```bash
# Run systematic extraction
python systematic_extraction_runner.py
```

See `SCRAPING_RESULTS.md` for detailed results and `improved_extracted_data/` for the latest extraction with icons. 