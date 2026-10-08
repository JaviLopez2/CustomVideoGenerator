"""Opt-in replay of retained VLM output; no inference or admission authority."""

import copy
import hashlib
import json
import re
from pathlib import Path


VERSION = "retained-visual-diagnostic-1"
PROTOCOLS = {"categorical-geometry-1", "target-component-observations-1", "target-component-observations-2"}
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_CONTENT_CHARACTERS = 65536


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _base(status="unavailable", reason=None):
    result = {"version": VERSION, "status": status, "available": status == "uncertain",
              "availability_scope": "recorded_output_only", "pixel_truth_verified": False,
              "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False}
    if reason:
        result["reason"] = reason
    return result


class RetainedVisualObservations:
    """Load one explicitly supplied, hash-pinned report; never follow its paths.

    Availability describes the saved transport/output, not perceptual truth.
    Failed observations keep their raw content and remain unavailable. The store
    is a snapshot: neither caller mutation nor report changes can alter it later.
    """

    def __init__(self):
        self._rows = {}
        self._provenance = {}

    @classmethod
    def from_file(cls, path, expected_sha256):
        if not _sha(expected_sha256):
            raise ValueError("Missing report SHA256")
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_REPORT_BYTES + 1)
        if len(data) > MAX_REPORT_BYTES:
            raise ValueError("Report too large")
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ValueError("Report changed")
        report = json.loads(data)
        if not isinstance(report, dict) or report.get("inventory_protocol") not in PROTOCOLS:
            raise ValueError("Unsupported observation protocol")
        target, rows = report.get("target"), report.get("rows")
        if not isinstance(target, str) or not target.strip() or len(target) > 512:
            raise ValueError("Invalid reported target")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
            raise ValueError("Invalid observation rows")
        store = cls()
        store._rows = {}
        store._provenance = {"source_report_sha256": expected_sha256, "reported_target": target,
                             "inventory_protocol": report["inventory_protocol"]}
        for key in ("harness_sha256", "component_source_sha256", "component_profile_sha256", "plan_sha256"):
            if _sha(report.get(key)):
                store._provenance[key] = report[key]
        if isinstance(report.get("execution_head"), str) and re.fullmatch(r"[0-9a-f]{40}", report["execution_head"]):
            store._provenance["execution_head"] = report["execution_head"]
        for row in rows:
            if not isinstance(row, dict) or not _sha(row.get("sha256")) or row["sha256"] in store._rows:
                raise ValueError("Invalid or duplicate image provenance")
            content = row.get("final_content")
            if content is not None and (not isinstance(content, str) or len(content) > MAX_CONTENT_CHARACTERS):
                raise ValueError("Invalid or oversized observation")
            completed = (row.get("transport_status") == "completed" and row.get("finish_reason") == "stop"
                         and type(row.get("reasoning_characters")) is int and row["reasoning_characters"] == 0)
            try:
                parsed = json.loads(content) if content is not None else None
                # Preserve exactly what was recorded, without prose extraction,
                # count repair or trusting a declared verdict/coverage summary.
                fields = {"target_presence", "components"} if report["inventory_protocol"].startswith("target-component") else {
                    "openings", "edge_cutouts", "rings_or_collars", "part_junctions"}
                completed = completed and isinstance(parsed, dict) and set(parsed) == fields and parsed == row.get("inventory")
            except ValueError:
                completed = False
            store._rows[row["sha256"]] = {
                **_base("uncertain" if completed else "unavailable", None if completed else "recorded_output_unavailable"),
                "raw_observation": {"final_content": content,
                                    "recorded_transport_status": "completed" if row.get("transport_status") == "completed" else "unavailable",
                                    "format_consistent_with_record": bool(completed)}}
        return store

    def observe(self, image_path):
        """Bind only to current bytes; model file paths/labels stay out of MPT."""
        image_sha = digest(image_path)
        if image_sha not in self._rows:
            return {**_base(reason="no_observation_for_current_pixels"), "image_sha256": image_sha,
                    **copy.deepcopy(self._provenance)}
        return {**copy.deepcopy(self._rows[image_sha]), "image_sha256": image_sha,
                **copy.deepcopy(self._provenance)}


def diagnose(image_path, store):
    """A diagnostic failure cannot accept, reject or interrupt an image scene."""
    if not isinstance(store, RetainedVisualObservations):
        return _base(reason="invalid_observation_store")
    try:
        return store.observe(image_path)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return _base(reason="diagnostic_unavailable")
