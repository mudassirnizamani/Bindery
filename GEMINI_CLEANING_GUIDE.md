# Gemini-Powered PDF Cleaning Guide

## What This Does

Combines **Google Vision API** (best OCR) + **Gemini 2.0 Flash** (AI cleaning) to:

1. Extract text from PDF with 95-99% accuracy (Vision API)
2. Clean each page with AI (Gemini):
   - Removes watermarks (www.BestUrduNovels.com)
   - Removes URLs, social media handles
   - Removes page numbers, headers, footers
   - Detects chapter titles automatically
   - Preserves ONLY meaningful book content

## Setup (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements_google.txt
```

### Step 2: Get Vision API Credentials

1. Go to https://console.cloud.google.com
2. Enable "Cloud Vision API"
3. Create service account → Download JSON key
4. Save as `~/google-vision-key.json`

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/google-vision-key.json"
```

### Step 3: Get Gemini API Key (FREE!)

1. Go to https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Copy the key

```bash
export GOOGLE_API_KEY="your-gemini-api-key-here"
```

## Usage

### Basic Usage (Recommended)
```bash
python google_vision_extractor.py book.pdf
```

This will:
- Extract with Vision API
- Clean with Gemini
- Save to `extracted_google/book/`

### Advanced Options

```bash
# Slower but safer (2 workers instead of 4)
python google_vision_extractor.py book.pdf --workers 2

# Disable Gemini (raw OCR only)
python google_vision_extractor.py book.pdf --no-gemini

# Use specific API keys
python google_vision_extractor.py book.pdf \
  --credentials ~/vision-key.json \
  --gemini-key YOUR_GEMINI_KEY
```

## Output Structure

```
extracted_google/
└── book_name/
    ├── chapters/
    │   ├── intro/
    │   │   ├── page_001.txt          # CLEAN content only!
    │   │   ├── page_002.txt
    │   │   └── page_001_metadata.json  # What was removed
    │   ├── chapter_1_Introduction/
    │   │   ├── page_003.txt
    │   │   └── ...
    │   └── ...
    ├── CHAPTER_INDEX.txt              # Quick navigation
    ├── book_name_complete.txt         # All pages, CLEAN
    ├── book_name_raw_ocr.txt          # Before cleaning (for comparison)
    └── book_name_metadata.json        # Stats
```

## What Gets Removed?

Gemini intelligently removes:

### ✅ Removed
- `www.BestUrduNovels.com`
- `http://example.com`
- `facebook`, `twitter`, social media
- Page numbers (e.g., "Page 7")
- Headers/footers
- Watermarks
- Website names

### ✅ Kept
- Chapter titles
- Book content
- Dialogue
- Paragraphs
- Author notes

## Cost Breakdown

### Free Tier
- **Vision API**: 1,000 pages/month FREE
- **Gemini 2.0 Flash**: FREE (current experimental version)

### After Free Tier
- **Vision API**: $1.50 per 1,000 pages
- **Gemini 2.0 Flash**: ~$0.075 per 1M input tokens

### Example Costs

| Book Size | Vision API | Gemini | Total |
|-----------|------------|--------|-------|
| 100 pages | FREE | FREE | $0.00 |
| 500 pages | FREE | FREE | $0.00 |
| 1,500 pages | $0.75 | $0.02 | $0.77 |
| 5,000 pages | $6.00 | $0.05 | $6.05 |

## Example: Urdu Book Cleaning

### Before (Raw OCR):
```
www.BestUrduNovels.com
http://BestUrduNovels.com
BestUrdu Novelz
facebook

باب اول

یہ ایک کہانی ہے...

Page 7
www.BestUrduNovels.com
```

### After (Gemini Cleaned):
```
باب اول

یہ ایک کہانی ہے...
```

## Troubleshooting

### "No Gemini API key found"
```bash
export GOOGLE_API_KEY="your-key-here"
# Or use:
python google_vision_extractor.py book.pdf --gemini-key YOUR_KEY
```

### "Vision API not initialized"
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/vision-key.json"
```

### "Gemini cleaning failed"
- The page will still be saved with raw OCR
- Check your internet connection
- Verify API key is valid

### Too Slow?
```bash
# Reduce workers to avoid rate limits
python google_vision_extractor.py book.pdf --workers 2
```

## Comparison: With vs Without Gemini

| Feature | With Gemini | Without Gemini |
|---------|-------------|----------------|
| Accuracy | 95-99% | 95-99% |
| Watermarks removed | ✅ Yes | ❌ No |
| URLs removed | ✅ Yes | ❌ No |
| Page numbers removed | ✅ Yes | ❌ No |
| Cost (500 pages) | ~$0.80 | ~$0.75 |
| Processing time | ~15-20 min | ~10-15 min |

**Recommendation**: Always use Gemini for books with watermarks!

## Tips

1. **Start small**: Test with 10-20 pages first
2. **Check metadata**: Look at `page_XXX_metadata.json` to see what was removed
3. **Compare**: Use `_raw_ocr.txt` vs `_complete.txt` to verify cleaning
4. **Save originals**: Keep your PDF files as backup
5. **Monitor costs**: Check Google Cloud Console

## API Keys Security

```bash
# Never commit keys to git!
echo "*.json" >> .gitignore
echo "GOOGLE_API_KEY=*" >> .gitignore

# Secure your key file
chmod 600 ~/google-vision-key.json
```
