"""Bind hash-pinned retained reports to current images, entirely offline."""

import argparse
import json
import runpy
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V = runpy.run_path(str(ROOT / "app/services/visual_observation_diagnostics.py"))
P = runpy.run_path(str(ROOT / "scripts/observe_visual_geometry.py"))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--report", nargs=2, action="append", required=True, metavar=("PATH", "SHA256"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Preserve existing output")
    plan = P["validate_plan"](json.loads(Path(args.plan).read_text(encoding="utf-8")))
    result = {"execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "diagnostic_version": V["VERSION"], "adapter_sha256": V["digest"](
                  ROOT / "app/services/visual_observation_diagnostics.py"),
              "script_sha256": V["digest"](__file__), "plan_sha256": V["digest"](args.plan),
              "model_requests": 0, "generation_requests": 0, "reports": []}
    for report_path, sha in args.report:
        store = V["RetainedVisualObservations"].from_file(report_path, sha)
        rows = []
        for image in plan["images"]:
            if V["digest"](image["path"]) != image["sha256"]:
                raise ValueError("Plan image changed")
            rows.append(V["diagnose"](image["path"], store))
        result["reports"].append({"source_report_sha256": sha, "rows": rows})
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reports": len(result["reports"]), "rows": sum(len(r["rows"]) for r in result["reports"]),
                      "model_requests": 0, "generation_requests": 0}))


if __name__ == "__main__":
    main()
