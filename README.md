# OCR PDF Reader

High-accuracy PDF text extraction with AI-powered cleaning for Urdu, Arabic, and English books.

## Features

- **Google Vision API**: 95-99% OCR accuracy
- **Gemini AI**: Intelligent content cleaning (removes watermarks, URLs, page numbers)
- **Urdu Support**: Proper detection of باب (chapters) and حصہ (parts)
- **Structure Detection**: Automatic parts and chapters organization
- **Parallel Processing**: Fast extraction with multiple workers
- **Clean Output**: Organized folders, complete text, table of contents

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_google.txt
```

### 2. Setup API Keys

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```env
# Gemini API Key (FREE)
GOOGLE_API_KEY=your-gemini-api-key-here

# Google Cloud Vision credentials path
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/vision-key.json
```

**Get your keys:**
- **Gemini API**: https://aistudio.google.com/apikey (FREE)
- **Vision API**: https://console.cloud.google.com (1000 pages/month FREE)

### 3. Extract PDF

**Step 1: OCR Extraction** (parallel, fast)

```bash
python google_vision_extractor.py your_book.pdf
```

**Step 2: AI Formatting** (sequential, ~30s per page)

```bash
python book_formatter.py extracted_google/your_book
```

## Output Structure

```
extracted_google/your_book/
├── raw_pages/                    # Raw OCR output
│   ├── page_001.txt
│   └── ...
├── chapters/                     # Organized by structure
│   ├── part_1_حصہ_اول/
│   │   ├── chapter_1_باب_اول/
│   │   │   ├── page_001.txt
│   │   │   └── ...
│   │   └── chapter_2_باب_دوم/
│   └── part_2_حصہ_دوم/
├── book_structure.txt            # Table of contents
├── your_book_complete.txt        # All clean text
├── your_book_metadata.json       # Structure info
└── pages_index.json              # OCR metadata
```

## Urdu Book Example

**book_structure.txt:**
```
فہرست (Contents)
============================================================

حصہ اول - محبت کا سفر (صفحہ 1 تا 50)
    باب اول - پہلی ملاقات
    باب دوم - دل کی باتیں

حصہ دوم - جدائی کا درد (صفحہ 51 تا 100)
    باب سوم - آنسوؤں کی بارش

فہرست ختم۔
```

## Advanced Usage

### Vision Extractor Options

```bash
# Use 2 parallel workers (safer for rate limits)
python google_vision_extractor.py book.pdf --workers 2

# Specify credentials path
python google_vision_extractor.py book.pdf --credentials ~/key.json
```

### Formatter Options

```bash
# Use API key from command line
python book_formatter.py extracted_google/book --gemini-key YOUR_KEY
```

## Costs

| Service | Free Tier | After Free Tier |
|---------|-----------|-----------------|
| Vision API | 1,000 pages/month | $1.50 per 1,000 pages |
| Gemini 2.0 Flash | FREE (experimental) | ~$0.02-0.05 per book |

**Example:** 500-page book = ~$0.75-0.80 (if within free tier: $0.00)

## Supported Languages

- **Urdu** (اردو): Full support with باب/حصہ detection
- **Arabic** (العربية): Right-to-left text support
- **English**: Standard chapter/part detection
- **Hindi** (हिन्दी): Full OCR support

## Features for Urdu Books

✅ Detects Urdu chapter patterns: باب اول، باب دوم، فصل اول
✅ Detects Urdu part patterns: حصہ اول، حصہ دوم، قسط اول
✅ Removes Urdu watermarks: BestUrduNovels, UrduNovels
✅ Removes Urdu page numbers: صفحہ، ص، پیج
✅ Preserves poetry indentation and dialogue
✅ UTF-8 with BOM encoding for better compatibility
✅ Urdu folder names with Unicode support

## Troubleshooting

### Vision API Issues

```bash
# Check credentials are set
echo $GOOGLE_APPLICATION_CREDENTIALS

# Or use .env file
cat .env
```

### Gemini Rate Limits

If you see "429 rate limit" errors:
- The formatter already includes 30s delay per page
- This is usually sufficient for free tier
- If issues persist, process books in smaller batches

### Missing Dependencies

```bash
# Reinstall all dependencies
pip install -r requirements_google.txt
```

## File Descriptions

- **google_vision_extractor.py**: OCR extraction only (no formatting)
- **book_formatter.py**: AI-powered cleaning and organization
- **main.py**: Tesseract-based extractor (English only, local)
- **.env.example**: Template for API keys
- **requirements_google.txt**: All dependencies

## Security

⚠️ **Never commit your `.env` file or JSON keys to git!**

The `.gitignore` is configured to exclude:
- `.env` files
- `*.json` credential files
- API keys

## Documentation

- **Vision API Setup**: See `GOOGLE_VISION_SETUP.md`
- **Gemini Setup**: See `GEMINI_CLEANING_GUIDE.md`
- **Local Setup**: See `INSTALL.md`

## License

MIT

## Support

For issues or questions:
- Check existing documentation files
- Review error messages carefully
- Ensure API keys are valid and have sufficient quota
