# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.config import config
from app.services import llm, material, task


class TestQwenQualityV31(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_hidden_internal_requires_internal_reference(self):
        inventory = [
            {"slot": 1, "role": "identity", "description": "whole subject"},
            {"slot": 2, "role": "detail", "description": "front controls"},
        ]
        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "internal",
                "evidence_scope": "hidden_internal",
                "reference_critical": True,
            },
            inventory,
        )

        self.assertEqual(status, "unsupported")
        self.assertIn("internal", reason)

    def test_preflight_flags_hidden_evidence_misclassified_as_detail(self):
        issues = llm._scene_plan_preflight_issues(
            [
                {
                    "reference_need": "detail",
                    "evidence_scope": "hidden_internal",
                    "safe_visual_alternative": "show the externally visible result",
                    "reference_critical": False,
                    "required_features": [],
                    "forbidden_features": [],
                    "environment_key": "workbench",
                    "composition_key": "macro_detail",
                    "shot_type": "detail",
                    "environment": "workbench",
                }
            ],
            reference_inventory=[
                {"slot": 1, "role": "identity", "description": "whole subject"}
            ],
        )

        self.assertTrue(
            any("reference_need='internal'" in issue for issue in issues),
            issues,
        )

    def test_preflight_limits_reference_critical_to_precision_budget(self):
        scenes = []
        for index in range(4):
            scenes.append(
                {
                    "reference_need": "identity",
                    "evidence_scope": "externally_visible",
                    "reference_critical": index < 3,
                    "required_features": [],
                    "forbidden_features": [],
                    "environment_key": f"env_{index}",
                    "composition_key": f"composition_{index}",
                    "shot_type": ["wide", "medium", "detail", "full"][index],
                    "environment": f"environment {index}",
                }
            )

        issues = llm._scene_plan_preflight_issues(
            scenes,
            reference_inventory=[
                {"slot": 1, "role": "identity", "description": "whole subject"}
            ],
            precision_budget_ratio=0.5,
        )

        self.assertTrue(any("reference_critical is over budget" in issue for issue in issues))

    def test_precision_budget_never_downgrades_reference_critical_scene(self):
        plan = [
            {
                "route": "precision",
                "reference_critical": True,
                "precision_importance": 0.9,
                "reference_need": "identity",
                "shot_role": "identity",
            },
            {
                "route": "precision",
                "reference_critical": False,
                "precision_importance": 0.2,
                "reference_need": "identity",
                "shot_role": "transition",
            },
            {
                "route": "precision",
                "reference_critical": False,
                "precision_importance": 0.8,
                "reference_need": "detail",
                "shot_role": "evidence",
            },
            {
                "route": "standard",
                "reference_critical": False,
            },
        ]

        result = task._apply_openai_image_precision_budget(
            plan,
            {"precision_ratio": 0.25, "profile": "balanced"},
        )

        self.assertEqual(result[0]["route"], "precision")
        self.assertEqual(
            result[0]["routing_reason"],
            "reference_critical_precision",
        )
        self.assertTrue(
            any(
                item.get("performance_route_override")
                == "precision_budget_to_standard"
                for item in result[1:3]
            )
        )

    def test_reference_selector_uses_anchor_then_scene_specific_evidence(self):
        info = {
            "reference_pack": [
                {
                    "slot": 1,
                    "role": "identity",
                    "anchor": True,
                    "original_file": "01_general_identity.jpg",
                    "description": "overall identity and proportions",
                    "comfyui_input": "ref-1",
                },
                {
                    "slot": 2,
                    "role": "identity",
                    "original_file": "02_primary_front.jpg",
                    "description": "straight front view",
                    "comfyui_input": "ref-2",
                },
                {
                    "slot": 3,
                    "role": "identity",
                    "original_file": "03_threequarter.jpg",
                    "description": "front three quarter view",
                    "comfyui_input": "ref-3",
                },
                {
                    "slot": 4,
                    "role": "identity",
                    "original_file": "04_rear.jpg",
                    "description": "rear view",
                    "comfyui_input": "ref-4",
                },
            ]
        }

        selected, selected_info = material._select_manual_references_for_scene(
            ["ref-1", "ref-2", "ref-3", "ref-4"],
            info,
            "identity",
            "front three quarter view",
            max_refs=3,
        )

        self.assertEqual(selected[0], "ref-1")
        self.assertIn("ref-2", selected)
        self.assertIn("ref-3", selected)
        self.assertNotIn("ref-4", selected)
        selection = selected_info["reference_selection"]
        self.assertEqual(
            selection["status"],
            "anchor_scene_specific_complementary",
        )
        self.assertEqual(
            selection["anchor_reference"]["file"],
            "01_general_identity.jpg",
        )

    def test_reference_library_default_is_twelve_but_scene_pack_remains_three(self):
        config.app.pop("openai_image_manual_reference_max_images", None)
        self.assertEqual(material._manual_precision_reference_max_images(), 12)

        config.app["openai_image_manual_reference_max_images"] = 100
        self.assertEqual(material._manual_precision_reference_max_images(), 20)

    def test_qwen_prompt_names_each_reference_role(self):
        prompt = material._qwen_precision_prompt_with_references(
            "new scene direction",
            "test subject",
            3,
            reference_info={
                "reference_pack": [
                    {"role": "identity", "description": "overall identity"},
                    {"role": "detail", "description": "front control"},
                    {"role": "context", "description": "natural habitat"},
                ]
            },
            forbidden_features=["fake extra dial", "invented label"],
        )

        self.assertIn("<image1>", prompt)
        self.assertIn("<image2>", prompt)
        self.assertIn("<image3>", prompt)
        self.assertIn("identity/whole-subject evidence", prompt)
        self.assertIn("detail evidence", prompt)
        self.assertIn("context/environment evidence", prompt)
        self.assertIn("Explicitly do not depict or introduce", prompt)
        self.assertIn("fake extra dial", prompt)
        self.assertIn("invented label", prompt)

    def test_near_duplicate_only_actionable_when_plan_expected_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "scene.png"
            image = Image.new("RGB", (128, 128), "white")
            for x in range(64):
                for y in range(128):
                    image.putpixel((x, y), (20, 20, 20))
            image.save(image_path)

            image_hash = material._image_dhash64(str(image_path))
            recent = [
                {
                    "scene": 1,
                    "path": str(image_path),
                    "dhash": image_hash,
                    "composition_key": "front_full",
                    "shot_type": "full",
                }
            ]

            same_plan = material._near_duplicate_assessment(
                str(image_path),
                recent,
                composition_key="front_full",
                shot_type="full",
            )
            different_plan = material._near_duplicate_assessment(
                str(image_path),
                recent,
                composition_key="macro_controls",
                shot_type="detail",
            )

        self.assertFalse(same_plan["actionable"])
        self.assertTrue(different_plan["actionable"])
        self.assertEqual(different_plan["best_similarity"], 1.0)
        self.assertEqual(different_plan["matched_scene"], 1)

    def test_qwen_debug_seed_is_honored(self):
        config.app["openai_image_qwen_debug_seed"] = "12345"
        self.assertEqual(material._qwen_request_seed(), 12345)


if __name__ == "__main__":
    unittest.main()
