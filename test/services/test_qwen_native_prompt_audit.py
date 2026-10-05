"""Offline planner-to-request audit using a generic device/output sequence."""
import re

import pytest

from app.services import material
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401
from test.services.test_evidence_semantic_fallback import plan, rejected


def capture_requests(monkeypatch, fallback=False):
    monkeypatch.setattr(material.config, "app", {})
    monkeypatch.setattr(material, "_openai_image_endpoint", lambda **kw: ("mock://image", "qwen-image-2.1"))
    monkeypatch.setattr(material, "_precision_fallback_model", lambda: "offline-fallback" if fallback else "")
    payloads = []
    monkeypatch.setattr(material, "_request_openai_image", lambda endpoint, payload: payloads.append(payload) or (None, "invalid image"))
    return payloads


@pytest.mark.parametrize("state", ["", "twin gears spraying lubricant", "rests on a desk"])
def test_rejected_state_cannot_return_through_visual_rewrite(monkeypatch, state):
    scene = plan([rejected(observable_subject="indicator tile", observable_state=state,
                           visual_state="twin gears spraying lubricant")],
                 ["The indicator tile rests on a desk."])[0]
    payloads = capture_requests(monkeypatch)
    material.generate_images_openai(scene["prompt"], 1)
    assert "indicator tile" in payloads[0]["prompt"]
    assert "twin gears" not in payloads[0]["prompt"]
    assert "spraying lubricant" not in payloads[0]["prompt"]


def test_fallback_model_keeps_canvas_role(monkeypatch):
    payloads = capture_requests(monkeypatch, fallback=True)
    material.generate_images_openai("The indicator tile shows a faint amber glyph.", 1,
        route="precision", reference_images=["root.png", "device.png"],
        reference_subject="indicator tile", reference_info={"reference_pack": [
            {"role": "continuity", "description": "indicator tile with triangular glyph"},
            {"role": "identity", "description": "source console"}]})
    assert len(payloads) == 2
    assert payloads[1]["reference_image"] == "root.png"
    assert "as the canvas" in payloads[1]["prompt"]
    assert "from scratch" not in payloads[1]["prompt"]
    assert "<image2>" not in payloads[1]["prompt"]


def test_duplicate_retry_never_prompts_with_composition_identifier(pipeline, monkeypatch):
    run, _ = pipeline
    payloads = capture_requests(monkeypatch)
    real_generate = material.generate_images_openai
    calls = []
    def generate(**kw):
        real_generate(**kw)
        calls.append(kw)
        return [item("original" if len(calls) == 1 else "retry")]
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda path, *a, **kw:
        {"actionable": path == "original.png", "best_similarity": .97 if path == "original.png" else .7})
    run(search_terms=["source console on desk"], scene_routes=["precision"],
        scene_subjects=["source console"], scene_composition_keys=["planner_layout_82"])
    assert len(payloads) == 2
    assert "clearly different" in payloads[1]["prompt"]
    assert "planner_layout_82" not in payloads[1]["prompt"]


@pytest.mark.parametrize("ambiguous", ["la hoja", "the sheet"])
def test_generic_sequence_reaches_clean_requests_with_stable_canvas(pipeline, monkeypatch, ambiguous):
    exterior = dict(subject="source console", canonical_subject="source console",
        scene_description="A source console on a desk.", reference_need="identity",
        reference_target="primary_subject", evidence_scope="externally_visible", route="precision")
    hidden = rejected(subject=ambiguous, canonical_subject=ambiguous,
        observable_subject=ambiguous, reference_target="output")
    rows = [exterior, hidden]
    narrations = ["A source console.", f"{ambiguous} rests beside the source console."]
    states = [("a blank surface", "una superficie vacía"),
              ("a faint amber glyph", "un símbolo tenue"),
              ("a clearer amber glyph", "un símbolo más claro"),
              ("a bright amber glyph", "un símbolo brillante"),
              ("a bright amber glyph", "un símbolo brillante")]
    for i, (english, spanish) in enumerate(states):
        rows.append(dict(subject="indicator tile", canonical_subject="indicator tile",
            scene_description="fully developed completed final display",
            composition="completed final display", required_features=["fully developed"],
            reference_need="none", reference_target="output", evidence_scope="externally_visible",
            route="standard", continuity_key="output_chain_82", planner_id="planner_draft_92",
            continuity_description="indicator tile with triangular glyph",
            observable_state=spanish, visual_state=english, temporal_progression=True,
            context_subject="source console" if i == 4 else "",
            includes_primary_subject=i == 4))
        narrations.append(f"La baldosa muestra {spanish}.")
    scenes = plan(rows, narrations)
    assert scenes[1]["planner_validation"] == "coverage_fallback"
    payloads = capture_requests(monkeypatch)
    real_generate = material.generate_images_openai
    calls = []
    def generate(**kw):
        real_generate(**kw)
        calls.append(kw)
        return [item(f"scene{len(calls)}")]
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False, "best_similarity": .4})
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: path)
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
    run, _ = pipeline
    run(search_terms=[s["prompt"] for s in scenes], scene_routes=[s["route"] for s in scenes],
        scene_subjects=[s["subject"] for s in scenes],
        scene_reference_targets=[s["reference_target"] for s in scenes],
        scene_includes_primary_subject=[s["includes_primary_subject"] for s in scenes],
        scene_continuity_keys=[s["continuity_key"] for s in scenes],
        scene_continuity_descriptions=[s["continuity_description"] for s in scenes])
    assert len(payloads) == 7
    assert "identity/reference evidence" in payloads[0]["prompt"]
    assert "reference_image" not in payloads[2]  # Standard root generation.
    for payload in payloads[3:]:
        assert payload["reference_image"] == "scene3.png"
    early = payloads[3]["prompt"]
    assert "a faint amber glyph" in early
    assert not re.search(r"\b(final|completed|developed)\b", early)
    last = payloads[-1]["prompt"]
    assert "<image1> is the canvas" in last
    assert "<image2> is identity evidence for the separate factual subject" in last
    assert "A separate source console is visible in the surrounding scene" in last
    assert last.count("Apply this change:") == 1
    for payload in payloads:
        assert all(token not in payload["prompt"] for token in
            (ambiguous, "twin gears", "spraying lubricant", "output_chain_82", "planner_draft_92", "La baldosa", "un símbolo"))
