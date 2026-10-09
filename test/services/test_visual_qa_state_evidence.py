"""Regression proof for ambiguous temporal captions; CPU only, no models."""
import pytest
from PIL import Image

from app.services import visual_qa as qa


@pytest.mark.parametrize("caption,field,term", [
    ("The surface may have frost.", "required_evidence", "frost"),
    ("Frost might cover the surface.", "required_evidence", "frost"),
    ("Perhaps the bottle is empty.", "required_evidence", "empty"),
    ("The surface has frost, possibly.", "required_evidence", "frost"),
    ("The surface has frost?", "required_evidence", "frost"),
    ("If the surface has frost, it is cold.", "required_evidence", "frost"),
    ("There might be smoke.", "forbidden_evidence", "smoke"),
    ("The container may have no smoke.", "forbidden_evidence", "smoke"),
    ("It is unclear whether the surface is wet.", "required_evidence", "wet"),
])
def test_qualified_state_is_not_certain(caption, field, term):
    result = qa.state_check(caption, {field: [term]})
    assert result["status"] == "uncertain"
    assert result["state_score"] is None and result["progression_score"] is None
    assert result["identity_score"] is None
    assert result["ambiguous_evidence"] == [term]
    assert result["violations"] == []


@pytest.mark.parametrize("caption,field,term", [
    ("The surface has frost. The surface has no frost.", "required_evidence", "frost"),
    ("The surface has no frost. The surface has frost.", "required_evidence", "frost"),
    ("Smoke rises. There is no smoke.", "forbidden_evidence", "smoke"),
    ("There is no smoke. Smoke rises.", "forbidden_evidence", "smoke"),
    ("Frost is visible. There may be no frost.", "required_evidence", "frost"),
])
def test_conflicting_state_mentions_abstain(caption, field, term):
    result = qa.state_check(caption, {field: [term]})
    assert result["status"] == "uncertain" and result["state_score"] is None
    assert result["ambiguous_evidence"] == [term] and result["violations"] == []


@pytest.mark.parametrize("caption", [
    "The lighting may change. The surface has frost.",
    "There might be a reflection, but the surface has frost.",
    "No smoke but frost on the surface.",
    "Maybe a reflection; frost covers the surface.",
])
def test_unrelated_clause_does_not_qualify_or_negate_state(caption):
    result = qa.state_check(caption, {"required_evidence": ["frost"]})
    assert result["status"] == "pass" and result["state_score"] == 1


@pytest.mark.parametrize("caption,field,term,status", [
    ("The surface has no\nfrost.", "required_evidence", "frost", "fail"),
    ("The container is without\nsmoke.", "forbidden_evidence", "smoke", "pass"),
    ("There may be\nfrost.", "required_evidence", "frost", "uncertain"),
    ("There might be no\nsmoke.", "forbidden_evidence", "smoke", "uncertain"),
])
def test_line_wrapping_preserves_negation_and_qualification(caption, field, term, status):
    result = qa.state_check(caption, {field: [term]})
    assert result["status"] == status
    assert result["state_score"] == (1 if status == "pass" else 0 if status == "fail" else None)


@pytest.mark.parametrize("previous", [
    "The surface might have no frost.",
    "There is no frost. There is frost.",
    "Frost may be absent.",
    "No frost?",
    "The surface is dark.",
])
def test_ambiguous_previous_evidence_never_establishes_progression(previous):
    result = qa.state_check("The surface has frost.", {"required_evidence": ["frost"]}, previous)
    assert result["status"] == "pass" and result["state_score"] == 1
    assert result["progression_score"] is None and result["identity_score"] is None


@pytest.mark.parametrize("caption,contract,status", [
    ("The surface shows frost.", {"required_evidence": ["frost"]}, "pass"),
    ("There is no frost on the surface.", {"required_evidence": ["frost"]}, "fail"),
    ("Smoke rises.", {"forbidden_evidence": ["smoke"]}, "fail"),
    ("There is no smoke.", {"forbidden_evidence": ["smoke"]}, "pass"),
    ("The surface is blue.", {"required_evidence": ["frost"]}, "uncertain"),
    ("A container is visible.", {"forbidden_evidence": ["smoke"]}, "uncertain"),
])
def test_unequivocal_evidence_and_omission_keep_existing_policy(caption, contract, status):
    assert qa.state_check(caption, contract)["status"] == status


def test_independent_definite_violation_still_fails_but_ambiguous_previous_cannot_progress():
    contract = {"required_evidence": ["frost"], "forbidden_evidence": ["smoke"]}
    previous = "The surface may have frost. Smoke rises."
    result = qa.state_check(previous, contract)
    assert result["status"] == "fail" and result["violations"] == ["smoke"]
    assert result["ambiguous_evidence"] == ["frost"]
    current = qa.state_check("The surface has frost. There is no smoke.", contract, previous)
    assert current["status"] == "pass" and current["progression_score"] is None


def test_definite_previous_absence_still_establishes_progression():
    result = qa.state_check("Frost covers the surface.", {"required_evidence": ["frost"]},
                            "There is no frost.")
    assert result["status"] == "pass" and result["progression_score"] == 1


class Captions:
    model_identity = "state-regression-evidence"

    def __init__(self, values):
        self.values, self.calls = values, []

    def read(self, image):
        self.calls.append(str(image))
        return {"available": True, "value": self.values[str(image)]}


def test_visual_qa_abstains_with_current_or_previous_ambiguity(tmp_path):
    current, previous = tmp_path / "current.png", tmp_path / "previous.png"
    for path in [current, previous]:
        Image.new("RGB", (8, 8), "white").save(path)
    evidence = Captions({str(current): "The surface may have frost.",
                         str(previous): "There is no frost."})
    contract = {"temporal": {"required_evidence": ["frost"], "previous_state": "without frost",
                              "previous_image": str(previous)}}
    first = qa.VisualQA(evidence).assess(current, contract)
    assert first["verdict"] == "uncertain" and first["checks"][0]["state_score"] is None
    evidence.values.update({str(current): "The surface has frost.",
                            str(previous): "There might be no frost."})
    second = qa.VisualQA(evidence).assess(current, contract)
    assert second["verdict"] == "uncertain" and second["checks"][0]["progression_score"] is None


def test_changed_qa_version_ignores_seeded_legacy_pass_cache(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "white").save(image)
    evidence = Captions({str(image): "The surface may have frost."})
    cache = qa.EvidenceCache()
    contract = {"temporal": {"required_evidence": ["frost"]}}
    legacy_key = qa.cache_key("visual-qa-2", evidence.model_identity, [qa.digest(image), None, None], contract)
    cache.put(legacy_key, {"verdict": "pass", "available": True, "checks": [], "qa_version": "visual-qa-2"})
    result = qa.VisualQA(evidence, cache).assess(image, contract)
    assert qa.VERSION != "visual-qa-2"
    assert result["verdict"] == "uncertain" and not result["cache_hit"]
    assert evidence.calls == [str(image)]
