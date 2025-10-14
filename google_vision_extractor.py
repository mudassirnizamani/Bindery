#!/usr/bin/env python3
"""
Google Cloud Vision API PDF Extractor
High-accuracy OCR using Google's Vision API (95-99% accuracy)
Supports Urdu, Arabic, and all major languages
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
import re

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

    def _detect_chapter(self, text: str) -> Dict:
        """Detect if this page starts a chapter"""
        lines = text.split('\n')[:10]

        for line in lines:
            line_stripped = line.strip()

            patterns = [
                r'^(?:Chapter|CHAPTER|باب)\s*(\d+|[IVX]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)',
                r'^(?:Ch|CH)\.?\s*(\d+)',
                r'^(\d+)\s*(?:\.|:)?\s*(?:Chapter|CHAPTER)',
                r'^(?:Part|PART|حصہ)\s*(\d+|[IVX]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, line_stripped, re.IGNORECASE)
                if match:
                    return {
                        'text': line_stripped,
                        'number': match.group(1) if match.groups() else '1',
                        'type': 'chapter'
                    }

        return None

    def _process_single_page(self, pdf_path: Path, page_num: int, output_dir: Path,
                            current_chapter: Dict, total_pages: int) -> Dict:
        """Process a single page with Google Vision API"""
        try:
            # Convert page to image
            images = convert_from_path(
                pdf_path,
                dpi=300,  # Higher DPI for better Google Vision accuracy
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

            # Extract full text
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

            # Detect chapter
            chapter_info = self._detect_chapter(text)

            # Write page immediately (streaming)
            self._write_page_immediately(output_dir, page_num, text, avg_confidence,
                                        chapter_info, current_chapter)

            # Clean up
            del image
            del images
            del img_byte_arr

            return {
                'page': page_num,
                'text': text,
                'char_count': len(text),
                'confidence': avg_confidence,
                'chapter': chapter_info
            }

        except Exception as e:
            print(f"\n  ✗ Error processing page {page_num}: {e}")
            return None

    def _write_page_immediately(self, output_dir: Path, page_num: int, text: str,
                               confidence: float, chapter_info: Dict, current_chapter: Dict):
        """Write page to disk immediately"""
        # Determine chapter folder
        if chapter_info:
            chapter_name = chapter_info['text'][:50]
            chapter_name = re.sub(r'[^\w\s-]', '', chapter_name)
            chapter_name = re.sub(r'[-\s]+', '_', chapter_name).strip('_')
            chapter_dir = output_dir / 'chapters' / f"chapter_{chapter_info['number']}_{chapter_name}"
        elif current_chapter.get('dir'):
            chapter_dir = current_chapter['dir']
        else:
            chapter_dir = output_dir / 'chapters' / 'intro'

        chapter_dir.mkdir(parents=True, exist_ok=True)

        # Write page file
        page_file = chapter_dir / f"page_{page_num:03d}.txt"
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(f"Page {page_num} (Google Vision Confidence: {confidence:.1f}%)\n")
            f.write("=" * 60 + "\n\n")
            f.write(text)

        return chapter_dir

    def extract_pdf(self, pdf_path: str, output_dir: str = "extracted_google",
                   max_workers: int = 4) -> Dict:
        """
        Extract text from PDF using Google Vision API with parallel processing

        Args:
            pdf_path: Path to PDF file
            output_dir: Output directory
            max_workers: Number of parallel workers (default 4)
                        Be careful: Google has rate limits!
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

        pages_text = []
        completed_count = 0
        lock = threading.Lock()
        current_chapter = {'dir': pdf_output / 'chapters' / 'intro'}

        def process_page(page_num):
            nonlocal completed_count
            result = self._process_single_page(pdf_path, page_num, pdf_output,
                                              current_chapter, total_pages)

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
                        pages_text.append(result)

                        # Update current chapter
                        if result.get('chapter'):
                            with lock:
                                current_chapter['dir'] = pdf_output / 'chapters' / f"chapter_{result['chapter']['number']}"
                except Exception as e:
                    print(f"\n  ✗ Error on page {page_num}: {e}")

        # Sort by page number
        pages_text.sort(key=lambda x: x['page'])

        print(f"\n  ✓ Google Vision OCR completed for {total_pages} pages")

        # Save results
        self._save_results(pdf_path, pages_text, pdf_output)

        return {
            'success': True,
            'method': 'google_vision_api',
            'pages': pages_text,
            'total_pages': len(pages_text),
            'total_chars': sum(p['char_count'] for p in pages_text),
            'avg_confidence': sum(p['confidence'] for p in pages_text) / len(pages_text) if pages_text else 0
        }

    def _save_results(self, pdf_path: Path, pages_text: List[Dict], output_dir: Path):
        """Save metadata and chapter index"""
        pdf_name = pdf_path.stem

        # Create chapter index
        chapters = {}
        for page in pages_text:
            if page.get('chapter'):
                chapter_num = page['chapter']['number']
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        'title': page['chapter']['text'],
                        'start_page': page['page'],
                        'pages': []
                    }
                chapters[chapter_num]['pages'].append(page['page'])

        # Write chapter index
        if chapters:
            index_file = output_dir / 'CHAPTER_INDEX.txt'
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(f"CHAPTER INDEX - {pdf_name}\n")
                f.write("=" * 60 + "\n\n")
                for chapter_num in sorted(chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                    ch = chapters[chapter_num]
                    f.write(f"Chapter {chapter_num}: {ch['title']}\n")
                    f.write(f"  Pages: {ch['start_page']}-{max(ch['pages'])}\n")
                    f.write(f"  Total pages: {len(ch['pages'])}\n\n")

        # Save complete text
        complete_file = output_dir / f"{pdf_name}_complete.txt"
        with open(complete_file, 'w', encoding='utf-8') as f:
            for page in pages_text:
                f.write(f"\n{'='*60}\n")
                f.write(f"PAGE {page['page']} (Confidence: {page['confidence']:.1f}%)\n")
                f.write(f"{'='*60}\n\n")
                f.write(page['text'])
                f.write('\n')

        # Save metadata
        metadata = {
            'source': str(pdf_path),
            'extraction_method': 'Google Cloud Vision API',
            'total_pages': len(pages_text),
            'total_characters': sum(p['char_count'] for p in pages_text),
            'avg_confidence': f"{sum(p['confidence'] for p in pages_text) / len(pages_text):.1f}%" if pages_text else "0%",
            'chapters': len(chapters) if chapters else 0
        }

        if chapters:
            metadata['chapters_list'] = {
                num: {'title': ch['title'], 'pages': len(ch['pages'])}
                for num, ch in chapters.items()
            }

        metadata_file = output_dir / f"{pdf_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n  ✓ Processing complete!")
        print(f"  📁 Output: {output_dir}/")
        if chapters:
            print(f"  📖 Chapters detected: {len(chapters)}")
            print(f"  📄 Chapter index: CHAPTER_INDEX.txt")
        print(f"  📊 Metadata: {metadata_file.name}")
        print(f"  📝 Complete text: {complete_file.name}")


def main():
    """Main function with CLI"""
    if len(sys.argv) < 2:
        print("Google Cloud Vision PDF Extractor")
        print("=" * 60)
        print("\nHigh-accuracy OCR using Google Vision API (95-99% accuracy)")
        print("\nSetup:")
        print("1. Install: pip install google-cloud-vision pdf2image")
        print("2. Get credentials from Google Cloud Console")
        print("3. Set environment variable:")
        print("   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
        print("\nUsage:")
        print("  python google_vision_extractor.py <pdf_file>")
        print("  python google_vision_extractor.py <pdf_file> --workers 2")
        print("  python google_vision_extractor.py <pdf_file> --credentials /path/to/key.json")
        print("\nExamples:")
        print("  python google_vision_extractor.py book.pdf")
        print("  python google_vision_extractor.py urdu_book.pdf --workers 2")
        print("\nNote:")
        print("  - Google Vision API has rate limits")
        print("  - Costs ~$1.50 per 1000 pages")
        print("  - First 1000 pages/month are free")
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
