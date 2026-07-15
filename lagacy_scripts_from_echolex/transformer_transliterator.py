#!/usr/bin/env python3
import sys
import json
try:
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
except ImportError:
    print(json.dumps({"error": "transformers not installed. Run: pip install transformers torch"}))
    sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python transformer_transliterator.py '<urdu_text>'"}))
        sys.exit(1)
    
    urdu_text = sys.argv[1]
    
    try:
        # Load pre-trained model (you might need to fine-tune this)
        model_name = "facebook/m2m100_418M"  # or larger variant
        model = M2M100ForConditionalGeneration.from_pretrained(model_name)
        tokenizer = M2M100Tokenizer.from_pretrained(model_name)
        
        # Set source and target languages
        tokenizer.src_lang = "ur"  # Urdu
        encoded_ur = tokenizer(urdu_text, return_tensors="pt")
        
        # Generate translation
        generated_tokens = model.generate(
            **encoded_ur, 
            forced_bos_token_id=tokenizer.get_lang_id("hi")  # Hindi
        )
        
        # Decode the result
        hindi_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        
        result = {
            "success": True,
            "original": urdu_text,
            "transliterated": hindi_text,
            "method": "transformer_m2m100"
        }
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "method": "transformer"
        }
        print(json.dumps(error_result))
        sys.exit(1)

if __name__ == "__main__":
    main() 