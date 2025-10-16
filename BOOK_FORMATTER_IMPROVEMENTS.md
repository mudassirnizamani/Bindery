# Book Formatter Improvements - Task List

## Current Issues Identified

### 1. **Chapter Content Assignment Problem**
- ✅ **Structure Detection**: Works correctly - identifies chapters and parts
- ❌ **Content Assignment**: Fails to properly assign raw page content to correct chapter files
- ❌ **Chapter Boundaries**: Doesn't accurately detect where each chapter starts/ends
- ❌ **Urdu/Arabic Support**: Poor handling of RTL text in chapter titles

### 2. **Root Cause Analysis**
The formatter correctly extracts book structure but fails at the content mapping stage because:
- Chapter detection relies on page numbers from TOC, which may be inaccurate
- No verification that detected chapter boundaries actually contain chapter titles
- Missing robust chapter title detection in page content
- Poor handling of Urdu/Arabic chapter titles during content assignment

## Proposed Solution Architecture

### Phase 1: Enhanced Structure Mapping
Create a comprehensive chapter mapping system that includes:

```json
{
  "chapter_mapping": [
    {
      "chapter_number": 1,
      "chapter_title": "ہمالیہ",
      "sanitized_title": "Himalaya",
      "folder_name": "chapter_01_Himalaya",
      "detected_start_page": 5,
      "verified_start_page": null,
      "content_pages": [],
      "status": "pending_verification"
    }
  ]
}
```

### Phase 2: LLM-Based Chapter Boundary Detection
Use Gemini to analyze each page and determine:
- Does this page contain a chapter title?
- What is the exact chapter title?
- Is this the start of a new chapter?

### Phase 3: Content Assignment Logic
- Track current chapter being processed
- Assign all content to current chapter until new chapter title detected
- Switch to new chapter file when new title found
- Maintain chapter content continuity

## Detailed Task List

### Task 1: Enhanced Structure JSON Creation
**Priority**: High
**Estimated Time**: 2-3 hours

**Requirements**:
- [ ] Create `book_structure_detailed.json` with comprehensive chapter mapping
- [ ] Include sanitized titles for folder creation
- [ ] Add verification status for each chapter
- [ ] Support both English and Urdu/Arabic titles

**Implementation**:
```python
def _create_detailed_structure_mapping(self, book_structure):
    """Create detailed chapter mapping with sanitized names"""
    detailed_mapping = {
        "book_info": {
            "has_parts": book_structure.get('has_parts', False),
            "total_chapters": len(book_structure.get('chapters', [])),
            "language": "urdu" if self._detect_urdu_content() else "english"
        },
        "chapters": []
    }
    
    for chapter in book_structure.get('chapters', []):
        chapter_info = {
            "chapter_number": chapter.get('number'),
            "original_title": chapter.get('title'),
            "sanitized_title": self._sanitize_name(chapter.get('title')),
            "folder_name": f"chapter_{chapter.get('number', 0):02d}_{self._sanitize_name(chapter.get('title'))}",
            "detected_start_page": chapter.get('start_page'),
            "verified_start_page": None,
            "content_pages": [],
            "status": "pending_verification"
        }
        detailed_mapping["chapters"].append(chapter_info)
    
    return detailed_mapping
```

### Task 2: LLM-Based Chapter Title Detection
**Priority**: High
**Estimated Time**: 3-4 hours

**Requirements**:
- [ ] Create function to detect chapter titles in page content
- [ ] Support Urdu/Arabic chapter title patterns
- [ ] Return JSON with chapter detection results
- [ ] Handle multiple languages in same book

**Implementation**:
```python
def _detect_chapter_title_in_page(self, page_content: str, page_num: int) -> Dict:
    """Use LLM to detect if page contains chapter title"""
    
    prompt = f"""Analyze this page content and detect if it contains a chapter title.

PAGE {page_num}:
{page_content}

TASK:
1. Check if this page contains a chapter title/header
2. Extract the exact chapter title if found
3. Determine if this is the start of a new chapter

RESPOND IN JSON:
{{
  "has_chapter_title": true/false,
  "chapter_title": "exact title" or null,
  "is_chapter_start": true/false,
  "confidence": 0.0-1.0
}}

CHAPTER TITLE PATTERNS:
Urdu: "باب اول", "باب دوم", "فصل اول", "حصہ اول"
English: "Chapter 1", "Chapter One", "CHAPTER I"
Arabic: "الفصل الأول", "الباب الأول"

IMPORTANT:
- Extract FULL chapter title including subtitle
- Preserve original language and formatting
- Return ONLY valid JSON"""
    
    # Process with Gemini and return structured result
```

### Task 3: Chapter Boundary Verification System
**Priority**: High
**Estimated Time**: 2-3 hours

**Requirements**:
- [ ] Verify detected chapter start pages actually contain chapter titles
- [ ] Adjust chapter boundaries based on LLM analysis
- [ ] Handle cases where TOC page numbers are inaccurate
- [ ] Update chapter mapping with verified information

