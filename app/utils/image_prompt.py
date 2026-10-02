"""Keep machine metadata out of model-visible scene language."""
import re


def internal_image_values(metadata) -> list[str]:
    """Collect declared machine identifiers, never infer provenance from prose."""
    values = []
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key == "internal_values" and isinstance(value, (list, tuple)):
                values.extend(x for x in value if isinstance(x, str))
            elif isinstance(value, str) and (
                key in {"id", "continuity_key", "planner_id"}
                or key.endswith("_id")
                or (key.endswith(("_key", "_family")) and re.search(r"[_\d-]", value))
            ):
                values.append(value)
            elif isinstance(value, (dict, list, tuple)):
                values.extend(internal_image_values(value))
    elif isinstance(metadata, (list, tuple)):
        for item in metadata:
            values.extend(internal_image_values(item))
    return values


def clean_image_text(value: str, internal_values=()) -> str:
    text = str(value or "")
    for token in internal_values:
        token = str(token or "")
        if token and token != "none":
            text = re.sub(r"(?<!\w)" + re.escape(token) + r"(?!\w)", "", text)
    # Spelling alone does not establish provenance: user-authored snake_case
    # and literal inscriptions survive unless explicitly declared internal.
    return " ".join(text.split())
