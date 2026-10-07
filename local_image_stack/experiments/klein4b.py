"""Offline Klein 4B contracts. No production imports, dispatch or downloads."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


MODEL_ID = "flux-klein-4b-distilled-fp8"
ALIASES = {"flux-klein-4b-t2i-exp": "t2i", "flux-klein-4b-edit-exp": "edit"}
FILENAMES = {
    "diffusion_model": "flux-2-klein-4b-fp8.safetensors",
    "text_encoder": "qwen_3_4b.safetensors",
    "vae": "flux2-vae.safetensors",
}
ROLES = {"continuity_anchor", "identity_reference", "factual_reference", "style_reference"}


@dataclass(frozen=True)
class Reference:
    image: str
    role: str


def resolve_alias(alias: str, manifest: dict, *, commercial: bool = False) -> dict:
    """Resolve a planned binding; this does not authorize execution."""
    if alias not in ALIASES:
        raise ValueError(f"Unknown experimental alias: {alias}")
    if manifest.get("model_id") != MODEL_ID:
        raise ValueError("Expected Klein 4B Distilled FP8 manifest")
    for key, filename in FILENAMES.items():
        component = manifest.get("components", {}).get(key, {})
        if component.get("filename") != filename:
            raise ValueError(f"{key}: expected {filename}")
        if commercial and component.get("license_scope") != "commercial_allowed":
            raise ValueError(f"{key}: incompatible commercial license scope")
        if component.get("license") != "Apache-2.0":
            raise ValueError(f"{key}: expected declared Apache-2.0 license")
    binding = manifest.get("workflows", {}).get(ALIASES[alias], {})
    if binding.get("alias") != alias or binding.get("checkpoint") != FILENAMES["diffusion_model"]:
        raise ValueError("Workflow binding must target this 4B alias and checkpoint")
    return dict(binding)


def build_request(
    manifest: dict, prompt: str, seed: int, size: str,
    references: tuple[Reference, ...] = (), *, alias: str | None = None,
    temporal_progression: bool = False, temporal_state: str = "", commercial: bool = False,
) -> dict:
    """Build a non-dispatchable request plus ordered role metadata."""
    if not prompt.strip():
        raise ValueError("Prompt is required")
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError("Seed must fit the bridge's non-negative signed integer")
    if not re.fullmatch(r"[1-9]\d*x[1-9]\d*", size) or any(int(x) % 16 for x in size.split("x")):
        raise ValueError("Size must contain positive dimensions divisible by 16")
    if len(references) > 3:
        raise ValueError("The experimental pack is limited to three references")
    images = [ref.image for ref in references]
    if any(not image.strip() for image in images) or len(set(images)) != len(images):
        raise ValueError("References must be nonempty and unique; order is never rewritten")
    if any(ref.role not in ROLES for ref in references):
        raise ValueError("Unknown reference role")
    if sum(ref.role == "continuity_anchor" for ref in references) > 1:
        raise ValueError("Only one stable continuity root is allowed")
    expected = "flux-klein-4b-edit-exp" if references else "flux-klein-4b-t2i-exp"
    alias = alias or expected
    binding = resolve_alias(alias, manifest, commercial=commercial)
    if alias != expected:
        raise ValueError("T2I requires zero references; Edit requires one to three")
    if temporal_progression:
        if not temporal_state.strip() or not any(ref.role == "continuity_anchor" for ref in references):
            raise ValueError("Temporal editing requires a continuity root and requested state")
        if re.search(
            r"keep all visible content unchanged|underlying depicted content unchanged|"
            r"preserve (?:the )?(?:previous|prior) (?:visual )?state", prompt, re.I,
        ):
            raise ValueError("Prompt contradicts temporal progression")
    elif temporal_state.strip():
        raise ValueError("Temporal state requires temporal_progression")
    clauses = [prompt.strip()]
    for index, ref in enumerate(references, 1):
        clauses.append(f"Input image {index} has role {ref.role}.")
        if ref.role == "continuity_anchor":
            clauses.append(
                f"Use image {index} as the stable root of the same physical subject. "
                "Preserve its identity and appropriate geometry/composition; "
                "physical identity does not require preserving the previous visual state."
            )
    if temporal_progression:
        clauses.append(f"The result MUST advance to this requested visible state: {temporal_state.strip()}.")
    payload = {"model": alias, "prompt": "\n".join(clauses), "seed": seed, "size": size,
               "steps": 4, "guidance": 1.0, "n": 1}
    for index, ref in enumerate(references, 1):
        key = "reference_image" if index == 1 else f"reference_image_{index}"
        payload[key] = ref.image
    return {"workflow": binding, "payload": payload, "dispatch_allowed": False,
            "reference_roles": [ref.role for ref in references]}


def fallback_alias(failure: str, *, has_references: bool, image_generated: bool = False,
                   enabled: bool = False) -> str | None:
    """Future opt-in policy only; no fallback is enabled in this experiment."""
    if enabled and has_references and not image_generated and failure in {
        "confirmed_generation_error", "invalid_output",
    }:
        return "flux-klein-4b-edit-exp"
    return None


def _verify_file(path: Path, description: dict, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"Missing asset: {label} ({path.name})")
    if not str(description.get("source", "")).startswith("https://") or not description.get("license_source"):
        raise ValueError(f"Unverified provenance/license: {label}")
    digest = description.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError(f"Missing verified SHA-256: {label}")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise ValueError(f"SHA-256 mismatch: {label}")


def require_ready(manifest: dict, assets: dict[str, Path], workflows: dict[str, Path],
                  *, commercial: bool = False) -> None:
    """Reject unverified local material; hashes do not certify GPU/semantic quality."""
    for alias in ALIASES:
        resolve_alias(alias, manifest, commercial=commercial)
    for key, filename in FILENAMES.items():
        path = Path(assets.get(key, "__missing__"))
        if path.name != filename:
            raise ValueError(f"Missing or wrong asset: {filename}")
        _verify_file(path, manifest["components"][key], filename)
    for mode in ("t2i", "edit"):
        description = manifest["workflows"][mode]
        if description.get("license") != "MIT":
            raise ValueError(f"{mode}: missing verified workflow license declaration")
        if description.get("format") != "comfyui_api":
            raise ValueError(f"{mode}: API workflow export has not been verified")
        path = Path(workflows.get(mode, "__missing__"))
        _verify_file(path, description, mode)
        graph = json.loads(path.read_text(encoding="utf-8-sig"))
        for node in graph.values():
            if not isinstance(node, dict):
                raise ValueError(f"{mode}: expected an API node graph")
            for field in ("unet_name", "clip_name", "vae_name", "ckpt_name"):
                name = node.get("inputs", {}).get(field)
                if name is not None and name not in FILENAMES.values():
                    raise ValueError(f"{mode}: undeclared graph asset {name}")
        for loader, field, component in (
            ("UNETLoader", "unet_name", "diffusion_model"),
            ("CLIPLoader", "clip_name", "text_encoder"),
            ("VAELoader", "vae_name", "vae"),
        ):
            names = [node.get("inputs", {}).get(field) for node in graph.values()
                     if isinstance(node, dict) and node.get("class_type") == loader]
            if names != [FILENAMES[component]]:
                raise ValueError(f"{mode}: graph must load exactly {FILENAMES[component]}")
    if not manifest.get("comfyui_commit") or not manifest.get("bridge_commit"):
        raise ValueError("ComfyUI and bridge revisions must be recorded")
    if manifest.get("status") != "ready":
        raise ValueError("Candidate remains planned, not ready")
