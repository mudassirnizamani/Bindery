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

class ManjaroPDFExtractor:
    def __init__(self, lang='eng'):
        """
        Initialize PDF extractor for Manjaro
        
        Args:
            lang: Language code(s) for OCR
                  'eng' - English
                  'urd' - Urdu
                  'ara' - Arabic
                  'hin' - Hindi
                  'eng+urd' - Multiple languages
        """
        self.lang = lang
        self.check_dependencies()
        
    def check_dependencies(self):
        """Check if all required tools are installed on Manjaro"""
        missing = []
        
        # Check Tesseract
        try:
            subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
            print("✓ Tesseract installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append("tesseract")
            
        # Check for language data
        try:
            result = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True)
            available_langs = result.stdout.lower()
            
            for lang in self.lang.split('+'):
                if lang not in available_langs:
                    print(f"⚠ Language '{lang}' not installed")
                    print(f"  Install with: sudo pacman -S tesseract-data-{lang}")
                else:
                    print(f"✓ Language '{lang}' available")
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

        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        print(f"\n📄 Processing: {pdf_path.name}")

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
                    result = self._ocr_extraction(pdf_path)
                elif result['total_chars'] < 100:
                    print("  → Low text content, using OCR...")
                    result = self._ocr_extraction(pdf_path)
                else:
                    print("  → Text layer found, extracting...")
            else:
                print("  → Using OCR (this may take a moment)...")
                result = self._ocr_extraction(pdf_path)
        else:
            print("  → Force OCR mode enabled...")
            result = self._ocr_extraction(pdf_path)

        # Save results
        self._save_results(pdf_path, result, output_dir)

        return result
    
    def _detect_structure(self, text: str) -> Dict:
        """Detect document structure like headings, sections, lists"""
        structure = {
            'headings': [],
            'lists': [],
            'paragraphs': []
        }

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

    def _ocr_extraction(self, pdf_path: Path) -> Dict:
        """Extract text using OCR with memory-efficient page-by-page processing"""
        pages_text = []

        try:
            # Get total page count
            total_pages = self._get_page_count(pdf_path)
            if total_pages == 0:
                raise Exception("Could not determine page count")

            print(f"  Processing {total_pages} pages with OCR...")

            # Process one page at a time to minimize memory usage
            for page_num in range(1, total_pages + 1):
                print(f"  OCR page {page_num}/{total_pages}", end='\r')

                # Convert only ONE page at a time - this is critical for memory
                images = convert_from_path(
                    pdf_path,
                    dpi=150,  # Reduced from 200 to save memory (still good quality)
                    first_page=page_num,
                    last_page=page_num,
                    grayscale=True  # Grayscale uses less memory than color
                )

                if not images:
                    continue

                image = images[0]

                # Perform OCR
                text = pytesseract.image_to_string(image, lang=self.lang)

                # Get OCR confidence data
                data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
                confidences = [int(c) for c in data['conf'] if int(c) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0

                pages_text.append({
                    'page': page_num,
                    'text': text,
                    'char_count': len(text),
                    'confidence': avg_confidence
                })

                # Explicitly delete image to free memory immediately
                del image
                del images
                del data

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
        """Save extraction results to files"""
        if not result.get('success'):
            print("  ✗ Extraction failed")
            return

        pdf_name = pdf_path.stem
        pdf_output = output_dir / pdf_name
        pdf_output.mkdir(exist_ok=True)

        # Save complete text
        text_file = pdf_output / f"{pdf_name}_complete.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            for page in result['pages']:
                f.write(f"\n{'='*60}\n")
                f.write(f"PAGE {page['page']}")
                if 'confidence' in page:
                    f.write(f" (OCR Confidence: {page['confidence']:.1f}%)")
                f.write(f"\n{'='*60}\n\n")
                f.write(page['text'])
                f.write('\n')

        # Save individual pages
        pages_dir = pdf_output / 'pages'
        pages_dir.mkdir(exist_ok=True)

        for page in result['pages']:
            page_file = pages_dir / f"page_{page['page']:03d}.txt"
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(page['text'])

        # Save document structure outline
        structure_dir = pdf_output / 'structure'
        structure_dir.mkdir(exist_ok=True)

        # Save structured outline
        outline_file = structure_dir / 'outline.txt'
        with open(outline_file, 'w', encoding='utf-8') as f:
            f.write("DOCUMENT OUTLINE\n")
            f.write("=" * 60 + "\n\n")

            for page in result['pages']:
                if 'structure' not in page:
                    continue

                structure = page['structure']
                if structure['headings']:
                    f.write(f"\nPage {page['page']}:\n")
                    f.write("-" * 40 + "\n")
                    for heading in structure['headings']:
                        indent = "  " * heading.get('level', 0)
                        f.write(f"{indent}{heading['text']}\n")

        # Save sections by headings
        sections_dir = structure_dir / 'sections'
        sections_dir.mkdir(exist_ok=True)

        section_num = 1
        for page in result['pages']:
            if 'structure' not in page:
                continue

            structure = page['structure']
            for heading in structure['headings']:
                # Create a safe filename from heading text
                safe_name = re.sub(r'[^\w\s-]', '', heading['text'][:50])
                safe_name = re.sub(r'[-\s]+', '_', safe_name).strip('_')
                section_file = sections_dir / f"{section_num:02d}_{safe_name}.txt"

                with open(section_file, 'w', encoding='utf-8') as f:
                    f.write(f"Page {page['page']}\n")
                    f.write(f"{heading['text']}\n")
                    f.write("=" * 60 + "\n\n")
                    # Write the text content
                    f.write(page['text'])

                section_num += 1

        # Save lists separately
        lists_file = structure_dir / 'lists.txt'
        with open(lists_file, 'w', encoding='utf-8') as f:
            f.write("EXTRACTED LISTS\n")
            f.write("=" * 60 + "\n\n")

            for page in result['pages']:
                if 'structure' not in page:
                    continue

                structure = page['structure']
                if structure['lists']:
                    f.write(f"\nPage {page['page']}:\n")
                    f.write("-" * 40 + "\n")
                    for item in structure['lists']:
                        f.write(f"{item['text']}\n")
                    f.write("\n")

        # Save tables with CSV export
        if result.get('tables'):
            tables_dir = pdf_output / 'tables'
            tables_dir.mkdir(exist_ok=True)

            tables_file = tables_dir / 'tables.txt'
            with open(tables_file, 'w', encoding='utf-8') as f:
                for table_info in result['tables']:
                    f.write(f"\n=== Tables from Page {table_info['page']} ===\n")
                    for idx, table in enumerate(table_info['tables'], 1):
                        f.write(f"\nTable {idx}:\n")
                        for row in table:
                            f.write(' | '.join(str(cell or '') for cell in row))
                            f.write('\n')
                        f.write('\n')

                        # Also save each table as CSV
                        csv_file = tables_dir / f"page_{table_info['page']}_table_{idx}.csv"
                        with open(csv_file, 'w', encoding='utf-8', newline='') as csvf:
                            writer = csv.writer(csvf)
                            for row in table:
                                writer.writerow([cell or '' for cell in row])

        # Save metadata
        metadata = {
            'source': str(pdf_path),
            'extraction_method': result['method'],
            'language': self.lang,
            'total_pages': result['page_count'],
            'total_characters': result['total_chars'],
            'avg_chars_per_page': result['total_chars'] // result['page_count'] if result['page_count'] > 0 else 0
        }

        if 'avg_confidence' in result:
            metadata['ocr_confidence'] = f"{result['avg_confidence']:.1f}%"

        # Add structure statistics
        total_headings = sum(len(p.get('structure', {}).get('headings', [])) for p in result['pages'])
        total_lists = sum(len(p.get('structure', {}).get('lists', [])) for p in result['pages'])

        metadata['structure'] = {
            'total_headings': total_headings,
            'total_list_items': total_lists,
            'total_tables': len(result.get('tables', []))
        }

        metadata_file = pdf_output / f"{pdf_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Saved to: {pdf_output}/")
        print(f"    - Complete text: {text_file.name}")
        print(f"    - Individual pages: {pages_dir.name}/")
        print(f"    - Document structure: {structure_dir.name}/")
        print(f"      • Outline: outline.txt")
        print(f"      • Sections: {section_num-1} files")
        print(f"      • Lists: lists.txt")
        print(f"    - Metadata: {metadata_file.name}")

        if result.get('tables'):
            table_count = sum(len(t['tables']) for t in result['tables'])
            print(f"    - Tables: {tables_dir.name}/ ({table_count} tables, CSV + TXT)")

