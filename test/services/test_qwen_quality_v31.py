# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from unittest.mock import patch
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

    def test_output_target_is_not_covered_by_primary_identity_pack(self):
        inventory = [
            {"slot": 1, "role": "identity", "description": "whole primary subject"},
            {"slot": 2, "role": "detail", "description": "primary subject controls"},
        ]

        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "identity",
                "reference_target": "output",
                "evidence_scope": "externally_visible",
                "reference_critical": True,
            },
            inventory,
        )

        self.assertEqual(status, "unsupported")
        self.assertIn("output", reason)

    def test_ordinary_output_importance_does_not_require_primary_pack(self):
        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "none",
                "reference_target": "output",
                "evidence_scope": "externally_visible",
                "reference_critical": True,
            },
            [{"slot": 1, "role": "identity", "description": "primary subject"}],
        )

        self.assertEqual(status, "covered")
        self.assertIn("does not require", reason)

    def test_preflight_flags_unsupported_even_with_safe_alternative(self):
        issues = llm._scene_plan_preflight_issues(
            [
                {
                    "reference_need": "internal",
                    "reference_target": "primary_subject",
                    "evidence_scope": "hidden_internal",
                    "safe_visual_alternative": "show only the externally visible result",
                    "reference_critical": True,
                    "required_features": [],
                    "forbidden_features": [],
                    "environment_key": "inside",
                    "composition_key": "macro_internal",
                    "shot_type": "macro",
                    "environment": "inside device",
                }
            ],
            reference_inventory=[
                {"slot": 1, "role": "identity", "description": "whole subject"}
            ],
        )

        self.assertTrue(any("must be rewritten" in issue for issue in issues), issues)

    def test_hard_coverage_fallback_removes_unsupported_visual_fields(self):
        draft = [
            {
                "subject": "internal rollers and chemical pods",
                "canonical_subject": "device internal rollers",
                "route": "precision",
                "scene_description": "open body showing two rollers and chemical pods",
                "required_features": ["two rollers", "chemical pods"],
                "forbidden_features": [],
                "environment": "dark internal cavity",
                "environment_key": "internal_cavity",
                "composition": "macro top-down cutaway inside the device",
                "composition_key": "macro_internal",
                "lighting": "internal fill light",
                "shot_type": "macro",
                "framing_intent": "detail",
                "shot_role": "process",
                "reference_need": "internal",
                "reference_target": "primary_subject",
                "reference_query": "internal rollers and pods",
                "evidence_scope": "hidden_internal",
                "reference_critical": True,
                "safe_visual_alternative": "two rollers squeezing chemical pods outside the housing",
                "continuity_key": "mechanism",
                "continuity_description": "two rollers squeezing chemical pods",
                "includes_primary_subject": True,
                "precision_importance": 1.0,
            }
        ]
        scene_plan = [
            {
                "narration": "An internal mechanism causes the visible result.",
                "beat": 1,
                "beats": 1,
                "duration": 5.0,
            }
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(draft), json.dumps(draft)],
        ):
            result = llm.generate_scene_image_plan(
                "generic mechanism",
                scene_plan,
                reference_inventory=[
                    {"slot": 1, "role": "identity", "description": "whole subject"}
                ],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(len(result), 1)
        scene = result[0]
        self.assertEqual(scene["route"], "standard")
        self.assertEqual(scene["reference_need"], "none")
        self.assertEqual(scene["reference_target"], "none")
        self.assertEqual(scene["evidence_scope"], "contextual")
        self.assertEqual(scene["planner_validation"], "coverage_fallback")
        self.assertEqual(scene["factual_audit_status"], "applied")
        prompt_text = scene["prompt"].lower()
        self.assertNotIn("chemical pods", prompt_text)
        self.assertNotIn("two rollers", prompt_text)
        self.assertNotIn("dark internal cavity", prompt_text)
        self.assertNotIn("macro top-down cutaway", prompt_text)
        self.assertIn("externally visible result or context", prompt_text)
        self.assertEqual(scene["reference_query"], "")
        self.assertEqual(scene["continuity_key"], "none")
        self.assertEqual(scene["continuity_description"], "")
        self.assertFalse(scene["includes_primary_subject"])
        self.assertNotIn("chemical pods", scene["safe_visual_alternative"])

    def test_unsupported_mechanism_can_reuse_only_previously_covered_exterior_identity(self):
        exterior = {
            "subject": "electric motor", "canonical_subject": "electric motor",
            "route": "precision", "scene_description": "closed electric motor on a bench",
            "reference_need": "identity", "reference_target": "primary_subject",
            "evidence_scope": "externally_visible", "reference_critical": True,
            "continuity_key": "none",
        }
        hidden = {
            **exterior, "scene_description": "electric motor cutaway with twin gears spraying lubricant",
            "reference_need": "internal", "evidence_scope": "hidden_internal",
            "safe_visual_alternative": "twin gears spraying lubricant outside the motor",
            "required_features": ["twin gears", "spraying lubricant"],
        }
        with patch.object(llm, "_generate_response", side_effect=[json.dumps([exterior, hidden])] * 2):
            result = llm.generate_scene_image_plan(
                "electric motor", [{"narration": "The electric motor is enclosed."},
                                   {"narration": "A hidden mechanism transfers force."}],
                reference_inventory=[{"role": "identity", "description": "whole electric motor"}],
            )
        fallback = result[1]
        self.assertEqual(fallback["planner_validation"], "coverage_fallback")
        self.assertEqual(fallback["subject"], "electric motor")
        self.assertEqual(fallback["reference_target"], "primary_subject")
        self.assertEqual(fallback["reference_need"], "identity")
        self.assertEqual(fallback["route"], "precision")
        self.assertTrue(fallback["includes_primary_subject"])
        self.assertIn("closed exterior of electric motor", fallback["prompt"])
        self.assertNotIn("twin gears", fallback["prompt"])
        self.assertNotIn("spraying lubricant", fallback["prompt"])
        self.assertEqual(fallback["continuity_key"], "none")

    def test_factual_audit_can_reclassify_apparently_visible_process_before_gpu(self):
        draft = [
            {
                "subject": "visible process",
                "canonical_subject": "primary device",
                "route": "standard",
                "scene_description": "a process visibly spreading across the output",
                "required_features": [],
                "forbidden_features": [],
                "environment": "table",
                "environment_key": "table",
                "composition": "close view",
                "composition_key": "close_process",
                "lighting": "soft light",
                "shot_type": "close",
                "framing_intent": "detail",
                "shot_role": "process",
                "reference_need": "none",
                "reference_target": "output",
                "reference_query": "",
                "evidence_scope": "externally_visible",
                "reference_critical": False,
                "safe_visual_alternative": "show the visible before and after state",
                "precision_importance": 0.2,
            }
        ]
        audited = [dict(draft[0])]
        audited[0].update(
            {
                "subject": "hidden process between layers",
                "route": "precision",
                "reference_need": "internal",
                "reference_target": "output",
                "reference_query": "process between hidden layers",
                "evidence_scope": "hidden_internal",
                "reference_critical": True,
            }
        )
        scene_plan = [
            {
                "narration": "A hidden reaction produces the visible change.",
                "beat": 1,
                "beats": 1,
                "duration": 5.0,
            }
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(draft), json.dumps(audited)],
        ):
            result = llm.generate_scene_image_plan(
                "generic layered process",
                scene_plan,
                reference_inventory=[
                    {"slot": 1, "role": "identity", "description": "primary subject"}
                ],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(result[0]["planner_validation"], "coverage_fallback")
        self.assertEqual(result[0]["route"], "standard")
        self.assertEqual(result[0]["reference_target"], "none")
        self.assertNotIn("hidden process between layers", result[0]["prompt"].lower())

    def test_hidden_view_language_overrides_visible_identity_classification(self):
        draft = [
            {
                "subject": "device internal component",
                "canonical_subject": "device",
                "route": "precision",
                "scene_description": "cutaway view inside the housing showing the mechanism",
                "required_features": ["internal component"],
                "forbidden_features": [],
                "environment": "interior cavity",
                "environment_key": "device",
                "composition": "direct cutaway through the casing",
                "composition_key": "cutaway",
                "lighting": "soft light",
                "shot_type": "detail",
                "framing_intent": "detail",
                "shot_role": "process",
                "reference_need": "identity",
                "reference_target": "primary_subject",
                "reference_query": "internal mechanism",
                "evidence_scope": "externally_visible",
                "reference_critical": True,
                "safe_visual_alternative": "show the external result",
                "continuity_key": "none",
                "continuity_description": "",
                "precision_importance": 1.0,
            }
        ]
        scene_plan = [
            {
                "narration": "An internal mechanism produces the result.",
                "beat": 1,
                "beats": 1,
                "duration": 5.0,
            }
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(draft), json.dumps(draft)],
        ):
            result = llm.generate_scene_image_plan(
                "generic device",
                scene_plan,
                reference_inventory=[
                    {"slot": 1, "role": "identity", "description": "whole device"}
                ],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(result[0]["planner_validation"], "coverage_fallback")
        self.assertEqual(result[0]["route"], "standard")
        self.assertEqual(result[0]["reference_need"], "none")
        self.assertEqual(result[0]["reference_target"], "none")
        prompt_lower = result[0]["prompt"].lower()
        self.assertNotIn("cutaway view inside", prompt_lower)
        self.assertNotIn("direct cutaway through the casing", prompt_lower)
        self.assertNotIn("internal component", prompt_lower)
        self.assertIn("no cutaway", prompt_lower)

    def test_continuity_preflight_rejects_changing_underlying_content(self):
        base = {
            "reference_need": "none",
            "reference_target": "output",
            "evidence_scope": "externally_visible",
            "reference_critical": False,
            "required_features": [],
            "forbidden_features": [],
            "environment_key": "desk",
            "shot_type": "medium",
            "environment": "desk",
            "canonical_subject": "developing print",
            "continuity_key": "same_print",
        }
        first = dict(base)
        first.update(
            {
                "composition_key": "stage_1",
                "continuity_description": "the same photograph showing a quiet room",
            }
        )
        second = dict(base)
        second.update(
            {
                "composition_key": "stage_2",
                "continuity_description": "the same photograph showing an ocean",
            }
        )

        issues = llm._scene_plan_preflight_issues(
            [first, second],
            reference_inventory=[],
            precision_budget_ratio=1.0,
        )

        self.assertTrue(
            any("changes continuity_description" in issue for issue in issues),
            issues,
        )

    def test_continuity_description_is_injected_into_model_prompt(self):
        draft = [
            {
                "subject": "developing instant photograph",
                "canonical_subject": "same print",
                "route": "standard",
                "scene_description": "the image is becoming clearer",
                "required_features": [],
                "forbidden_features": [],
                "environment": "wooden desk",
                "environment_key": "desk",
                "composition": "slight high angle",
                "composition_key": "development_stage",
                "lighting": "soft daylight",
                "shot_type": "medium",
                "framing_intent": "medium_subject",
                "shot_role": "process",
                "reference_need": "none",
                "reference_target": "output",
                "reference_query": "",
                "evidence_scope": "externally_visible",
                "reference_critical": False,
                "safe_visual_alternative": "show the print on a desk",
                "continuity_key": "print_a",
                "continuity_description": "one photograph showing the same softly lit room",
                "precision_importance": 0.2,
            }
        ]
        scene_plan = [
            {
                "narration": "The same photograph continues developing.",
                "beat": 1,
                "beats": 1,
                "duration": 5.0,
            }
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(draft), json.dumps(draft)],
        ):
            result = llm.generate_scene_image_plan(
                "instant photograph development",
                scene_plan,
                reference_inventory=[],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(result[0]["continuity_key"], "print_a")
        self.assertIn(
            "one photograph showing the same softly lit room",
            result[0]["prompt"].lower(),
        )
        self.assertNotIn(
            "exact same physical instance/content",
            result[0]["prompt"].lower(),
        )

    def test_continuity_gate_locks_later_scene_to_first_description(self):
        scenes = []
        descriptions = [
            "one photograph showing a quiet room",
            "one photograph showing an ocean",
        ]
        for index, description in enumerate(descriptions):
            scenes.append(
                {
                    "subject": "developing print",
                    "canonical_subject": "same print",
                    "route": "standard",
                    "scene_description": f"development stage {index + 1}",
                    "required_features": [],
                    "forbidden_features": [],
                    "environment": "wooden desk",
                    "environment_key": "desk",
                    "composition": "slight high angle",
                    "composition_key": f"stage_{index + 1}",
                    "lighting": "soft daylight",
                    "shot_type": "medium",
                    "framing_intent": "medium_subject",
                    "shot_role": "process",
                    "reference_need": "none",
                    "reference_target": "output",
                    "reference_query": "",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "safe_visual_alternative": "show the same print",
                    "continuity_key": "print_a",
                    "continuity_description": description,
                    "precision_importance": 0.2,
                }
            )
        scene_plan = [
            {"narration": "Stage one.", "beat": 1, "beats": 2, "duration": 5.0},
            {"narration": "Stage two.", "beat": 2, "beats": 2, "duration": 5.0},
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(scenes), json.dumps(scenes)],
        ):
            result = llm.generate_scene_image_plan(
                "developing output",
                scene_plan,
                reference_inventory=[],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(
            result[0]["continuity_description"],
            result[1]["continuity_description"],
        )
        self.assertIn(
            "one photograph showing a quiet room",
            result[1]["prompt"].lower(),
        )
        self.assertNotIn(
            "one photograph showing an ocean",
            result[1]["prompt"].lower(),
        )

    def test_default_script_prompt_discourages_plausible_specific_inventions(self):
        prompt = llm.build_script_prompt("how a generic mechanism works")

        self.assertIn("never invent exact mechanisms", prompt.lower())
        self.assertIn("plausible-sounding specificity", prompt.lower())

    def test_specialized_detail_requires_semantic_match_not_role_presence_only(self):
        inventory = [
            {"slot": 1, "role": "identity", "description": "whole device"},
            {"slot": 2, "role": "detail", "description": "front control buttons and lens ring"},
        ]

        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "detail",
                "reference_target": "primary_subject",
                "reference_query": "rear roller assembly and pressure plate",
                "evidence_scope": "specialized_visible",
                "reference_critical": True,
            },
            inventory,
        )

        self.assertEqual(status, "unsupported")
        self.assertIn("none of their user descriptions", reason)

    def test_specialized_detail_without_description_is_not_factual_coverage(self):
        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "detail",
                "reference_target": "primary_subject",
                "reference_query": "rear roller assembly",
                "evidence_scope": "specialized_visible",
                "reference_critical": True,
            },
            [
                {"slot": 1, "role": "identity", "description": ""},
                {"slot": 2, "role": "detail", "description": ""},
            ],
        )

        self.assertEqual(status, "unsupported")
        self.assertIn("no user description", reason)

    def test_specialized_detail_is_covered_when_user_description_matches_query(self):
        inventory = [
            {"slot": 1, "role": "identity", "description": "whole device"},
            {"slot": 2, "role": "detail", "description": "rear roller assembly and pressure plate"},
        ]

        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "detail",
                "reference_target": "primary_subject",
                "reference_query": "roller assembly pressure plate close view",
                "evidence_scope": "specialized_visible",
                "reference_critical": True,
            },
            inventory,
        )

        self.assertEqual(status, "covered")
        self.assertIn("semantically matches", reason)

    def test_externally_visible_detail_still_requires_matching_detail_evidence(self):
        inventory = [
            {"slot": 1, "role": "identity", "description": "whole device exterior"},
            {"slot": 2, "role": "detail", "description": "front control buttons and lens ring"},
        ]

        status, reason = llm._scene_reference_coverage(
            {
                "reference_need": "detail",
                "reference_target": "primary_subject",
                "reference_query": "rear roller assembly and exit gap",
                "evidence_scope": "externally_visible",
                "reference_critical": True,
            },
            inventory,
        )

        self.assertEqual(status, "unsupported")
        self.assertIn("none of their user descriptions", reason)

    def test_named_primary_output_is_reclassified_even_when_name_repeats(self):
        rows = llm._normalize_scene_identity_and_continuity(
            [
                {
                    "subject": "Example Model X",
                    "canonical_subject": "Example Model X",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "evidence_scope": "externally_visible",
                    "reference_critical": True,
                    "continuity_key": "none",
                },
                {
                    "subject": "Example Model X instant print",
                    "canonical_subject": "Example Model X instant print",
                    "scene_description": "a freshly ejected blank photo sheet from Example Model X",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "evidence_scope": "externally_visible",
                    "reference_critical": True,
                    "includes_primary_subject": True,
                    "continuity_key": "same_output",
                    "continuity_description": "the same instant print sheet",
                },
            ]
        )

        self.assertEqual(rows[1]["reference_target"], "output")
        self.assertEqual(rows[1]["reference_need"], "none")
        self.assertTrue(rows[1]["includes_primary_subject"])
        self.assertEqual(
            rows[1]["identity_relation_guard"],
            "reclassified_derived_output",
        )

    def test_closing_composite_inherits_previous_output_continuity_group(self):
        rows = llm._normalize_scene_identity_and_continuity(
            [
                {
                    "subject": "Example Model X",
                    "canonical_subject": "Example Model X",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "evidence_scope": "externally_visible",
                    "reference_critical": True,
                    "includes_primary_subject": True,
                    "continuity_key": "none",
                },
                {
                    "subject": "finished print",
                    "canonical_subject": "finished print",
                    "scene_description": "final developed photo on a neutral surface",
                    "route": "standard",
                    "reference_need": "none",
                    "reference_target": "output",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "includes_primary_subject": False,
                    "continuity_key": "print_chain",
                    "continuity_description": "the same produced print progressing to its final state",
                },
                {
                    "subject": "Example Model X with final photo",
                    "canonical_subject": "Example Model X",
                    "scene_description": "camera and final developed photo arranged together",
                    "reference_query": "final developed photo beside the source device",
                    "route": "standard",
                    "reference_need": "none",
                    "reference_target": "environment",
                    "evidence_scope": "contextual",
                    "reference_critical": False,
                    "includes_primary_subject": True,
                    "continuity_key": "none",
                },
            ]
        )

        self.assertEqual(rows[2]["continuity_key"], "print_chain")
        self.assertEqual(
            rows[2]["continuity_description"],
            rows[1]["continuity_description"],
        )
        self.assertEqual(
            rows[2]["continuity_inference"],
            "adjacent_closing_output_composite",
        )

    def test_primary_identity_relation_guard_reclassifies_non_primary_output(self):
        rows = llm._normalize_scene_identity_and_continuity(
            [
                {
                    "subject": "Example Model X",
                    "canonical_subject": "Example Model X",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "reference_query": "Example Model X whole body",
                    "evidence_scope": "externally_visible",
                    "reference_critical": True,
                    "shot_role": "identity",
                    "continuity_key": "none",
                },
                {
                    "subject": "finished produced photograph",
                    "canonical_subject": "developed photograph",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "reference_query": "finished output",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "shot_role": "closing",
                    "continuity_key": "none",
                },
            ]
        )

        self.assertEqual(rows[0]["reference_target"], "primary_subject")
        self.assertTrue(rows[0]["includes_primary_subject"])
        self.assertEqual(rows[1]["reference_target"], "output")
        self.assertEqual(rows[1]["reference_need"], "none")
        self.assertFalse(rows[1]["includes_primary_subject"])
        self.assertEqual(rows[1]["route"], "standard")
        self.assertEqual(
            rows[1]["identity_relation_guard"],
            "reclassified_derived_output",
        )

    def test_temporal_non_primary_stages_get_inferred_continuity_chain(self):
        rows = llm._normalize_scene_identity_and_continuity(
            [
                {
                    "subject": "Example Model X",
                    "canonical_subject": "Example Model X",
                    "route": "precision",
                    "reference_need": "identity",
                    "reference_target": "primary_subject",
                    "evidence_scope": "externally_visible",
                    "reference_critical": True,
                    "shot_role": "identity",
                    "continuity_key": "none",
                },
                {
                    "subject": "developing print",
                    "canonical_subject": "instant print development",
                    "route": "standard",
                    "reference_need": "none",
                    "reference_target": "output",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "shot_role": "process",
                    "scene_description": "initial stage of the same print developing",
                    "continuity_key": "none",
                },
                {
                    "subject": "print development",
                    "canonical_subject": "instant print developing",
                    "route": "standard",
                    "reference_need": "none",
                    "reference_target": "output",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "shot_role": "process",
                    "scene_description": "mid-development stage with details emerging",
                    "continuity_key": "none",
                },
                {
                    "subject": "developed print",
                    "canonical_subject": "finished print developed",
                    "route": "standard",
                    "reference_need": "none",
                    "reference_target": "output",
                    "evidence_scope": "externally_visible",
                    "reference_critical": False,
                    "shot_role": "closing",
                    "scene_description": "final developed stage",
                    "continuity_key": "none",
                },
            ]
        )

        keys = [rows[index]["continuity_key"] for index in (1, 2, 3)]
        self.assertNotEqual(keys[0], "none")
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(keys[1], keys[2])
        self.assertEqual(
            rows[1]["continuity_description"],
            rows[3]["continuity_description"],
        )

    def test_primary_identity_request_is_hard_locked_to_precision(self):
        draft = [
            {
                "subject": "Example Model X",
                "canonical_subject": "Example Model X",
                "route": "standard",
                "scene_description": "whole product on a table",
                "required_features": [],
                "forbidden_features": [],
                "environment": "table",
                "environment_key": "table",
                "composition": "three quarter view",
                "composition_key": "threequarter",
                "lighting": "soft daylight",
                "shot_type": "full",
                "framing_intent": "full_subject",
                "shot_role": "identity",
                "reference_need": "identity",
                "reference_target": "primary_subject",
                "reference_query": "Example Model X whole body",
                "evidence_scope": "externally_visible",
                "reference_critical": False,
                "includes_primary_subject": True,
                "safe_visual_alternative": "whole product on a table",
                "continuity_key": "none",
                "continuity_description": "",
                "precision_importance": 0.6,
            }
        ]
        scene_plan = [
            {
                "narration": "This is the Example Model X.",
                "beat": 1,
                "beats": 1,
                "duration": 5.0,
            }
        ]

        with patch.object(
            llm,
            "_generate_response",
            side_effect=[json.dumps(draft), json.dumps(draft)],
        ):
            result = llm.generate_scene_image_plan(
                "Example Model X",
                scene_plan,
                reference_inventory=[
                    {"slot": 1, "role": "identity", "description": "whole Example Model X"}
                ],
                precision_budget_ratio=1.0,
            )

        self.assertEqual(result[0]["route"], "precision")
        self.assertTrue(result[0]["reference_critical"])
        self.assertTrue(result[0]["includes_primary_subject"])

    def test_qwen_continuity_reference_uses_input_as_edit_canvas(self):
        prompt = material._qwen_precision_prompt_with_references(
            "make the image slightly more developed",
            "the same output",
            1,
            reference_info={
                "reference_pack": [
                    {
                        "role": "continuity",
                        "description": "same physical output at the stable root stage",
                    }
                ],
                "reference_selection": {
                    "selected_references": [
                        {
                            "kind": "continuity_anchor",
                            "role": "continuity",
                        }
                    ]
                },
            },
        )

        prompt_lower = prompt.lower()
        self.assertIn("edit the input image as the canvas", prompt_lower)
        self.assertIn("same physical output at the stable root stage", prompt_lower)
        self.assertIn("apply this change", prompt_lower)
        self.assertIn("keep all other visible content unchanged", prompt_lower)
        self.assertNotIn("changing only the state/progression", prompt_lower)

    def test_qwen_multi_reference_prompt_assigns_canvas_and_identity_roles(self):
        prompt = material._qwen_precision_prompt_with_references(
            "show the output at a later development stage with the source device beside it",
            "the produced output",
            2,
            reference_info={
                "primary_identity_only": True,
                "reference_pack": [
                    {
                        "role": "continuity",
                        "description": "same output at stable root stage",
                    },
                    {
                        "role": "identity",
                        "description": "whole source device",
                    },
                ],
                "reference_selection": {
                    "selected_references": [
                        {"kind": "continuity_anchor", "role": "continuity"},
                        {"kind": "identity_anchor", "role": "identity"},
                    ]
                },
            },
        )

        prompt_lower = prompt.lower()
        self.assertIn("<image1> is the canvas", prompt_lower)
        self.assertIn("<image2> is identity evidence", prompt_lower)
        self.assertIn("edit <image1>", prompt_lower)
        self.assertIn("use every other image only for the role stated above", prompt_lower)
        self.assertNotIn("recursive picture-in-picture", prompt_lower)
        self.assertNotIn("never reinterpret the whole reference frame", prompt_lower)

    def test_continuity_edit_chain_enabled_by_default(self):
        config.app.pop("openai_image_continuity_edit_chain_enabled", None)
        self.assertTrue(material._continuity_edit_chain_enabled())
        config.app["openai_image_continuity_edit_chain_enabled"] = "false"
        self.assertFalse(material._continuity_edit_chain_enabled())

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

    def test_reference_selector_suppresses_primary_anchor_for_output_target(self):
        info = {
            "reference_pack": [
                {
                    "slot": 1,
                    "role": "identity",
                    "anchor": True,
                    "original_file": "01_primary_identity.jpg",
                    "description": "whole primary subject",
                    "comfyui_input": "ref-1",
                },
                {
                    "slot": 2,
                    "role": "detail",
                    "original_file": "02_primary_detail.jpg",
                    "description": "primary subject detail",
                    "comfyui_input": "ref-2",
                },
            ]
        }

        selected, selected_info = material._select_manual_references_for_scene(
            ["ref-1", "ref-2"],
            info,
            "identity",
            "final produced output",
            reference_target="output",
            max_refs=3,
        )

        self.assertEqual(selected, [])
        selection = selected_info["reference_selection"]
        self.assertEqual(selection["status"], "reference_target_not_covered")
        self.assertEqual(selection["reference_target"], "output")
        self.assertIsNone(selection["anchor_reference"])

    def test_reference_selector_suppresses_output_target_without_pack_metadata(self):
        selected, selected_info = material._select_manual_references_for_scene(
            ["ref-1"],
            {},
            "identity",
            "produced output",
            reference_target="output",
            max_refs=3,
        )

        self.assertEqual(selected, [])
        self.assertEqual(
            selected_info["reference_selection"]["status"],
            "reference_target_not_covered",
        )

    def test_reference_library_default_is_twelve_but_scene_pack_remains_three(self):
        config.app.pop("openai_image_manual_reference_max_images", None)
        self.assertEqual(material._manual_precision_reference_max_images(), 12)

        config.app["openai_image_manual_reference_max_images"] = 100
        self.assertEqual(material._manual_precision_reference_max_images(), 20)

    def test_qwen_prompt_names_each_reference_role(self):
        prompt = material._qwen_precision_prompt_with_references(
            "new scene direction; the frame does not show a fake extra dial or invented label",
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
        self.assertIn("identity evidence", prompt)
        self.assertIn("detail evidence", prompt)
        self.assertIn("context evidence", prompt)
        self.assertIn("fake extra dial", prompt)
        self.assertIn("invented label", prompt)
        self.assertNotIn("Explicitly do not depict or introduce", prompt)

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
