#!/usr/bin/env python3
import sys
import json
import re

def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python urdu_transliterator_simple.py '<urdu_text>'"}))
        sys.exit(1)
    
    urdu_text = sys.argv[1]
    
    try:
        # Basic Urdu to Hindi character mapping (similar to your Go implementation)
        conversions = {
            # Common Urdu-specific characters to Hindi equivalents
            "ں": "न्",  # Urdu noon ghunna to Hindi na + halant
            "ے": "े",   # Urdu ye to Hindi e matra
            "ہ": "ह",   # Urdu he to Hindi ha
            "ٹ": "ट",   # Urdu retroflex ta to Hindi ta
            "ڈ": "ड",   # Urdu retroflex da to Hindi da
            "ڑ": "ड़",  # Urdu retroflex ra to Hindi ra
            "ژ": "ज़",  # Urdu zhe to Hindi za
            "گ": "ग",   # Urdu gaf to Hindi ga
            "پ": "प",   # Urdu pe to Hindi pa
            "چ": "च",   # Urdu che to Hindi cha
            "ک": "क",   # Urdu kaf to Hindi ka
            "ی": "ी",   # Urdu ye to Hindi i matra
            "و": "ो",   # Urdu vao to Hindi o matra (context-dependent)
            "ا": "आ",   # Urdu alif to Hindi aa
            "آ": "आ",   # Urdu alif madda to Hindi aa
            "ع": "",    # Urdu ain - often silent, remove
            "غ": "ग़",  # Urdu ghain to Hindi gha with nukta
            "ف": "फ़",  # Urdu fe to Hindi pha with nukta
            "ق": "क़",  # Urdu qaf to Hindi qa with nukta
            "ث": "स",   # Urdu se to Hindi sa
            "ذ": "ज़",  # Urdu zal to Hindi za
            "ض": "ज़",  # Urdu zwad to Hindi za
            "ط": "त",   # Urdu toe to Hindi ta
            "ظ": "ज़",  # Urdu zoe to Hindi za
            "ص": "स",   # Urdu swad to Hindi sa
            "ح": "ह",   # Urdu he to Hindi ha
            "خ": "ख़",  # Urdu khe to Hindi kha with nukta
            "ج": "ज",   # Urdu jeem to Hindi ja
            "ش": "श",   # Urdu sheen to Hindi sha
            "س": "स",   # Urdu seen to Hindi sa
            "ز": "ज़",  # Urdu ze to Hindi za
            "ر": "र",   # Urdu re to Hindi ra
            "ت": "त",   # Urdu te to Hindi ta
            "ب": "ब",   # Urdu be to Hindi ba
            "ن": "न",   # Urdu noon to Hindi na
            "م": "म",   # Urdu meem to Hindi ma
            "ل": "ल",   # Urdu lam to Hindi la
            "د": "द",   # Urdu dal to Hindi da
        }
        
        # Apply character conversions
        result_text = urdu_text
        for urdu, hindi in conversions.items():
            result_text = result_text.replace(urdu, hindi)
        
        # Clean up text - remove Arabic diacritics
        diacritics_pattern = r'[\u064B-\u065F\u0670\u06D6-\u06ED]'
        result_text = re.sub(diacritics_pattern, '', result_text)
        
        # Normalize whitespace
        result_text = re.sub(r'\s+', ' ', result_text).strip()
        
        # Return result as JSON
        result = {
            "success": True,
            "original": urdu_text,
            "transliterated": result_text,
            "method": "python-simple-mapping"
        }
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "method": "python-simple-mapping"
        }
        print(json.dumps(error_result))
        sys.exit(1)

if __name__ == "__main__":
    main()