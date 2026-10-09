"""Owned process lifecycle, pinned runtime and budgets without a real server."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts import observe_paired_shape as runner


@pytest.fixture
def plan():
    return json.loads((Path(__file__).parents[1] / "docs/validation/paired-shape-probe-plan-2026-10-09.json").read_text())


def test_frozen_plan_remains_valid(plan):
    before = copy.deepcopy(plan)
    assert runner.validate_plan(plan) == plan
    assert plan == before


@pytest.mark.parametrize("fault", ["version", "budget", "retry", "tokens", "timeout", "thinking", "duplicates", "prompt", "schema"])
def test_altered_protocol_or_budget_is_rejected_before_dispatch(plan, fault):
    if fault == "version": plan["protocol"] = "other"
    elif fault == "budget": plan["execution"]["requests_per_model"] = 4
    elif fault == "retry": plan["execution"]["automatic_retries"] = 1
    elif fault == "tokens": plan["execution"]["max_tokens"] = 512
    elif fault == "timeout": plan["execution"]["http_timeout_seconds"] = 120
    elif fault == "thinking": plan["execution"]["thinking"] = True
    elif fault == "duplicates": plan["cases"][1]["case_id"] = plan["cases"][0]["case_id"]
    elif fault == "prompt": plan["model_prompt"] += " Label B is a failure."
    else: plan["response_schema"]["properties"]["verdict"] = {"type": "string"}
    with pytest.raises(ValueError): runner.validate_plan(plan)


def test_command_preserves_bounded_vision_flags():
    args = runner.command(Path("server.exe"), [Path("model.gguf"), Path("mmproj.gguf")])
    expected = {"--host": "127.0.0.1", "--port": "8092", "-c": "8192", "-np": "1",
                "--image-min-tokens": "1024", "--image-max-tokens": "1536",
                "--flash-attn": "on", "--reasoning": "off"}
    for flag, value in expected.items(): assert args[args.index(flag) + 1] == value
    assert json.loads(args[args.index("--chat-template-kwargs") + 1]) == {"enable_thinking": False}


def test_runtime_archive_and_extracted_bytes_are_both_checked(tmp_path):
    folder = tmp_path / "test-build"; folder.mkdir()
    (folder / "llama-server.exe").write_bytes(b"verified executable")
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as z: z.writestr("llama-server.exe", b"verified executable")
    runtime = {"tag": "test-build", "assets": [{"name": "runtime.zip", "digest": "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()}]}
    evidence = runner.verify_runtime(tmp_path, runtime)
    assert evidence["extracted_files_checked"] == 1
    (folder / "llama-server.exe").write_bytes(b"modified")
    with pytest.raises(ValueError): runner.verify_runtime(tmp_path, runtime)


class Process:
    pid = 12345
    def __init__(self): self.closed = False; self.terminated = 0
    def poll(self): return 0 if self.closed else None
    def terminate(self): self.terminated += 1; self.closed = True
    def wait(self, timeout): return 0
    def kill(self): self.closed = True


def launch(process):
    def factory(args, **kwargs):
        assert "creationflags" in kwargs
        kwargs["stdout"].write("server is listening on http://127.0.0.1:8092\n")
        kwargs["stdout"].flush()
        return process
    return factory


def test_owned_server_closes_only_its_process_on_body_failure(tmp_path):
    process = Process()
    def request(url, timeout): return {"modalities": {"vision": True}}
    with pytest.raises(RuntimeError):
        with runner.owned_server(["server.exe"], tmp_path / "own.log", request, launch(process)) as info:
            assert info["owned_pid"] == process.pid
            raise RuntimeError("body failed")
    assert process.closed and process.terminated == 1


def test_readiness_failure_still_closes_owned_process(tmp_path):
    process = Process()
    def request(url, timeout): return {"modalities": {"vision": False}}
    with pytest.raises(ValueError):
        with runner.owned_server(["server.exe"], tmp_path / "own.log", request, launch(process)): pass
    assert process.closed and process.terminated == 1


def test_owned_log_is_never_overwritten(tmp_path):
    log = tmp_path / "own.log"; log.write_text("preserved")
    calls = []
    with pytest.raises(FileExistsError):
        with runner.owned_server(["server.exe"], log, lambda *a, **k: None, lambda *a, **k: calls.append(a)): pass
    assert log.read_text() == "preserved" and calls == []


def test_ownership_state_is_independent_of_other_listeners(tmp_path):
    process, state = Process(), {}
    with runner.owned_server(["server.exe"], tmp_path / "own.log",
                             lambda *a, **k: {"modalities": {"vision": True}}, launch(process), state) as info:
        assert info is state and state["owned_server_closed"] is False
    assert state["owned_server_closed"] is True and state["owned_pid"] == process.pid


def test_load_error_records_ownership_and_proven_closure(tmp_path):
    process, state = Process(), {}
    with pytest.raises(ValueError):
        with runner.owned_server(["server.exe"], tmp_path / "own.log",
                                 lambda *a, **k: {"modalities": {"vision": False}}, launch(process), state): pass
    assert state["owned_pid"] == process.pid and state["owned_server_closed"] is True
