"""Text normalization for market title matching."""

import re
import unicodedata

# Common stop words in prediction market titles
STOP_WORDS = frozenset({
    "will", "the", "be", "a", "an", "in", "on", "at", "to", "of", "for",
    "is", "by", "this", "that", "it", "or", "and", "if", "do", "does",
    "has", "have", "had", "was", "were", "are", "been", "being",
    "before", "after", "than", "more", "most", "least", "less",
    "yes", "no", "not",
})


def normalize_title(title: str) -> str:
    """Normalize a market title for comparison.

    Steps:
    1. Unicode normalize + lowercase
    2. Strip punctuation
    3. Remove stop words
    4. Collapse whitespace
    """
    # Unicode normalize
    text = unicodedata.normalize("NFKD", title)
    text = text.lower().strip()

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Strip punctuation except hyphens in numbers (e.g. "2026-03")
    text = re.sub(r"[^\w\s-]", " ", text)

    # Remove stop words
    words = text.split()
    words = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    # Collapse whitespace
    return " ".join(words)


def extract_entities(title: str) -> set[str]:
    """Extract key entities from a market title using regex patterns.

    Looks for: proper nouns (capitalized words), numbers, dates, percentages.
    """
    entities: set[str] = set()

    # Dates (YYYY, YYYY-MM, YYYY-MM-DD, Month YYYY)
    for match in re.finditer(r"\b(20\d{2}(?:-\d{2}(?:-\d{2})?)?)\b", title):
        entities.add(match.group(1))

    months = (
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
        r"|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    )
    for match in re.finditer(rf"\b({months})\s+(20\d{{2}})\b", title, re.IGNORECASE):
        entities.add(f"{match.group(1).lower()} {match.group(2)}")

    # Numbers and percentages
    for match in re.finditer(r"\b(\d+(?:\.\d+)?%?)\b", title):
        entities.add(match.group(1))

    # Capitalized words (likely proper nouns) — from original title
    for match in re.finditer(r"\b([A-Z][a-z]{2,})\b", title):
        word = match.group(1).lower()
        if word not in STOP_WORDS:
            entities.add(word)

    return entities


def slug_from_title(title: str) -> str:
    """Generate a URL-safe slug from a title."""
    text = normalize_title(title)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:200]
