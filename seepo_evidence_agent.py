from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys

ROOT = Path.home() / "seepo_evidence"

STATE = ROOT / "state.json"
LOG = ROOT / "evidence.jsonl"
POLICY = ROOT / "policy.json"
CHECKPOINT = ROOT / "checkpoint.json"

ROOT.mkdir(parents=True, exist_ok=True)

CURRENT_RUN = None
STOP_REQUESTED = False


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def save_json(path, obj):
    raw = json.dumps(
        obj,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )
    atomic_write(path, raw)


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARNING] cannot load {path}: {exc}")
        return default


def load_state():
    return load_json(
        STATE,
        {
            "run_count": 0,
            "history": [],
            "learned": {},
        },
    )


def load_policy():
    return load_json(
        POLICY,
        {
            "version": 1,
            "rules": {},
            "strategy_history": [],
        },
    )


def save_checkpoint(run_id, stage, status, extra=None):
    checkpoint = {
        "run_id": run_id,
        "timestamp": now(),
        "stage": stage,
        "status": status,
        "extra": extra or {},
    }

    save_json(CHECKPOINT, checkpoint)

    checkpoint_hash = sha256(
        CHECKPOINT.read_bytes()
    )

    print(
        f"[CHECKPOINT] "
        f"run={run_id} "
        f"stage={stage} "
        f"status={status} "
        f"sha256={checkpoint_hash[:16]}"
    )

    return checkpoint


def evidence(run_id, stage, status, details):
    record = {
        "run_id": run_id,
        "timestamp": now(),
        "stage": stage,
        "status": status,
        "details": details,
    }

    raw = json.dumps(
        record,
        sort_keys=True,
        ensure_ascii=False,
    )

    record["evidence_hash"] = sha256(raw)

    with LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

    print(
        f"[{status}] "
        f"RUN={run_id} "
        f"{stage} "
        f"{record['evidence_hash'][:16]}"
    )

    save_checkpoint(
        run_id,
        stage,
        status,
        {
            "evidence_hash": record["evidence_hash"],
        },
    )

    return record


def signal_handler(signum, frame):
    global STOP_REQUESTED

    STOP_REQUESTED = True

    print()
    print(
        f"[STOP REQUEST] signal={signum}"
    )

    if CURRENT_RUN is not None:
        save_checkpoint(
            CURRENT_RUN,
            "INTERRUPTED",
            "BLOCKED",
            {
                "signal": signum,
                "reason": "external_stop_request",
            },
        )


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def should_stop():
    if STOP_REQUESTED:
        return True

    return False


def discover(run_id):
    env = {
        "python": sys.version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
        "uid": getattr(os, "getuid", lambda: None)(),
        "euid": getattr(os, "geteuid", lambda: None)(),
        "pid": os.getpid(),
    }

    return evidence(
        run_id,
        "DISCOVER",
        "PASS",
        env,
    )


def detect_capabilities(run_id):
    commands = [
        "python3",
        "sh",
        "curl",
        "git",
    ]

    capabilities = {}

    for cmd in commands:
        path = shutil.which(cmd)
        capabilities[cmd] = path if path else False

    return evidence(
        run_id,
        "CAPABILITY_DETECTED",
        "PASS",
        capabilities,
    )


def file_io_test(run_id):
    test_file = ROOT / "write_test.txt"

    try:
        test_file.write_text(
            f"SEEPo write test run={run_id}\n",
            encoding="utf-8",
        )

        readback = test_file.read_text(
            encoding="utf-8"
        )

        if readback.startswith("SEEPo write test"):
            return evidence(
                run_id,
                "FILE_IO",
                "PASS",
                {
                    "path": str(test_file),
                    "readback": readback.strip(),
                },
            )

        return evidence(
            run_id,
            "FILE_IO",
            "FAIL",
            {
                "reason": "readback mismatch",
            },
        )

    except Exception as exc:
        return evidence(
            run_id,
            "FILE_IO",
            "BLOCKED",
            {
                "error": repr(exc),
            },
        )


