"""Scoped, local visual QA. Evidence gaps remain uncertain, never implicit passes."""

import copy
import hashlib
import json
import math
import re
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


VERSION = "visual-qa-2"
NUMBERS = {word: i for i, word in enumerate(
    ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"))}
STATUSES = {"pass", "fail", "uncertain", "unavailable"}


class EvidenceCache:
    def __init__(self, limit=128):
        self.limit = limit
        self.entries = OrderedDict()

    def get(self, key):
        if key not in self.entries:
            return None
        self.entries.move_to_end(key)
        return copy.deepcopy(self.entries[key])

    def put(self, key, value):
        self.entries[key] = copy.deepcopy(value)
        self.entries.move_to_end(key)
        while len(self.entries) > self.limit:
            self.entries.popitem(last=False)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_key(*values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class FlorenceEvidence:
    """Reuse the existing runtime; cache only small CPU descriptions/coordinates."""
    def __init__(self, runtime_loader, model_identity, cache=None):
        self.runtime_loader = runtime_loader
        self.model_identity = model_identity
        self.cache = cache or EvidenceCache()
        self.runtime = None

    def read(self, image, task="<MORE_DETAILED_CAPTION>", query="", crop=None):
        started = time.perf_counter()
        try:
            image_hash = digest(image)
            key = cache_key(VERSION, self.model_identity, image_hash, task, query, crop, 1, 256)
            cached = self.cache.get(key)
            if cached is not None:
                return {**cached, "cache_hit": True, "load_seconds": 0, "infer_seconds": 0,
                        "seconds": time.perf_counter() - started}
            load = time.perf_counter()
            if self.runtime is None:
                self.runtime = self.runtime_loader()
            load_seconds = time.perf_counter() - load
            if self.runtime is None:
                return {"available": False, "error": "model_unavailable", "seconds": time.perf_counter() - started}
            model, processor, torch, device, dtype = self.runtime
            with Image.open(image) as source:
                source = source.convert("RGB")
                if crop:
                    source = source.crop(tuple(crop))
                infer = time.perf_counter()
                inputs = processor(text=task + query, images=source, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}
                if device.startswith("cuda"):
                    inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
                with torch.inference_mode():
                    ids = model.generate(**inputs, max_new_tokens=256, num_beams=1, do_sample=False)
                raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
                value = processor.post_process_generation(raw, task=task, image_size=source.size).get(task)
                result = {"available": value is not None, "value": value, "size": list(source.size),
                          "load_seconds": load_seconds, "infer_seconds": time.perf_counter() - infer,
                          "seconds": time.perf_counter() - started, "cache_hit": False,
                          "image_sha256": image_hash, "task": task, "query": query}
            if result["available"]:
                self.cache.put(key, result)
            return result
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            return {"available": False, "error": type(exc).__name__, "seconds": time.perf_counter() - started}


def aliases(subject, supplied=()):
    # Caller-supplied aliases handle ontology differences without scene rules.
    terms = {subject.casefold().strip(), *[str(x).casefold().strip() for x in supplied]}
    terms |= {term[:-1] for term in terms if term.endswith("s") and len(term) > 3}
    return sorted(term for term in terms if term)


def caption_counts(caption, subject, supplied=()):
    observed = set()
    for term in aliases(subject, supplied):
        noun = re.escape(term) + ("s?" if not term.endswith("s") else "")
        adjectives = r"(?:(?!(?:and|or|beside|with|next|near|behind|above|below|under|on|is|are|has|have|a|an|single|one|two|three)\b)[a-z]+\s+){0,3}?"
        pattern = r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|\d+|no|a|an|single)\s+" + adjectives + noun + r"\b"
        for match in re.finditer(pattern, caption.casefold()):
            if re.search(r"\b(?:and|beside|with|next|near|behind|above|below|under|on|is|are|has|have)\b",
                         match.group()[len(match.group(1)): -len(term)]):
                continue
            word = match.group(1)
            number = int(word) if word.isdigit() else 0 if word in {"no", "zero"} else 1 if word in {"a", "an", "single"} else NUMBERS[word]
            observed.add((number, word not in {"a", "an"}))
    return observed


def quantity(caption, detections, constraint):
    expected = constraint["expected_count"]
    tolerance = constraint.get("tolerance", 0)
    if type(expected) is not int or expected < 0 or type(tolerance) is not int or tolerance < 0:
        raise ValueError("Count and tolerance must be non-negative integers")
    subject = constraint["subject"]
    names = aliases(subject, constraint.get("aliases", []))
    observations = caption_counts(caption, subject, constraint.get("aliases", []))
    if observations and re.search(r"\b(?:or|maybe|possibly|perhaps|unclear|might|may)\b", caption.casefold()):
        return {"status": "uncertain", "subject": subject, "reason": "caption expresses count ambiguity"}
    values = {n for n, _ in observations}
    detected = sum(str(label).casefold().strip() in names for label in detections.get("labels", []))
    explicit = {n for n, strong in observations if strong}
    if len(values) > 1 or (detected > 0 and values and detected not in values):
        return {"status": "uncertain", "subject": subject, "reason": "conflicting local count evidence"}
    number = next(iter(values)) if len(values) == 1 else None
    supported = number is not None and (number in explicit or detected == number and detected > 0)
    if not supported:
        return {"status": "uncertain", "subject": subject, "observed_count": number,
                "reason": "caption/recognition does not establish exact cardinality"}
    status = "pass" if abs(number - expected) <= tolerance else "fail"
    return {"status": status, "subject": subject, "observed_count": number,
            "expected_count": expected, "reason": "explicit count or agreement of caption and recognition"}


def normalized_mask(polygons, size, rotate=False):
    image = Image.new("L", tuple(size), 0)
    draw = ImageDraw.Draw(image)
    def rings(value):
        # Florence groups polygon rings by detected instance; accept either
        # grouped native output or a flat ring, without discarding instances.
        if not isinstance(value, (list, tuple)) or not value:
            return
        if all(isinstance(n, (int, float)) and math.isfinite(n) for n in value):
            if len(value) >= 6 and len(value) % 2 == 0:
                yield value
        else:
            for child in value:
                yield from rings(child)
    for polygon in rings(polygons):
        draw.polygon(list(zip(polygon[::2], polygon[1::2])), fill=255)
    box = image.getbbox()
    if box is None:
        return None
    image = image.crop(box)
    if rotate:
        y, x = np.nonzero(np.asarray(image))
        if len(x) < 16:
            return None
        eigenvalues, vectors = np.linalg.eigh(np.cov(np.vstack((x, y))))
        axis = vectors[:, int(np.argmax(eigenvalues))]
        angle = math.degrees(math.atan2(axis[1], axis[0]))
        image = image.rotate(angle, expand=True, resample=Image.Resampling.NEAREST)
        image = image.crop(image.getbbox())
    scale = 112 / max(image.size)
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                         Image.Resampling.NEAREST)
    canvas = Image.new("L", (128, 128), 0)
    canvas.paste(image, ((128 - image.width) // 2, (128 - image.height) // 2))
    return canvas


def silhouette(candidate, reference, allow_rotation=False):
    a = normalized_mask(candidate.get("polygons", []), candidate["size"], allow_rotation)
    b = normalized_mask(reference.get("polygons", []), reference["size"], allow_rotation)
    if a is None or b is None:
        return {"status": "uncertain", "reason": "no usable subject segmentation"}
    scores = []
    for rotated in ([a, a.rotate(180)] if allow_rotation else [a]):
        aa = np.asarray(rotated.filter(ImageFilter.MaxFilter(5))) > 0
        bb = np.asarray(b.filter(ImageFilter.MaxFilter(5))) > 0
        scores.append(float(2 * np.logical_and(aa, bb).sum() / max(1, aa.sum() + bb.sum())))
    score = max(scores)
    # Preliminary conservative bands; the middle is explicitly unresolved.
    status = "pass" if score >= 0.9 else "fail" if score < 0.5 else "uncertain"
    return {"status": status, "silhouette_score": round(score, 5),
            "reason": "normalized segmented outer shape; internal structure not certified"}


def state_check(caption, temporal, previous_caption=""):
    required = temporal.get("required_evidence", [])
    forbidden = temporal.get("forbidden_evidence", [])
    def present(term):
        text = caption.casefold()
        pattern = r"\b" + re.escape(str(term).casefold()) + r"\b"
        matches = list(re.finditer(pattern, text))
        positive, negative = False, False
        for match in matches:
            prefix = text[max(0, match.start() - 24):match.start()]
            negated = bool(re.search(r"\b(?:no|without|absent|not)\s+(?:\w+\s+){0,2}$", prefix))
            positive |= not negated
            negative |= negated
        return positive, negative
    violated = [term for term in forbidden if present(term)[0]]
    violated += ["absent " + term for term in required if present(term)[1] and not present(term)[0]]
    missing = [term for term in required if not present(term)[0]]
    unknown_absence = [term for term in forbidden if not present(term)[1] and not present(term)[0]]
    if violated:
        status = "fail"
    elif (required or forbidden) and not missing and not unknown_absence:
        status = "pass"
    else:
        status = "uncertain"
    progression = None
    if status == "pass" and previous_caption:
        previous = state_check(previous_caption, temporal)
        progression = 1.0 if previous["status"] == "fail" else None
    elif status == "pass" and temporal.get("previous_state"):
        progression = None  # Narrated previous state is not observed visual evidence.
    return {"status": status, "state_score": 1.0 if status == "pass" else 0.0 if status == "fail" else None,
            "progression_score": progression, "identity_score": None,
            "reason": "observed state evidence" if status != "uncertain" else "missing/ambiguous state evidence",
            "missing_evidence": missing, "violations": violated,
            "unknown_absence": unknown_absence}


def overall(checks):
    statuses = [check["status"] for check in checks]
    return "fail" if "fail" in statuses else "unavailable" if "unavailable" in statuses else "uncertain" if "uncertain" in statuses else "pass"


class VisualQA:
    def __init__(self, evidence, result_cache=None):
        self.evidence = evidence
        self.result_cache = result_cache or EvidenceCache()

    def assess(self, image, contract):
        started = time.perf_counter()
        active = bool(contract.get("counts") or contract.get("geometry_constraints") or contract.get("identity_critical")
                      or contract.get("temporal") or contract.get("forbid_text"))
        if not active:
            return {"verdict": "pass", "available": True, "checks": [], "status": "not_required",
                    "seconds": time.perf_counter() - started, "cache_hit": False}
        try:
            hashes = [digest(image)]
            for path in [contract.get("reference_image"), (contract.get("temporal") or {}).get("previous_image")]:
                hashes.append(digest(path) if path else None)
        except OSError:
            return {"verdict": "unavailable", "available": False, "checks": [],
                    "reason": "candidate/reference artifact unavailable", "seconds": time.perf_counter() - started,
                    "cache_hit": False}
        key = cache_key(VERSION, self.evidence.model_identity, hashes, contract)
        cached = self.result_cache.get(key)
        if cached is not None:
            return {**cached, "seconds": time.perf_counter() - started, "cache_hit": True}
        observations, checks = [], []
        caption_result = self.evidence.read(image)
        observations.append(caption_result)
        if not caption_result.get("available") or not str(caption_result.get("value") or "").strip():
            return {"verdict": "unavailable", "available": False, "checks": [], "reason": "caption unavailable",
                    "observations": observations, "seconds": time.perf_counter() - started, "cache_hit": False}
        caption = str(caption_result["value"])
        if contract.get("identity_critical"):
            checks.append({"kind": "identity", "status": "uncertain", "identity_score": None,
                           "reason": "critical identity needs stronger visual evidence than captions/outer masks"})
        if contract.get("counts"):
            detection_result = self.evidence.read(image, "<OD>")
            observations.append(detection_result)
            detections = detection_result.get("value") if detection_result.get("available") else {}
            for constraint in contract["counts"]:
                try:
                    check = quantity(caption, detections or {}, constraint)
                except (ValueError, KeyError, TypeError):
                    check = {"status": "unavailable", "reason": "invalid quantity contract/evidence"}
                checks.append({"kind": "quantity", **check})
        if contract.get("forbid_text") and overall(checks) != "fail":
            ocr = self.evidence.read(image, "<OCR>")
            observations.append(ocr)
            if not ocr.get("available"):
                check = {"status": "unavailable", "reason": "OCR unavailable"}
            else:
                words = re.findall(r"[A-Za-z]{3,}", str(ocr.get("value") or ""))
                check = {"status": "fail" if words else "pass", "detected_text": words,
                         "reason": "visible alphabetic text" if words else "no alphabetic text detected; OCR recall limited"}
            checks.append({"kind": "text", **check})
        if contract.get("geometry_constraints") and overall(checks) != "fail":
            reference = contract.get("reference_image")
            if not reference:
                checks.append({"kind": "geometry", "status": "unavailable", "reason": "reference missing"})
            else:
                query = contract["subject"]
                a = self.evidence.read(image, "<REFERRING_EXPRESSION_SEGMENTATION>", query)
                b = self.evidence.read(reference, "<REFERRING_EXPRESSION_SEGMENTATION>", query)
                observations.extend([a, b])
                if a.get("available") and b.get("available") and isinstance(a.get("value"), dict) and isinstance(b.get("value"), dict):
                    measured = silhouette({**a["value"], "size": a["size"]}, {**b["value"], "size": b["size"]},
                                          "rotation" in contract.get("allowed_changes", []))
                else:
                    measured = {"status": "uncertain", "reason": "segmentation unavailable"}
                # Outer masks cannot establish part counts or internal arrangement.
                constraints = contract["geometry_constraints"]
                if measured["status"] == "pass" and any(item != "silhouette" for item in constraints):
                    measured["status"] = "uncertain"
                    measured["reason"] = "outer shape matches; requested internal structure not established"
                checks.append({"kind": "geometry", **measured})
        if contract.get("temporal") and overall(checks) != "fail":
            temporal = contract["temporal"]
            previous_caption = ""
            if temporal.get("previous_image"):
                previous = self.evidence.read(temporal["previous_image"])
                observations.append(previous)
                previous_caption = str(previous.get("value") or "") if previous.get("available") else ""
            state = state_check(caption, temporal, previous_caption)
            if temporal.get("previous_state") and state["status"] == "pass" and state["progression_score"] is None:
                state["status"] = "uncertain"
                state["reason"] = "state evidenced but progression lacks previous visual evidence"
            checks.append({"kind": "temporal", **state})
        result = {"verdict": overall(checks), "available": overall(checks) != "unavailable",
                  "checks": checks, "caption": caption, "observations": observations,
                  "seconds": time.perf_counter() - started, "cache_hit": False,
                  "image_sha256": hashes[0], "qa_version": VERSION}
        if result["verdict"] != "unavailable":
            self.result_cache.put(key, result)
        return result
