"""Keep machine metadata out of model-visible scene language."""
import re


def clean_image_text(value: str, internal_values=()) -> str:
    text = str(value or "")
    for token in internal_values:
        token = str(token or "")
        if token and token != "none":
            text = re.sub(r"(?<!\w)" + re.escape(token) + r"(?!\w)", "", text)
    # Explicit literal inscriptions are semantic content. Everything else that
    # looks like a machine enum/group name is omitted, including copied IDs in
    # reference descriptions. Known internal values above are always removed.
    literals = []
    def keep(match):
        literals.append(match.group(0))
        return f"LITERALPLACEHOLDER{len(literals) - 1}"
    text = re.sub(r'(?i)literal text:\s*"[^"\n]*"', keep, text)
    text = re.sub(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b", "", text)
    for index, literal in enumerate(literals):
        text = text.replace(f"LITERALPLACEHOLDER{index}", literal)
    return " ".join(text.split())
