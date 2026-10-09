"""Generic explicit state negation, without models or image generations."""
import pytest
from PIL import Image

from app.services import visual_qa as qa
from test.services.test_visual_qa_state_evidence import Captions


@pytest.mark.parametrize("caption,term", [
    ("Frost is absent.", "frost"),
    ("Frost is not visible.", "frost"),
    ("Frost isn't visible.", "frost"),
    ("There isn't any frost.", "frost"),
    ("There aren’t any cracks.", "cracks"),
    ("The surface is free of frost.", "frost"),
    ("The surface is devoid of scratches.", "scratches"),
    ("Still liquid is not observed.", "still liquid"),
    ("The required mark is missing.", "mark"),
    ("Frost is\nabsent.", "frost"),
])
def test_explicit_absence_respects_required_and_forbidden_contracts(caption, term):
    required = qa.state_check(caption, {"required_evidence": [term]})
    forbidden = qa.state_check(caption, {"forbidden_evidence": [term]})
    assert required["status"] == "fail" and required["state_score"] == 0
    assert forbidden["status"] == "pass" and forbidden["state_score"] == 1
    assert required["violations"] == ["absent " + term]
    assert required["ambiguous_evidence"] == forbidden["ambiguous_evidence"] == []


@pytest.mark.parametrize("caption", [
    "The surface is not without frost.",
    "Frost is not absent.",
    "Frost isn't absent.",
    "The surface is not free of frost.",
    "Frost is not missing.",
])
def test_double_negation_does_not_prove_either_state(caption):
    for field in ["required_evidence", "forbidden_evidence"]:
        result = qa.state_check(caption, {field: ["frost"]})
        assert result["status"] == "uncertain" and result["state_score"] is None
        assert result["progression_score"] is None and result["ambiguous_evidence"] == ["frost"]


@pytest.mark.parametrize("caption,required_status,forbidden_status", [
    ("The surface is devoid of any detectable frost.", "fail", "pass"),
    ("The surface is not free of any detectable frost.", "uncertain", "uncertain"),
    ("The surface is not completely free of frost.", "uncertain", "uncertain"),
])
@pytest.mark.parametrize("field", ["required_evidence", "forbidden_evidence"])
def test_modifiers_preserve_negation_scope(caption, required_status, forbidden_status, field):
    result = qa.state_check(caption, {field: ["frost"]})
    expected = required_status if field == "required_evidence" else forbidden_status
    assert result["status"] == expected
    if expected == "uncertain":
        assert result["ambiguous_evidence"] == ["frost"] and result["state_score"] is None


@pytest.mark.parametrize("caption", [
    "Frost may be absent.",
    "There possibly isn't any frost.",
    "The surface might be free of frost.",
])
def test_qualified_explicit_absence_still_abstains(caption):
    assert qa.state_check(caption, {"required_evidence": ["frost"]})["status"] == "uncertain"


@pytest.mark.parametrize("caption", [
    "Frost is not blue.",
    "Frost covers a surface free of dirt.",
    "Frost covers the surface. Smoke is absent.",
])
def test_other_property_or_other_term_negation_does_not_deny_subject(caption):
    assert qa.state_check(caption, {"required_evidence": ["frost"]})["status"] == "pass"


def test_postfix_absence_and_presence_conflict_stays_uncertain():
    result = qa.state_check("Frost is absent. Frost covers the surface.", {"required_evidence": ["frost"]})
    assert result["status"] == "uncertain" and result["ambiguous_evidence"] == ["frost"]


def test_postfix_previous_absence_establishes_progress_but_double_negation_cannot():
    contract = {"required_evidence": ["frost"]}
    clear = qa.state_check("Frost covers the surface.", contract, "Frost is absent.")
    assert clear["status"] == "pass" and clear["progression_score"] == 1
    double = qa.state_check("Frost covers the surface.", contract, "Frost is not absent.")
    assert double["progression_score"] is None


def test_v3_cached_false_pass_is_not_reused_after_negation_fix(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "white").save(image)
    evidence = Captions({str(image): "Frost is absent."})
    cache = qa.EvidenceCache()
    contract = {"temporal": {"required_evidence": ["frost"]}}
    legacy_key = qa.cache_key("visual-qa-3", evidence.model_identity, [qa.digest(image), None, None], contract)
    cache.put(legacy_key, {"verdict": "pass", "available": True, "checks": [], "qa_version": "visual-qa-3"})
    result = qa.VisualQA(evidence, cache).assess(image, contract)
    assert qa.VERSION != "visual-qa-3"
    assert result["verdict"] == "fail" and not result["cache_hit"] and evidence.calls == [str(image)]
