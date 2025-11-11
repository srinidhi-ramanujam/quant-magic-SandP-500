"""
PoC evaluation with 10 curated simple questions.

This test validates the complete end-to-end flow with real questions.
"""

import pytest
import time
from src.cli import FinancialCLI


# 10 PoC evaluation questions
POC_QUESTIONS = [
    {
        "id": "POC_001",
        "question": "How many S&P 500 companies are in the Information Technology sector?",
        "expected_contains": ["143", "Information Technology"],
        "question_type": "sector_count",
    },
    {
        "id": "POC_002",
        "question": "What is Apple Inc's CIK?",
        "expected_contains": ["CIK", "Apple"],
        "question_type": "company_cik",
    },
    {
        "id": "POC_003",
        "question": "What sector is Microsoft Corporation in?",
        "expected_contains": ["sector", "Microsoft"],
        "question_type": "company_sector",
    },
    {
        "id": "POC_004",
        "question": "How many companies are in the Healthcare sector?",
        "expected_contains": ["Healthcare", "Health Care"],
        "question_type": "sector_count",
    },
    {
        "id": "POC_005",
        "question": "What is Tesla Inc's CIK?",
        "expected_contains": ["CIK", "Tesla"],
        "question_type": "company_cik",
    },
    {
        "id": "POC_006",
        "question": "What sector is JPMorgan Chase in?",
        "expected_contains": ["sector", "JPMorgan"],
        "question_type": "company_sector",
    },
    {
        "id": "POC_007",
        "question": "How many companies are in the Financials sector?",
        "expected_contains": ["Financials"],
        "question_type": "sector_count",
    },
    {
        "id": "POC_008",
        "question": "What is Amazon's CIK?",
        "expected_contains": ["CIK", "Amazon"],
        "question_type": "company_cik",
    },
    {
        "id": "POC_009",
        "question": "What sector is Alphabet Inc in?",
        "expected_contains": ["sector", "Alphabet"],
        "question_type": "company_sector",
    },
    {
        "id": "POC_010",
        "question": "How many companies are in the Energy sector?",
        "expected_contains": ["Energy"],
        "question_type": "sector_count",
    },
]


@pytest.fixture(scope="module")
def cli():
    """Create a CLI instance for all tests."""
    cli_instance = FinancialCLI(allow_offline=True)
    yield cli_instance
    cli_instance.close()


def test_poc_10_questions(cli):
    """
    Run all 10 PoC questions and verify pass rate.

    Success criteria: ≥9/10 questions answered correctly (90%)
    """
    results = []
    total_time = 0

    for test_case in POC_QUESTIONS:
        start_time = time.time()

        # Process question
        response = cli.process_question(test_case["question"], debug_mode=False)

        elapsed = time.time() - start_time
        total_time += elapsed

        # Check if successful
        success = response.success

        # Check if answer contains expected text (basic validation)
        contains_expected = False
        if success and response.answer:
            answer_lower = response.answer.lower()
            contains_expected = any(
                expected.lower() in answer_lower
                for expected in test_case["expected_contains"]
            )

        # Record result
        results.append(
            {
                "id": test_case["id"],
                "question": test_case["question"],
                "success": success,
                "contains_expected": contains_expected,
                "passed": success and contains_expected,
                "elapsed": elapsed,
                "answer": response.answer[:100] if response.answer else "",
            }
        )

    # Calculate metrics
    passed = sum(1 for r in results if r["passed"])
    pass_rate = passed / len(POC_QUESTIONS)
    avg_time = total_time / len(POC_QUESTIONS)

    # Print summary
    print(f"\n{'='*60}")
    print("PoC Evaluation Results")
    print(f"{'='*60}")
    print(f"Total questions: {len(POC_QUESTIONS)}")
    print(f"Passed: {passed}")
    print(f"Pass rate: {pass_rate:.1%}")
    print(f"Average time: {avg_time:.3f}s")
    print(f"Total time: {total_time:.3f}s")
    print(f"{'='*60}")

    # Print individual results
    print("\nDetailed Results:")
    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"{status} | {r['id']} | {r['elapsed']:.3f}s | {r['question'][:50]}...")
        if not r["passed"]:
            print(f"      Answer: {r['answer']}")

    print(f"{'='*60}\n")

    # Assert success criteria
    assert (
        pass_rate >= 0.90
    ), f"PoC pass rate {pass_rate:.1%} is below 90% threshold (passed {passed}/10)"
    assert (
        avg_time < 10.0
    ), f"Average response time {avg_time:.3f}s exceeds 10s threshold"


# Individual test cases for better granularity
@pytest.mark.parametrize(
    "test_case", POC_QUESTIONS, ids=[q["id"] for q in POC_QUESTIONS]
)
def test_individual_question(cli, test_case):
    """Test each PoC question individually."""
    response = cli.process_question(test_case["question"], debug_mode=False)

    # Should succeed
    assert response.success is True, f"Question failed: {test_case['question']}"

    # Should have an answer
    assert len(response.answer) > 0, f"Empty answer for: {test_case['question']}"

    # Should have reasonable confidence
    assert response.confidence > 0.3, f"Low confidence for: {test_case['question']}"
