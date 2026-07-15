#!/usr/bin/env python3
"""
Icon Downloader for Bookey Categories
Downloads icons for subcategories from existing extracted JSON files
"""

import sys
from categories.icon_downloader import BookeyIconDownloader

def main():
    """Main function"""
    downloader = BookeyIconDownloader()
    downloader.process_all_extracted_files()

if __name__ == "__main__":
    main() 