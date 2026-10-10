"""Frozen CPU audit; archived evidence only. Does not instantiate visual models."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
BASE = "f39b46d3544243f563615e408fe26cc70b935b04"
# These hashes are bound before executing the recipe, not recomputed as expectations.
PINNED = {
    "app/services/visual_qa.py": "092690cb77ccf3e67d823512f467601a789c207a979a87f8849ff90033a39fdd",
    "app/services/material.py": "2b80fb84296131338dbb063b78588478d9f07b10e9f3c69e6079e5408bf44c52",
    "app/services/paired_visual_observation_diagnostics.py": "c25879a6b4248ab7c821add9a8dc4401e76330d93a6498174f9cc71278825b66",
    "scripts/paired_shape_observations.py": "d8f2cf2ac75d3eb9350265cb1108f679bdfef9a75f4b85c7f8819b173dc454d1",
    "test/services/test_visual_qa_quantity_negation.py": "b2cdd6b7a25a2505044e14f0840181fe62eda2ff6b5dfff70c6ad5f4a348e3a6",
    "test/services/test_visual_qa.py": "9e2fead6d7042d13c0fa20be375f62eacfec9d36fb1064aa6953d0e139a798c3",
    "docs/validation/visual-qa-dataset-2026-10-08.json": "87d5f99a2bdf258012aec080c84f0df4ac89ad1ba39d118d3abe4f52db44d37f",
    "docs/validation/visual-qa-final-results-2026-10-08.json": "4652017900a1c5d29f90c6b9c3bd6f8a6a869fb4b161a19c990b8d5614813882",
    "docs/validation/profiled-camera-shape-analysis-2026-10-10.json": "a35758d772d6982e82dad44e60a37e3fad459e298c41661af3c0c8e56b9a0100",
    "docs/validation/profiled-camera-shape-plan-2026-10-10.json": "2fd9a264b1928a95337d5e7b5fbbf5fb9971c2944380cbdcf685b5699a807b67",
    "docs/validation/camera-independent-review-preparation-2026-10-10.json": "9d01129929c8b713be811c2bd8ce59505bb91d74d78e50879064460c7e1fb1ea",
    "docs/validation/clock-visible-count-human-review-2026-10-10.json": "246f7fda37250a88db4c1ceade617dee5f64fc09fff57bb7f400b85699890b53",
    "docs/validation/quantity-negation-final-v2-tests-2026-10-10.txt": "6be67394b6a99d0c94c03d1021b9f23429e4f7cc9ad005c601d52bce026ef8ac"
}
OUTPUT = ROOT / "docs/validation/part-state-and-quantity-audit-2026-10-10.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def functions(source):
    return {node.name: node for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def arguments(node):
    return [arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]


def main():
    if not PINNED or OUTPUT.exists():
        raise ValueError("Missing frozen bindings or output already exists")
    for relative, expected in PINNED.items():
        if digest(ROOT / relative) != expected:
            raise ValueError("Frozen audit input changed: " + relative)
    sys.path.insert(0, str(ROOT))
    from app.services import visual_qa as current
    from app.config import config

    old_source = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", BASE + ":app/services/visual_qa.py"]
    )
    old = types.ModuleType("frozen_quantity_v4")
    exec(compile(old_source, "git:" + BASE + ":app/services/visual_qa.py", "exec"), old.__dict__)
    assert old.VERSION == "visual-qa-4" and current.VERSION == "visual-qa-5"
    new_source = (ROOT / "app/services/visual_qa.py").read_text(encoding="utf-8")
    old_functions, new_functions = functions(old_source.decode("utf-8")), functions(new_source)
    unchanged = {name: ast.dump(old_functions[name]) == ast.dump(new_functions[name])
                 for name in ("state_check", "silhouette", "overall")}
    assert all(unchanged.values())

    material_source = (ROOT / "app/services/material.py").read_text(encoding="utf-8")
    material_functions = functions(material_source)
    private_args = arguments(material_functions["_download_videos_openai_image_on_demand"])
    public_args = arguments(material_functions["download_videos"])
    assert "scene_qa_contracts" in private_args and "scene_qa_contracts" not in public_args
    factory_source = ast.get_source_segment(material_source, material_functions["_new_visual_qa_engine"])
    assert "visual_qa.FlorenceEvidence" in factory_source
    allowed_reads = [ast.get_source_segment(new_source, node) for node in ast.walk(ast.parse(new_source))
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                     and node.func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant)
                     and node.args[0].value == "allowed_changes"]
    assert allowed_reads == ['contract.get("allowed_changes", [])']

    dataset = json.loads((ROOT / "docs/validation/visual-qa-dataset-2026-10-08.json").read_text(encoding="utf-8"))
    archive = json.loads((ROOT / "docs/validation/visual-qa-final-results-2026-10-08.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in dataset["cases"]}
    replays = []
    for row in archive["rows"]:
        case, result = cases[row["id"]], row["new"]
        candidate_hash = digest(case["artifact"])
        assert candidate_hash == case["sha256"] == result["image_sha256"]
        caption_reads = [o for o in result["observations"]
                         if o.get("task") == "<MORE_DETAILED_CAPTION>" and o.get("image_sha256") == candidate_hash]
        od_reads = [o for o in result["observations"] if o.get("task") == "<OD>"
                    and o.get("image_sha256") == candidate_hash]
        assert len(caption_reads) == len(od_reads) == 1
        assert caption_reads[0]["available"] and caption_reads[0]["value"] == result["caption"]
        detections = od_reads[0]["value"] if od_reads[0].get("available") else {}
        for constraint in case["contract"].get("counts", []):
            before = old.quantity(result["caption"], detections, constraint)
            after = current.quantity(result["caption"], detections, constraint)
            replays.append({"case_id": row["id"], "candidate_sha256": candidate_hash,
                            "caption_sha256": canonical_digest(result["caption"]),
                            "detections_sha256": canonical_digest(detections),
                            "constraint": constraint, "v4": before, "v5": after,
                            "same_result": before == after})
    assert replays and all(row["same_result"] for row in replays)

    controls = []
    literals = [("No keys are visible.", "key", 1, "fail"),
                ("Not a single key is visible.", "key", 1, "uncertain"),
                ("There are not two keys in this image.", "key", 2, "uncertain"),
                ("The image does not show one key.", "key", 1, "uncertain"),
                ("Two keys have not been seen.", "key", 2, "uncertain"),
                ("Two keys are not being shown.", "key", 2, "uncertain"),
                ("There are two absent keys.", "key", 2, "uncertain"),
                ("Two keys have not been painted blue.", "key", 2, "pass"),
                ("A single camera is visible; the photograph is not developed.", "camera", 1, "pass")]
    for caption, subject, count, expected in literals:
        constraint = {"subject": subject, "expected_count": count}
        before, after = old.quantity(caption, {}, constraint), current.quantity(caption, {}, constraint)
        assert after["status"] == expected
        controls.append({"caption": caption, "constraint": constraint, "expected_status": expected,
                         "expectation_provenance": "synthetic linguistic policy control, no image/model inference",
                         "v4": before, "v5": after})

    value = {"protocol": "part-state-contract-and-quantity-audit-1",
             "executed_utc": datetime.now(timezone.utc).isoformat(), "base_head": BASE,
             "recipe": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": digest(__file__)},
             "bindings": {name: {"path": name, "sha256": sha} for name, sha in PINNED.items()},
             "git_v4_source_sha256": hashlib.sha256(old_source).hexdigest(),
             "versions": {"before": old.VERSION, "after": current.VERSION},
             "unchanged_function_ast": unchanged,
             "contracts": {"public_wrapper_exposes_scene_qa_contracts": False,
                           "private_loop_exposes_scene_qa_contracts": True,
                           "default_evidence_constructor": "FlorenceEvidence",
                           "qa_flag_current_is_literal_true": config.app.get("openai_image_visual_qa_experimental_enabled") is True,
                           "allowed_changes_reads": allowed_reads,
                           "allowed_change_used": "rotation for outer silhouette only",
                           "identity_critical_is_uncertain": True,
                           "part_or_internal_geometry_not_established_by_outer_mask": True,
                           "paired_observer_generic_major_parts_has_no_allowed_functional_state_context": True,
                           "diagnostic_callback_private_and_explicit": True,
                           "diagnostic_has_no_admission_authority": True},
             "quantity_replay": {"archive_rows": len(archive["rows"]), "quantity_checks": len(replays),
                                 "identical_results": len(replays), "rows": replays,
                                 "meaning": "v4/v5 quantity logic over identical archived caption/OD, not fresh QA or visual accuracy"},
             "synthetic_controls": controls,
             "human_camera_review": {"status": "pending", "board_excludes_model_values": True,
                                     "chat_disclosed_disagreement": True,
                                     "fully_blind_human_review_not_established": True},
             "human_clock_review": {"status": "received_previously_and_preserved",
                                    "counts_hands_keys": [[2, 1], [3, 1], [2, 2], [3, 1]],
                                    "merged_key_is_not_two_detached_objects": True,
                                    "aesthetic_preference_not_identity_approval": True},
             "new_inference_requests": 0, "generation_requests": 0, "model_downloads": 0,
             "gpu_benchmarks": 0, "service_controls": 0,
             "next": "Ground a generic subject part/state scope and structural controls before any new judge queries; preserve closed raw and pending independent labels."}
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "quantity_checks": len(replays),
                      "identical_results": len(replays), "synthetic_controls": len(controls)}))


if __name__ == "__main__":
    main()
