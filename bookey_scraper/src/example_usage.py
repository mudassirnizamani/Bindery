#!/usr/bin/env python3
"""
Example Usage of Bookey Scraper Data with Icons
Demonstrates how to integrate the extracted data and downloaded icons into applications
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

class BookeyCategoryManager:
    def __init__(self, data_directory: str = "data"):
        self.data_directory = Path(data_directory)
        self.icons_directory = self.data_directory / "icons"
        self.categories_data = {}
        self.load_all_categories()

    def load_all_categories(self):
        """Load all category data from JSON files"""
        json_files = self.data_directory.glob("*_extracted.json")
        
        for json_file in json_files:
            if json_file.name.startswith("IMPROVED_"):
                continue  # Skip summary file
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    category_name = data.get('main_category', 'Unknown')
                    self.categories_data[category_name] = data
                    print(f"✅ Loaded: {category_name}")
            except Exception as e:
                print(f"❌ Failed to load {json_file}: {e}")

    def get_categories_overview(self) -> Dict:
        """Get an overview of all categories with statistics"""
        overview = {
            'total_categories': len(self.categories_data),
            'total_subcategories': 0,
            'total_books': 0,
            'categories': {}
        }
        
        for category_name, data in self.categories_data.items():
            category_info = {
                'subcategories_count': data.get('total_subcategories', 0),
                'books_count': data.get('total_books', 0),
                'subcategories': list(data.get('subcategories', {}).values()),
                'icons_available': self.get_category_icons_summary(category_name)
            }
            
            overview['categories'][category_name] = category_info
            overview['total_subcategories'] += category_info['subcategories_count']
            overview['total_books'] += category_info['books_count']
        
        return overview

    def get_category_icons_summary(self, category_name: str) -> Dict:
        """Get summary of available icons for a category"""
        category_data = self.categories_data.get(category_name, {})
        subcategories_with_icons = category_data.get('subcategories_with_icons', {})
        
        icons_summary = {
            'total_subcategories': len(subcategories_with_icons),
            'subcategories_with_icons': 0,
            'total_icons_available': 0,
            'icon_types_available': set()
        }
        
        for subcat_data in subcategories_with_icons.values():
            local_icons = subcat_data.get('local_icon_paths', {})
            if local_icons:
                icons_summary['subcategories_with_icons'] += 1
                icons_summary['total_icons_available'] += len(local_icons)
                icons_summary['icon_types_available'].update(local_icons.keys())
        
        icons_summary['icon_types_available'] = list(icons_summary['icon_types_available'])
        return icons_summary

    def get_subcategory_with_icons(self, category_name: str, subcategory_name: str) -> Optional[Dict]:
        """Get detailed subcategory information including local icon paths"""
        category_data = self.categories_data.get(category_name, {})
        subcategories_with_icons = category_data.get('subcategories_with_icons', {})
        
        for subcat_data in subcategories_with_icons.values():
            if subcat_data.get('name') == subcategory_name:
                return subcat_data
        
        return None

    def get_books_by_subcategory(self, category_name: str, subcategory_name: str) -> List[Dict]:
        """Get all books for a specific subcategory"""
        category_data = self.categories_data.get(category_name, {})
        subcategory_books = category_data.get('subcategory_books', {})
        
        return subcategory_books.get(subcategory_name, [])

    def generate_html_preview(self, output_file: str = "bookey_preview.html"):
        """Generate an HTML preview showing categories and their icons"""
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bookey Categories with Icons</title>
    <style>
        body {{font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5;}}
        .category {{background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}}
        .category h2 {{color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px;}}
        .subcategory {{margin: 10px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;}}
        .subcategory h3 {{margin: 0 0 10px 0; color: #555;}}
        .icons {{display: flex; gap: 10px; flex-wrap: wrap;}}
        .icon {{text-align: center;}}
        .icon img {{width: 40px; height: 40px; border-radius: 4px;}}
        .icon span {{display: block; font-size: 10px; margin-top: 5px;}}
        .stats {{background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0;}}
        .book-count {{color: #666; font-size: 14px;}}
    </style>
</head>
<body>
    <h1>🎨 Bookey Categories with Downloaded Icons</h1>
    <div class="stats">
        <h3>📊 Overview</h3>
        <p><strong>Total Categories:</strong> {total_categories}</p>
        <p><strong>Total Subcategories:</strong> {total_subcategories}</p>
        <p><strong>Total Books:</strong> {total_books}</p>
    </div>
"""
        
        overview = self.get_categories_overview()
        html_content = html_content.format(**overview)
        
        for category_name, category_info in overview['categories'].items():
            category_data = self.categories_data[category_name]
            subcategories_with_icons = category_data.get('subcategories_with_icons', {})
            
            html_content += f"""
    <div class="category">
        <h2>📂 {category_name}</h2>
        <div class="stats">
            <strong>Subcategories:</strong> {category_info['subcategories_count']} | 
            <strong>Books:</strong> {category_info['books_count']} | 
            <strong>Icons Downloaded:</strong> {category_info['icons_available']['total_icons_available']}
        </div>
"""
            
            for subcat_data in subcategories_with_icons.values():
                subcat_name = subcat_data.get('name', 'Unknown')
                local_icons = subcat_data.get('local_icon_paths', {})
                
                html_content += f"""
        <div class="subcategory">
            <h3>🏷️ {subcat_name}</h3>
            <div class="icons">
"""
                
                for icon_type, icon_path in local_icons.items():
                    if os.path.exists(icon_path):
                        icon_name = icon_type.replace('local_', '').replace('_path', '')
                        html_content += f"""
                <div class="icon">
                    <img src="{icon_path}" alt="{icon_name}" title="{icon_name}">
                    <span>{icon_name}</span>
                </div>
"""
                
                # Get book count for this subcategory
                books = self.get_books_by_subcategory(category_name, subcat_name)
                html_content += f"""
            </div>
            <div class="book-count">📚 {len(books)} books</div>
        </div>
"""
            
            html_content += "    </div>\n"
        
        html_content += """
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"📄 HTML preview generated: {output_file}")

    def export_for_integration(self, output_file: str = "bookey_integration_data.json"):
        """Export simplified data structure for easy integration"""
        integration_data = {
            'categories': {},
            'metadata': {
                'extraction_timestamp': None,
                'total_categories': len(self.categories_data),
                'total_subcategories': 0,
                'total_books': 0
            }
        }
        
        for category_name, category_data in self.categories_data.items():
            subcategories_with_icons = category_data.get('subcategories_with_icons', {})
            
            category_integration = {
                'id': category_data.get('main_category_id'),
                'name': category_name,
                'subcategories': {}
            }
            
            for subcat_id, subcat_data in subcategories_with_icons.items():
                subcat_name = subcat_data.get('name')
                local_icons = subcat_data.get('local_icon_paths', {})
                books = self.get_books_by_subcategory(category_name, subcat_name)
                
                category_integration['subcategories'][subcat_id] = {
                    'name': subcat_name,
                    'icons': {
                        'original_urls': {
                            'icon': subcat_data.get('iconPath', ''),
                            'dark_icon': subcat_data.get('darkIconPath', ''),
                            'mini_icon': subcat_data.get('miniIconPath', ''),
                            'watch_icon': subcat_data.get('watchIconPath', ''),
                            'warmth_icon': subcat_data.get('warmthIconPath', '')
                        },
                        'local_paths': local_icons
                    },
                    'books_count': len(books),
                    'sample_books': books[:3]  # First 3 books as sample
                }
                
                integration_data['metadata']['total_books'] += len(books)
            
            integration_data['categories'][category_name] = category_integration
            integration_data['metadata']['total_subcategories'] += len(subcategories_with_icons)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(integration_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Integration data exported: {output_file}")

def main():
    """Demonstration of the Bookey data and icon usage"""
    print("🎨 BOOKEY CATEGORY MANAGER DEMO")
    print("=" * 50)
    
    # Initialize the manager
    manager = BookeyCategoryManager()
    
    # Get overview
    overview = manager.get_categories_overview()
    print(f"\n📊 DATA OVERVIEW")
    print(f"Categories: {overview['total_categories']}")
    print(f"Subcategories: {overview['total_subcategories']}")
    print(f"Books: {overview['total_books']}")
    
    # Show category details
    print(f"\n📂 CATEGORY DETAILS")
    for category_name, info in overview['categories'].items():
        print(f"\n{category_name}:")
        print(f"  📁 Subcategories: {info['subcategories_count']}")
        print(f"  📚 Books: {info['books_count']}")
        print(f"  🎨 Icons: {info['icons_available']['total_icons_available']}")
        print(f"  🏷️  Subcategories: {', '.join(info['subcategories'][:3])}{'...' if len(info['subcategories']) > 3 else ''}")
    
    # Example: Get specific subcategory with icons
    print(f"\n🎯 EXAMPLE: Getting subcategory details")
    economics_data = manager.get_subcategory_with_icons("Finance & Investments", "Economics")
    if economics_data:
        print(f"Economics subcategory found!")
        print(f"  Original icon URLs: {len([url for url in [economics_data.get('iconPath', ''), economics_data.get('darkIconPath', ''), economics_data.get('miniIconPath', '')] if url])}")
        print(f"  Local icon paths: {len(economics_data.get('local_icon_paths', {}))}")
    
    # Generate outputs
    print(f"\n📄 GENERATING OUTPUTS")
    manager.generate_html_preview()
    manager.export_for_integration()
    
    print(f"\n✅ Demo complete! Check the generated files:")
    print(f"  - bookey_preview.html (visual preview)")
    print(f"  - bookey_integration_data.json (integration data)")

if __name__ == "__main__":
    main()