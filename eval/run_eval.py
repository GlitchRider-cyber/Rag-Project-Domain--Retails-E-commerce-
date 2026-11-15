#!/usr/bin/env python3
"""
Aurelia & Co. — RAG Evaluation Runner

Loads eval/golden_set.json, queries the /chat endpoint for each question,
and measures retrieval hit rate, answer quality, refusal accuracy, and latency.
Results are printed as a summary table and saved to eval/results.json.
"""

import json
import time
import argparse
import sys
from pathlib import Path
from urllib import request, error

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:8000"
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
RESULTS_PATH = Path(__file__).parent / "results.json"

REFUSAL_KEYWORDS = [
    "i can't", "i cannot", "i don't have", "outside my knowledge",
    "not able to", "beyond my scope", "i'm not sure", "no information",
    "don't have information", "not something i can help with",
    "not related to", "unfortunately",
]


def load_golden_set() -> list[dict]:
    """Load the golden evaluation set from JSON."""
    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def query_chat(base_url: str, question: str, session_id: str | None = None) -> dict:
    """
    Send a question to the /chat endpoint and collect the full response.
    Returns dict with keys: answer, sources, latency_ms, error.
    """
    url = f"{base_url}/chat"
    payload = {"message": question}
    if session_id:
        payload["session_id"] = session_id

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )

    answer_parts: list[str] = []
    sources: list[dict] = []
    start = time.perf_counter()

    try:
        with request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "token":
                    answer_parts.append(event.get("content", ""))
                elif event.get("type") == "sources":
                    sources = event.get("sources", [])
                elif event.get("type") == "done":
                    break

        latency = (time.perf_counter() - start) * 1000
        return {
            "answer": "".join(answer_parts),
            "sources": sources,
            "latency_ms": round(latency, 1),
            "error": None,
        }
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        latency = (time.perf_counter() - start) * 1000
        return {
            "answer": "",
            "sources": [],
            "latency_ms": round(latency, 1),
            "error": str(exc),
        }


# ──────────────────────────────────────────────
# Evaluation metrics
# ──────────────────────────────────────────────

def check_retrieval_hit(sources: list[dict], expected_doc_type: str) -> bool:
    """Does the expected document type appear in the retrieved sources?"""
    for src in sources:
        if src.get("doc_type", "").lower() == expected_doc_type.lower():
            return True
        if src.get("type", "").lower() == expected_doc_type.lower():
            return True
    return False


def check_answer_contains(answer: str, expected_phrases: list[str]) -> tuple[int, int]:
    """Returns (hits, total) for expected phrases found in the answer."""
    if not expected_phrases:
        return (0, 0)
    answer_lower = answer.lower()
    hits = sum(1 for phrase in expected_phrases if phrase.lower() in answer_lower)
    return (hits, len(expected_phrases))


def check_refusal(answer: str) -> bool:
    """Check if the answer is a polite refusal / deflection."""
    answer_lower = answer.lower()
    return any(kw in answer_lower for kw in REFUSAL_KEYWORDS)


# ──────────────────────────────────────────────
# Main evaluation loop
# ──────────────────────────────────────────────

