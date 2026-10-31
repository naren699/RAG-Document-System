#!/usr/bin/env python3
"""Test visual page extraction with OCR and Vision modes.

STEP 8: Test questions on the AI infographic
STEP 9: Edge case testing

Run: python test_visual_extraction.py
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "What are the three types of AI based on capability?",
        "expected": ["Narrow AI", "General AI", "Super AI"],
        "answer_check": lambda a: all(x.lower() in a.lower() for x in ["narrow", "general", "super"]),
    },
    {
        "id": 2,
        "question": "Which example is given for Reactive Machines?",
        "expected": ["IBM Deep Blue"],
        "answer_check": lambda a: "ibm" in a.lower() and "deep blue" in a.lower(),
    },
    {
        "id": 3,
        "question": "What are the steps in 'How AI Works'?",
        "expected": ["Data Collection", "Data Preprocessing", "Model Training", "Evaluation", "Prediction/Inference"],
        "answer_check": lambda a: sum(1 for x in ["collection", "preprocessing", "training", "evaluation", "prediction"] if x in a.lower()) >= 3,
    },
    {
        "id": 4,
        "question": "What does an LSTM improve over an RNN?",
        "expected": ["long-term dependencies", "improved version"],
        "answer_check": lambda a: "lstm" in a.lower() and ("long" in a.lower() or "dependencies" in a.lower() or "improved" in a.lower()),
    },
    {
        "id": 5,
        "question": "Which architecture uses the attention mechanism?",
        "expected": ["Transformer", "BERT", "GPT"],
        "answer_check": lambda a: "transformer" in a.lower() or "attention" in a.lower(),
    },
    {
        "id": 6,
        "question": "What are the four types of AI based on functionality?",
        "expected": ["Reactive Machines", "Limited Memory", "Theory of Mind", "Self-Aware AI"],
        "answer_check": lambda a: sum(1 for x in ["reactive", "limited memory", "theory of mind", "self-aware"] if x in a.lower()) >= 2,
    },
    {
        "id": 7,
        "question": "What does this document say about quantum computing?",
        "expected": ["not in document"],
        "answer_check": lambda a: "couldn't find" in a.lower() or "not in" in a.lower() or "no information" in a.lower(),
        "should_refuse": True,
    },
    {
        "id": 8,
        "question": "Who created the Transformer architecture?",
        "expected": ["not in document"],
        "answer_check": lambda a: "couldn't find" in a.lower() or "not in" in a.lower() or "no information" in a.lower(),
        "should_refuse": True,
    },
]

EDGE_CASES = [
    {
        "id": "multi_page_scanned",
        "name": "Scanned multi-page PDF",
        "description": "A PDF where all pages are scanned images",
        "test_file": "edge_case_scanned.pdf",
    },
    {
        "id": "mixed_text_chart",
        "name": "PDF with text plus a chart image",
        "description": "Mixed content: some pages are text, some have embedded charts",
        "test_file": "edge_case_mixed.pdf",
    },
    {
        "id": "blank_page",
        "name": "Blank page",
        "description": "A PDF with a completely blank page",
        "test_file": "edge_case_blank.pdf",
    },
    {
        "id": "large_image",
        "name": "Very large image",
        "description": "A PDF with a very high resolution image (4K+)",
        "test_file": "edge_case_large.pdf",
    },
    {
        "id": "password_protected",
        "name": "Password-protected PDF",
        "description": "A PDF that requires a password to open",
        "test_file": "edge_case_protected.pdf",
    },
]


def run_query(question: str, k: int = 5) -> dict:
    """Run a single query and return the result with timing."""
    start = time.time()
    try:
        resp = requests.post(
            f"{API_URL}/api/query",
            json={"query": question, "k": k, "method": "hybrid"},
            timeout=120,
        )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "latency_ms": latency_ms,
            }

        data = resp.json()
        return {
            "success": True,
            "answer": data.get("answer", ""),
            "is_not_found": data.get("is_not_found", False),
            "sources": data.get("sources", []),
            "tokens": data.get("tokens_used", {}),
            "cost": data.get("estimated_cost_usd"),
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": int((time.time() - start) * 1000),
        }


def test_question(q: dict, run_num: int) -> dict:
    """Test a single question and evaluate the answer."""
    result = run_query(q["question"])

    if not result["success"]:
        return {
            "question_id": q["id"],
            "run": run_num,
            "answered": False,
            "correct": False,
            "error": result["error"],
            "latency_ms": result["latency_ms"],
        }

    answer = result["answer"]
    should_refuse = q.get("should_refuse", False)
    is_refusal = result["is_not_found"] or "couldn't find" in answer.lower()

    if should_refuse:
        correct = is_refusal
    else:
        correct = q["answer_check"](answer) if not is_refusal else False

    chunks_retrieved = []
    for s in result.get("sources", []):
        chunks_retrieved.append({
            "chunk_id": s.get("chunk_id"),
            "page_num": s.get("page_num"),
            "extraction_method": s.get("extraction_method"),
            "score": s.get("score"),
        })

    return {
        "question_id": q["id"],
        "run": run_num,
        "answered": not is_refusal,
        "correct": correct,
        "answer_snippet": answer[:200] if answer else "",
        "chunks_retrieved": chunks_retrieved,
        "latency_ms": result["latency_ms"],
        "tokens": result.get("tokens", {}),
        "cost": result.get("cost"),
    }


def upload_pdf(filepath: str) -> dict:
    """Upload a PDF and return the ingestion result."""
    if not Path(filepath).exists():
        return {"success": False, "error": f"File not found: {filepath}"}

    start = time.time()
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(
                f"{API_URL}/api/ingest",
                files={"file": (Path(filepath).name, f, "application/pdf")},
                timeout=300,
            )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                "latency_ms": latency_ms,
            }

        data = resp.json()
        return {
            "success": True,
            "doc_id": data.get("doc_id"),
            "chunks_count": data.get("chunks_count", 0),
            "text_chunks": data.get("text_chunks", 0),
            "visual_chunks": data.get("visual_chunks", 0),
            "ocr_pages": data.get("ocr_pages", 0),
            "vision_pages": data.get("vision_pages", 0),
            "warnings": data.get("warnings", []),
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": int((time.time() - start) * 1000),
        }


def clear_database():
    """Clear all documents from the database."""
    try:
        resp = requests.delete(f"{API_URL}/api/clear", timeout=30)
        return resp.status_code == 200
    except:
        return False


def run_step8_tests(pdf_path: str, use_vision: bool = False):
    """Run Step 8 tests: questions on the infographic."""
    mode = "vision" if use_vision else "ocr"
    print(f"\n{'='*60}")
    print(f"STEP 8: Testing with {mode.upper()} mode")
    print(f"{'='*60}\n")

    clear_database()

    if use_vision:
        os.environ["VISION_LLM_ENABLED"] = "true"
    else:
        os.environ["VISION_LLM_ENABLED"] = "false"

    print(f"Uploading {pdf_path}...")
    upload_result = upload_pdf(pdf_path)

    if not upload_result["success"]:
        print(f"UPLOAD FAILED: {upload_result['error']}")
        return None

    print(f"Upload complete: {upload_result['chunks_count']} chunks "
          f"(OCR: {upload_result['ocr_pages']}, Vision: {upload_result['vision_pages']})")
    print()

    results = []
    for q in TEST_QUESTIONS:
        print(f"Q{q['id']}: {q['question'][:50]}...")
        for run_num in range(1, 4):
            result = test_question(q, run_num)
            results.append(result)
            status = "✓" if result["correct"] else "✗"
            answered = "answered" if result["answered"] else "refused"
            print(f"  Run {run_num}: {status} ({answered}, {result['latency_ms']}ms)")
            time.sleep(0.5)
        print()

    correct_count = sum(1 for r in results if r["correct"])
    total = len(results)
    unique_correct = len(set(r["question_id"] for r in results if r["correct"]))
    unique_total = len(TEST_QUESTIONS)

    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0
    total_tokens = sum(r.get("tokens", {}).get("input_tokens", 0) + r.get("tokens", {}).get("output_tokens", 0) for r in results)
    total_cost = sum(r.get("cost", 0) or 0 for r in results)

    summary = {
        "mode": mode,
        "correct_runs": f"{correct_count}/{total}",
        "unique_correct": f"{unique_correct}/{unique_total}",
        "accuracy": f"{correct_count/total*100:.1f}%" if total else "N/A",
        "avg_latency_ms": int(avg_latency),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 5),
        "results": results,
    }

    print(f"\nSUMMARY ({mode.upper()}):")
    print(f"  Correct: {summary['correct_runs']} runs, {summary['unique_correct']} questions")
    print(f"  Accuracy: {summary['accuracy']}")
    print(f"  Avg latency: {summary['avg_latency_ms']}ms")
    print(f"  Total tokens: {summary['total_tokens']}")
    print(f"  Total cost: ${summary['total_cost_usd']:.5f}")

    return summary


def run_step9_edge_cases():
    """Run Step 9: edge case testing."""
    print(f"\n{'='*60}")
    print("STEP 9: Edge Case Testing")
    print(f"{'='*60}\n")

    results = []

    for case in EDGE_CASES:
        print(f"Testing: {case['name']}...")
        filepath = f"test_files/{case['test_file']}"

        if not Path(filepath).exists():
            print(f"  SKIP: Test file not found ({filepath})")
            results.append({
                "id": case["id"],
                "name": case["name"],
                "status": "SKIP",
                "message": "Test file not found",
            })
            continue

        clear_database()

        upload_result = upload_pdf(filepath)

        if upload_result["success"]:
            status = "PASS"
            message = f"{upload_result['chunks_count']} chunks created"
            if upload_result.get("warnings"):
                message += f", {len(upload_result['warnings'])} warning(s)"
        else:
            error = upload_result.get("error", "Unknown error")
            if "password" in error.lower() or "encrypted" in error.lower():
                status = "PASS"
                message = "Correctly rejected password-protected PDF"
            elif any(x in error.lower() for x in ["no content", "blank", "empty"]):
                status = "PASS"
                message = "Correctly handled blank/empty PDF"
            else:
                status = "FAIL"
                message = error[:100]

        print(f"  {status}: {message}")
        results.append({
            "id": case["id"],
            "name": case["name"],
            "status": status,
            "message": message,
        })

    print("\n" + "-" * 40)
    print("EDGE CASE SUMMARY:")
    print("-" * 40)
    for r in results:
        status_icon = "✓" if r["status"] == "PASS" else "✗" if r["status"] == "FAIL" else "○"
        print(f"  {status_icon} {r['name']}: {r['status']}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    return results


def create_edge_case_files():
    """Create test files for edge cases (placeholder)."""
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)

    print("Edge case test files should be created in backend/test_files/:")
    for case in EDGE_CASES:
        filepath = test_dir / case["test_file"]
        if not filepath.exists():
            print(f"  - {case['test_file']}: {case['description']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_visual_extraction.py <infographic.pdf> [--ocr-only|--vision-only|--both]")
        print("\nThis script tests visual PDF extraction with OCR and Vision modes.")
        print("\nOptions:")
        print("  --ocr-only    Run tests with OCR extraction only")
        print("  --vision-only Run tests with Vision LLM extraction only")
        print("  --both        Run tests with both modes (default)")
        print("  --edge-cases  Run edge case tests only")
        print("\nExample:")
        print("  python test_visual_extraction.py ai_infographic.pdf --both")
        sys.exit(1)

    pdf_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--both"

    if mode == "--edge-cases":
        create_edge_case_files()
        run_step9_edge_cases()
        return

    if not Path(pdf_path).exists():
        print(f"ERROR: File not found: {pdf_path}")
        sys.exit(1)

    all_results = {}

    if mode in ("--ocr-only", "--both"):
        ocr_results = run_step8_tests(pdf_path, use_vision=False)
        if ocr_results:
            all_results["ocr"] = ocr_results

    if mode in ("--vision-only", "--both"):
        vision_results = run_step8_tests(pdf_path, use_vision=True)
        if vision_results:
            all_results["vision"] = vision_results

    if len(all_results) == 2:
        print(f"\n{'='*60}")
        print("COMPARISON: OCR vs Vision")
        print(f"{'='*60}")
        print(f"{'Metric':<20} {'OCR':>15} {'Vision':>15}")
        print("-" * 50)
        print(f"{'Correct runs':<20} {all_results['ocr']['correct_runs']:>15} {all_results['vision']['correct_runs']:>15}")
        print(f"{'Accuracy':<20} {all_results['ocr']['accuracy']:>15} {all_results['vision']['accuracy']:>15}")
        print(f"{'Avg latency (ms)':<20} {all_results['ocr']['avg_latency_ms']:>15} {all_results['vision']['avg_latency_ms']:>15}")
        print(f"{'Total cost ($)':<20} {all_results['ocr']['total_cost_usd']:>15.5f} {all_results['vision']['total_cost_usd']:>15.5f}")

    output_file = Path("test_results.json")
    output_file.write_text(json.dumps(all_results, indent=2))
    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
