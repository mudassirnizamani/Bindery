 #!/usr/bin/env python3
"""
Urdu to Hindi Transliterator using Indic-PersoArabic-Script-Converter
This script converts Urdu (Arabic script) to Hindi (Devanagari script) 
while preserving Urdu vocabulary for TTS purposes.
"""

import sys
import json
import re
import argparse
from typing import Dict, Any

try:
    from IndicPersoArabicConverter import transliterate
    CONVERTER_AVAILABLE = True
except ImportError:
    CONVERTER_AVAILABLE = False

def preprocess_urdu_text(text: str) -> str:
    """Preprocess Urdu text for better transliteration results."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Normalize Arabic numerals to standard form
    arabic_to_standard = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for arabic_num, standard_num in arabic_to_standard.items():
        text = text.replace(arabic_num, standard_num)
    
    return text

def postprocess_hindi_text(text: str) -> str:
    """Postprocess Hindi text for better TTS pronunciation."""
    # Fix common transliteration issues
    fixes = {
        'अा': 'आ', 'इी': 'ई', 'उू': 'ऊ', 'एे': 'ए', 'ओो': 'ओ'
    }
    
    for wrong, correct in fixes.items():
        text = text.replace(wrong, correct)
    
    # Clean up spacing
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def fallback_transliterate(urdu_text: str) -> str:
    """Fallback rule-based transliteration."""
    urdu_to_hindi_map = {
        # Basic character mapping
        'ا': 'अ', 'آ': 'आ', 'ی': 'ी', 'و': 'ू', 'ے': 'े',
        'ب': 'ब', 'پ': 'प', 'ت': 'त', 'ٹ': 'ट', 'ث': 'स',
        'ج': 'ज', 'چ': 'च', 'ح': 'ह', 'خ': 'ख़', 'د': 'द',
        'ڈ': 'ड', 'ذ': 'ज़', 'ر': 'र', 'ڑ': 'ड़', 'ز': 'ज़',
        'ژ': 'झ़', 'س': 'स', 'ش': 'श', 'ص': 'स', 'ض': 'ज़',
        'ط': 'त', 'ظ': 'ज़', 'ع': '', 'غ': 'ग़', 'ف': 'फ़',
        'ق': 'क़', 'ک': 'क', 'گ': 'ग', 'ل': 'ل', 'م': 'म',
        'ن': 'न', 'ں': 'ं', 'ہ': 'ह', 'ھ': 'ह', 'ء': ''
    }
    
    result = urdu_text
    for urdu_char, hindi_char in urdu_to_hindi_map.items():
        result = result.replace(urdu_char, hindi_char)
    
    return result

def transliterate_urdu_to_hindi(urdu_text: str, use_fallback: bool = False) -> Dict[str, Any]:
    """Main transliteration function."""
    if not urdu_text.strip():
        return {
            "original": urdu_text,
            "transliterated": "",
            "success": True,
            "method": "none"
        }
    
    preprocessed_text = preprocess_urdu_text(urdu_text)
    
    try:
        if CONVERTER_AVAILABLE and not use_fallback:
            hindi_text = transliterate(preprocessed_text, "ur", "hi")
            method = "indic-perso-arabic-converter"
        else:
            hindi_text = fallback_transliterate(preprocessed_text)
            method = "fallback-rule-based"
            
        final_text = postprocess_hindi_text(hindi_text)
        
        return {
            "original": urdu_text,
            "transliterated": final_text,
            "success": True,
            "method": method
        }
        
    except Exception as e:
        if not use_fallback and CONVERTER_AVAILABLE:
            return transliterate_urdu_to_hindi(urdu_text, use_fallback=True)
        else:
            return {
                "original": urdu_text,
                "transliterated": "",
                "success": False,
                "error": str(e)
            }

def main():
    """Command line interface for the transliterator."""
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python indic_converter_transliterator.py '<urdu_text>'"}))
        sys.exit(1)
    
    urdu_text = sys.argv[1]
    result = transliterate_urdu_to_hindi("""
                                         اس باب میں، میں تنہائی کو رومانوی بنانے کی خواہش اور اس کے نتیجے میں پیدا ہونے والے دل ٹوٹنے اور مایوسی کا جائزہ لیتا ہوں۔ یہ سب اُس دل فریب کشش سے شروع ہوتا ہے جو ایک مثالی زندگی کے تصور سے جنم لیتی ہے — ایک ایسا تصور جو کتابوں، فلموں، اور حتیٰ کہ سوشل میڈیا سے پروان چڑھتا ہے۔ میں غور کرتا ہوں کہ یہ فنتاسی کس طرح حقیقت کے برعکس کھڑی ہوتی ہے، اور کیسے یہ توقعات کا ایک سراب تخلیق کرتی ہے جو آہستہ آہستہ انسان کی خودی کو کمزور کر دیتا ہے۔

                                          """)
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main() 