#!/usr/bin/env python3
import sys
import json
try:
    from ai4bharat.transliteration import XlitEngine
except ImportError:
    print(json.dumps({"error": "ai4bharat not installed. Run: pip install ai4bharat-transliteration"}))
    sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python ai4bharat_transliterator.py '<urdu_text>'"}))
        sys.exit(1)
    
    urdu_text = sys.argv[1]
    
    try:
        # Initialize transliterator for Urdu to Hindi (Devanagari)
        engine = XlitEngine(target_script="hi", beam_width=3)
        
        # Convert Urdu script to Hindi script
        hindi_text = engine.translit_sentence(urdu_text)
        
        result = {
            "success": True,
            "original": urdu_text,
            "transliterated": hindi_text,
            "method": "ai4bharat-indic-xlit"
        }
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "method": "ai4bharat-indic-xlit"
        }
        print(json.dumps(error_result))
        sys.exit(1)

if __name__ == "__main__":
    main() 