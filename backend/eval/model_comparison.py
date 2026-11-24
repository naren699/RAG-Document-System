"""Compare LLM configurations for the FARE RAG pipeline.

Runs the same set of test questions through multiple model/reasoning configurations
and collects timing, token usage, cost, and answer text for comparison.

Usage:
    cd backend
    ./venv/Scripts/python.exe -I eval/model_comparison.py
"""

import csv
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CONFIGS = [
    {"name": "gemini-3.8-flash (default)", "model": "google/gemini-3.8-flash", "reasoning_effort": ""},
    {"name": "gemini-3.8-flash (low reasoning)", "model": "google/gemini-3.8-flash", "reasoning_effort": "low"},
    {"name": "gemini-2.0-flash-001 (no thinking)", "model": "google/gemini-2.0-flash-001", "reasoning_effort": ""},
    {"name": "gemini-2.5-flash-preview", "model": "google/gemini-2.5-flash-preview", "reasoning_effort": "low"},
]

TEST_QUESTIONS = [
    "What is machine learning?",
    "What is supervised learning?",
    "When did transformers revolutionize NLP?",
    "What are key NLP tasks?",
    "What is computer vision?",
    "What is the capital of Mars?",
    "How do neural networks relate to both NLP and computer vision?",
    "What is deep learning?",
    "What are applications of computer vision?",
    "What is the relationship between AI and machine learning?",
]


def run_single_query(question: str, model: str, reasoning_effort: str) -> dict:
    import llm_provider
    from retriever import retrieve_hybrid
    from grounding import compute_grounding_score

    old_model = llm_provider.OPENROUTER_MODEL
    old_effort = llm_provider.OPENROUTER_REASONING_EFFORT
    llm_provider.OPENROUTER_MODEL = model
    llm_provider.OPENROUTER_REASONING_EFFORT = reasoning_effort

    try:
        start = time.time()
        chunks, _ = retrieve_hybrid(question, k=5)
        retrieval_ms = int((time.time() - start) * 1000)

        if not chunks:
            return {"error": "no chunks", "retrieval_ms": retrieval_ms}

        gen_start = time.time()
        result = llm_provider.query_with_openrouter(
            llm_provider.format_context(chunks), question
        )
        gen_ms = int((time.time() - gen_start) * 1000)
        total_ms = int((time.time() - start) * 1000)

        answer = result.get("answer", "")
        grounding = compute_grounding_score(answer, chunks)

        return {
            "answer": answer[:300],
            "total_ms": total_ms,
            "retrieval_ms": retrieval_ms,
            "generation_ms": gen_ms,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "reasoning_tokens": result.get("reasoning_tokens", 0),
            "visible_tokens": result.get("output_tokens", 0) - result.get("reasoning_tokens", 0),
            "cost_usd": result.get("estimated_cost_usd", 0),
            "grounding_score": grounding.get("score", 0),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        llm_provider.OPENROUTER_MODEL = old_model
        llm_provider.OPENROUTER_REASONING_EFFORT = old_effort


def run_comparison():
    output_dir = Path(__file__).parent.parent.parent / "data" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for config in CONFIGS:
        name = config["name"]
        print(f"\n{'='*60}")
        print(f"Config: {name}")
        print(f"  Model: {config['model']}")
        print(f"  Reasoning effort: {config['reasoning_effort'] or '(default)'}")
        print(f"{'='*60}")

        results = []
        for i, q in enumerate(TEST_QUESTIONS):
            print(f"  [{i+1}/{len(TEST_QUESTIONS)}] {q[:50]}...", end=" ", flush=True)
            r = run_single_query(q, config["model"], config["reasoning_effort"])
            if "error" in r:
                print(f"ERROR: {r['error']}")
            else:
                print(f"{r['total_ms']}ms, {r['reasoning_tokens']}r/{r['visible_tokens']}v tokens")
            r["question"] = q
            results.append(r)

        all_results[name] = results

        ok = [r for r in results if "error" not in r]
        if ok:
            total_times = [r["total_ms"] for r in ok]
            gen_times = [r["generation_ms"] for r in ok]
            reasoning = [r["reasoning_tokens"] for r in ok]
            visible = [r["visible_tokens"] for r in ok]
            costs = [r["cost_usd"] or 0 for r in ok]

            print(f"\n  Summary ({len(ok)}/{len(results)} succeeded):")
            print(f"    Median total:      {statistics.median(total_times):.0f}ms")
            print(f"    Slowest total:     {max(total_times)}ms")
            print(f"    Median generation: {statistics.median(gen_times):.0f}ms")
            print(f"    Median reasoning:  {statistics.median(reasoning):.0f} tokens")
            print(f"    Median visible:    {statistics.median(visible):.0f} tokens")
            print(f"    Total cost:        ${sum(costs):.5f}")

    # Save detailed results
    output_path = output_dir / "model_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_path}")

    # Print comparison table
    print(f"\n{'='*80}")
    print("COMPARISON TABLE")
    print(f"{'='*80}")
    print(f"{'Config':45} {'Med total':>10} {'Slowest':>10} {'Med reason':>12} {'Med vis':>10} {'Cost':>10}")
    print("-" * 100)
    for name, results in all_results.items():
        ok = [r for r in results if "error" not in r]
        if ok:
            print(f"{name:45} "
                  f"{statistics.median([r['total_ms'] for r in ok]):>9.0f}ms "
                  f"{max([r['total_ms'] for r in ok]):>9}ms "
                  f"{statistics.median([r['reasoning_tokens'] for r in ok]):>11.0f} "
                  f"{statistics.median([r['visible_tokens'] for r in ok]):>9.0f} "
                  f"${sum([r['cost_usd'] or 0 for r in ok]):>8.5f}")
        else:
            print(f"{name:45} {'FAILED':>10}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_comparison()
