import json
import os
import requests
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .auth import SmartFMAuth

class CategoryFetcher:
    def __init__(self, base_api_url: str, auth: SmartFMAuth, email: str, password: str):
        self.base_api_url = base_api_url
        self.auth = auth
        self.email = email
        self.password = password
        self.access_token = None
        self.last_request_time = 0
        self.min_request_delay = 1.0  # Rate limiting: 1 second between requests

        # Statistics
        self.stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0
        }

    def _ensure_token(self):
        """Ensures that a valid access token is available."""
        self.access_token = self.auth.get_valid_token(self.email, self.password)
        if not self.access_token:
            raise Exception("Failed to obtain a valid access token. Please check your credentials.")

    def _get_headers(self) -> Dict:
        """Returns headers with the access token."""
        if not self.access_token:
            self._ensure_token()
            
        return {
            "Authorization": f"Bearer {self.access_token.strip()}",  # Ensure token is properly formatted
            "Content-Type": "application/json"
        }

    def _respect_rate_limit(self):
        """Respect rate limiting between requests"""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_request_delay:
            sleep_time = self.min_request_delay - time_since_last
            print(f"    ⏳ Rate limiting: waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_api_request(self, method: str, url: str, json_data: Optional[Dict] = None) -> Optional[Dict]:
        """Makes an authenticated API request with rate limiting and enhanced error handling."""
        self._respect_rate_limit()
        headers = self._get_headers()

        self.stats['requests_made'] += 1

        try:
            print(f"📡 Sending {method} request to {url}")
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=60)
            else:
                print(f"❌ Unsupported HTTP method: {method}")
                self.stats['failed_requests'] += 1
                return None

            # If we get a 403, try refreshing the token and retry once
            if response.status_code == 403:
                print("🔄 Token expired, refreshing...")
                self._ensure_token()  # This updates self.access_token
                # Get fresh headers with the new token
                headers = self._get_headers()

                # Retry the request with new token
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=60)

            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            self.stats['successful_requests'] += 1
            print(f"✅ Request successful: {response.status_code}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            self.stats['failed_requests'] += 1
            print(f"❌ HTTP Error for {url}: {e.response.status_code} - {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            self.stats['failed_requests'] += 1
            print(f"❌ Request failed for {url}: {e}")
            return None

    def get_all_categories(self) -> List[Dict]:
        """Fetches all categories from the database."""
        response = self._make_api_request("GET", f"{self.base_api_url}/categories")
        if response and response.get('success'):
            data = response.get('data', [])
            # Handle case where data is explicitly null
            return data if data is not None else []
        return []

    def display_stats(self):
        """Display CategoryFetcher statistics"""
        print(f"\n📊 CATEGORY FETCHER STATISTICS")
        print("=" * 40)
        print(f"📡 Requests Made: {self.stats['requests_made']}")
        print(f"✅ Successful Requests: {self.stats['successful_requests']}")
        print(f"❌ Failed Requests: {self.stats['failed_requests']}")
        print(f"🔄 Token Refreshes: {self.stats['token_refreshes']}")
        if self.stats['requests_made'] > 0:
            success_rate = (self.stats['successful_requests'] / self.stats['requests_made']) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")

    def sync_categories_with_db(self, categories_dir: Path, make_api_request_func) -> None:
        """Syncs categories with the database and updates category_data.json files.
        
        Args:
            categories_dir: Path to the categories directory
            make_api_request_func: Function to make API requests (from CategoryUploader)
        """
        # Get all categories from DB
        db_categories = self.get_all_categories()
        db_category_map = {cat['name']: cat for cat in db_categories}

        # Iterate through scraped categories
        for category_dir in categories_dir.iterdir():
            if not category_dir.is_dir():
                continue

            category_data_file = category_dir / "category_data.json"
            if not category_data_file.exists():
                continue

            try:
                with open(category_data_file, 'r', encoding='utf-8') as f:
                    category_info = json.load(f)

                category_name = category_info.get('name')
                if not category_name:
                    print(f"Warning: Category name missing in {category_data_file}")
                    continue

                # Check if category exists in DB
                if category_name in db_category_map:
                    # Update category_data.json with DB ID
                    category_info['id'] = db_category_map[category_name]['id']
                else:
                    # Create new category in DB
                    print(f"Creating new category: {category_name}")
                    category_payload = {
                        "name": category_name,
                        "description": "",
                        "sortOrder": 0,
                        "status": 1
                    }
                    
                    response = make_api_request_func("POST", f"{self.base_api_url}/categories", json_data=category_payload)
                    if response and response.get('success'):
                        category_info['id'] = response['data']['id']
                    else:
                        print(f"Failed to create category: {category_name}")
                        continue

                # Save updated category info
                with open(category_data_file, 'w', encoding='utf-8') as f:
                    json.dump(category_info, f, indent=2)

            except Exception as e:
                print(f"Error processing category in {category_dir}: {e}")

class CategoryUploader:
    def __init__(self, base_api_url: str, email: str, password: str, data_dir: str = "../scrapped_data",
                 max_workers: int = 3, request_delay: float = 2.0, max_file_size_mb: int = 5):
        self.base_api_url = base_api_url
        self.auth = SmartFMAuth(base_api_url)
        self.email = email
        self.password = password
        self.data_dir = Path(data_dir)
        self.categories_dir = self.data_dir / "categories"
        self.access_token = None
        self.category_fetcher = CategoryFetcher(base_api_url, self.auth, email, password)

        # Enhanced configuration
        self.max_workers = max_workers  # Concurrent workers
        self.request_delay = request_delay  # Rate limiting
        self.max_file_size_mb = max_file_size_mb  # File size limit

        # Statistics
        self.stats = {
            'categories_processed': 0,
            'categories_created': 0,
            'subcategories_uploaded': 0,
            'subcategories_failed': 0,
            'file_validation_failures': 0,
            'total_upload_time': 0,
            'start_time': None
        }

        self._ensure_token()

    def _ensure_token(self):
        """Ensures that a valid access token is available."""
        self.access_token = self.auth.get_valid_token(self.email, self.password)
        if not self.access_token:
            raise Exception("Failed to obtain a valid access token. Please check your credentials.")

    def _get_headers(self) -> Dict:
        """Returns headers with the access token."""
        if not self.access_token:
            self._ensure_token()
            
        return {
            "Authorization": f"Bearer {self.access_token.strip()}",  # Ensure token is properly formatted
            "Content-Type": "application/json"
        }

    def _validate_image_file(self, file_path: str) -> bool:
        """Validate image file for security and size limits"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            # Check file size
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                print(f"      ⚠️  File too large: {file_size_mb:.1f}MB (max: {self.max_file_size}MB)")
                self.stats['file_validation_failures'] += 1
                return False

            # Check file extension
            allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            if path.suffix.lower() not in allowed_extensions:
                print(f"      ⚠️  Invalid file type: {path.suffix}")
                self.stats['file_validation_failures'] += 1
                return False

            # Additional security: Check if it's actually an image
            try:
                from PIL import Image
                with Image.open(path) as img:
                    img.verify()  # Verify it's a valid image
            except ImportError:
                # PIL not available, skip image verification
                pass
            except Exception:
                print(f"      ⚠️  Invalid image file: {path.name}")
                self.stats['file_validation_failures'] += 1
                return False

            return True

        except Exception as e:
            print(f"      ❌ Error validating file {file_path}: {e}")
            self.stats['file_validation_failures'] += 1
            return False

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file for integrity checking"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception:
            return ""

    def _make_api_request(self, method: str, url: str, json_data: Optional[Dict] = None, files: Optional[Dict] = None) -> Optional[Dict]:
        """Makes an authenticated API request with enhanced error handling and rate limiting."""
        # Rate limiting
        if not files:  # Only rate limit non-file requests
            time.sleep(self.request_delay)

        headers = self._get_headers()
        # Remove Content-Type header if files are present, as requests will set it automatically for multipart/form-data
        if files:
            headers.pop("Content-Type", None)

        print(f"\n=== API Request Details ===")
        print(f"Method: {method}")
        print(f"URL: {url}")
        if json_data:
            if files:
                print(f"Form Data: {json.dumps(json_data, indent=2)}")
            else:
                print(f"JSON Data: {json.dumps(json_data, indent=2)}")
        if files:
            file_info = []
            for key, (filename, file_handle, content_type) in files.items():
                file_size = file_handle.seek(0, 2)  # Get file size
                file_handle.seek(0)  # Reset file pointer
                file_hash = self._calculate_file_hash(file_handle.name) if hasattr(file_handle, 'name') else "unknown"
                file_info.append(f"{filename} ({file_size} bytes, sha256: {file_hash[:16]}...)")
            print(f"Files to upload: {file_info}")
        print("========================\n")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"📡 Attempt {attempt + 1}/{max_retries}: {method} {url}")

                if method == "POST":
                    if files:
                        # Use form data when files are present
                        response = requests.post(url, data=json_data, headers=headers, files=files, timeout=120)
                    else:
                        # Use JSON when no files are present
                        response = requests.post(url, json=json_data, headers=headers, timeout=60)
                elif method == "PUT":
                    if files:
                        # Use form data when files are present
                        response = requests.put(url, data=json_data, headers=headers, files=files, timeout=120)
                    else:
                        # Use JSON when no files are present
                        response = requests.put(url, json=json_data, headers=headers, timeout=60)
                else:
                    print(f"❌ Unsupported HTTP method: {method}")
                    return None

                # If we get a 403, try refreshing the token and retry once
                if response.status_code == 403:
                    print("🔄 Token expired, refreshing...")
                    self._ensure_token()  # This updates self.access_token
                    # Get fresh headers with the new token
                    headers = self._get_headers()
                    if files:
                        headers.pop("Content-Type", None)

                    # Retry the request with new token
                    if method == "POST":
                        if files:
                            response = requests.post(url, data=json_data, headers=headers, files=files, timeout=120)
                        else:
                            response = requests.post(url, json=json_data, headers=headers, timeout=60)
                    elif method == "PUT":
                        if files:
                            response = requests.put(url, data=json_data, headers=headers, files=files, timeout=120)
                        else:
                            response = requests.put(url, json=json_data, headers=headers, timeout=60)

                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                print(f"✅ Request successful: {response.status_code}")
                return response.json()

            except requests.exceptions.HTTPError as e:
                print(f"❌ HTTP Error on attempt {attempt + 1}: {e.response.status_code} - {e.response.text}")
                if attempt == max_retries - 1:
                    return None
                # Exponential backoff
                time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                print(f"❌ Request failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return None
                # Exponential backoff
                time.sleep(2 ** attempt)

        return None

    def load_scraped_data(self) -> List[Dict]:
        """Loads all scraped category data from the local file system."""
        all_categories_data = []
        for category_dir in self.categories_dir.iterdir():
            if category_dir.is_dir():
                category_data_file = category_dir / "category_data.json"
                if category_data_file.exists():
                    try:
                        with open(category_data_file, 'r', encoding='utf-8') as f:
                            category_info = json.load(f)
                            
                        # Load subcategory data
                        subcategories_data = []
                        subcategories_path = category_dir / "subcategories"
                        if subcategories_path.exists():
                            for subcat_dir in subcategories_path.iterdir():
                                if subcat_dir.is_dir():
                                    subcategory_data_file = subcat_dir / "subcategory_data.json"
                                    if subcategory_data_file.exists():
                                        with open(subcategory_data_file, 'r', encoding='utf-8') as f_sub:
                                            subcategories_data.append(json.load(f_sub))
                        
                        category_info['subcategories_data'] = subcategories_data
                        all_categories_data.append(category_info)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from {category_data_file}: {e}")
                    except Exception as e:
                        print(f"Error loading category data from {category_data_file}: {e}")
        return all_categories_data

    def upload_subcategory(self, category_id: str, category_name: str, subcategory_data: Dict) -> bool:
        """Upload a single subcategory with enhanced validation and error handling"""
        try:
            print(f"  📤 Processing subcategory: {subcategory_data.get('name')}")

            # Validate both required icon files
            local_icon_paths = subcategory_data.get('local_icon_paths', {})
            icon_path = local_icon_paths.get('local_icon_path')
            dark_icon_path = local_icon_paths.get('local_dark_icon_path')

            if not icon_path or not self._validate_image_file(icon_path):
                print(f"    ❌ Missing or invalid icon file")
                return False

            if not dark_icon_path or not self._validate_image_file(dark_icon_path):
                print(f"    ❌ Missing or invalid dark icon file")
                return False

            sub_category_payload = {
                "parentCategoryId": category_id,
                "name": subcategory_data.get('name'),
                "description": "",  # Description might not be in scraped data, set to empty
                "sortOrder": subcategory_data.get('sort', 0),
                "status": subcategory_data.get('status', 1)
            }

            files = {
                'icon': (Path(icon_path).name, open(icon_path, 'rb'), 'image/png'),
                'darkIcon': (Path(dark_icon_path).name, open(dark_icon_path, 'rb'), 'image/png')
            }

            sub_response = self._make_api_request("POST", f"{self.base_api_url}/subcategories", json_data=sub_category_payload, files=files)

            # Close file handles
            for file_handle in files.values():
                file_handle[1].close()

            if sub_response and sub_response.get('success'):
                uploaded_subcategory = sub_response['data']
                print(f"    ✅ Successfully uploaded: {uploaded_subcategory.get('name')} (ID: {uploaded_subcategory.get('id')})")
                self.stats['subcategories_uploaded'] += 1
                return True
            else:
                print(f"    ❌ Failed to upload: {subcategory_data.get('name')}")
                self.stats['subcategories_failed'] += 1
                return False

        except Exception as e:
            print(f"    ❌ Error processing subcategory: {e}")
            self.stats['subcategories_failed'] += 1
            return False

    def upload_categories_and_subcategories(self):
        """Uploads all categories and their subcategories to the API with enhanced processing."""
        self.stats['start_time'] = datetime.now()

        print("🚀 ENHANCED CATEGORY UPLOADER")
        print("=" * 60)
        print(f"🔐 Authentication: {self.email}")
        print(f"📁 Data Directory: {self.data_dir}")
        print(f"⚡ Max Workers: {self.max_workers}")
        print(f"⏱️  Request Delay: {self.request_delay}s")
        print(f"📏 Max File Size: {self.max_file_size_mb}MB")
        print()

        # First sync categories with DB
        print("🔄 Syncing categories with database...")
        self.category_fetcher.sync_categories_with_db(self.categories_dir, self._make_api_request)

        # Now load the updated data
        scraped_categories = self.load_scraped_data()

        if not scraped_categories:
            print("❌ No scraped category data found to upload.")
            return

        print(f"📊 Found {len(scraped_categories)} categories to process")
        print()

        # Process categories
        for category_data in scraped_categories:
            category_id = category_data.get('id')
            if not category_id:
                print(f"⚠️  Skipping category {category_data.get('name')} - no ID found")
                continue

            self.stats['categories_processed'] += 1
            category_name = category_data.get('name', 'Unknown')
            print(f"📂 Processing category: {category_name}")

            # Get subcategories for this category
            subcategories = category_data.get('subcategories_data', [])
            if not subcategories:
                print(f"  ℹ️  No subcategories found for {category_name}")
                continue

            print(f"  📦 Found {len(subcategories)} subcategories")

            # Use concurrent processing for subcategories
            if len(subcategories) > 1 and self.max_workers > 1:
                print(f"  ⚡ Processing subcategories concurrently ({self.max_workers} workers)")
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all subcategory upload tasks
                    future_to_subcategory = {
                        executor.submit(self.upload_subcategory, category_id, category_name, subcat): subcat
                        for subcat in subcategories
                    }

                    # Process completed tasks
                    for future in as_completed(future_to_subcategory):
                        subcat = future_to_subcategory[future]
                        try:
                            success = future.result()
                            # Statistics are updated in upload_subcategory method
                        except Exception as e:
                            print(f"    ❌ Concurrent processing error for {subcat.get('name')}: {e}")
                            self.stats['subcategories_failed'] += 1
            else:
                # Sequential processing for single subcategory or if concurrency disabled
                for subcategory_data in subcategories:
                    self.upload_subcategory(category_id, category_name, subcategory_data)

            print()  # Add spacing between categories

        # Calculate total time
        if self.stats['start_time']:
            self.stats['total_upload_time'] = (datetime.now() - self.stats['start_time']).total_seconds()

        # Display final statistics
        self.display_stats()
        self.category_fetcher.display_stats()

    def display_stats(self):
        """Display comprehensive upload statistics"""
        print(f"\n📊 UPLOAD STATISTICS")
        print("=" * 50)
        print(f"📂 Categories Processed: {self.stats['categories_processed']}")
        print(f"✅ Subcategories Uploaded: {self.stats['subcategories_uploaded']}")
        print(f"❌ Subcategories Failed: {self.stats['subcategories_failed']}")
        print(f"⚠️  File Validation Failures: {self.stats['file_validation_failures']}")

        if self.stats['total_upload_time'] > 0:
            print(f"⏱️  Total Time: {self.stats['total_upload_time']:.1f}s")
            if self.stats['subcategories_uploaded'] + self.stats['subcategories_failed'] > 0:
                total_subcats = self.stats['subcategories_uploaded'] + self.stats['subcategories_failed']
                rate = total_subcats / self.stats['total_upload_time']
                print(f"🚀 Upload Rate: {rate:.2f} subcategories/second")

        if self.stats['subcategories_uploaded'] + self.stats['subcategories_failed'] > 0:
            success_rate = (self.stats['subcategories_uploaded'] / (self.stats['subcategories_uploaded'] + self.stats['subcategories_failed'])) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")

    
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced Category Uploader for SmartFM')
    parser.add_argument('--api-url', default='http://localhost:6969', help='API URL (default: http://localhost:6969)')
    parser.add_argument('--email', default='admin@gmail.com', help='Login email')
    parser.add_argument('--password', default='test@123', help='Login password')
    parser.add_argument('--data-dir', default='../scrapped_data', help='Data directory path')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum concurrent workers (default: 3)')
    parser.add_argument('--request-delay', type=float, default=2.0, help='Delay between requests in seconds (default: 2.0)')
    parser.add_argument('--max-file-size', type=int, default=5, help='Maximum file size in MB (default: 5)')

    args = parser.parse_args()

    try:
        print("🚀 Starting Enhanced Category Uploader")
        print(f"Command line args: {vars(args)}")

        uploader = CategoryUploader(
            base_api_url=args.api_url,
            email=args.email,
            password=args.password,
            data_dir=args.data_dir,
            max_workers=args.max_workers,
            request_delay=args.request_delay,
            max_file_size_mb=args.max_file_size
        )
        uploader.upload_categories_and_subcategories()

    except KeyboardInterrupt:
        print("\n⚠️  Upload interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

