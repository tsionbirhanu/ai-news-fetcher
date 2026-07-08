"""
Run this once after installing requirements.txt to download
the NLTK tokenizer data that `sumy` needs for summarization.

    python setup_nltk.py
"""

import nltk

nltk.download("punkt")
nltk.download("punkt_tab")

print("Done: NLTK data downloaded. You're ready to run `python main.py fetch`.")