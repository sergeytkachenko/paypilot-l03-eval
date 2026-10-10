""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import assertions as A
import console
import stand
from loader import load, set_hash, summarise

SETS_DIR = HERE / "sets"
REPORTS_DIR = HERE / "reports"
RUBRIC_VERSION = os.environ.get("RUBRIC_VERSION", "rubric.v1")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL") or "not-used"



def _engines():
    ""
    root = HERE.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.engines import disputes, fx, limits, policy
    return {"fx": fx, "limits": limits, "disputes": disputes, "policy": policy}



class JudgeUnavailable(RuntimeError):
    pass


def _judge(question, answer, rubric):
    ""
    if JUDGE_MODEL == "not-used":
        raise JudgeUnavailable("judge not configured (set JUDGE_MODEL)")
    from judge import verdict
    return verdict(question, answer, rubric, JUDGE_MODEL)


def evaluate(case: dict, results: list[dict]) -> A.Verdict:
    ""
    meta = case["additional_metadata"]
    name = meta["assertion"]
    answer = results[-1]["answer"] if results else ""
    tree = results[-1].get("trace") or {}
    expected = case.get("expected_output")

    if name in ("equals", "exact"):
        return A.level1_exact(answer, expected)
    if name == "exact_tool_calls":
        return A.tool_calls_exact(tree, meta.get("expected_tool_calls", []))
    if name in ("numeric", "number", "amount"):
        return A.level2_numeric(answer, meta.get("expected_number", expected),
                                meta.get("tolerance", 0.01))
    if name == "budget":
        return _budget(meta, results)
    if name in ("contains", "pattern"):
        return A.level3_contains(answer, expected or meta.get("reference", ""))
    if name == "regex":
        return A.level3_regex(answer, meta["pattern"])
    if name in ("not_contains", "absent"):
        return A.level4_not_contains(answer, meta["forbidden"])
    if name == "not_regex":
        return A.level4_not_regex(answer, meta["forbidden_pattern"])
    if name == "tool_result_numeric":
        return A.tool_result_numeric(tree, meta["tool"], meta["field"],
                                     meta["expected_number"],
                                     meta.get("tolerance", 0.01))
    if name == "tool_grounded_numeric":
        return A.tool_grounded_numeric(tree, answer, meta["tool"],
                                       meta["field"], meta["expected_number"],
                                       meta.get("tolerance", 0.01))
    if name == "tool_result_flag":
        return A.tool_result_flag(tree, meta["tool"], meta["field"],
                                  meta["expected_flag"])
    if name == "tool_called_with":
        return A.tool_called_with(tree, meta["tool"], meta["args"])
    if name == "tool_sequence":
        return A.tool_sequence(tree, meta.get("must_include"),
                               meta.get("must_exclude"),
                               tuple(meta["before"]) if meta.get("before") else None)
    if name == "state_row":
        rows = stand.state(meta["table"])
        return A.state_row(rows, meta.get("where", {}),
                           meta.get("expect_fields", {}),
                           meta.get("expected_count"))
    if name == "tool_call_count":
        return A.tool_call_count(tree, meta["tool"], meta["expected_count"])
    if name == "no_span":
        return A.level4_no_span(tree, meta["forbidden_span"])
    if name == "similar":
        return A.level5_similar(answer, meta.get("reference", expected or ""),
                                meta.get("threshold", 0.5))
    if name == "k_of_n":
        hits = [A.level3_contains(r["answer"], expected).passed for r in results]
        return A.level6_k_of_n(hits, meta.get("k", 4))
    if name == "judge":
        return A.level7_judge(answer, meta.get("rubric", ""),
                              case.get("input", ""), _judge)
    return A.Verdict(False, 0, name, f"no handler for assertion {name!r}")


def _budget(meta: dict, results: list[dict]) -> A.Verdict:
    ""
    budget = meta.get("budget", {})
    tokens = sum(r["usage"]["input_tokens"] + r["usage"]["output_tokens"]
                 for r in results)
    identical = 0
    for r in results:
        names = [c["name"] for c in stand.tool_calls(r.get("trace") or {})]
        identical = max(identical,
                        max((names.count(n) for n in set(names)), default=0))
    problems = []
    if "tokens_total" in budget and tokens > budget["tokens_total"]:
        problems.append(f"tokens {tokens} > {budget['tokens_total']}")
    if ("identical_tool_calls_max" in budget
            and identical > budget["identical_tool_calls_max"]):
        problems.append(f"identical tool calls {identical} > "
                        f"{budget['identical_tool_calls_max']}")
    if "latency_ms" in budget:
        worst = max((r.get("latency_ms", 0) for r in results), default=0)
        if worst > budget["latency_ms"]:
            problems.append(f"latency {worst}ms > {budget['latency_ms']}ms")
    ok = not problems
    return A.Verdict(ok, 2, "budget",
                     "; ".join(problems) if problems else
                     f"tokens {tokens}, identical calls {identical}")



