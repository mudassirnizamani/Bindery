#!/usr/bin/env python3
"""
PDF Text Extractor for Manjaro/Arch Linux
Handles both regular PDFs and scanned images with OCR
Supports multiple languages including Urdu, Arabic, Hindi
"""

import sys
import subprocess
from pathlib import Path
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import json
import csv
import re
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class ManjaroPDFExtractor:
    def __init__(self):
        """
        Initialize PDF extractor for English documents
        Optimized for English-only text extraction
        """
        self.lang = 'eng'  # English only
        self.check_dependencies()
        
    def check_dependencies(self):
        """Check if all required tools are installed on Manjaro"""
        missing = []

        # Check Tesseract
        try:
            subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
            print("✓ Tesseract installed (English)")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("tesseract")

        # Check for English language data
        try:
            result = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True)
            available_langs = result.stdout.lower()

            if 'eng' in available_langs:
                print("✓ English language data available")
            else:
                print("⚠ English language data not found")
                print("  Install with: sudo pacman -S tesseract-data-eng")
                missing.append("tesseract-data-eng")
        except:
            pass

        # Check pdftoppm (from poppler)
        try:
            subprocess.run(['pdftoppm', '-h'], capture_output=True, check=True)
            print("✓ Poppler installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("poppler")

        if missing:
            print("\n⚠ Missing dependencies:")
            for dep in missing:
                print(f"  sudo pacman -S {dep}")
            print("\nInstall missing dependencies and try again.")
            sys.exit(1)
    
    def _is_garbled_text(self, text: str) -> bool:
        """Check if extracted text is garbled (contains many (cid:) codes)"""
        if not text:
            return False

        # Count (cid:) patterns which indicate garbled/unmapped characters
        cid_count = text.count('(cid:')
        total_chars = len(text)

        # If more than 10% of text is (cid: codes, it's likely garbled
        if total_chars > 0 and (cid_count / total_chars) > 0.05:
            return True

        # Check for high ratio of non-ASCII without proper Unicode
        non_ascii = sum(1 for c in text if ord(c) > 127)
        if total_chars > 100 and (non_ascii / total_chars) < 0.1 and cid_count > 10:
            return True

        return False

    def extract_from_pdf(self, pdf_path: str, output_dir: str = "extracted", force_ocr: bool = False) -> Dict:
        """
        Extract text from PDF with automatic method detection

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory for output files
            force_ocr: Force OCR even if text layer exists

        Returns:
            Dictionary with extraction results
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Create output directory with exact PDF name
        output_base = Path(output_dir)
        output_base.mkdir(exist_ok=True)

        pdf_output = output_base / pdf_path.stem
        pdf_output.mkdir(exist_ok=True)

        print(f"\n📄 Processing: {pdf_path.name}")
        print(f"📁 Output folder: {pdf_output}/")

        # First try text extraction if not forcing OCR
        if not force_ocr:
            result = self._try_text_extraction(pdf_path)

            # Check if text is garbled or insufficient
            if result['success']:
                sample_text = result['pages'][0]['text'] if result['pages'] else ""
                is_garbled = self._is_garbled_text(sample_text)

                if is_garbled:
                    print("  ⚠ Detected garbled text (likely non-English embedded font)")
                    print("  → Switching to OCR mode...")
                    result = self._ocr_extraction(pdf_path, pdf_output)
                elif result['total_chars'] < 100:
                    print("  → Low text content, using OCR...")
                    result = self._ocr_extraction(pdf_path, pdf_output)
                else:
                    print("  → Text layer found, extracting...")
            else:
                print("  → Using OCR (this may take a moment)...")
                result = self._ocr_extraction(pdf_path, pdf_output)
        else:
            print("  → Force OCR mode enabled...")
            result = self._ocr_extraction(pdf_path, pdf_output)

        # Save results
        self._save_results(pdf_path, result, pdf_output)

        return result
    
    def _detect_chapter(self, text: str) -> Optional[Dict]:
        """Detect if this page starts a chapter (English only)"""
        lines = text.split('\n')[:10]  # Check first 10 lines

        for line in lines:
            line_stripped = line.strip()

            # Patterns for English chapter detection
            patterns = [
                r'^(?:Chapter|CHAPTER)\s*(\d+|[IVX]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)',
                r'^(?:Ch|CH)\.?\s*(\d+)',
                r'^(\d+)\s*(?:\.|:)?\s*(?:Chapter|CHAPTER)',
                r'^(?:Part|PART)\s*(\d+|[IVX]+)',
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

    def _detect_structure(self, text: str) -> Dict:
        """Detect document structure like headings, sections, lists"""
        structure = {
            'headings': [],
            'lists': [],
            'paragraphs': [],
            'chapter': None
        }

        # Check for chapter
        structure['chapter'] = self._detect_chapter(text)

        lines = text.split('\n')
        current_section = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Detect numbered headings (e.g., "1. Introduction", "1.1 Background")
            if re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_stripped):
                structure['headings'].append({
                    'line_num': i + 1,
                    'text': line_stripped,
                    'level': line_stripped.count('.')
                })
                current_section = line_stripped

            # Detect all-caps headings
            elif len(line_stripped) > 3 and line_stripped.isupper() and not line_stripped.endswith('.'):
                structure['headings'].append({
                    'line_num': i + 1,
                    'text': line_stripped,
                    'level': 0,
                    'type': 'caps'
                })
                current_section = line_stripped

            # Detect bullet points or numbered lists
            elif re.match(r'^[\*\-\•\◦]\s+', line_stripped) or re.match(r'^\d+[\.\)]\s+', line_stripped):
                structure['lists'].append({
                    'line_num': i + 1,
                    'text': line_stripped,
                    'section': current_section
                })

            # Regular paragraphs
            elif len(line_stripped) > 20:
                structure['paragraphs'].append({
                    'line_num': i + 1,
                    'text': line_stripped[:100] + '...' if len(line_stripped) > 100 else line_stripped,
                    'section': current_section
                })

        return structure

    def _try_text_extraction(self, pdf_path: Path) -> Dict:
        """Try to extract text directly from PDF"""
        pages_text = []
        tables_data = []
        document_structure = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []

                    # Detect structure in the text
                    structure = self._detect_structure(text)

                    pages_text.append({
                        'page': i,
                        'text': text,
                        'char_count': len(text),
                        'structure': structure
                    })

                    if tables:
                        tables_data.append({
                            'page': i,
                            'tables': tables
                        })

            total_chars = sum(p['char_count'] for p in pages_text)

            return {
                'success': True,
                'method': 'text_extraction',
                'pages': pages_text,
                'tables': tables_data,
                'total_chars': total_chars,
                'page_count': len(pages_text)
            }

        except Exception as e:
            print(f"  Text extraction failed: {e}")
            return {'success': False, 'total_chars': 0}
    
    def _get_page_count(self, pdf_path: Path) -> int:
        """Get total page count efficiently using pdfplumber"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except:
            # Fallback: use pdfinfo command
            try:
                result = subprocess.run(
                    ['pdfinfo', str(pdf_path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                for line in result.stdout.split('\n'):
                    if line.startswith('Pages:'):
                        return int(line.split(':')[1].strip())
            except:
                pass
        return 0

    def _process_single_page_ocr(self, pdf_path: Path, page_num: int, output_dir: Path, current_chapter: Dict) -> Dict:
        """Process a single page with OCR and write immediately to disk"""
        try:
            # Convert only ONE page
            images = convert_from_path(
                pdf_path,
                dpi=150,
                first_page=page_num,
                last_page=page_num,
                grayscale=True
            )

            if not images:
                return None

            image = images[0]

            # Perform OCR
            text = pytesseract.image_to_string(image, lang=self.lang)

            # Get OCR confidence
            data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Detect structure
            structure = self._detect_structure(text)

            # Write page immediately to disk (streaming)
            self._write_page_immediately(output_dir, page_num, text, avg_confidence, structure, current_chapter)

            result = {
                'page': page_num,
                'text': text,
                'char_count': len(text),
                'confidence': avg_confidence,
                'structure': structure
            }

            # Free memory immediately
            del image
            del images
            del data

            return result

        except Exception as e:
            print(f"\n  Error processing page {page_num}: {e}")
            return None

    def _write_page_immediately(self, output_dir: Path, page_num: int, text: str, confidence: float, structure: Dict, current_chapter: Dict):
        """Write page to disk immediately (streaming write)"""
        # Determine which chapter folder to use
        if structure.get('chapter'):
            chapter_name = structure['chapter']['text'][:50]
            chapter_name = re.sub(r'[^\w\s-]', '', chapter_name)
            chapter_name = re.sub(r'[-\s]+', '_', chapter_name).strip('_')
            chapter_dir = output_dir / 'chapters' / f"chapter_{structure['chapter']['number']}_{chapter_name}"
        elif current_chapter:
            chapter_dir = current_chapter['dir']
        else:
            chapter_dir = output_dir / 'chapters' / 'intro'

        chapter_dir.mkdir(parents=True, exist_ok=True)

        # Write page file
        page_file = chapter_dir / f"page_{page_num:03d}.txt"
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(f"Page {page_num} (OCR Confidence: {confidence:.1f}%)\n")
            f.write("=" * 60 + "\n\n")
            f.write(text)

        return chapter_dir

    def _ocr_extraction(self, pdf_path: Path, output_dir: Path) -> Dict:
        """Extract text using OCR with parallel processing and streaming writes"""
        try:
            total_pages = self._get_page_count(pdf_path)
            if total_pages == 0:
                raise Exception("Could not determine page count")

            print(f"  Processing {total_pages} pages with OCR (4 parallel threads)...")

            pages_text = []
            completed_count = 0
            lock = threading.Lock()
            current_chapter = {'dir': output_dir / 'chapters' / 'intro'}

            def process_page(page_num):
                nonlocal completed_count
                result = self._process_single_page_ocr(pdf_path, page_num, output_dir, current_chapter)

                with lock:
                    completed_count += 1
                    print(f"  ✓ Completed {completed_count}/{total_pages} pages", end='\r')

                return result

            # Use ThreadPoolExecutor for parallel processing (4 threads)
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit all pages
                future_to_page = {executor.submit(process_page, page_num): page_num
                                for page_num in range(1, total_pages + 1)}

                # Collect results as they complete
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        result = future.result()
                        if result:
                            pages_text.append(result)

                            # Update current chapter if new chapter detected
                            if result.get('structure', {}).get('chapter'):
                                with lock:
                                    current_chapter['dir'] = output_dir / 'chapters' / f"chapter_{result['structure']['chapter']['number']}"
                    except Exception as e:
                        print(f"\n  Error on page {page_num}: {e}")

            # Sort pages by page number
            pages_text.sort(key=lambda x: x['page'])

            print(f"\n  ✓ OCR completed for {total_pages} pages")

            return {
                'success': True,
                'method': 'ocr',
                'pages': pages_text,
                'tables': [],
                'total_chars': sum(p['char_count'] for p in pages_text),
                'page_count': len(pages_text),
                'avg_confidence': sum(p.get('confidence', 0) for p in pages_text) / len(pages_text) if pages_text else 0
            }

        except Exception as e:
            print(f"\n  OCR failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _save_results(self, pdf_path: Path, result: Dict, output_dir: Path):
        """Save extraction results and metadata"""
        if not result.get('success'):
            print("  ✗ Extraction failed")
            return

        pdf_name = pdf_path.stem

        # Create chapter index
        chapters = {}
        for page in result.get('pages', []):
            chapter_info = page.get('structure', {}).get('chapter')
            if chapter_info:
                chapter_num = chapter_info['number']
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        'title': chapter_info['text'],
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

        # Save metadata
        metadata = {
            'source': str(pdf_path),
            'extraction_method': result['method'],
            'language': 'English',
            'total_pages': result['page_count'],
            'total_characters': result['total_chars'],
            'avg_chars_per_page': result['total_chars'] // result['page_count'] if result['page_count'] > 0 else 0,
            'chapters': len(chapters) if chapters else 0
        }

        if 'avg_confidence' in result:
            metadata['ocr_confidence'] = f"{result['avg_confidence']:.1f}%"

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

def batch_process(folder: str, output_dir: str = 'extracted'):
    """Process all PDFs in a folder"""
    extractor = ManjaroPDFExtractor()
    folder_path = Path(folder)

    pdf_files = list(folder_path.glob('*.pdf'))
    print(f"\n📁 Found {len(pdf_files)} PDF files in {folder}")

    results = []
    for pdf in pdf_files:
        try:
            result = extractor.extract_from_pdf(pdf, output_dir)
            results.append({'file': pdf.name, 'status': 'success'})
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append({'file': pdf.name, 'status': 'failed', 'error': str(e)})

    # Summary
    success = sum(1 for r in results if r['status'] == 'success')
    print(f"\n📊 Summary: {success}/{len(results)} files processed successfully")

    return results

def main():
    """Main function with command line interface"""
    if len(sys.argv) < 2:
        print("PDF Text Extractor for English Documents")
        print("==========================================")
        print("\nOptimized for English-only PDFs with parallel processing")
        print("\nUsage:")
        print("  python main.py <pdf_file>           # Extract from single PDF")
        print("  python main.py <pdf_file> --force-ocr  # Force OCR (ignore text layer)")
        print("  python main.py --batch <folder>     # Process entire folder")
        print("\nExamples:")
        print("  python main.py document.pdf")
        print("  python main.py scanned_doc.pdf --force-ocr")
        print("  python main.py --batch ./pdfs")
        print("\nFeatures:")
        print("  ✓ Parallel processing (4 threads)")
        print("  ✓ Streaming writes (low memory usage)")
        print("  ✓ Auto chapter detection")
        print("  ✓ Auto-detects garbled text and switches to OCR")
        print("\nSetup:")
        print("  sudo pacman -S tesseract tesseract-data-eng poppler")
        print("  pip install -r requirements.txt")
        sys.exit(0)

    # Parse arguments
    force_ocr = False

    if '--force-ocr' in sys.argv:
        force_ocr = True

    if '--batch' in sys.argv:
        idx = sys.argv.index('--batch')
        if idx + 1 < len(sys.argv):
            folder = sys.argv[idx + 1]
            batch_process(folder)
    else:
        pdf_file = sys.argv[1]
        extractor = ManjaroPDFExtractor()
        extractor.extract_from_pdf(pdf_file, force_ocr=force_ocr)

if __name__ == "__main__":
    main()