def run_evaluation(base_url: str, verbose: bool = False) -> dict:
    golden_set = load_golden_set()
    results: list[dict] = []

    # Accumulators
    total = len(golden_set)
    retrieval_hits = 0
    retrieval_eligible = 0
    phrase_hits = 0
    phrase_total = 0
    refusal_correct = 0
    refusal_eligible = 0
    errors = 0
    latencies: list[float] = []

    print(f"\n{'='*72}")
    print(f"  Aurelia & Co. RAG Evaluation — {total} test cases")
    print(f"  Endpoint: {base_url}/chat")
    print(f"{'='*72}\n")

    for i, tc in enumerate(golden_set, 1):
        q = tc["question"]
        print(f"  [{i:>2}/{total}] {q[:60]}{'...' if len(q) > 60 else ''}", end="", flush=True)

        resp = query_chat(base_url, q)

        result = {
            "id": tc["id"],
            "question": q,
            "category": tc["category"],
            "is_answerable": tc["is_answerable"],
            "answer": resp["answer"],
            "sources": resp["sources"],
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
        }

        latencies.append(resp["latency_ms"])

        if resp["error"]:
            errors += 1
            result["retrieval_hit"] = None
            result["phrase_hits"] = None
            result["phrase_total"] = None
            result["refusal_correct"] = None
            print(f"  ✗ ERROR: {resp['error'][:40]}")
        else:
            # Retrieval hit rate (only for answerable questions)
            if tc["is_answerable"]:
                retrieval_eligible += 1
                hit = check_retrieval_hit(resp["sources"], tc["expected_doc_type"])
                if hit:
                    retrieval_hits += 1
                result["retrieval_hit"] = hit
            else:
                result["retrieval_hit"] = None

            # Phrase coverage
            ph, pt = check_answer_contains(resp["answer"], tc["expected_answer_contains"])
            result["phrase_hits"] = ph
            result["phrase_total"] = pt
            phrase_hits += ph
            phrase_total += pt

            # Refusal accuracy (only for unanswerable / off-topic)
            if not tc["is_answerable"]:
                refusal_eligible += 1
                refused = check_refusal(resp["answer"])
                if refused:
                    refusal_correct += 1
                result["refusal_correct"] = refused
            else:
                result["refusal_correct"] = None

            status = "✓" if (result.get("retrieval_hit") is not False) else "○"
            print(f"  {status}  ({resp['latency_ms']:.0f}ms)")

        results.append(result)

    # ── Summary ──
    retrieval_rate = (retrieval_hits / retrieval_eligible * 100) if retrieval_eligible else 0
    phrase_rate = (phrase_hits / phrase_total * 100) if phrase_total else 0
    refusal_rate = (refusal_correct / refusal_eligible * 100) if refusal_eligible else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    summary = {
        "total_cases": total,
        "errors": errors,
        "retrieval_hit_rate": round(retrieval_rate, 1),
        "retrieval_hits": retrieval_hits,
        "retrieval_eligible": retrieval_eligible,
        "phrase_coverage": round(phrase_rate, 1),
        "phrase_hits": phrase_hits,
        "phrase_total": phrase_total,
        "refusal_accuracy": round(refusal_rate, 1),
        "refusal_correct": refusal_correct,
        "refusal_eligible": refusal_eligible,
        "avg_latency_ms": round(avg_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
    }

    # Category breakdown
    categories: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "retrieval_hits": 0, "phrase_hits": 0, "phrase_total": 0, "errors": 0}
        categories[cat]["total"] += 1
        if r.get("error"):
            categories[cat]["errors"] += 1
        if r.get("retrieval_hit"):
            categories[cat]["retrieval_hits"] += 1
        if r.get("phrase_hits") is not None:
            categories[cat]["phrase_hits"] += r["phrase_hits"]
            categories[cat]["phrase_total"] += r["phrase_total"]

    summary["by_category"] = categories

    # Print summary table
    print(f"\n{'='*72}")
    print("  EVALUATION SUMMARY")
    print(f"{'='*72}")
    print(f"  {'Metric':<35} {'Value':>15}")
    print(f"  {'─'*35} {'─'*15}")
    print(f"  {'Total Test Cases':<35} {total:>15}")
    print(f"  {'Errors':<35} {errors:>15}")
    print(f"  {'Retrieval Hit Rate':<35} {retrieval_rate:>14.1f}%")
    print(f"    {'(hits / eligible)':<33} {retrieval_hits:>6} / {retrieval_eligible}")
    print(f"  {'Phrase Coverage':<35} {phrase_rate:>14.1f}%")
    print(f"    {'(hits / total phrases)':<33} {phrase_hits:>6} / {phrase_total}")
    print(f"  {'Refusal Accuracy':<35} {refusal_rate:>14.1f}%")
    print(f"    {'(correct / eligible)':<33} {refusal_correct:>6} / {refusal_eligible}")
    print(f"  {'Avg Latency':<35} {avg_latency:>12.1f}ms")
    print(f"  {'P95 Latency':<35} {p95_latency:>12.1f}ms")

    print(f"\n  {'Category':<25} {'Count':>6} {'Retrieval':>10} {'Phrases':>10}")
    print(f"  {'─'*25} {'─'*6} {'─'*10} {'─'*10}")
    for cat, data in sorted(categories.items()):
        r_str = f"{data['retrieval_hits']}/{data['total']}" if data["total"] else "—"
        p_str = f"{data['phrase_hits']}/{data['phrase_total']}" if data["phrase_total"] else "—"
        print(f"  {cat:<25} {data['total']:>6} {r_str:>10} {p_str:>10}")

    print(f"{'='*72}\n")

    # Save results
    output = {"summary": summary, "results": results}
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Results saved to {RESULTS_PATH}\n")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAG evaluation against golden set")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Backend base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    run_evaluation(args.base_url, verbose=args.verbose)
