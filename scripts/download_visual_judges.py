"""Download explicitly selected public GGUFs; preserve files and verify SHA256."""
import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, target, expected_size, expected_hash):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != expected_size or sha256(target) != expected_hash:
            raise ValueError("Existing destination differs; refusing overwrite")
        return {"file": target.name, "sha256": expected_hash, "cached": True}
    part = target.with_suffix(target.suffix + ".part")
    offset = part.stat().st_size if part.exists() else 0
    if offset > expected_size:
        raise ValueError("Partial file larger than expected")
    started = time.monotonic()
    if offset < expected_size:
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                raise ValueError("Server did not honor resume range; partial file preserved")
            with part.open("ab" if offset else "wb") as stream:
                last = time.monotonic()
                while chunk := response.read(4 * 1024 * 1024):
                    stream.write(chunk)
                    offset += len(chunk)
                    if time.monotonic() - last >= 30:
                        print(json.dumps({"file": target.name, "downloaded": offset, "total": expected_size}), flush=True)
                        last = time.monotonic()
    if part.stat().st_size != expected_size or sha256(part) != expected_hash:
        raise ValueError("Size/hash mismatch; partial file retained")
    part.rename(target)
    result = {"file": target.name, "sha256": expected_hash, "seconds": time.monotonic() - started, "cached": False}
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    destination = Path(args.destination).resolve()
    jobs = []
    for model in manifest["models"]:
        for artifact in model["files"]:
            target = destination / model["repo"].split("/")[-1] / artifact["file"]
            if not target.resolve().is_relative_to(destination):
                raise ValueError("Destination escapes selected directory")
            url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{artifact['file']}"
            jobs.append((url, target, artifact["size"], artifact["sha256"]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(download, *job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                # URLs may redirect to signed URLs; never log exception values.
                print(json.dumps({"error_type": type(exc).__name__}), flush=True)
                raise SystemExit(1)


if __name__ == "__main__":
    main()
