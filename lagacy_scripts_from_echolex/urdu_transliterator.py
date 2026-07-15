#!/usr/bin/env python3
import sys
import json
from hutrans import transliterator

def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python urdu_transliterator.py '<urdu_text>'"}))
        sys.exit(1)
    
    urdu_text = sys.argv[1]
    
    try:
        # Initialize transliterator for Urdu to Hindi
        trn = transliterator(format_='text', source='urdu')
        
        # Convert Urdu script to Hindi script
        hindi_text = trn.transform(urdu_text)
        
        # Return result as JSON
        result = {
            "success": True,
            "original": urdu_text,
            "transliterated": hindi_text,
            "method": "python-hutrans"
        }
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "method": "python-hutrans"
        }
        print(json.dumps(error_result))
        sys.exit(1)

if __name__ == "__main__":
    main() 