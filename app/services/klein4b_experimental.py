"""Explicit opt-in MPT adapter for the isolated Klein 4B bridge."""

import json
from pathlib import Path

from app.utils.image_prompt import clean_image_text, internal_image_values
from local_image_stack.experiments.klein4b import ALIASES, Reference
from local_image_stack.experiments.klein4b_graph import prepare_graph


MANIFEST = Path(__file__).resolve().parents[2] / "docs/validation/flux-klein-4b-assets.json"
ROLE_MAP = {
    "identity": "identity_reference", "identity_reference": "identity_reference",
    "detail": "factual_reference", "factual_reference": "factual_reference",
    "style": "style_reference", "style_reference": "style_reference",
    "continuity": "continuity_anchor", "continuity_anchor": "continuity_anchor",
}


def validate_local_assets(manifest: dict) -> None:
    # Full SHA verification is a session preflight, not 13 GB reread per scene.
    for component in manifest["components"].values():
        path = Path(component.get("local_path", "__missing__"))
        if (component.get("verification_status") != "verified_local_bytes"
                or not path.is_file() or path.name != component["filename"]
                or path.stat().st_size != component["expected_size_bytes"]):
            raise ValueError(f"Missing or changed Klein asset: {component['filename']}")


def prepare_scene(app_config: dict, *, model: str, prompt: str, size: str,
                  quality_tier: str, references: list[str], reference_info: dict | None,
                  forbidden_features: list[str] | None = None) -> dict:
    if app_config.get("openai_image_klein4b_experimental_enabled") is not True:
        raise ValueError("Klein 4B experimental dispatch is not enabled")
    if quality_tier not in {"standard", "precision"}:
        raise ValueError("Unknown quality tier")
    info = reference_info or {}
    pack = info.get("reference_pack") or []
    if len(pack) != len(references):
        raise ValueError("Klein references require exactly one explicit ordered role each")
    refs = []
    for index, (image, item) in enumerate(zip(references, pack), 1):
        role = ROLE_MAP.get(item.get("role"))
        if role is None:
            raise ValueError("Unsupported Klein reference role")
        # Prevent the legacy primary-reference insertion from misaligning roles.
        if item.get("comfyui_input") and item["comfyui_input"] != image:
            raise ValueError("Reference order differs from declared role pack")
        refs.append(Reference(image, role))
        description = clean_image_text(str(item.get("description") or ""), internal_image_values(info)).strip()
        if description:
            prompt += f"\nImage {index} evidence: {description}. Use it only for its declared role."
    exclusions = [str(feature).strip() for feature in (forbidden_features or []) if str(feature).strip()]
    if exclusions:
        prompt += "\nExclude these scene-specific features: " + "; ".join(exclusions) + "."
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_local_assets(manifest)
    temporal = info.get("temporal_progression", False)
    if type(temporal) is not bool:
        raise ValueError("temporal_progression must be boolean")
    options = {"alias": model, "temporal_progression": temporal,
               "temporal_state": str(info.get("temporal_state") or "")}
    prepared = prepare_graph(manifest, prompt, app_config.get("openai_image_klein4b_seed", 42),
                             size, tuple(refs), **options)
    payload = {**prepared["payload"], "reference_roles": prepared["reference_roles"],
               "temporal_progression": temporal, "temporal_state": options["temporal_state"],
               "response_format": "b64_json"}
    conditioning = ("continuity_reference" if any(r.role == "continuity_anchor" for r in refs)
                    else "manual_reference" if refs else "none")
    return {"endpoint": "http://127.0.0.1:8091/v1/images/generations", "payload": payload,
            "metadata": {"experimental": True, "quality_tier": quality_tier,
                         "conditioning_mode": conditioning, "reference_roles": payload["reference_roles"],
                         "workflow": prepared["workflow"]["path"],
                         "workflow_sha256": prepared["workflow"]["sha256"],
                         "final_prompt": payload["prompt"], "temporal_progression": temporal,
                         "temporal_state": options["temporal_state"],
                         "qa_status": "pending"}}


def confirmed_technical_failure(detail: str) -> bool:
    """Conservative legacy transport mapping; ambiguous failures never resubmit."""
    text = str(detail).lower()
    if any(word in text for word in ("semantic", "temporal", "factual", "qa", "unconfirmed")):
        return False
    return (text.startswith("http 404:") and
            any(reason in text for reason in ("workflow not found", "unknown model", "model not found")))


def qa_verified(assessment: dict | None) -> bool:
    """Gross 'pass' with an uncertain factual verdict is not verified evidence."""
    return bool(assessment and assessment.get("available") is True
                and assessment.get("status") == "pass" and assessment.get("verdict") == "pass"
                and not assessment.get("gross_failure") and not assessment.get("temporal_failure"))
