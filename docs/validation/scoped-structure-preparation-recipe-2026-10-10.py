"""CPU-only preparation of fixed structure/state diagnostic cases; no HTTP."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = "658e767d3a1a20425c3d6bb4cbc64f4bfeb4db05"
PINNED = {
    "scripts/scoped_structure_observations.py": "c2559fb6b1e2d5ab889ba2b2ff500fc6e4975661bdb5eec219283c57b9dd5e49",
    "test/test_scoped_structure_observations.py": "47c1205bff89c9ce233c218da27b9e46943f1c261af184128a52cda91c112b2d",
    "scripts/paired_shape_observations.py": "d8f2cf2ac75d3eb9350265cb1108f679bdfef9a75f4b85c7f8819b173dc454d1",
    "scripts/paired_shape_preflight.py": "f7895f49f8507d27a2ef12db3810d942f4aa0731f524e61b0f3edb0c44b1ac83",
    "scripts/prepare_visual_regions.py": "5e876b7fd44102900707a54daadbdbaf97cad112372709a5682cf7caebb0488c",
    "scripts/prepare_profiled_visual_inputs.py": "dc79a073f2f983b0b95b168f8ee85f7f65984070c19ce97aad2600df69f88d23",
    "scripts/observe_paired_shape.py": "b291198e215c3d4f1d2ee805e4e8c6dd639f7f6e047a1ecd1bf193bc3e574618",
    "scripts/evaluate_multimodal_judges.py": "22f593ad2d1f6144f9b55595d885937cbe8c70b9334535dc851961613414b71f",
    "docs/validation/profiled-camera-shape-recipe-2026-10-10.py": "c323312059569f3c91c4dd08bbe9faf0d16fa85fce4ec8f9b237091819aca616",
    "docs/validation/profiled-camera-shape-plan-2026-10-10.json": "2fd9a264b1928a95337d5e7b5fbbf5fb9971c2944380cbdcf685b5699a807b67",
    "docs/validation/retained-camera-control-audit-2026-10-09.json": "4b42f4a20b18ccae31d40e052c6e68bba2c424e98865e464f09eb80709b1d65c",
    "docs/validation/profiled-camera-input-plan-v2-2026-10-10.json": "52c5321236d9732f5b5922991ce5bcee4f3da8fb6ba75175d408fb701c4c9f47",
    "docs/validation/profiled-camera-input-result-v2-2026-10-10.json": "353ea8aca9a488dcd9a66fd7eb4734a58d98801a297deebeee7f01c27b9a2cff",
    "docs/validation/camera-independent-review-preparation-2026-10-10.json": "9d01129929c8b713be811c2bd8ce59505bb91d74d78e50879064460c7e1fb1ea",
    "docs/validation/visual-geometry-human-review-2026-10-08.json": "9d40d80a3fb00dd95894c729840d5e197c7795fe7bb5a881ee1ed3ce61faf7f3",
    "docs/validation/clock-visible-count-human-review-2026-10-10.json": "246f7fda37250a88db4c1ceade617dee5f64fc09fff57bb7f400b85699890b53",
    "docs/validation/visual-qa-dataset-2026-10-08.json": "87d5f99a2bdf258012aec080c84f0df4ac89ad1ba39d118d3abe4f52db44d37f",
    "docs/MUG_MASKED_EDIT_EXECUTION.md": "7233520e1407bdd78ca67214eea22db6d3f1695fe76300824d224440ac316a51",
    "docs/MUG_MASKED_NO_REFERENCE_REPORT.md": "9c615cd3ddd04b0d393ea1a07fe48e1474c9afb66697c77f9a86229509406d93",
    "docs/validation/scoped-structure-final-tests-2026-10-10.txt": "b9eadf0e1ec7516792c5a80765b83e52c5814dd172f575a5bb2b763b2492121c"
}
OUTPUTS = {name: ROOT / ("docs/validation/scoped-structure-" + name + "-2026-10-10.json")
           for name in ["inventory", "plan", "preflight"]}
FOLDER = ROOT / "local_image_stack/experiments/bridge/target/scoped-structure-fullframes-2026-10-10"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    if not PINNED or FOLDER.exists() or any(path.exists() for path in OUTPUTS.values()):
        raise ValueError("Unbound preparation or output already exists")
    for name, expected in PINNED.items():
        if sha(ROOT / name) != expected:
            raise ValueError("Changed preparation input: " + name)
    sys.path.insert(0, str(ROOT))
    from scripts import prepare_visual_regions as native
    from scripts import scoped_structure_observations as observer
    from scripts import paired_shape_preflight as checks
    def read(name):
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    camera_recipe = runpy.run_path(str(ROOT / "docs/validation/profiled-camera-shape-recipe-2026-10-10.py"))
    camera_plan, assets, camera_preflight = camera_recipe["verify"](
        ROOT / "docs/validation/profiled-camera-shape-plan-2026-10-10.json")
    abc = read("docs/validation/visual-geometry-human-review-2026-10-08.json")
    clock = read("docs/validation/clock-visible-count-human-review-2026-10-10.json")
    dataset = read("docs/validation/visual-qa-dataset-2026-10-08.json")
    by_hash = {case["sha256"]: case for case in dataset["cases"]}
    image_hashes = {h for row in abc["rows"] for h in row["image_hashes"].values()}
    image_hashes.update(row["source"]["sha256"] for row in clock["rows"])
    key_inventory = []
    for image_hash in sorted(image_hashes):
        source = by_hash[image_hash]
        from PIL import Image
        assert sha(source["artifact"]) == image_hash
        with Image.open(source["artifact"]) as image:
            key_inventory.append({"case_id": source["id"], "path": source["artifact"], "sha256": image_hash,
                                  "size": list(image.size), "mode": image.mode, "metadata_keys": list(image.info),
                                  "alpha_extrema": list(image.getchannel("A").getextrema()) if image.mode == "RGBA" else None,
                                  "family": "key", "metadata_not_forwarded_to_new_requests": True})
    # Source IDs and review numbers are verified; never reuse an ordinal as an array identity.
    reference = next(row for row in clock["rows"] if row["review_id"] == "1")
    fusion = next(row for row in clock["rows"] if row["review_id"] == "3")
    human_b = next(row for row in abc["rows"] if row["pair"] == "B")
    assert human_b["image_hashes"]["candidate"] != fusion["source"]["sha256"]
    preparation = {"protocol": "visual-region-preparation-plan-1", "margin_pixels": 0, "regions": []}
    for label, row in [("key_reference", reference), ("key_fusion", fusion)]:
        source = row["source"]
        preparation["regions"].append({"id": label, "source": {k: source[k] for k in ["path", "sha256", "size"]},
                                       "box": [0, 0, *source["size"]], "required_box": [0, 0, *source["size"]]})
    manifest = native.prepare(preparation, FOLDER, workspace_root=ROOT)
    prepared = {row["id"]: {k: row["crop"][k] for k in ["path", "sha256", "size"]} for row in manifest["regions"]}
    audit = read("docs/validation/retained-camera-control-audit-2026-10-09.json")
    diagnostics = checks.checked_json(audit["bindings"]["diagnostics"], ROOT)
    scene = next(s for s in diagnostics["plan_scenes"] if s["scene"] == 3)
    state = "a blank white photo sheet emerging from the front slot"
    assert state in scene["prompt"] and scene["canonical_subject"] == "Polaroid SX-70 camera"
    key_scope = {"subject": "silver key", "protected_structure": "The complete key's inherent physical parts and the connections between them.",
                 "allowed_state_changes": []}
    camera_scope = {"subject": "instant camera", "protected_structure": "The camera body and its attached components, excluding separately emitted photographic output.",
                    "allowed_state_changes": [state]}
    cases = [{"case_id": "identical_key_control", "reference": prepared["key_reference"], "candidate": prepared["key_reference"], "scope": key_scope},
             {"case_id": "human_reported_key_fusion", "reference": prepared["key_reference"], "candidate": prepared["key_fusion"], "scope": key_scope},
             {"case_id": "camera_body_with_declared_output_state", "reference": camera_plan["cases"][0]["reference"],
              "candidate": camera_plan["cases"][0]["candidate"], "scope": camera_scope}]
    inventory = {"protocol": "retained-structure-state-control-inventory-1", "checked_utc": datetime.now(timezone.utc).isoformat(),
                 "base_head": BASE, "key_images": key_inventory, "distinct_key_images": len(key_inventory),
                 "human_shape_review": {"path": "docs/validation/visual-geometry-human-review-2026-10-08.json", "pairs": ["A", "B", "C"]},
                 "human_clock_review": {"path": "docs/validation/clock-visible-count-human-review-2026-10-10.json", "images": 4},
                 "human_b_and_clock_fusion_are_distinct_images": True,
                 "human_structural_defect_images_in_inventory": [human_b["image_hashes"]["candidate"], fusion["source"]["sha256"]],
                 "independent_structural_defect_families": ["key"],
                 "camera": {"prepared_pair": camera_plan["cases"][0], "human_structure_label": None,
                            "fully_blind_review_established": False, "state_policy_origin": "explicit experimental scope grounded in scene3 prompt, not a runtime QA contract field",
                            "original_scene_metadata": {key: scene.get(key) for key in ["scene", "canonical_subject", "reference_need", "reference_target", "continuity_description"]},
                            "state_prompt_literal": state, "transitive_preflight": camera_preflight,
                            "unknown_body_correctness_does_not_count_as_negative_or_false_alarm": True},
                 "exclusions": [{"id": "photo_whole_object", "reason": "candidate right edge clipped by assistant inspection; no whole-object gold"},
                                {"id": "mug_masked_and_no_reference_controls", "reason": "closed unusable structural controls, no clean separation; mask-region approval is not result gold"},
                                {"id": "warm_hot_cooled_mug", "reason": "temporal cue controls do not establish an independently reviewed structural defect"}],
                 "native_key_preparation": {"plan": preparation, "manifest_path": str(FOLDER / "manifest.json"),
                                            "manifest_sha256": sha(FOLDER / "manifest.json"), "fullframe_pixels_preserved": True,
                                            "metadata_removed": True, "color_transform": False, "resampling": False,
                                            "rectangle_completeness_not_physical_object_coverage": True},
                 "color_camera_preparation_reused": True, "original_pixel_identity_claimed_for_camera": False,
                 "new_model_requests": 0, "generation_requests": 0, "model_selection_approved": False}
    save(OUTPUTS["inventory"], inventory)
    offline_labels = [{"case_id": cases[0]["case_id"], "structure_expectation": "not_observed", "origin": "byte-identical prepared PNG control, not physical identity"},
                      {"case_id": cases[1]["case_id"], "structure_expectation": "observed", "origin": "direct user's image3 fusion statement; exploratory selected case, not a held-out label",
                       "connection_expectation": "fusion_reported", "numeric_keys_are_not_two_detached_objects": True},
                      {"case_id": cases[2]["case_id"], "structure_expectation": None, "origin": "camera human review pending; assistant/model outputs not independent gold"}]
    budget = {"requests_per_model": 3, "maximum_requests_total": 6, "automatic_retries": 0, "generation_requests": 0,
              "downloads": 0, "max_tokens": 512, "temperature": 0, "thinking": False, "http_timeout_seconds": 60,
              "context": 8192, "min_image_tokens": 1024, "max_image_tokens": 1536, "port": 8092,
              "owned_sequential_servers_only": True, "stop_each_cohort_at_first_invalid_or_unavailable": True}
    plan = {"protocol": "scoped-structure-state-probe-plan-1", "declared_utc": datetime.now(timezone.utc).isoformat(),
            "base_head": BASE, "stage": "prepared_cpu_not_executed", "budget": budget,
            "models": ["unsloth/Qwen3.5-9B-GGUF", "Qwen/Qwen3-VL-8B-Instruct-GGUF"],
            "cases": cases, "case_order": [case["case_id"] for case in cases], "offline_labels_not_sent": offline_labels,
            "scope_origin": "manual experimental mapping of retained target and scene state; no live planner schema added",
            "assets_manifest": camera_plan["assets_manifest"], "response_schema": observer.schema(),
            "observer": {"path": "scripts/scoped_structure_observations.py", "sha256": sha(ROOT / "scripts/scoped_structure_observations.py"), "version": observer.VERSION},
            "bindings": {name: {"path": name, "sha256": expected} for name, expected in PINNED.items()},
            "inventory": {"path": str(OUTPUTS["inventory"].relative_to(ROOT)), "sha256": sha(OUTPUTS["inventory"])},
            "recipe": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(__file__)},
            "limits": ["New explicit scope and 512-token response budget; not a causal prompt-only ablation of older generic256 results.",
                       "Selection follows prior raw/model/human observations; no general accuracy, holdout or blind human review claimed.",
                       "A completed structural-change enum is not proof of specifically detected fusion; inspect literal evidence independently.",
                       "No identity, admission, automatic rejection or routing authority; old cohorts, labels and raw remain unchanged.",
                       "No independent structural defect of a second family is currently established."]}
    bindings = []
    for case in cases:
        request = observer.payload(case["reference"], case["candidate"], case["scope"])
        bindings.append({"case_id": case["case_id"], "scope_sha256": fingerprint(case["scope"]),
                         "request_sha256": fingerprint(request), "prompt": request["messages"][0]["content"][0]["text"],
                         "ordered_inputs": [{"role": role, "sha256": case[role]["sha256"]} for role in ["reference", "candidate"]]})
    plan["request_bindings"] = bindings
    save(OUTPUTS["plan"], plan)
    for region in manifest["regions"]:
        source_row = next(row for row in preparation["regions"] if row["id"] == region["id"])
        rebuilt, data = native.render(source_row, 0)
        assert data == Path(region["crop"]["path"]).read_bytes()
    save(OUTPUTS["preflight"], {"protocol": "scoped-structure-preparation-preflight-1", "checked_utc": datetime.now(timezone.utc).isoformat(),
                               "plan": {"path": str(OUTPUTS["plan"].relative_to(ROOT)), "sha256": sha(OUTPUTS["plan"])},
                               "key_pngs_reconstructed_exactly": True, "original_sources_rehashed": True,
                               "camera_transitive_preflight_passed": True, "ordered_request_bindings": bindings,
                               "new_model_requests": 0, "generation_requests": 0, "admission_allowed": False})
    print(json.dumps({"distinct_key_images": len(key_inventory), "distinct_human_structural_defect_images": 2,
                      "defect_families": 1, "prepared_pairs": len(cases), "new_model_requests": 0}))


if __name__ == "__main__":
    main()
