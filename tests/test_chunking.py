
import unittest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from page_cleaner import PageCleaner

class TestPageCleanerChunking(unittest.TestCase):
    def setUp(self):
        # Mock __init__ so we don't need env vars or real files
        with patch('page_cleaner.PageCleaner.__init__', return_value=None):
            self.cleaner = PageCleaner("dummy_path")

    def test_chunking_preserves_order_simple(self):
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        # Chunk size small enough to force split by paragraph
        chunks = self.cleaner.split_text_into_chunks(text, chunk_size=10)

        reconstructed = "".join(chunks)
        self.assertEqual(text, reconstructed)

        # Check chunks
        # Should correspond to paragraphs + delimiters roughly
        # Chunk logic:
        # P1 (length 12) -> >10. Fits in empty chunk? Yes.
        # \n\n (length 2). Fits in current? 12+2 > 10. No.
        # Wait, if buffer has P1, length is 12.
        # Next part is \n\n.
        # current_length + part_len = 12 + 2 = 14 > 10.
        # So it flushes P1.
        # New chunk: \n\n.
        # Next: P2.

        self.assertIn("Paragraph 1.", chunks[0])

    def test_chunking_preserves_order_complex(self):
        # Create a text with mixed newlines and long sentences
        input_text = "Part 1.\n\nChapter 1.\nThis is a long paragraph that might need splitting if the chunk size is very small. It continues here."

        # Chunk size 20.
        # "Part 1." (7)
        # "\n\n" (2) -> "Part 1.\n\n" (9)
        # "Chapter 1." (10) -> "Part 1.\n\nChapter 1." (19) -> Fits.
        # "\n" (1) -> 20. Fits.
        # "This is a long..." (huge).

        chunks = self.cleaner.split_text_into_chunks(input_text, chunk_size=20)
        reconstructed = "".join(chunks)
        self.assertEqual(input_text, reconstructed)

    def test_huge_paragraph_splitting(self):
        # Paragraph larger than chunk size
        text = "Sentence one. Sentence two."
        # Length ~27.
        # Chunk size 10.
        chunks = self.cleaner.split_text_into_chunks(text, chunk_size=10)
        reconstructed = "".join(chunks)
        self.assertEqual(text, reconstructed)

        # Expect split inside the text
        self.assertTrue(len(chunks) > 1)
        self.assertIn("Sentence one.", chunks[0])

    def test_no_periods(self):
        # Case where no periods exist
        text = "Word1 word2 word3 word4"
        chunks = self.cleaner.split_text_into_chunks(text, chunk_size=10)
        reconstructed = "".join(chunks)
        self.assertEqual(text, reconstructed)

    def test_exact_reconstruction_user_like(self):
        # Using a snippet of user text style
        text = """Header\n\nParagraph 1 is here.\n\nParagraph 2 is here also."""
        chunks = self.cleaner.split_text_into_chunks(text, chunk_size=15)
        self.assertEqual(text, "".join(chunks))

if __name__ == '__main__':
    unittest.main()