**Implementation**:
```python
def _verify_chapter_boundaries(self, detailed_mapping: Dict) -> Dict:
    """Verify and adjust chapter boundaries using LLM analysis"""
    
    for chapter in detailed_mapping["chapters"]:
        start_page = chapter["detected_start_page"]
        
        # Check pages around detected start for actual chapter title
        for offset in range(-2, 3):  # Check 2 pages before and after
            check_page = start_page + offset
            if check_page < 1:
                continue
                
            page_content = self._get_page_content(check_page)
            detection_result = self._detect_chapter_title_in_page(page_content, check_page)
            
            if detection_result["has_chapter_title"] and detection_result["confidence"] > 0.8:
                chapter["verified_start_page"] = check_page
                chapter["status"] = "verified"
                break
```

### Task 4: Content Assignment Logic
**Priority**: High
**Estimated Time**: 4-5 hours

**Requirements**:
- [ ] Track current chapter being processed
- [ ] Assign content to current chapter until new chapter detected
- [ ] Switch to new chapter when title found
- [ ] Maintain content continuity
- [ ] Handle edge cases (missing chapters, overlapping content)

**Implementation**:
```python
def _assign_content_to_chapters(self, pages_data: List[Dict], detailed_mapping: Dict):
    """Assign page content to appropriate chapter files"""
    
    current_chapter = None
    chapter_files = {}
    
    for page_data in pages_data:
        page_num = page_data['page']
        page_content = page_data['cleaned_content']
        
        # Check if this page starts a new chapter
        chapter_detection = self._detect_chapter_title_in_page(page_content, page_num)
        
        if chapter_detection["has_chapter_title"] and chapter_detection["is_chapter_start"]:
            # Find matching chapter in mapping
            new_chapter = self._find_matching_chapter(
                chapter_detection["chapter_title"], 
                detailed_mapping
            )
            
            if new_chapter:
                current_chapter = new_chapter
                print(f"  📖 Starting Chapter {current_chapter['chapter_number']}: {current_chapter['original_title']}")
        
        # Assign content to current chapter
        if current_chapter:
            chapter_file = self._get_or_create_chapter_file(current_chapter)
            chapter_file.write(page_content + "\n\n")
            chapter_file.flush()
            
            # Track content pages
            current_chapter["content_pages"].append(page_num)
```

### Task 5: Urdu/Arabic Language Support
**Priority**: High
**Estimated Time**: 3-4 hours

**Requirements**:
- [ ] Enhanced chapter title patterns for Urdu/Arabic
- [ ] Better RTL text handling in file names
- [ ] Improved sanitization for non-Latin characters
- [ ] Language detection and appropriate processing

**Implementation**:
```python
def _detect_urdu_content(self, sample_text: str = None) -> bool:
    """Detect if content is primarily Urdu/Arabic"""
    if not sample_text:
        return False
    
    urdu_chars = sum(1 for c in sample_text if '\u0600' <= c <= '\u06FF')
    total_chars = len([c for c in sample_text if c.isalpha()])
    
    return (urdu_chars / total_chars) > 0.3 if total_chars > 0 else False

def _sanitize_urdu_name(self, name: str) -> str:
    """Enhanced sanitization for Urdu/Arabic names"""
    # Remove filesystem-unsafe characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    name = re.sub(r'\s+', '_', name)
    # Limit length but preserve important characters
    if len(name) > 50:
        name = name[:50]
    return name.strip('_')
```

### Task 6: Error Handling and Recovery
**Priority**: Medium
**Estimated Time**: 2-3 hours

**Requirements**:
- [ ] Handle cases where chapter detection fails
- [ ] Fallback to page-based assignment
- [ ] Recovery mechanisms for incomplete chapters
- [ ] Better error reporting and debugging

### Task 7: Testing and Validation
**Priority**: Medium
**Estimated Time**: 2-3 hours

**Requirements**:
- [ ] Test with English books
- [ ] Test with Urdu books
- [ ] Test with mixed-language books
- [ ] Validate chapter content completeness
- [ ] Performance testing with large books

## Implementation Priority

1. **Phase 1** (Week 1): Tasks 1-3 (Structure mapping and verification)
2. **Phase 2** (Week 2): Tasks 4-5 (Content assignment and Urdu support)
3. **Phase 3** (Week 3): Tasks 6-7 (Error handling and testing)

## Success Criteria

- [ ] Correctly assigns 95%+ of page content to appropriate chapters
- [ ] Handles Urdu/Arabic chapter titles accurately
- [ ] Maintains content continuity within chapters
- [ ] Provides clear debugging information
- [ ] Works reliably with both English and Urdu books

## Technical Considerations

### LLM Processing Strategy
- Use smaller batches for chapter detection to avoid token limits
- Implement caching for repeated chapter title patterns
- Consider using different prompts for different languages

### File Management
- Create chapter files only when content is actually assigned
- Maintain file handles efficiently
- Implement proper cleanup and error recovery

### Performance Optimization
- Cache chapter detection results
- Minimize API calls for repeated patterns
- Use efficient file I/O operations

## Future Enhancements

1. **Multi-language Support**: Handle books with mixed languages
2. **Advanced Structure Detection**: Support for sub-chapters and sections
3. **Content Quality Assessment**: Detect and flag low-quality OCR content
4. **Batch Processing**: Process multiple books simultaneously
5. **User Interface**: Web interface for monitoring and manual corrections