def process_test(run_id):
    try:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "print('SEEPo_PROCESS_TEST')",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return evidence(
            run_id,
            "PROCESS_EXECUTION",
            "PASS"
            if result.returncode == 0
            else "FAIL",
            {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        )

    except Exception as exc:
        return evidence(
            run_id,
            "PROCESS_EXECUTION",
            "BLOCKED",
            {
                "error": repr(exc),
            },
        )


def choose_strategy(policy):
    rules = policy.get("rules", {})

    challenge_rule = rules.get(
        "controlled_learning_challenge"
    )

    if challenge_rule:
        avoided = challenge_rule.get(
            "avoid_strategy"
        )

        if avoided == "A":
            return "B", "previous evidence says A failed"

        if avoided == "B":
            return "A", "previous evidence says B failed"

    return "A", "no previous strategy failure recorded"


def strategy_a():
    """
    Controlled failure.

    This deliberately checks a file that should not exist.
    It does not modify the operating system and does not
    bypass permissions.
    """

    target = ROOT / "controlled_missing_target.txt"

    exists = target.exists()

    if exists:
        return {
            "success": True,
            "result": "unexpected_target_exists",
            "target": str(target),
        }

    return {
        "success": False,
        "result": "target_missing",
        "target": str(target),
    }


def strategy_b():
    """
    Controlled successful strategy.

    Uses a local file that this agent is authorized to create.
    """

    target = ROOT / "controlled_learning_target.txt"

    target.write_text(
        "SEEPo_CONTROLLED_LEARNING_SUCCESS\n",
        encoding="utf-8",
    )

    readback = target.read_text(
        encoding="utf-8"
    )

    success = (
        readback
        == "SEEPo_CONTROLLED_LEARNING_SUCCESS\n"
    )

    return {
        "success": success,
        "result": "readback_verified"
        if success
        else "readback_mismatch",
        "target": str(target),
        "sha256": sha256(readback),
    }


def controlled_learning(run_id, policy):
    strategy, reason = choose_strategy(policy)

    decision = evidence(
        run_id,
        "LEARNING_DECISION",
        "PASS",
        {
            "selected_strategy": strategy,
            "reason": reason,
            "policy_hash_before": sha256(
                json.dumps(
                    policy,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            ),
        },
    )

    if should_stop():
        return {
            "stopped": True,
            "decision": decision,
        }

    if strategy == "A":
        outcome = strategy_a()
    else:
        outcome = strategy_b()

    if outcome["success"]:
        status = "PASS"
    else:
        status = "FAIL"

    result = evidence(
        run_id,
        f"STRATEGY_{strategy}_RESULT",
        status,
        outcome,
    )

    # --------------------------------------------------------
    # LEARNING UPDATE
    # --------------------------------------------------------

    if not outcome["success"]:
        policy.setdefault("rules", {})[
            "controlled_learning_challenge"
        ] = {
            "avoid_strategy": strategy,
            "learned_from_run": run_id,
            "reason": outcome["result"],
        }

        policy.setdefault(
            "strategy_history",
            [],
        ).append(
            {
                "run_id": run_id,
                "strategy": strategy,
                "success": False,
                "result": outcome["result"],
            }
        )

        save_json(POLICY, policy)

        policy_hash = sha256(
            POLICY.read_bytes()
        )

        learned = evidence(
            run_id,
            "POLICY_UPDATED",
            "PASS",
            {
                "avoid_strategy": strategy,
                "next_expected_strategy": (
                    "B" if strategy == "A" else "A"
                ),
                "policy_sha256": policy_hash,
                "source_evidence": result[
                    "evidence_hash"
                ],
            },
        )

        return {
            "stopped": False,
            "decision": decision,
            "result": result,
            "learned": learned,
        }

    policy.setdefault(
        "strategy_history",
        [],
    ).append(
        {
            "run_id": run_id,
            "strategy": strategy,
            "success": True,
            "result": outcome["result"],
        }
    )

    save_json(POLICY, policy)

    policy_hash = sha256(
        POLICY.read_bytes()
    )

    verified = evidence(
        run_id,
        "LEARNING_OUTCOME",
        "PASS",
        {
            "strategy": strategy,
            "success": True,
            "policy_sha256": policy_hash,
            "result_evidence": result[
                "evidence_hash"
            ],
        },
    )

    return {
        "stopped": False,
        "decision": decision,
        "result": result,
        "verified": verified,
    }


def commit_run(state, policy, run_id, environment, results):
    run_record = {
        "run_id": run_id,
        "timestamp": now(),
        "environment": environment,
        "results": results,
        "policy_sha256": sha256(
            POLICY.read_bytes()
        )
        if POLICY.exists()
        else None,
    }

    state.setdefault(
        "history",
        []
    ).append(run_record)

    state["history"] = state["history"][-20:]

    state["learned"] = policy.get(
        "rules",
        {},
    )

    save_json(STATE, state)

    state_hash = sha256(
        STATE.read_bytes()
    )

    checkpoint = save_checkpoint(
        run_id,
        "COMMITTED",
        "PASS",
        {
            "state_sha256": state_hash,
            "policy_sha256": (
                sha256(POLICY.read_bytes())
                if POLICY.exists()
                else None
            ),
        },
    )

    return checkpoint


def run():
    global CURRENT_RUN

    state = load_state()
    policy = load_policy()

    state["run_count"] = (
        int(state.get("run_count", 0)) + 1
    )

    run_id = state["run_count"]
    CURRENT_RUN = run_id

    previous_checkpoint = load_json(
        CHECKPOINT,
        None,
    )

    print()
    print("=" * 64)
    print(
        f"SEEPo EVIDENCE AGENT — RUN {run_id}"
    )
    print("=" * 64)

    if previous_checkpoint:
        print(
            "RECOVERY CHECKPOINT : "
            f"run={previous_checkpoint.get('run_id')} "
            f"stage={previous_checkpoint.get('stage')} "
            f"status={previous_checkpoint.get('status')}"
        )
    else:
        print("RECOVERY CHECKPOINT : none")

    print(
        f"POLICY              : {POLICY}"
    )
    print(
        f"CHECKPOINT          : {CHECKPOINT}"
    )

    save_checkpoint(
        run_id,
        "START",
        "PASS",
        {
            "previous_checkpoint": (
                previous_checkpoint
            ),
        },
    )

    results = []

    if should_stop():
        return

    results.append(
        discover(run_id)
    )

    if should_stop():
        return

    results.append(
        detect_capabilities(run_id)
    )

    if should_stop():
        return

    results.append(
        file_io_test(run_id)
    )

    if should_stop():
        return

    results.append(
        process_test(run_id)
    )

    if should_stop():
        return

    learning = controlled_learning(
        run_id,
        policy,
    )

    if learning.get("decision"):
        results.append(
            learning["decision"]
        )

    if learning.get("result"):
        results.append(
            learning["result"]
        )

    if learning.get("learned"):
        results.append(
            learning["learned"]
        )

    if learning.get("verified"):
        results.append(
            learning["verified"]
        )

    if learning.get("stopped"):
        return

    environment = {
        "python": platform.python_version(),
        "uid": getattr(
            os,
            "getuid",
            lambda: None,
        )(),
        "cwd": str(Path.cwd()),
        "commands": {
            cmd: shutil.which(cmd)
            for cmd in [
                "python3",
                "sh",
                "curl",
                "git",
            ]
        },
    }

    commit_run(
        state,
        policy,
        run_id,
        environment,
        results,
    )

    print()
    print("=" * 64)
    print("EVIDENCE RESULT")
    print("=" * 64)

    print(
        f"RUN             : {run_id}"
    )

    print(
        f"STATE           : {STATE}"
    )

    print(
        f"POLICY          : {POLICY}"
    )

    print(
        f"CHECKPOINT      : {CHECKPOINT}"
    )

    print(
        f"EVIDENCE LOG    : {LOG}"
    )

    print(
        f"STATE SHA256    : "
        f"{sha256(STATE.read_bytes())}"
    )

    print(
        f"POLICY SHA256   : "
        f"{sha256(POLICY.read_bytes())}"
    )

    print(
        f"CHECKPOINT SHA256: "
        f"{sha256(CHECKPOINT.read_bytes())}"
    )

    print("=" * 64)
    print()
    print("NO CLAIM WITHOUT EVIDENCE")


if __name__ == "__main__":
    run()
