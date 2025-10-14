# Installation Guide for Manjaro Linux

## System Dependencies

First, install the system packages:

```bash
# Install Tesseract OCR engine and Poppler utilities
sudo pacman -S tesseract tesseract-data-eng poppler

# Optional: Install additional language packs
sudo pacman -S tesseract-data-urd  # Urdu
sudo pacman -S tesseract-data-ara  # Arabic
sudo pacman -S tesseract-data-hin  # Hindi
```

## Python Dependencies

Since this project already has a virtual environment, activate it and install:

```bash
# Activate the virtual environment
source bin/activate

# Install from requirements file
pip install -r requirements.txt

# Or install individually:
pip install pdfplumber pytesseract pdf2image Pillow
```

If not using the venv, install directly:
```bash
./bin/pip install -r requirements.txt
```

## Usage

```bash
# Single PDF
python main.py document.pdf

# With OCR language
python main.py document.pdf --lang eng

# Urdu document
python main.py urdu_doc.pdf --lang urd

# Multiple languages
python main.py mixed_doc.pdf --lang eng+urd

# Batch process folder
python main.py --batch ./pdfs --lang eng
```

## Output Structure

The program creates organized output:

```
extracted/
└── document_name/
    ├── document_name_complete.txt      # Full text
    ├── document_name_metadata.json     # Metadata
    ├── pages/                          # Individual pages
    ├── structure/                      # Document structure
    │   ├── outline.txt                 # Hierarchical outline
    │   ├── lists.txt                   # Extracted lists
    │   └── sections/                   # Sections by headings
    └── tables/                         # Tables (CSV + TXT)
```
