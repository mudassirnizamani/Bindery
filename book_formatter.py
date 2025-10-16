#!/usr/bin/env python3
"""
Book Formatter with Gemini AI
Takes raw OCR text and cleans/organizes it into structured book format
Processes 50 pages at a time, creates one file per chapter
"""

import sys
import os
from pathlib import Path
import json
import google.generativeai as genai
import time
import re
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BookFormatter:
    def __init__(self, gemini_api_key: str = None, batch_size: int = 5):
        """
        Initialize Book Formatter with Gemini AI

        Args:
            gemini_api_key: Google AI API key for Gemini 2.0 Flash
                           If None, uses GOOGLE_API_KEY env var
            batch_size: Number of pages to process at once (default: 5)
        """
        try:
            api_key = gemini_api_key or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("✗ No Gemini API key found")
                print("  Set GOOGLE_API_KEY environment variable or use --gemini-key")
                sys.exit(1)

            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
            self.initial_batch_size = batch_size
            self.batch_size = batch_size
            print(f"✓ Gemini 2.0 Flash initialized (batch size: {batch_size} pages)")
        except Exception as e:
            print(f"✗ Failed to initialize Gemini: {e}")
            sys.exit(1)

        # Track structure
        self.book_structure = None  # Will hold the detected structure from TOC
        self.current_part = None
        self.current_chapter = None
        self.chapter_files = {}  # {chapter_id: file_handle}
        self.batch_adjustments = 0  # Track how many times we adjusted batch size

    def _sanitize_text_for_api(self, text: str, log_issues: bool = False) -> str:
        """
        Remove problematic characters that can break JSON parsing

        Args:
            text: Raw OCR text
            log_issues: Whether to log found issues

        Returns:
            Sanitized text safe for API processing
        """
        if not text:
            return text

        original_length = len(text)
        issues_found = []

        # Remove common control characters that break JSON
        control_chars = [
            '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
            '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
            '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
            '\x1b', '\x1c', '\x1d', '\x1e', '\x1f'
        ]

        for char in control_chars:
            count = text.count(char)
            if count > 0:
                text = text.replace(char, '')
                if log_issues:
                    issues_found.append(f"Control char \\x{ord(char):02x}: {count} occurrences")

        # Remove zero-width characters that can break JSON
        zero_width_chars = {
            '\u200b': 'Zero-width space',
            '\u200c': 'Zero-width non-joiner',
            '\u200d': 'Zero-width joiner',
            '\ufeff': 'Zero-width no-break space (BOM)'
        }

        for char, name in zero_width_chars.items():
            count = text.count(char)
            if count > 0:
                text = text.replace(char, '')
                if log_issues:
                    issues_found.append(f"{name}: {count} occurrences")

        # Replace problematic quotes that can break JSON strings
        quote_chars = {
            '\u201c': ('"', 'Left double quote'),
            '\u201d': ('"', 'Right double quote'),
            '\u2018': ("'", 'Left single quote'),
            '\u2019': ("'", 'Right single quote')
        }

        for char, (replacement, name) in quote_chars.items():
            count = text.count(char)
            if count > 0:
                text = text.replace(char, replacement)
                if log_issues:
                    issues_found.append(f"{name}: {count} occurrences")

        # Remove other problematic Unicode characters
        replacement_char_count = text.count('\ufffd')
        if replacement_char_count > 0:
            text = text.replace('\ufffd', '')
            if log_issues:
                issues_found.append(f"Replacement character: {replacement_char_count} occurrences")

        # Normalize whitespace but keep valid newlines and tabs
        # Replace any sequence of spaces with single space
        text = re.sub(r' +', ' ', text)

        if log_issues and issues_found:
            print(f"    🧹 Sanitized: {len(issues_found)} types of issues, {original_length - len(text)} chars removed")
            for issue in issues_found[:5]:  # Show first 5 issues
                print(f"       - {issue}")

        return text

    def _estimate_batch_tokens(self, batch_pages: List[Dict]) -> int:
        """
        Estimate output tokens for a batch of pages

        Args:
            batch_pages: List of page data

        Returns:
            Estimated token count
        """
        total_chars = sum(len(page['raw_text']) for page in batch_pages)
        # Estimate: cleaned text is ~80% of input, 1 token ≈ 4 chars
        estimated_output_chars = total_chars * 0.8
        estimated_tokens = int(estimated_output_chars / 4)
        return estimated_tokens

    def _adjust_batch_size(self, batch_pages: List[Dict], current_batch_size: int) -> int:
        """
        Dynamically adjust batch size if token estimate is too high

        Args:
            batch_pages: Current batch of pages
            current_batch_size: Current batch size

        Returns:
            Adjusted batch size
        """
        estimated_tokens = self._estimate_batch_tokens(batch_pages)

        # If we're within safe limits, return current size
        if estimated_tokens <= 7500:
            return current_batch_size

        # Calculate how much we need to reduce
        # Target: 7000 tokens to leave some safety margin
        target_tokens = 7000
        reduction_factor = target_tokens / estimated_tokens
        new_batch_size = max(3, int(current_batch_size * reduction_factor))  # Minimum 3 pages

        print(f"  📉 Batch too large (~{estimated_tokens:,} tokens), reducing from {current_batch_size} to {new_batch_size} pages")
        self.batch_adjustments += 1

        return new_batch_size

    def _extract_book_structure(self, raw_pages_dir: Path, pages_index: Dict) -> Dict:
        """
        Extract book structure from first 15 pages (table of contents)

        Args:
            raw_pages_dir: Directory containing raw_pages/
            pages_index: Pages index JSON

        Returns:
            {
                'has_parts': bool,
                'parts': [{'number': int, 'title': str, 'start_page': int, 'chapters': [...]}],
                'chapters': [{'number': int, 'title': str, 'start_page': int, 'part_number': int or None}]
            }
        """
        print("  🔍 Analyzing book structure from first 15 pages...")

        # Read first 15 pages (TOC is usually in first pages)
        structure_pages_count = min(15, pages_index['total_pages'])
        toc_content = ""

        for i in range(structure_pages_count):
            page_info = pages_index['pages'][i]
            page_file = raw_pages_dir / page_info['file']

            with open(page_file, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                sanitized = self._sanitize_text_for_api(raw_text)
                toc_content += f"\n\n--- PAGE {page_info['page']} ---\n"
                toc_content += sanitized

        prompt = f"""You are analyzing the beginning pages of a book to extract its structure.

BOOK PAGES 1-{structure_pages_count}:
{toc_content}

TASK:
Analyze these pages and extract the book's structure (table of contents).
Most books describe their structure in first 10-15 pages with parts and chapters.

RESPOND IN JSON FORMAT:
{{
  "has_structure": true/false,
  "has_parts": true/false,
  "parts": [
    {{
      "number": 1,
      "title": "Part One: Fundamental Techniques In Handling People",
      "start_page": 11
    }}
  ],
  "chapters": [
    {{
      "number": 1,
      "title": "If you want to gather honey, don't kick over the beehive",
      "start_page": 11,
      "part_number": 1
    }},
    {{
      "number": 2,
      "title": "The big secret of dealing with people",
      "start_page": 18,
      "part_number": 1
    }}
  ]
}}

STRUCTURE DETECTION RULES:
- Look for "Contents", "Table of Contents", "فہرست" (Urdu), "Index"
- Detect Parts: "Part One", "Part 1", "PART I", "حصہ اول", "قسم اول"
- Detect Chapters: "Chapter 1", "Ch 1", "باب اول", "فصل اول"
- Extract page numbers (look for numbers at end of lines)
- If book has no parts, set has_parts=false and part_number=null for all chapters
- If no clear structure found, set has_structure=false

IMPORTANT:
- Extract EXACT titles as written in the book
- Page numbers are critical - extract them accurately
- If Urdu/Arabic content, preserve RTL text
- Return ONLY valid JSON, no explanation"""

        try:
            time.sleep(5)  # Small delay for structure extraction

            # Use lenient safety settings for structure extraction too
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            print(f"  📖 Processing first 15 pages for structure (filters: DISABLED)")

            response = self.gemini_model.generate_content(prompt, safety_settings=safety_settings)
            result_text = response.text.strip()

            # Extract JSON from markdown
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            structure = json.loads(result_text)

            # Validate structure
            if not structure.get('has_structure'):
                print("  ⚠ No clear structure detected in first pages")
                return None

            print(f"  ✓ Structure detected:")
            print(f"    Parts: {len(structure.get('parts', []))}")
            print(f"    Chapters: {len(structure.get('chapters', []))}")

            return structure

        except Exception as e:
            print(f"  ⚠ Structure extraction failed: {e}")
            print("  Falling back to dynamic chapter detection...")
            return None

    def _create_folder_structure(self, output_dir: Path):
        """
        Create folder structure based on detected book structure

        Args:
            output_dir: Base output directory
        """
        if not self.book_structure:
            return

        chapters_dir = output_dir / 'chapters'
        chapters_dir.mkdir(exist_ok=True)

        # Create folders based on structure
        if self.book_structure.get('has_parts'):
            # Create part folders
            for part in self.book_structure.get('parts', []):
                part_num = part['number']
                part_title = self._sanitize_name(part['title'])
                part_folder = chapters_dir / f"part_{part_num:02d}_{part_title}"
                part_folder.mkdir(exist_ok=True)
                print(f"  📁 Created: {part_folder.name}")

    def _get_chapter_info_for_page(self, page_num: int, page_content: str) -> Dict:
        """
        Determine which chapter/part this page belongs to

        Args:
            page_num: Page number
            page_content: Cleaned page content

        Returns:
            {'part_num': int or None, 'chapter_num': int, 'chapter_title': str, 'is_start': bool}
        """
        if not self.book_structure:
            return None

        # Find chapter by page number
        for chapter in self.book_structure.get('chapters', []):
            chapter_start = chapter.get('start_page')

            # Check if this page could be the start of this chapter
            if chapter_start and abs(page_num - chapter_start) <= 2:
                # This might be the chapter start, verify with content
                return {
                    'part_num': chapter.get('part_number'),
                    'chapter_num': chapter['number'],
                    'chapter_title': chapter['title'],
                    'is_start': True
                }

        # If not a start page, find which chapter range we're in
        for i, chapter in enumerate(self.book_structure.get('chapters', [])):
            next_chapter_start = None
            if i + 1 < len(self.book_structure['chapters']):
                next_chapter_start = self.book_structure['chapters'][i + 1].get('start_page')

            chapter_start = chapter.get('start_page', 0)

            if next_chapter_start:
                if chapter_start <= page_num < next_chapter_start:
                    return {
                        'part_num': chapter.get('part_number'),
                        'chapter_num': chapter['number'],
                        'chapter_title': chapter['title'],
                        'is_start': False
                    }
            else:
                # Last chapter - extends to end of book
                if page_num >= chapter_start:
                    return {
                        'part_num': chapter.get('part_number'),
                        'chapter_num': chapter['number'],
                        'chapter_title': chapter['title'],
                        'is_start': False
                    }

        return None

    def _get_or_create_chapter_file(self, output_dir: Path, part_num: int,
                                    chapter_num: int, chapter_title: str) -> object:
        """
        Get or create file handle for a chapter (opens in append mode)

        Args:
            output_dir: Base output directory
            part_num: Part number (or None)
            chapter_num: Chapter number
            chapter_title: Chapter title

        Returns:
            Open file handle
        """
        chapter_id = f"part{part_num}_ch{chapter_num}" if part_num else f"ch{chapter_num}"

        # Return existing handle if already open
        if chapter_id in self.chapter_files:
            return self.chapter_files[chapter_id]

        # Create new file
        chapters_dir = output_dir / 'chapters'

        if part_num and self.book_structure.get('has_parts'):
            # Find part title
            part_title = "Unknown_Part"
            for part in self.book_structure.get('parts', []):
                if part['number'] == part_num:
                    part_title = self._sanitize_name(part['title'])
                    break

            part_folder = chapters_dir / f"part_{part_num:02d}_{part_title}"
            part_folder.mkdir(exist_ok=True)
            chapter_file = part_folder / f"chapter_{chapter_num:02d}_{self._sanitize_name(chapter_title)}.txt"
        else:
            chapter_file = chapters_dir / f"chapter_{chapter_num:02d}_{self._sanitize_name(chapter_title)}.txt"

        # Open in append mode (or write mode if new)
        mode = 'a' if chapter_file.exists() else 'w'
        file_handle = open(chapter_file, mode, encoding='utf-8-sig')

        # Write header if new file
        if mode == 'w':
            file_handle.write(f"{chapter_title}\n")
            file_handle.write("=" * 60 + "\n\n")
            print(f"  📝 Created: {chapter_file.name}")

        self.chapter_files[chapter_id] = file_handle
        return file_handle

    def _close_all_chapter_files(self):
        """Close all open chapter file handles"""
        for file_handle in self.chapter_files.values():
            file_handle.close()
        self.chapter_files = {}

    def _save_structure_json(self, output_dir: Path, book_name: str):
        """
        Save the detected structure to JSON file

        Args:
            output_dir: Output directory
            book_name: Book name
        """
        if not self.book_structure:
            return

        structure_file = output_dir / f"{book_name}_structure.json"
        with open(structure_file, 'w', encoding='utf-8') as f:
            json.dump(self.book_structure, f, indent=2, ensure_ascii=False)

        print(f"  💾 Saved: {structure_file.name}")

    def _process_batch_with_gemini(self, batch_pages: List[Dict]) -> Dict:
        """
        Process a batch of pages with Gemini

        Args:
            batch_pages: List of {page_num, raw_text}

        Returns:
            {
                'pages': [
                    {
                        'page': int,
                        'cleaned_content': str,
                        'new_chapter_starts': bool,
                        'chapter_title': str or None
                    }
                ]
            }
        """
        # Build batch content with sanitization
        batch_content = ""
        total_original_chars = 0
        total_sanitized_chars = 0

        print(f"\n  🔧 Sanitizing {len(batch_pages)} pages...")
        for i, page_data in enumerate(batch_pages):
            original_text = page_data['raw_text']
            total_original_chars += len(original_text)

            # Log issues only for first page to avoid spam
            log_issues = (i == 0)
            sanitized_text = self._sanitize_text_for_api(original_text, log_issues=log_issues)
            total_sanitized_chars += len(sanitized_text)

            batch_content += f"\n\n--- PAGE {page_data['page']} ---\n"
            batch_content += sanitized_text

        chars_removed = total_original_chars - total_sanitized_chars
        if chars_removed > 0:
            print(f"  🧹 Total sanitization: {chars_removed} chars removed from {len(batch_pages)} pages")
        else:
            print(f"  ✓ No problematic characters found in batch")

        print(f"  📤 Batch content size: {len(batch_content):,} characters")
        print(f"  📄 Average per page: {len(batch_content) // len(batch_pages):,} chars")

        prompt = f"""You are an expert book content analyzer. Analyze these {len(batch_pages)} pages and clean them.

{batch_content}

TASK:
1. Remove all noise from each page (watermarks, URLs, social media, page numbers, website names, headers, footers)
2. Detect if any page starts a new CHAPTER (باب/Chapter)
3. Extract only meaningful book content
4. Preserve original language and formatting (Urdu right-to-left, Arabic, English)

RESPOND IN JSON FORMAT - Array of pages:
{{
  "pages": [
    {{
      "page": 1,
      "cleaned_content": "The clean text without noise",
      "new_chapter_starts": true/false,
      "chapter_title": "Chapter title in original language" or null
    }},
    {{
      "page": 2,
      "cleaned_content": "...",
      "new_chapter_starts": false,
      "chapter_title": null
    }}
    ... (continue for all {len(batch_pages)} pages)
  ]
}}

RULES FOR NOISE REMOVAL:
- Remove: www.*, http*, facebook, twitter, instagram, WhatsApp, social media
- Remove: "BestUrduNovels", "UrduNovels", website watermarks
- Remove: Page numbers (صفحہ، Page, ص، پیج، page)
- Remove: Headers/footers that repeat on multiple pages
- Keep: Chapter titles, book content, dialogue, poetry, paragraphs

CHAPTER DETECTION PATTERNS:
Urdu: "باب اول", "باب دوم", "پہلا باب", "فصل اول"
English: "Chapter 1", "Chapter One", "CHAPTER I", "Ch 1"

IMPORTANT:
- Extract FULL chapter title (e.g., "Chapter 1: Introduction" or "باب اول: محبت")
- Preserve Urdu/Arabic text direction and formatting
- Keep poetry indentation intact
- Return ONLY valid JSON, no explanation
- Process ALL {len(batch_pages)} pages in order"""

        try:
            print(f"  ⏳ Processing batch with Gemini (pages {batch_pages[0]['page']}-{batch_pages[-1]['page']})...", end='\r')
            time.sleep(10)  # Rate limit delay

            # Configure generation settings for more reliable JSON
            # Gemini 2.5 Flash supports up to 8192 output tokens
            generation_config = {
                'temperature': 0.1,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 8192,  # Maximum for Gemini 2.5 Flash
            }

            # Safety settings - Allow all content types for book processing
            # Books may contain sensitive topics, violence, etc. which we need to process
            from google.generativeai.types import HarmCategory, HarmBlockThreshold

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            print(f"  🛡️  Safety filters: DISABLED (processing book content)")

            # Estimate required tokens (rough estimate: 1 token ≈ 4 chars)
            estimated_output_chars = len(batch_content) * 0.8  # Cleaned content is usually 80% of input
            estimated_tokens = estimated_output_chars / 4
            print(f"  🔢 Estimated output: ~{int(estimated_tokens):,} tokens (limit: 8,192)")

            if estimated_tokens > 7500:
                print(f"  ⚠️  Warning: Output may be truncated. Consider reducing --batch-size")

            response = self.gemini_model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Check response status before accessing text
            print(f"\n  📊 Gemini response received")

            # Log finish reason and safety ratings
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason
                finish_reason_names = {
                    0: "FINISH_REASON_UNSPECIFIED",
                    1: "STOP (Natural stop)",
                    2: "MAX_TOKENS (Output limit reached)",
                    3: "SAFETY (Content filtered)",
                    4: "RECITATION (Copyright content)",
                    5: "OTHER"
                }
                finish_reason_name = finish_reason_names.get(finish_reason, f"UNKNOWN({finish_reason})")
                print(f"  🏁 Finish reason: {finish_reason_name}")

                # Check if response was blocked or incomplete
                if finish_reason == 2:  # MAX_TOKENS
                    print(f"  ⚠️  WARNING: Response hit maximum token limit!")
                    print(f"     Output was truncated. Trying to parse partial response...")
                elif finish_reason == 3:  # SAFETY
                    print(f"  ❌ ERROR: Response blocked by safety filters!")
                    if hasattr(candidate, 'safety_ratings'):
                        print(f"     Safety ratings:")
                        for rating in candidate.safety_ratings:
                            print(f"       - {rating.category}: {rating.probability}")
                    print(f"  🔄 Falling back to individual page processing...")
                    return self._process_pages_individually(batch_pages)
                elif finish_reason == 4:  # RECITATION
                    print(f"  ❌ ERROR: Response blocked due to recitation (copyright content)!")
                    print(f"  🔄 Falling back to individual page processing...")
                    return self._process_pages_individually(batch_pages)
                elif finish_reason not in [0, 1]:  # Not normal completion
                    print(f"  ⚠️  Unexpected finish reason: {finish_reason_name}")

            # Try to get response text
            try:
                result_text = response.text.strip()
                print(f"  📝 Response text: {len(result_text)} characters")
            except ValueError as ve:
                print(f"  ❌ ERROR: Cannot access response.text: {ve}")
                print(f"  📋 Response details:")
                print(f"     Candidates: {len(response.candidates) if response.candidates else 0}")
                if response.candidates:
                    candidate = response.candidates[0]
                    print(f"     Finish reason: {candidate.finish_reason}")
                    print(f"     Has content: {hasattr(candidate, 'content')}")
                    if hasattr(candidate, 'content') and candidate.content:
                        print(f"     Parts: {len(candidate.content.parts) if hasattr(candidate.content, 'parts') else 0}")

                print(f"  🔄 Falling back to individual page processing...")
                return self._process_pages_individually(batch_pages)
            except Exception as e:
                print(f"  ❌ ERROR: Unexpected error accessing response: {e}")
                print(f"  🔄 Falling back to individual page processing...")
                return self._process_pages_individually(batch_pages)

            # Extract JSON from markdown if needed
            original_length = len(result_text)
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
                print(f"  🔧 Extracted from ```json block: {len(result_text)} chars")
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
                print(f"  🔧 Extracted from ``` block: {len(result_text)} chars")
            else:
                print(f"  📝 No markdown blocks found, using raw response")

            # Try to fix common JSON issues
            result_text = result_text.replace('\n', ' ').replace('\r', '')
            # Remove any trailing commas before closing braces/brackets
            result_text = re.sub(r',(\s*[}\]])', r'\1', result_text)

            print(f"  🧹 After cleanup: {len(result_text)} characters")

            # Save the response for debugging
            debug_file = Path(f"/tmp/gemini_response_batch_{batch_pages[0]['page']}-{batch_pages[-1]['page']}.json")
            try:
                with open(debug_file, 'w', encoding='utf-8') as df:
                    df.write(result_text)
                print(f"  💾 Debug: Saved response to {debug_file}")
            except Exception as e:
                print(f"  ⚠ Could not save debug file: {e}")

            # Try to parse JSON
            try:
                result = json.loads(result_text)
                print(f"  ✅ JSON parsed successfully: {len(result.get('pages', []))} pages")
            except json.JSONDecodeError as json_err:
                print(f"\n  ❌ JSON parsing failed: {json_err}")
                print(f"  📍 Error at position: {json_err.pos}")
                print(f"  📄 Error line: {json_err.lineno}, column: {json_err.colno}")

                # Show context around error
                error_pos = json_err.pos
                context_start = max(0, error_pos - 100)
                context_end = min(len(result_text), error_pos + 100)
                context = result_text[context_start:context_end]

                print(f"  🔍 Context around error:")
                print(f"     ...{context}...")

                # Check for common issues
                brace_balance = result_text.count('{') - result_text.count('}')
                bracket_balance = result_text.count('[') - result_text.count(']')

                if brace_balance != 0:
                    print(f"  ⚠ Unbalanced braces: {{ count={result_text.count('{')} }} count={result_text.count('}')} (diff={brace_balance})")
                if bracket_balance != 0:
                    print(f"  ⚠ Unbalanced brackets: [ count={result_text.count('[')} ] count={result_text.count(']')} (diff={bracket_balance})")

                # Try to repair common issues
                print(f"  🔧 Attempting JSON repair...")
                repaired = False

                # Try 1: Add missing closing braces/brackets
                if brace_balance > 0 or bracket_balance > 0:
                    repair_text = result_text
                    if bracket_balance > 0:
                        repair_text += ']' * bracket_balance
                        print(f"     Added {bracket_balance} closing bracket(s)")
                    if brace_balance > 0:
                        repair_text += '}' * brace_balance
                        print(f"     Added {brace_balance} closing brace(s)")

                    try:
                        result = json.loads(repair_text)
                        print(f"  ✅ JSON repaired and parsed successfully!")
                        repaired = True
                    except json.JSONDecodeError:
                        print(f"     Repair attempt failed")

                # Try 2: Truncate at last valid JSON closing
                if not repaired:
                    print(f"  🔧 Trying truncation approach...")
                    # Find the last complete "page" object
                    last_page_end = result_text.rfind('}')
                    if last_page_end > 0:
                        truncated = result_text[:last_page_end + 1]
                        # Check if we need to close the pages array and main object
                        if truncated.count('[') > truncated.count(']'):
                            truncated += ']'
                        if truncated.count('{') > truncated.count('}'):
                            truncated += '}'

                        try:
                            result = json.loads(truncated)
                            print(f"  ✅ JSON truncated and parsed (may have incomplete pages)")
                            repaired = True
                        except json.JSONDecodeError:
                            print(f"     Truncation failed")

                if not repaired:
                    print(f"  🔄 All repair attempts failed, processing pages individually...")
                    return self._process_pages_individually(batch_pages)

            # Validate response structure
            if 'pages' not in result or not isinstance(result['pages'], list):
                print(f"\n  ⚠ Invalid response structure, falling back to individual processing")
                return self._process_pages_individually(batch_pages)

            # Check if we got all pages
            received_pages = len(result['pages'])
            expected_pages = len(batch_pages)

            if received_pages < expected_pages:
                print(f"\n  ⚠ Incomplete response: {received_pages}/{expected_pages} pages received")

                # If we got less than half, better to reprocess all
                if received_pages < expected_pages * 0.5:
                    print(f"  🔄 Too many missing pages, processing individually...")
                    return self._process_pages_individually(batch_pages)

                # Otherwise, process only the missing pages
                print(f"  🔧 Processing {expected_pages - received_pages} missing pages individually...")
                result = self._fill_missing_pages(result, batch_pages)
            else:
                print(f"  ✓ All {expected_pages} pages received")

            return result

        except Exception as e:
            print(f"\n  ⚠ Gemini processing failed for batch: {e}")
            print(f"  Processing pages individually as fallback...")
            return self._process_pages_individually(batch_pages)

    def _process_pages_individually(self, batch_pages: List[Dict]) -> Dict:
        """
        Fallback: Process pages one at a time when batch processing fails

        Args:
            batch_pages: List of {page_num, raw_text}

        Returns:
            Same format as _process_batch_with_gemini
        """
        print(f"\n  Processing {len(batch_pages)} pages individually...")
        results = []

        for page_data in batch_pages:
            # Sanitize text before sending to API
            sanitized_text = self._sanitize_text_for_api(page_data['raw_text'])

            prompt = f"""Clean this page and detect chapter start.

PAGE {page_data['page']}:
{sanitized_text}

Remove: watermarks, URLs, page numbers, social media, headers/footers
Detect: Chapter starts (باب/Chapter patterns)

RESPOND IN JSON:
{{
  "page": {page_data['page']},
  "cleaned_content": "clean text",
  "new_chapter_starts": true/false,
  "chapter_title": "title" or null
}}"""

            try:
                time.sleep(2)  # Small delay between individual pages

                # Use same safety settings as batch processing
                from google.generativeai.types import HarmCategory, HarmBlockThreshold
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }

                response = self.gemini_model.generate_content(prompt, safety_settings=safety_settings)

                # Check response status
                if response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = candidate.finish_reason

                    if finish_reason == 2:  # MAX_TOKENS
                        print(f"\n    ⚠ Page {page_data['page']}: Response truncated (MAX_TOKENS)")
                    elif finish_reason == 3:  # SAFETY
                        print(f"\n    ⚠ Page {page_data['page']}: Blocked by safety filters")
                        # Use raw content as fallback
                        results.append({
                            'page': page_data['page'],
                            'cleaned_content': page_data['raw_text'],
                            'new_chapter_starts': False,
                            'chapter_title': None
                        })
                        continue
                    elif finish_reason == 4:  # RECITATION
                        print(f"\n    ⚠ Page {page_data['page']}: Blocked (copyright content)")
                        results.append({
                            'page': page_data['page'],
                            'cleaned_content': page_data['raw_text'],
                            'new_chapter_starts': False,
                            'chapter_title': None
                        })
                        continue

                # Try to get response text
                try:
                    result_text = response.text.strip()
                except ValueError as ve:
                    print(f"\n    ⚠ Page {page_data['page']}: Cannot access response.text (finish_reason: {candidate.finish_reason})")
                    results.append({
                        'page': page_data['page'],
                        'cleaned_content': page_data['raw_text'],
                        'new_chapter_starts': False,
                        'chapter_title': None
                    })
                    continue

                # Extract JSON
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0].strip()
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0].strip()

                page_result = json.loads(result_text)
                results.append(page_result)
                print(f"    ✓ Page {page_data['page']} processed", end='\r')

            except json.JSONDecodeError as je:
                print(f"\n    ⚠ Page {page_data['page']}: JSON parsing failed - {je}")
                # Use raw content as fallback
                results.append({
                    'page': page_data['page'],
                    'cleaned_content': page_data['raw_text'],
                    'new_chapter_starts': False,
                    'chapter_title': None
                })
            except Exception as e:
                print(f"\n    ⚠ Page {page_data['page']}: Unexpected error - {e}")
                # Use raw content as fallback
                results.append({
                    'page': page_data['page'],
                    'cleaned_content': page_data['raw_text'],
                    'new_chapter_starts': False,
                    'chapter_title': None
                })

        return {'pages': results}

    def _fill_missing_pages(self, result: Dict, batch_pages: List[Dict]) -> Dict:
        """
        Fill in any missing pages in the result by processing them individually

        Args:
            result: Partial result from Gemini
            batch_pages: Original batch pages

        Returns:
            Complete result with all pages
        """
        received_pages = {p['page']: p for p in result['pages']}
        missing_pages = []

        # Identify missing pages
        for page_data in batch_pages:
            page_num = page_data['page']
            if page_num not in received_pages:
                missing_pages.append(page_data)

        # Process missing pages individually with Gemini
        if missing_pages:
            print(f"     Processing {len(missing_pages)} missing pages: {[p['page'] for p in missing_pages]}")
            missing_result = self._process_pages_individually(missing_pages)

            # Merge results
            for page_result in missing_result['pages']:
                received_pages[page_result['page']] = page_result

        # Build complete ordered result
        complete_pages = []
        for page_data in batch_pages:
            page_num = page_data['page']
            if page_num in received_pages:
                complete_pages.append(received_pages[page_num])
            else:
                # Fallback if individual processing also failed
                print(f"     ⚠ Page {page_num} still missing, using raw content")
                complete_pages.append({
                    'page': page_num,
                    'cleaned_content': page_data['raw_text'],
                    'new_chapter_starts': False,
                    'chapter_title': None
                })

        return {'pages': complete_pages}

    def _sanitize_name(self, name: str) -> str:
        """Convert title to safe folder name (supports Urdu/Arabic)"""
        name = name[:80]  # Longer limit for Urdu titles
        name = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove filesystem-unsafe chars
        name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
        name = name.strip('_')
        return name if name else 'untitled'

    def format_book(self, raw_pages_dir: str) -> Dict:
        """
        Format book from raw OCR pages with real-time file writing
        Uses structure from table of contents when available

        Args:
            raw_pages_dir: Directory containing raw_pages/ and pages_index.json
        """
        raw_pages_dir = Path(raw_pages_dir)
        if not raw_pages_dir.exists():
            raise FileNotFoundError(f"Directory not found: {raw_pages_dir}")

        # Load pages index
        index_file = raw_pages_dir / 'pages_index.json'
        if not index_file.exists():
            raise FileNotFoundError(f"pages_index.json not found in {raw_pages_dir}")

        with open(index_file, 'r', encoding='utf-8') as f:
            pages_index = json.load(f)

        book_name = raw_pages_dir.name
        total_pages = pages_index['total_pages']

        print(f"\n📚 Formatting book: {book_name}")
        print(f"📁 Source: {raw_pages_dir}/")

        # STEP 1: Extract book structure from first pages
        print(f"\n📖 STEP 1: Analyzing book structure...")
        self.book_structure = self._extract_book_structure(raw_pages_dir, pages_index)

        # STEP 2: Save structure JSON immediately
        if self.book_structure:
            self._save_structure_json(raw_pages_dir, book_name)
            self._create_folder_structure(raw_pages_dir)
            print(f"\n📂 Structure-based processing mode")
        else:
            print(f"\n📄 Dynamic chapter detection mode")
            # Create chapters directory even without structure
            chapters_dir = raw_pages_dir / 'chapters'
            chapters_dir.mkdir(exist_ok=True)

        print(f"\n🔍 STEP 2: Processing {total_pages} pages with dynamic batching (initial size: {self.batch_size})")

        # Track current chapter
        current_chapter_info = None
        chapters_metadata = []  # Track chapter info for final metadata
        current_batch_size = self.batch_size

        try:
            # STEP 3: Process pages in batches and write files in real-time
            batch_start = 0
            while batch_start < total_pages:
                # Read initial batch
                initial_batch_end = min(batch_start + current_batch_size, total_pages)
                batch_pages = []

                for i in range(batch_start, initial_batch_end):
                    page_info = pages_index['pages'][i]
                    page_file = raw_pages_dir / page_info['file']

                    with open(page_file, 'r', encoding='utf-8') as f:
                        raw_text = f.read()

                    batch_pages.append({
                        'page': page_info['page'],
                        'raw_text': raw_text
                    })

                # Check if we need to adjust batch size
                adjusted_size = self._adjust_batch_size(batch_pages, len(batch_pages))

                # If batch needs to be smaller, re-read with adjusted size
                if adjusted_size < len(batch_pages):
                    batch_pages = batch_pages[:adjusted_size]
                    current_batch_size = adjusted_size  # Update for next iteration

                batch_end = batch_pages[-1]['page']

                # Process batch with Gemini
                result = self._process_batch_with_gemini(batch_pages)

                # Move to next batch
                batch_start = initial_batch_end if adjusted_size == len(batch_pages) else (batch_start + adjusted_size)

                # STEP 4: Write content to files in real-time
                for page_result in result['pages']:
                    page_num = page_result['page']
                    cleaned_content = page_result['cleaned_content']

                    if not cleaned_content.strip():
                        continue

                    # Determine which chapter this page belongs to
                    if self.book_structure:
                        # Use structure-based detection
                        chapter_info = self._get_chapter_info_for_page(page_num, cleaned_content)

                        if chapter_info:
                            # Check if we need to switch to a new chapter
                            if not current_chapter_info or chapter_info['chapter_num'] != current_chapter_info['chapter_num']:
                                current_chapter_info = chapter_info

                                # Track chapter metadata
                                chapters_metadata.append({
                                    'chapter_num': chapter_info['chapter_num'],
                                    'chapter_title': chapter_info['chapter_title'],
                                    'part_num': chapter_info.get('part_num'),
                                    'start_page': page_num
                                })

                                print(f"\n  📖 Chapter {chapter_info['chapter_num']}: {chapter_info['chapter_title']}")

                            # Get or create chapter file and write content
                            file_handle = self._get_or_create_chapter_file(
                                raw_pages_dir,
                                chapter_info.get('part_num'),
                                chapter_info['chapter_num'],
                                chapter_info['chapter_title']
                            )
                            file_handle.write(cleaned_content + "\n\n")
                            file_handle.flush()  # Ensure it's written immediately

                    else:
                        # Use dynamic chapter detection (old behavior)
                        if page_result.get('new_chapter_starts') and page_result.get('chapter_title'):
                            # New chapter detected dynamically
                            new_chapter_num = (current_chapter_info['chapter_num'] + 1) if current_chapter_info else 1
                            current_chapter_info = {
                                'chapter_num': new_chapter_num,
                                'chapter_title': page_result['chapter_title'],
                                'part_num': None
                            }

                            chapters_metadata.append({
                                'chapter_num': new_chapter_num,
                                'chapter_title': page_result['chapter_title'],
                                'part_num': None,
                                'start_page': page_num
                            })

                            print(f"\n  📖 Chapter {new_chapter_num}: {page_result['chapter_title']}")

                        if not current_chapter_info:
                            # Default to first chapter if none detected yet
                            current_chapter_info = {
                                'chapter_num': 1,
                                'chapter_title': 'Introduction',
                                'part_num': None
                            }

                        # Write to chapter file
                        file_handle = self._get_or_create_chapter_file(
                            raw_pages_dir,
                            current_chapter_info.get('part_num'),
                            current_chapter_info['chapter_num'],
                            current_chapter_info['chapter_title']
                        )
                        file_handle.write(cleaned_content + "\n\n")
                        file_handle.flush()

                # Show progress with actual processed pages
                actual_batch_end = batch_pages[-1]['page']
                print(f"  ✓ Processed pages {batch_pages[0]['page']}-{actual_batch_end}/{total_pages}", end='\r')

        finally:
            # Close all open file handles
            self._close_all_chapter_files()

        print(f"\n\n  ✓ Gemini formatting completed for {total_pages} pages")
        print(f"  📖 Created {len(chapters_metadata)} chapter files")

        if self.batch_adjustments > 0:
            print(f"  📊 Batch size auto-adjusted {self.batch_adjustments} times due to content density")

        # STEP 5: Generate final metadata and summary files
        self._generate_final_files(raw_pages_dir, book_name, chapters_metadata, pages_index)

        return {
            'success': True,
            'book_name': book_name,
            'total_pages': total_pages,
            'total_chapters': len(chapters_metadata)
        }

    def _generate_final_files(self, output_dir: Path, book_name: str,
                             chapters_metadata: List[Dict], original_index: Dict):
        """
        Generate final summary files: book_structure.txt, complete text, and metadata

        Args:
            output_dir: Output directory
            book_name: Book name
            chapters_metadata: List of chapter metadata
            original_index: Original pages index
        """
        print(f"\n  📄 Generating summary files...")

        chapters_dir = output_dir / 'chapters'

        # Generate book_structure.txt
        structure_file = output_dir / 'book_structure.txt'

        # Check if content is Urdu/Arabic
        has_rtl = any(
            any('\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' or '\uFB50' <= c <= '\uFDFF'
                for c in ch['chapter_title'])
            for ch in chapters_metadata
        )

        with open(structure_file, 'w', encoding='utf-8-sig') as f:
            if has_rtl:
                f.write("فہرست (Contents)\n")
            else:
                f.write("Contents\n")
            f.write("=" * 60 + "\n\n")

            # Group by parts if available
            if self.book_structure and self.book_structure.get('has_parts'):
                current_part = None
                for chapter in chapters_metadata:
                    if chapter.get('part_num') != current_part:
                        current_part = chapter['part_num']
                        # Find part title
                        for part in self.book_structure.get('parts', []):
                            if part['number'] == current_part:
                                f.write(f"\n{part['title']}\n")
                                f.write("-" * 40 + "\n")
                                break

                    f.write(f"  Chapter {chapter['chapter_num']}: {chapter['chapter_title']} (Page {chapter['start_page']})\n")
            else:
                for chapter in chapters_metadata:
                    f.write(f"Chapter {chapter['chapter_num']}: {chapter['chapter_title']} (Page {chapter['start_page']})\n")

            if has_rtl:
                f.write("\nفہرست ختم۔\n")
            else:
                f.write("\nContent end.\n")

        print(f"  ✓ Saved: book_structure.txt")

        # Generate complete book file by reading all chapter files
        complete_file = output_dir / f"{book_name}_complete.txt"
        with open(complete_file, 'w', encoding='utf-8-sig') as complete_f:
            for chapter in chapters_metadata:
                # Find the actual chapter file
                chapter_name = self._sanitize_name(chapter['chapter_title'])

                if chapter.get('part_num') and self.book_structure and self.book_structure.get('has_parts'):
                    # Find part folder
                    for part in self.book_structure.get('parts', []):
                        if part['number'] == chapter['part_num']:
                            part_title = self._sanitize_name(part['title'])
                            part_folder = chapters_dir / f"part_{chapter['part_num']:02d}_{part_title}"
                            chapter_file = part_folder / f"chapter_{chapter['chapter_num']:02d}_{chapter_name}.txt"
                            break
                else:
                    chapter_file = chapters_dir / f"chapter_{chapter['chapter_num']:02d}_{chapter_name}.txt"

                # Read and append chapter content
                if chapter_file.exists():
                    with open(chapter_file, 'r', encoding='utf-8-sig') as cf:
                        content = cf.read()
                        complete_f.write(content)
                        complete_f.write("\n\n")

        print(f"  ✓ Saved: {book_name}_complete.txt")

        # Generate metadata JSON
        metadata = {
            'source': original_index.get('source'),
            'book_name': book_name,
            'extraction_method': 'Google Cloud Vision API + Gemini 2.5 Flash Real-time Formatting',
            'total_pages': original_index['total_pages'],
            'original_avg_confidence': original_index.get('avg_confidence'),
            'total_chapters': len(chapters_metadata),
            'has_structure': self.book_structure is not None,
            'has_parts': self.book_structure.get('has_parts', False) if self.book_structure else False,
            'chapters': [
                {
                    'chapter_number': ch['chapter_num'],
                    'title': ch['chapter_title'],
                    'part_number': ch.get('part_num'),
                    'start_page': ch['start_page']
                }
                for ch in chapters_metadata
            ]
        }

        if self.book_structure:
            metadata['parts'] = self.book_structure.get('parts', [])

        metadata_file = output_dir / f"{book_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Saved: {book_name}_metadata.json")

        print(f"\n  ✅ Formatting complete!")
        print(f"  📁 Output: {output_dir}/")
        print(f"  📂 Chapters: {len(chapters_metadata)} chapter files in chapters/")
        print(f"  📄 Book structure: book_structure.txt")
        print(f"  📊 Metadata: {book_name}_metadata.json")
        print(f"  📝 Complete text: {book_name}_complete.txt")

    def _save_formatted_results(self, output_dir: Path, book_name: str,
                               all_pages: List[Dict], original_index: Dict):
        """DEPRECATED: Old method - kept for compatibility"""

        # Create chapters folder
        chapters_dir = output_dir / 'chapters'
        chapters_dir.mkdir(exist_ok=True)

        # Save each chapter as ONE file
        chapter_list = []
        for chapter_num, chapter_data in self.chapters_content.items():
            chapter_title = chapter_data['title']
            chapter_content = chapter_data['content']

            # Sanitize chapter name
            chapter_name = self._sanitize_name(chapter_title)
            chapter_file = chapters_dir / f"chapter_{chapter_num:02d}_{chapter_name}.txt"

            # Write chapter file
            with open(chapter_file, 'w', encoding='utf-8-sig') as f:
                f.write(f"{chapter_title}\n")
                f.write("=" * 60 + "\n\n")
                f.write(chapter_content)

            chapter_list.append({
                'number': chapter_num,
                'title': chapter_title,
                'file': str(chapter_file.name)
            })

            print(f"  ✓ Saved: {chapter_file.name}")

        # Generate book_structure.txt
        self._generate_book_structure(book_name, chapter_list, output_dir)

        # Save complete text
        complete_file = output_dir / f"{book_name}_complete.txt"
        with open(complete_file, 'w', encoding='utf-8-sig') as f:
            for chapter_num, chapter_data in self.chapters_content.items():
                f.write(f"\n{'='*60}\n")
                f.write(f"{chapter_data['title']}\n")
                f.write(f"{'='*60}\n\n")
                f.write(chapter_data['content'])
                f.write('\n\n')

        # Save metadata
        metadata = {
            'source': original_index.get('source'),
            'extraction_method': 'Google Cloud Vision API + Gemini 2.0 Flash Batch Formatting',
            'total_pages': len(all_pages),
            'total_characters': sum(len(p['text']) for p in all_pages),
            'original_avg_confidence': original_index.get('avg_confidence'),
            'total_chapters': len(self.chapters_content),
            'chapters': [
                {
                    'chapter_number': ch['number'],
                    'title': ch['title'],
                    'file': ch['file']
                }
                for ch in chapter_list
            ]
        }

        metadata_file = output_dir / f"{book_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n  ✓ Formatting complete!")
        print(f"  📁 Output: {output_dir}/")
        print(f"  📖 Chapters: {len(self.chapters_content)} chapter files created")
        print(f"  📄 Book structure: book_structure.txt")
        print(f"  📊 Metadata: {metadata_file.name}")
        print(f"  📝 Complete text: {complete_file.name}")

    def _generate_book_structure(self, book_name: str, chapter_list: List[Dict], output_dir: Path):
        """Generate book_structure.txt file"""
        structure_file = output_dir / 'book_structure.txt'

        # Check if content is Urdu/Arabic
        has_rtl = any(
            any('\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' or '\uFB50' <= c <= '\uFDFF'
                for c in ch['title'])
            for ch in chapter_list
        )

        with open(structure_file, 'w', encoding='utf-8-sig') as f:
            if has_rtl:
                f.write("فہرست (Contents)\n")
            else:
                f.write("Contents\n")
            f.write("=" * 60 + "\n\n")

            for chapter in chapter_list:
                f.write(f"Chapter {chapter['number']}: {chapter['title']}\n")

            if has_rtl:
                f.write("\nفہرست ختم۔\n")
            else:
                f.write("\nContent end.\n")


