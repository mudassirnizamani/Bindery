#!/usr/bin/env python3
"""
Google Cloud Vision API PDF Extractor
High-accuracy OCR using Google's Vision API (95-99% accuracy)
Simple extraction - just OCR, no formatting
"""

import sys
import os
from pathlib import Path
from google.cloud import vision
from pdf2image import convert_from_path
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Dict, List

class GoogleVisionPDFExtractor:
    def __init__(self, credentials_path: str = None):
        """
        Initialize Google Vision API extractor

        Args:
            credentials_path: Path to Google Cloud service account JSON key
                             If None, uses GOOGLE_APPLICATION_CREDENTIALS env var
        """
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

        try:
            self.client = vision.ImageAnnotatorClient()
            print("✓ Google Cloud Vision API initialized")
        except Exception as e:
            print(f"✗ Failed to initialize Google Vision API: {e}")
            print("\nSetup instructions:")
            print("1. Create a Google Cloud project at https://console.cloud.google.com")
            print("2. Enable Cloud Vision API")
            print("3. Create a service account and download JSON key")
            print("4. Set environment variable:")
            print("   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
            sys.exit(1)

    def _process_single_page(self, pdf_path: Path, page_num: int, output_dir: Path,
                            total_pages: int) -> Dict:
        """Process a single page with Google Vision API"""
        try:
            # Convert page to image
            images = convert_from_path(
                pdf_path,
                dpi=300,  # Higher DPI for better accuracy
                first_page=page_num,
                last_page=page_num
            )

            if not images:
                return None

            image = images[0]

            # Convert PIL Image to bytes
            import io
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            # Call Google Vision API
            vision_image = vision.Image(content=img_byte_arr)

            # Detect text with language hints for better accuracy
            image_context = vision.ImageContext(
                language_hints=['ur', 'ar', 'en', 'hi']  # Urdu, Arabic, English, Hindi
            )

            response = self.client.document_text_detection(
                image=vision_image,
                image_context=image_context
            )

            if response.error.message:
                raise Exception(f"API Error: {response.error.message}")

            # Extract full text from Vision API
            text = response.full_text_annotation.text if response.full_text_annotation else ""

            # Calculate confidence (Google Vision provides per-word confidence)
            confidences = []
            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                confidences.append(word.confidence)

            avg_confidence = (sum(confidences) / len(confidences) * 100) if confidences else 0

            # Save page immediately
            page_file = output_dir / 'raw_pages' / f"page_{page_num:03d}.txt"
            page_file.parent.mkdir(parents=True, exist_ok=True)
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(text)

            # Clean up
            del image
            del images
            del img_byte_arr

            return {
                'page': page_num,
                'text': text,
                'char_count': len(text),
                'confidence': avg_confidence
            }

        except Exception as e:
            print(f"\n  ✗ Error processing page {page_num}: {e}")
            return None

    def extract_pdf(self, pdf_path: str, output_dir: str = "extracted_google",
                   max_workers: int = 4) -> Dict:
        """
        Extract text from PDF using Google Vision API

        Args:
            pdf_path: Path to PDF file
            output_dir: Output directory
            max_workers: Number of parallel workers (default 4)
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Create output directory
        output_base = Path(output_dir)
        output_base.mkdir(exist_ok=True)

        pdf_output = output_base / pdf_path.stem
        pdf_output.mkdir(exist_ok=True)

        print(f"\n📄 Processing: {pdf_path.name}")
        print(f"📁 Output folder: {pdf_output}/")
        print(f"🔍 Using Google Cloud Vision API (high accuracy)")

        # Get page count
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
        except:
            # Fallback
            test_images = convert_from_path(pdf_path, dpi=72, last_page=1)
            del test_images
            import subprocess
            result = subprocess.run(['pdfinfo', str(pdf_path)],
                                   capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    total_pages = int(line.split(':')[1].strip())
                    break

        print(f"  Processing {total_pages} pages with {max_workers} parallel workers...")
        print(f"  ⚠️  Note: Google API has rate limits and costs")

        pages_data = []
        completed_count = 0
        lock = threading.Lock()

        def process_page(page_num):
            nonlocal completed_count
            result = self._process_single_page(pdf_path, page_num, pdf_output, total_pages)

            with lock:
                completed_count += 1
                print(f"  ✓ Completed {completed_count}/{total_pages} pages "
                      f"(Avg confidence: {result['confidence']:.1f}%)" if result else "",
                      end='\r')

            return result

        # Process pages in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(process_page, page_num): page_num
                            for page_num in range(1, total_pages + 1)}

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    result = future.result()
                    if result:
                        pages_data.append(result)
                except Exception as e:
                    print(f"\n  ✗ Error on page {page_num}: {e}")

        # Sort by page number
        pages_data.sort(key=lambda x: x['page'])

        print(f"\n  ✓ Google Vision OCR completed for {total_pages} pages")

        # Save pages index JSON
        pages_index = {
            'source': str(pdf_path),
            'extraction_method': 'Google Cloud Vision API',
            'total_pages': len(pages_data),
            'total_characters': sum(p['char_count'] for p in pages_data),
            'avg_confidence': f"{sum(p['confidence'] for p in pages_data) / len(pages_data):.1f}%" if pages_data else "0%",
            'pages': [
                {
                    'page': p['page'],
                    'file': f"raw_pages/page_{p['page']:03d}.txt",
                    'char_count': p['char_count'],
                    'confidence': p['confidence']
                }
                for p in pages_data
            ]
        }

        index_file = pdf_output / 'pages_index.json'
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(pages_index, f, indent=2, ensure_ascii=False)

        print(f"\n  ✓ OCR extraction complete!")
        print(f"  📁 Output: {pdf_output}/")
        print(f"  📄 Raw pages: raw_pages/ folder")
        print(f"  📊 Pages index: pages_index.json")
        print(f"\n  💡 Next step: Run book_formatter.py to clean and organize the text")

        return {
            'success': True,
            'method': 'google_vision_api',
            'output_dir': str(pdf_output),
            'total_pages': len(pages_data),
            'avg_confidence': sum(p['confidence'] for p in pages_data) / len(pages_data) if pages_data else 0
        }


def main():
    """Main function with CLI"""
    if len(sys.argv) < 2:
        print("Google Cloud Vision API PDF Extractor")
        print("=" * 60)
        print("\nHigh-accuracy OCR extraction (no formatting)")
        print("  - Vision API: 95-99% OCR accuracy")
        print("  - Extracts raw text from all pages")
        print("  - Use book_formatter.py afterwards for cleaning & organizing")
        print("\nSetup:")
        print("1. Install: pip install google-cloud-vision pdf2image")
        print("2. Get Vision API credentials from Google Cloud Console")
        print("3. Set environment variable:")
        print("   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/vision-key.json'")
        print("\nUsage:")
        print("  python google_vision_extractor.py <pdf_file>")
        print("  python google_vision_extractor.py <pdf_file> --workers 2")
        print("\nExamples:")
        print("  python google_vision_extractor.py book.pdf")
        print("  python google_vision_extractor.py urdu_book.pdf --workers 2")
        print("\nCosts:")
        print("  - Vision API: $1.50 per 1000 pages (first 1000/month free)")
        sys.exit(0)

    pdf_file = sys.argv[1]
    credentials = None
    workers = 4

    # Parse arguments
    if '--credentials' in sys.argv:
        idx = sys.argv.index('--credentials')
        if idx + 1 < len(sys.argv):
            credentials = sys.argv[idx + 1]

    if '--workers' in sys.argv:
        idx = sys.argv.index('--workers')
        if idx + 1 < len(sys.argv):
            workers = int(sys.argv[idx + 1])

    # Extract
    extractor = GoogleVisionPDFExtractor(credentials_path=credentials)
    extractor.extract_pdf(pdf_file, max_workers=workers)


if __name__ == "__main__":
    main()
