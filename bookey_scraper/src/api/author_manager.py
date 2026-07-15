import json
import os
import requests
from pathlib import Path
from typing import Dict, Optional, List
from .auth import SmartFMAuth

class AuthorManager:
    def __init__(self, base_api_url: str, auth: SmartFMAuth, email: str, password: str):
        self.base_api_url = base_api_url
        self.auth = auth
        self.email = email
        self.password = password

    def _get_headers(self) -> Dict:
        """Returns headers with the access token."""
        access_token = self.auth.get_valid_token(self.email, self.password)
        if not access_token:
            raise Exception("Failed to obtain a valid access token. Please check your credentials.")
            
        return {
            "Authorization": f"Bearer {access_token.strip()}",
            "Content-Type": "application/json"
        }

    def _make_api_request(self, method: str, url: str, json_data: Optional[Dict] = None) -> Optional[Dict]:
        """Makes an authenticated API request."""
        headers = self._get_headers()

        try:
            print(f"\n=== API Request Details ===")
            print(f"Method: {method}")
            print(f"URL: {url}")
            if json_data:
                print(f"JSON Data: {json.dumps(json_data, indent=2)}")
            print("========================\n")

            if method == "POST":
                response = requests.post(url, json=json_data, headers=headers, timeout=60)
            elif method == "GET":
                response = requests.get(url, headers=headers, timeout=60)
            else:
                print(f"Unsupported HTTP method: {method}")
                return None

            # If we get a 403, try refreshing the token and retry once
            if response.status_code == 403:
                print("Token expired, refreshing...")
                headers = self._get_headers()
                
                if method == "POST":
                    response = requests.post(url, json=json_data, headers=headers, timeout=60)
                elif method == "GET":
                    response = requests.get(url, headers=headers, timeout=60)

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error for {url}: {e.response.status_code} - {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {url}: {e}")
            return None

    def extract_authors_from_books(self, data_dir: str = "../scrapped_data") -> None:
        """
        Extracts author information from all book JSON files in the scraped data directory
        and saves it to an authors.json file. Authors with commas are saved to multi_author.json.
        """
        data_path = Path(data_dir)
        books_dir = data_path / "books"
        authors_file = data_path / "authors.json"
        multi_authors_file = data_path / "multi_author.json"
        
        if not books_dir.exists():
            print(f"Books directory not found: {books_dir}")
            return
        
        authors_data = {}
        multi_authors_data = {}
        processed_count = 0
        error_count = 0
        
        print(f"Scanning books directory: {books_dir}")
        print("Extracting author information from book JSON files...")
        
        for book_dir in books_dir.iterdir():
            if not book_dir.is_dir():
                continue
                
            # Get the book name from the directory name (remove timestamp prefix)
            book_name = "_".join(book_dir.name.split("_")[1:])
            book_data_file = book_dir / f"{book_name}_book_data.json"
            
            if not book_data_file.exists():
                print(f"Warning: No book data file found in {book_dir}")
                error_count += 1
                continue
            
            try:
                with open(book_data_file, 'r', encoding='utf-8') as f:
                    book_data = json.load(f)
                
                author_name = book_data.get("author")
                author_info = book_data.get("authorInfo", "")
                
                if not author_name:
                    print(f"Warning: No author found in {book_data_file}")
                    error_count += 1
                    continue
                
                book_title = book_data.get("title", book_name)
                
                # Check if author name contains comma (multiple authors)
                if ',' in author_name:
                    # Handle multiple authors
                    if author_name not in multi_authors_data:
                        multi_authors_data[author_name] = {
                            "name": author_name,
                            "info": author_info,
                            "books": []
                        }
                    
                    if book_title not in multi_authors_data[author_name]["books"]:
                        multi_authors_data[author_name]["books"].append(book_title)
                    
                    print(f"Processed (multi-author): {book_title} by {author_name}")
                else:
                    # Handle single author
                    if author_name not in authors_data:
                        authors_data[author_name] = {
                            "name": author_name,
                            "info": author_info,
                            "books": []
                        }
                    
                    if book_title not in authors_data[author_name]["books"]:
                        authors_data[author_name]["books"].append(book_title)
                    
                    print(f"Processed: {book_title} by {author_name}")
                
                processed_count += 1
                
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {book_data_file}: {e}")
                error_count += 1
            except Exception as e:
                print(f"Error processing {book_data_file}: {e}")
                error_count += 1
        
        # Convert to list format for easier processing
        authors_list = list(authors_data.values())
        multi_authors_list = list(multi_authors_data.values())
        
        # Save single authors to authors.json file
        try:
            with open(authors_file, 'w', encoding='utf-8') as f:
                json.dump(authors_list, f, indent=2, ensure_ascii=False)
            print(f"Single authors data saved to: {authors_file}")
        except Exception as e:
            print(f"Error saving authors data to {authors_file}: {e}")
        
        # Save multiple authors to multi_author.json file
        try:
            with open(multi_authors_file, 'w', encoding='utf-8') as f:
                json.dump(multi_authors_list, f, indent=2, ensure_ascii=False)
            print(f"Multiple authors data saved to: {multi_authors_file}")
        except Exception as e:
            print(f"Error saving multi-authors data to {multi_authors_file}: {e}")
        
        print(f"\n=== Extraction Summary ===")
        print(f"Total books processed: {processed_count}")
        print(f"Single authors found: {len(authors_list)}")
        print(f"Multiple authors found: {len(multi_authors_list)}")
        print(f"Errors encountered: {error_count}")
        print("========================\n")
        
        # Print some statistics
        if authors_list:
            print("Sample single authors extracted:")
            for i, author in enumerate(authors_list[:5]):  # Show first 5 authors
                print(f"  {i+1}. {author['name']} ({len(author['books'])} books)")
            if len(authors_list) > 5:
                print(f"  ... and {len(authors_list) - 5} more single authors")
        
        if multi_authors_list:
            print("\nSample multiple authors extracted:")
            for i, author in enumerate(multi_authors_list[:5]):  # Show first 5 multi-authors
                print(f"  {i+1}. {author['name']} ({len(author['books'])} books)")
            if len(multi_authors_list) > 5:
                print(f"  ... and {len(multi_authors_list) - 5} more multiple authors")

    def get_or_create_author(self, author_name: str, author_info: str) -> Optional[str]:
        """
        Gets an existing author or creates a new one.
        Returns the author ID if successful, None otherwise.
        """
        # Convert author name to lowercase and replace spaces and commas with hyphens for slug lookup
        formatted_author_name = author_name.lower().replace(" ", "-").replace(",", "-")
        
        # First try to find the author by name using slug
        response = self._make_api_request("GET", f"{self.base_api_url}/authors/slug={formatted_author_name}")
        if response and response.get('success'):
            author = response.get('data')
            if author:
                print(f"Found existing author: {author_name}")
                return author.get('id')

        # If author not found, create new author with original name
        print(f"Creating new author: {author_name}")
        author_payload = {
            "name": author_name,  # Use original name with proper capitalization
            "description": author_info,
            "status": 1  # Active status
        }

        response = self._make_api_request("POST", f"{self.base_api_url}/authors", json_data=author_payload)
        if response and response.get('success'):
            author = response.get('data')
            print(f"Successfully created author: {author_name}")
            return author.get('id')
        
        print(f"Failed to create author: {author_name}")
        return None

    def create_authors_from_json(self, data_dir: str = "../scrapped_data") -> None:
        """
        Creates authors in the API from the authors.json file.
        Skips authors that already exist in the API.
        Updates the authors.json file with API IDs for successfully processed authors.
        """
        data_path = Path(data_dir)
        authors_file = data_path / "authors.json"
        
        if not authors_file.exists():
            print(f"Authors file not found: {authors_file}")
            print("Please run extract_authors_from_books first to generate the authors.json file.")
            return
        
        try:
            with open(authors_file, 'r', encoding='utf-8') as f:
                authors_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {authors_file}: {e}")
            return
        except Exception as e:
            print(f"Error loading authors data from {authors_file}: {e}")
            return
        
        if not authors_data:
            print("No authors found in the authors.json file.")
            return
        
        print(f"Found {len(authors_data)} authors in {authors_file}")
        print("Starting to create authors in the API...")
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        updated_authors = []  # Track updated authors with API IDs
        
        for i, author in enumerate(authors_data, 1):
            author_name = author.get("name")
            author_info = author.get("info", "")
            
            if not author_name:
                print(f"Warning: Author at index {i} has no name, skipping...")
                error_count += 1
                continue
            
            print(f"\n[{i}/{len(authors_data)}] Processing author: {author_name}")
            
            try:
                # Try to create the author (this method handles checking if author exists)
                author_id = self.get_or_create_author(author_name, author_info)
                
                if author_id:
                    # Update the author data with the API ID
                    author["api_id"] = author_id
                    updated_authors.append(author)
                    created_count += 1
                    print(f"✓ Successfully processed author: {author_name} (ID: {author_id})")
                else:
                    # Author might already exist or there was an error
                    skipped_count += 1
                    print(f"- Skipped author: {author_name} (may already exist)")
                    # Keep the original author data without API ID
                    updated_authors.append(author)
                
                # Add a small delay to avoid overwhelming the API
                import time
                time.sleep(0.5)
                
            except Exception as e:
                print(f"✗ Error processing author {author_name}: {str(e)}")
                error_count += 1
                # Keep the original author data without API ID
                updated_authors.append(author)
                # Continue with next author even if one fails
                continue
        
        # Save the updated authors data back to the file
        try:
            with open(authors_file, 'w', encoding='utf-8') as f:
                json.dump(updated_authors, f, indent=2, ensure_ascii=False)
            print(f"\nUpdated authors data saved to: {authors_file}")
            print(f"Authors with API IDs: {len([a for a in updated_authors if 'api_id' in a])}")
        except Exception as e:
            print(f"Error saving updated authors data to {authors_file}: {e}")
        
        print(f"\n=== Author Creation Summary ===")
        print(f"Total authors processed: {len(authors_data)}")
        print(f"Successfully created: {created_count}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Errors encountered: {error_count}")
        print("==============================\n")
        
        if error_count > 0:
            print("Note: Some authors failed to process. You may want to check the logs above.")
        elif created_count > 0:
            print("All authors processed successfully!")
        else:
            print("No new authors were created. They may already exist in the API.") 