def main():
    """Main function with CLI"""
    if len(sys.argv) < 2:
        print("Book Formatter with Gemini AI (Structure-Aware Real-Time Processing)")
        print("=" * 60)
        print("\nCleans and organizes raw OCR text into structured book format")
        print("  - Extracts book structure from table of contents")
        print("  - Dynamic batch sizing (default: 5, auto-adjusts if needed)")
        print("  - Writes chapter files in real-time")
        print("  - Removes watermarks, URLs, page numbers")
        print("  - Supports parts and chapters organization")
        print("\nSetup:")
        print("1. Install: pip install -r requirements_google.txt")
        print("2. Create .env file with GOOGLE_API_KEY")
        print("3. Get Gemini API key from https://aistudio.google.com/apikey")
        print("\nUsage:")
        print("  python book_formatter.py <extracted_book_dir>")
        print("  python book_formatter.py <extracted_book_dir> --batch-size 10")
        print("  python book_formatter.py <extracted_book_dir> --gemini-key YOUR_KEY")
        print("\nDynamic Batch Sizing:")
        print("  - Default: 5 pages per batch (safe for most books)")
        print("  - Automatically reduces if pages are too dense")
        print("  - Target: ~7,000 tokens per batch (Gemini limit: 8,192)")
        print("  - Minimum: 3 pages per batch")
        print("  - You can increase with --batch-size for lighter content")
        print("\nExamples:")
        print("  python book_formatter.py extracted_google/my_book")
        print("  python book_formatter.py extracted_google/dense_book --batch-size 10")
        print("\nOutput:")
        print("  book_name_structure.json       # Saved immediately after detection")
        print("  chapters/")
        print("    part_01_Introduction/")
        print("      chapter_01_Title.txt       # Written in real-time")
        print("      chapter_02_Title.txt")
        print("  book_structure.txt             # Human-readable contents")
        print("  book_name_complete.txt         # All chapters combined")
        print("  book_name_metadata.json        # Complete metadata")
        sys.exit(0)

    raw_pages_dir = sys.argv[1]
    gemini_key = None
    batch_size = 5  # Default: 5 pages for optimal token management

    # Parse arguments
    if '--gemini-key' in sys.argv:
        idx = sys.argv.index('--gemini-key')
        if idx + 1 < len(sys.argv):
            gemini_key = sys.argv[idx + 1]

    if '--batch-size' in sys.argv:
        idx = sys.argv.index('--batch-size')
        if idx + 1 < len(sys.argv):
            batch_size = int(sys.argv[idx + 1])

    # Format book
    formatter = BookFormatter(gemini_api_key=gemini_key, batch_size=batch_size)
    formatter.format_book(raw_pages_dir)


if __name__ == "__main__":
    main()
