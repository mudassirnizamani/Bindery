# Smart FM Server Scripts

This directory contains utility scripts for the Smart FM Server project.

## urdu_transliterator.py

Transliterates Urdu text to Hindi script using the `hutrans` library.

### Setup (First Time Only)

**Note**: The `hutrans` library is installed from GitHub, not PyPI, and requires specific dependencies.

```bash
# Set up virtual environment and install dependencies
task scripts:setup
```

If the setup fails, you can install dependencies manually:

```bash
cd smart_fm_server/scripts
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install cython scipy
pip install git+https://github.com/irshadbhat/indic-wx-converter.git
pip install --no-build-isolation git+https://github.com/ltrc/python-hutrans.git
pip install requests>=2.28.0
```

### Installation (After Setup)

```bash
# Install/update dependencies in existing virtual environment
task scripts:install
```

### Usage

```bash
# Test with sample text
task scripts:test-transliterate

# Custom text
task scripts:transliterate -- "آپ کا نام کیا ہے؟"
```

### Output Format

```json
{
  "success": true,
  "original": "یہ اردو متن ہے", 
  "transliterated": "यह उर्दू मतन है",
  "method": "python-hutrans"
}
```

### Manual Usage

If you prefer to run the script manually:

```bash
cd smart_fm_server/scripts
venv/bin/python urdu_transliterator.py "یہ اردو متن ہے"
```

### Troubleshooting

If you encounter installation issues:

1. **Make sure you have development tools installed** (required for compiling dependencies):
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install build-essential python3-dev
   
   # On CentOS/RHEL
   sudo yum groupinstall "Development Tools"
   sudo yum install python3-devel
   
   # On Manjaro/Arch
   sudo pacman -S base-devel python
   ```

2. **The installation order matters** - dependencies must be installed in this sequence:
   - cython
   - scipy
   - indic-wx-converter
   - python-hutrans (with `--no-build-isolation` flag)

3. **Build isolation issue**: The `--no-build-isolation` flag is required for `python-hutrans` because it needs access to the previously installed Cython during build time.

4. **If GitHub access fails**, ensure you have internet connectivity and GitHub isn't blocked.

## urdu_transliterator_simple.py (Alternative Solution)

If you're having trouble with the `hutrans` library installation, this simple alternative uses basic character mapping without external dependencies.

### Setup (Simple Version)

```bash
# Simple setup - no complex dependencies
task scripts:simple-setup
```

### Usage (Simple Version)

```bash
# Test with sample text
task scripts:test-simple

# Custom text
task scripts:transliterate-simple -- "آپ کا نام کیا ہے؟"
```

### Direct Usage

```bash
cd smart_fm_server/scripts
python urdu_transliterator_simple.py "یہ اردو متن ہے"
```

### Comparison

| Feature | hutrans version | Simple version |
|---------|----------------|----------------|
| Dependencies | Complex (hutrans, cython, scipy) | None (built-in Python) |
| Accuracy | High (linguistic rules) | Good (character mapping) |
| Compatibility | Python < 3.13 | All Python versions |
| Installation | Complex | Simple |
| Maintenance | External dependency | Self-contained |

**Recommendation**: Start with the simple version for immediate functionality, then optionally upgrade to hutrans if you need more sophisticated transliteration. 