def batch_process(folder: str, lang: str = 'eng', output_dir: str = 'extracted'):
    """Process all PDFs in a folder"""
    extractor = ManjaroPDFExtractor(lang=lang)
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
        print("PDF Text Extractor for Manjaro/Arch Linux")
        print("==========================================")
        print("\nUsage:")
        print("  python main.py <pdf_file>                      # Extract from single PDF")
        print("  python main.py <pdf_file> --lang urd           # Extract Urdu text")
        print("  python main.py <pdf_file> --lang eng+urd       # Extract mixed English/Urdu")
        print("  python main.py <pdf_file> --force-ocr          # Force OCR (ignore text layer)")
        print("  python main.py --batch <folder>                # Process entire folder")
        print("\nExamples:")
        print("  python main.py document.pdf")
        print("  python main.py urdu_doc.pdf --lang urd")
        print("  python main.py urdu_doc.pdf --lang urd --force-ocr")
        print("  python main.py --batch ./pdfs --lang eng+urd")
        print("\nSupported languages:")
        print("  eng (English), urd (Urdu), ara (Arabic), hin (Hindi)")
        print("\nTo install language packs:")
        print("  sudo pacman -S tesseract-data-urd  # For Urdu")
        print("  sudo pacman -S tesseract-data-ara  # For Arabic")
        print("\nNote: Program auto-detects garbled text and switches to OCR")
        sys.exit(0)

    # Parse arguments
    lang = 'eng'
    force_ocr = False

    if '--lang' in sys.argv:
        idx = sys.argv.index('--lang')
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]

    if '--force-ocr' in sys.argv:
        force_ocr = True

    if '--batch' in sys.argv:
        idx = sys.argv.index('--batch')
        if idx + 1 < len(sys.argv):
            folder = sys.argv[idx + 1]
            batch_process(folder, lang=lang)
    else:
        pdf_file = sys.argv[1]
        extractor = ManjaroPDFExtractor(lang=lang)
        extractor.extract_from_pdf(pdf_file, force_ocr=force_ocr)

if __name__ == "__main__":
    main()
