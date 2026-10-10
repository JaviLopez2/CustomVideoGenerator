"""Negated numeric mentions cannot certify a visible count; CPU only."""
from PIL import Image
import pytest

from app.services import visual_qa as qa


@pytest.mark.parametrize("caption,count", [
    ("Not a single key is visible.", 1),
    ("There are not two keys in this image.", 2),
    ("The image does not show one key.", 1),
    ("The image doesn't show one key.", 1),
    ("The image doesn’t show one key.", 1),
    ("The image is without two keys.", 2),
    ("The image never shows three keys.", 3),
    ("The image cannot show two keys.", 2),
    ("There are not\ntwo metal keys visible.", 2),
    ("Two keys are not visible.", 2),
    ("Two keys aren't visible.", 2),
    ("Two keys aren’t visible.", 2),
    ("Two keys cannot be seen.", 2),
    ("Two keys are absent.", 2),
    ("A single key is missing.", 1),
    ("No keys are not visible.", 0),
    ("Not no keys are visible.", 0),
    ("Two keys are visible, not one key.", 2),
    ("There are not just two keys.", 2),
    ("There are no more than two keys.", 2),
    ("There are no fewer than two keys.", 2),
    ("Two keys are not missing.", 2),
    ("Two keys have not been seen.", 2),
    ("Two keys are not being shown.", 2),
    ("Two keys haven't been seen.", 2),
    ("Two keys aren't being shown.", 2),
    ("There are two absent keys.", 2),
    ("There are two missing keys.", 2),
])
def test_negated_count_remains_uncertain_without_replacement_count(caption, count):
    result = qa.quantity(caption, {}, {"subject": "key", "expected_count": count})
    assert result["status"] == "uncertain"
    assert result.get("observed_count") is None


def test_detector_agreement_does_not_rehabilitate_negated_caption():
    result = qa.quantity("Not a single key is visible.", {"labels": ["key"]},
                         {"subject": "key", "expected_count": 1})
    assert result["status"] == "uncertain" and result.get("observed_count") is None


@pytest.mark.parametrize("caption,subject,count", [
    ("No keys are visible.", "key", 0),
    ("Two metal keys are visible.", "key", 2),
    ("A single camera is visible; the photograph is not developed.", "camera", 1),
    ("One key is visible. The camera is not printing.", "key", 1),
    ("One key is visible but the camera is not printing.", "key", 1),
    ("One key is visible, not a camera.", "key", 1),
    ("One key is not blue.", "key", 1),
    ("There is not a camera; two keys are visible.", "key", 2),
    ("The camera is not printing and one key is visible.", "key", 1),
    ("Two keys have not been painted blue.", "key", 2),
    ("Two keys are not blue.", "key", 2),
    ("There are two small metal keys.", "key", 2),
    ("Two clock hands are visible.", "clock hands", 2),
])
def test_explicit_counts_keep_their_scope(caption, subject, count):
    result = qa.quantity(caption, {}, {"subject": subject, "expected_count": count})
    assert result["status"] == "pass" and result["observed_count"] == count


@pytest.mark.parametrize("caption", [
    "Two hands have not been detected.",
    "There are two absent hands.",
])
def test_negated_quantity_aliases_are_not_affirmative(caption):
    result = qa.quantity(caption, {}, {"subject": "clock hands", "aliases": ["hands"], "expected_count": 2})
    assert result["status"] == "uncertain" and result.get("observed_count") is None


def test_new_qa_cache_version_rechecks_and_retains_uncertain_result(tmp_path):
    image = tmp_path / "candidate.png"
    Image.new("RGB", (8, 8), "white").save(image)
    contract = {"counts": [{"subject": "key", "expected_count": 1}]}
    class Evidence:
        model_identity = "quantity-negation-fixture"
        calls = 0
        def read(self, path, task="<MORE_DETAILED_CAPTION>"):
            self.calls += 1
            value = "Not a single key is visible." if task == "<MORE_DETAILED_CAPTION>" else {"labels": ["key"]}
            return {"available": True, "value": value}
    evidence = Evidence()
    cache = qa.EvidenceCache()
    old_key = qa.cache_key("visual-qa-4", evidence.model_identity, [qa.digest(image), None, None], contract)
    cache.put(old_key, {"verdict": "pass", "qa_version": "visual-qa-4", "checks": []})
    engine = qa.VisualQA(evidence, result_cache=cache)
    first = engine.assess(image, contract)
    assert first["verdict"] == "uncertain" and first["cache_hit"] is False
    assert first["qa_version"] == "visual-qa-5" and evidence.calls == 2
    second = engine.assess(image, contract)
    assert second["verdict"] == "uncertain" and second["cache_hit"] is True and evidence.calls == 2
    assert cache.get(old_key)["verdict"] == "pass"
