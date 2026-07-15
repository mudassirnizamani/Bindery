 #!/usr/bin/env python3
"""Quick test for Urdu-Hindi transliterator."""

import sys
import json
import subprocess
import os

def main():
    print("🚀 Testing Urdu-Hindi Transliterator")
    
    # Test cases
    test_cases = [
        "السلام علیکم",
        "یہ ایک آزمائشی متن ہے",
        "کمپیوٹر سائنس"
    ]
    
    script_path = "indic_converter_transliterator.py"
    
    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        return 1
    
    for i, urdu_text in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {urdu_text}")
        
        try:
            result = subprocess.run(
                ["python3", script_path, urdu_text],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = json.loads(result.stdout)
                print(f"   Output: {output['transliterated']}")
                print(f"   Method: {output['method']}")
                print("   ✅ Success")
            else:
                print(f"   ❌ Error: {result.stderr}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    print("\n🎉 Test completed!")
    return 0

if __name__ == "__main__":
    exit(main()) 