def run_case(case: dict) -> dict:
    meta = case["additional_metadata"]
    runs = int(meta.get("runs", 1))
    results = []
    for _ in range(runs):
        stand.reset()
        t0 = time.time()
        customer = (case.get("context") or {}).get("customer_id")
        if case.get("turns"):
            turns = [t["content"] for t in case["turns"] if t["role"] == "user"]
            outs = stand.dialog(turns, customer)
            last = outs[-1]
        else:
            last = stand.chat(case["input"], customer_id=customer)
        results.append({
            "answer": last.get("answer", ""),
            "usage": last.get("usage", {"input_tokens": 0, "output_tokens": 0}),
            "latency_ms": int((time.time() - t0) * 1000),
            "trace": stand.trace(last["request_id"]),
        })
    try:
        verdict = evaluate(case, results)
        skipped = False
    except JudgeUnavailable as e:
        verdict = A.Verdict(False, 7, "judge", str(e))
        skipped = True
    return {
        "skipped": skipped,
        "id": case["id"],
        "layer": meta["layer"],
        "oracle": meta["oracle"],
        "severity": meta["severity"],
        "gate": meta.get("gate", "daily"),
        "runs": runs,
        "verdict": verdict.as_dict(),
        "answers": [r["answer"][:400] for r in results],
        "latency_ms": results[-1]["latency_ms"] if results else 0,
        "tokens": sum((r["usage"] or {}).get("input_tokens", 0)
                      + (r["usage"] or {}).get("output_tokens", 0)
                      for r in results),
        "tool_calls": (stand.tool_calls(results[-1].get("trace") or {})
                       if results else []),
    }


def main() -> int:
    set_name = os.environ.get("SET", "l03_reference")
    gate = os.environ.get("GATE", "")
    only = {x.strip() for x in os.environ.get("CASE", "").split(",") if x.strip()}
    path = SETS_DIR / f"{set_name}.jsonl"

    stand.wait_until_ready()
    profile_now = stand.profile()["profile"]
    prompt_ver = stand.prompt_version()
    cases = load(path)
    if only:
        cases = [c for c in cases if c["id"] in only]
        if not cases:
            print(f"no case matched CASE={sorted(only)}")
            return 1
    if gate:
        cases = [c for c in cases
                 if c["additional_metadata"].get("gate", "daily") == gate]
        if not cases:
            print(f"no cases with gate={gate} in {set_name}")
            return 0

    print(f"set {set_name} ({len(cases)} cases)  profile {profile_now}  "
          f"prompt {prompt_ver}" + (f"  gate {gate}" if gate else ""))
    print("-" * 72)

    brief = os.environ.get("BRIEF", "") == "1"
    colour = console.colour_enabled()
    t0 = time.time()
    rows = []
    for case in cases:
        row = run_case(case)
        rows.append(row)
        for line in console.case_lines(case, row, brief=brief, colour=colour):
            print(line)
    elapsed = round(time.time() - t0, 1)

    graded = [r for r in rows if not r.get("skipped")]
    skipped = [r for r in rows if r.get("skipped")]
    passed = sum(1 for r in graded if r["verdict"]["passed"])
    by_layer = {}
    for r in graded:
        s = by_layer.setdefault(r["layer"], {"passed": 0, "total": 0})
        s["total"] += 1
        s["passed"] += bool(r["verdict"]["passed"])

    print("-" * 72)
    print(f"{passed}/{len(graded)} passed"
          + (f"   {len(skipped)} skipped (no judge)" if skipped else "")
          + f"   elapsed {elapsed}s")
    for layer, s in sorted(by_layer.items()):
        print(f"  {layer:<12} {s['passed']}/{s['total']}")
    failed = None if brief else console.failed_line(rows, colour)
    if failed:
        print(failed)

    record = {
        "prompt_version": prompt_ver,
        "set_hash": set_hash(path),
        "profile": profile_now,
        "judge_model": JUDGE_MODEL,
        "rubric_version": RUBRIC_VERSION,
        "elapsed": elapsed,
        "set": set_name,
        "gate": gate or "all",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": len(graded),
        "skipped": len(skipped),
        "by_layer": by_layer,
        "coverage": summarise(cases),
        "cases": rows,
    }
    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = REPORTS_DIR / f"{set_name}-{profile_now}-{stamp}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"report -> {out.relative_to(HERE.parent)}")
    return 0 if passed == len(graded) else 1


if __name__ == "__main__":
    sys.exit(main())
