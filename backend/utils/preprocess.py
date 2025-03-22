import re

def preprocess_text(text: str) -> str:
    """Basic text preprocessing: lowercasing, removing special characters."""
    text = text.lower()
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Remove special characters
    return text.strip()
