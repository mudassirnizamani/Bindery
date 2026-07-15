import json
import os
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional

from .auth import SmartFMAuth
from .author_manager import AuthorManager

class BookUploader:
    def __init__(self, base_api_url: str, email: str, password: str, data_dir: str = "../scrapped_data"):
        self.base_api_url = base_api_url
        self.auth = SmartFMAuth(base_api_url)
        self.email = email
        self.password = password
        self.data_dir = Path(data_dir)
        self.books_dir = self.data_dir / "books"
        self.author_manager = AuthorManager(base_api_url, self.auth, self.email, self.password)
        self.authors_data = self._load_authors_data()
        
        self._ensure_token()

    def _load_authors_data(self) -> Dict[str, str]:
        """Load authors data from authors.json and create a mapping of name to api_id."""
        authors_file = self.data_dir / "authors.json"
        if not authors_file.exists():
            print(f"Authors file not found: {authors_file}")
            return {}

        try:
            with open(authors_file, 'r', encoding='utf-8') as f:
                authors = json.load(f)
                # Create a mapping of author name to api_id
                return {author['name']: author['api_id'] for author in authors if 'name' in author and 'api_id' in author}
        except Exception as e:
            print(f"Error loading authors data: {e}")
            return {}

    def _get_author_id(self, author_name: str) -> Optional[str]:
        """Get author ID from the loaded authors data."""
        return self.authors_data.get(author_name)

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
            "Authorization": f"Bearer {self.access_token.strip()}",
            "Content-Type": "application/json"
        }

    def _make_api_request(self, method: str, url: str, json_data: Optional[Dict] = None, files: Optional[Dict] = None) -> Optional[Dict]:
        """Makes an authenticated API request."""
        headers = self._get_headers()
        if files:
            headers.pop("Content-Type", None)

        try:
            print(f"\n=== API Request Details ===")
            print(f"Method: {method}")
            print(f"URL: {url}")
            if json_data:
                print(f"Form Data: {json.dumps(json_data, indent=2)}")
            if files:
                print(f"Files to upload: {[f[0] for f in files.values()]}")
            print("========================\n")

            # Use longer timeout for book creation (2 minutes)
            timeout = 120 if "/audiobooks" in url else 60
            
            print(f"Making request with {timeout} second timeout...")
            if timeout > 60:
                print("Note: This request may take up to 2 minutes to complete...")

            if method == "POST":
                response = requests.post(url, data=json_data, headers=headers, files=files, timeout=timeout)
            elif method == "PUT":
                response = requests.put(url, data=json_data, headers=headers, files=files, timeout=timeout)
            elif method == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                print(f"Unsupported HTTP method: {method}")
                return None

            # If we get a 403, try refreshing the token and retry once
            if response.status_code == 403:
                print("Token expired, refreshing...")
                self._ensure_token()
                headers = self._get_headers()
                if files:
                    headers.pop("Content-Type", None)
                
                if method == "POST":
                    response = requests.post(url, data=json_data, headers=headers, files=files, timeout=timeout)
                elif method == "PUT":
                    response = requests.put(url, data=json_data, headers=headers, files=files, timeout=timeout)
                elif method == "GET":
                    response = requests.get(url, headers=headers, timeout=timeout)

            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            print(f"Request timed out after {timeout} seconds for {url}")
            print("The server is taking longer than expected to respond. This is normal for book creation.")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error for {url}: {e.response.status_code} - {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {url}: {e}")
            return None

    def load_book_data(self, book_dir: Path) -> Optional[Dict]:
        """Loads book data from a specific book directory."""
        # Get the book name from the directory name (remove timestamp prefix)
        book_name = "_".join(book_dir.name.split("_")[1:])
        book_data_file = book_dir / f"{book_name}_book_data.json"
        
        if not book_data_file.exists():
            print(f"No book data file found in {book_dir}")
            return None

        try:
            with open(book_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {book_data_file}: {e}")
            return None
        except Exception as e:
            print(f"Error loading book data from {book_data_file}: {e}")
            return None

    def save_book_response_data(self, book_dir: Path, book_data: Dict, api_response: Dict):
        """Saves the API response data back to the book_data.json file."""
        # Get the book name from the directory name (remove timestamp prefix)
        book_name = "_".join(book_dir.name.split("_")[1:])
        book_data_file = book_dir / f"{book_name}_book_data.json"
        
        # Extract the IDs from the API response
        response_data = api_response.get('data', {})
        audiobook_ids = {
            "audiobookId": response_data.get("audiobookId"),
            "summaryId": response_data.get("summaryId"),
            "fullId": response_data.get("fullId"),
            "urduSummaryId": response_data.get("urduSummaryId"),
            "urduFullId": response_data.get("urduFullId")
        }
        
        # Update the book data with the API response
        updated_book_data = {
            **book_data,  # Keep all original data
            "api_response": api_response,  # Store the full API response
            "audiobook_ids": audiobook_ids  # Store the IDs separately for easy access
        }
        
        try:
            with open(book_data_file, 'w', encoding='utf-8') as f:
                json.dump(updated_book_data, f, indent=2, ensure_ascii=False)
            print(f"Updated book data file with API response: {book_data_file}")
        except Exception as e:
            print(f"Error saving updated book data to {book_data_file}: {e}")

    def upload_books(self):
        """Uploads all books from the scraped data to the API."""
        if not self.books_dir.exists():
            print(f"Books directory not found: {self.books_dir}")
            return

        for book_dir in self.books_dir.iterdir():
            if not book_dir.is_dir():
                continue

            print(f"\nProcessing book directory: {book_dir.name}")
            book_data = self.load_book_data(book_dir)
            if not book_data:
                continue

            # Get the author name
            author_name = book_data.get("author")
            if not author_name:
                print(f"Skipping book {book_data.get('title')} - no author found")
                continue

            # Skip books with multiple authors (containing commas)
            if ',' in author_name:
                print(f"Skipping book {book_data.get('title')} - multiple authors detected: {author_name}")
                continue

            # Get author ID from authors.json
            author_id = self._get_author_id(author_name)
            if not author_id:
                print(f"Skipping book {book_data.get('title')} - author {author_name} not found in authors.json")
                continue

            # Prepare book payload
            book_payload = {
                "title": book_data.get("title", ""),
                "description": book_data.get("desc", ""),
                "language": "en",  # Default to English
                "genres": [],  # Map genres
                "authors": [author_id],  # Add the author ID from authors.json
                "hasSummaryVersion": True,  # Since these are summaries
                "hasUrduLanguage": True,  # Default to False
            }

            # Look for cover image
            files = {}
            cover_path = book_dir / "icons" / "cover.jpg"
            if cover_path.exists():
                files['cover'] = ('cover.jpg', open(cover_path, 'rb'), 'image/jpeg')

            try:
                # Upload book
                response = self._make_api_request(
                    "POST",
                    f"{self.base_api_url}/audiobooks",
                    json_data=book_payload,
                    files=files
                )

                if response and response.get('success'):
                    uploaded_book = response['data']
                    print(f"Successfully uploaded book: {uploaded_book.get('title')} with ID: {uploaded_book.get('id')}")
                    
                    # Save the API response data back to the book_data.json file
                    self.save_book_response_data(book_dir, book_data, response)
                    
                    # Wait for 2 seconds before processing the next book
                    print("Waiting 2 seconds before processing next book...")
                    time.sleep(2)
                else:
                    print(f"Failed to upload book: {book_data.get('title')}")
                    print("Waiting 5 seconds before continuing due to failure...")
                    time.sleep(5)
            except Exception as e:
                print(f"Error uploading book {book_data.get('title')}: {str(e)}")
                print("Waiting 5 seconds before continuing due to error...")
                time.sleep(5)
            finally:
                # Close any open files
                for file_tuple in files.values():
                    file_tuple[1].close()

if __name__ == "__main__":
    # Example Usage:
    API_URL = "http://localhost:6969"
    YOUR_EMAIL = "test@gmail.com"
    YOUR_PASSWORD = "minemine123@"

    try:
        uploader = BookUploader(API_URL, YOUR_EMAIL, YOUR_PASSWORD)
        uploader.upload_books()
    except Exception as e:
        print(f"An error occurred: {e}") 
