# Google Cloud Vision API Setup Guide

## Step 1: Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Name your project (e.g., "pdf-ocr-project")
4. Click "Create"

## Step 2: Enable Cloud Vision API

1. In the Google Cloud Console, search for "Vision API"
2. Click "Cloud Vision API"
3. Click "Enable"
4. Wait for activation (takes ~1 minute)

## Step 3: Create Service Account & Credentials

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Name: `pdf-ocr-service`
4. Click "Create and Continue"
5. Grant role: **"Cloud Vision API User"**
6. Click "Done"

## Step 4: Download JSON Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON"
5. Click "Create"
6. Save the downloaded JSON file securely
   - Example location: `~/google-cloud-key.json`

## Step 5: Set Environment Variable

**Linux/Mac:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/google-cloud-key.json"

# Make it permanent (add to ~/.bashrc or ~/.zshrc):
echo 'export GOOGLE_APPLICATION_CREDENTIALS="$HOME/google-cloud-key.json"' >> ~/.bashrc
source ~/.bashrc
```

**Or use it directly in the command:**
```bash
python google_vision_extractor.py book.pdf --credentials ~/google-cloud-key.json
```

## Step 6: Install Dependencies

```bash
pip install google-cloud-vision pdf2image Pillow
```

## Step 7: Test It

```bash
python google_vision_extractor.py your_book.pdf
```

## Pricing

- **Free Tier**: First 1,000 pages/month FREE
- **After free tier**: $1.50 per 1,000 pages
- **Example costs**:
  - 100-page book: FREE (or $0.15)
  - 500-page book: FREE (or $0.75)
  - 5,000-page book: $7.50

## Rate Limits

- **Default**: 1,800 requests/minute
- **Recommended workers**: 2-4 parallel workers
- Use `--workers 2` for safer rate limiting

## Accuracy

- **English**: 98-99%
- **Urdu/Arabic**: 96-98%
- **Hindi**: 97-99%
- **Mixed languages**: 95-97%

## Comparison with Tesseract

| Feature | Google Vision | Tesseract |
|---------|---------------|-----------|
| Accuracy (Urdu) | 96-98% | 85-92% |
| Speed | Fast | Fast |
| Cost | $1.50/1000 pages | Free |
| Quality on poor scans | Excellent | Good |
| Handwriting | Good | Poor |
| Setup | Medium | Easy |

## Usage Examples

```bash
# Basic usage
python google_vision_extractor.py book.pdf

# With credentials path
python google_vision_extractor.py book.pdf --credentials ~/key.json

# Slower but safer (2 parallel workers)
python google_vision_extractor.py book.pdf --workers 2

# Fast processing (4 workers - watch rate limits!)
python google_vision_extractor.py book.pdf --workers 4
```

## Troubleshooting

**Error: "Could not automatically determine credentials"**
- Make sure `GOOGLE_APPLICATION_CREDENTIALS` is set
- Or use `--credentials /path/to/key.json`

**Error: "API has not been used in project"**
- Enable Cloud Vision API in Google Cloud Console
- Wait 1-2 minutes for activation

**Error: "Rate limit exceeded"**
- Reduce workers: `--workers 2`
- Add delays between requests

**Error: "Billing must be enabled"**
- Add billing account to Google Cloud project
- Free tier still applies!

## Security Notes

- **Never commit** your JSON key to git
- Add to `.gitignore`: `*.json`
- Store key securely with restricted permissions:
  ```bash
  chmod 600 ~/google-cloud-key.json
  ```

## Output Structure

```
extracted_google/
└── your_book/
    ├── chapters/
    │   ├── intro/
    │   │   ├── page_001.txt
    │   │   └── page_002.txt
    │   ├── chapter_1_Introduction/
    │   │   ├── page_003.txt
    │   │   └── page_004.txt
    │   └── ...
    ├── CHAPTER_INDEX.txt
    ├── your_book_complete.txt
    └── your_book_metadata.json
```

## Best Practices

1. **Start small**: Test with 5-10 pages first
2. **Check costs**: Monitor in Google Cloud Console
3. **Backup**: Keep original PDFs
4. **Workers**: Use 2-4 workers max to avoid rate limits
5. **Free tier**: Process up to 1000 pages/month free!
