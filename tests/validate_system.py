"""
Simple validation tests for the content generation system.
Run with: python tests/validate_system.py
"""

import sys
import json
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_json_outputs_exist():
    """Verify all 3 JSON outputs exist."""
    output_dir = Path(__file__).parent.parent / "output"

    required_files = ["faq.json", "product_page.json", "comparison_page.json"]

    print("\n" + "=" * 60)
    print("VALIDATION: JSON Outputs")
    print("=" * 60)

    for filename in required_files:
        filepath = output_dir / filename
        if filepath.exists():
            print(f"✓ {filename} exists")

            # Validate JSON
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"  - Valid JSON with {len(data)} top-level keys")
        else:
            print(f"✗ {filename} MISSING")
            return False

    return True


def test_faq_structure():
    """Validate FAQ structure."""
    output_dir = Path(__file__).parent.parent / "output"
    faq_path = output_dir / "faq.json"

    print("\n" + "=" * 60)
    print("VALIDATION: FAQ Structure")
    print("=" * 60)

    with open(faq_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check required fields
    assert "product" in data, "Missing 'product' field"
    assert "faqs" in data, "Missing 'faqs' field"
    assert "total_questions" in data, "Missing 'total_questions' field"

    # Check question count
    assert (
        data["total_questions"] >= 15
    ), f"Only {data['total_questions']} questions (need 15+)"
    assert len(data["faqs"]) >= 15, f"Only {len(data['faqs'])} FAQs (need 15+)"

    # Check FAQ structure
    for faq in data["faqs"]:
        assert "question" in faq, "FAQ missing 'question'"
        assert "answer" in faq, "FAQ missing 'answer'"

    print(f"✓ Product: {data['product']}")
    print(f"✓ Questions: {data['total_questions']}")
    print(f"✓ All FAQs have question and answer")

    return True


def test_product_page_structure():
    """Validate product page structure."""
    output_dir = Path(__file__).parent.parent / "output"
    product_path = output_dir / "product_page.json"

    print("\n" + "=" * 60)
    print("VALIDATION: Product Page Structure")
    print("=" * 60)

    with open(product_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check required sections
    assert "product_info" in data, "Missing 'product_info'"
    assert "benefits" in data, "Missing 'benefits'"
    assert "ingredients" in data, "Missing 'ingredients'"
    assert "usage" in data, "Missing 'usage'"
    assert "pricing" in data, "Missing 'pricing'"

    print(f"✓ Product: {data['product_info']['name']}")
    print(f"✓ Benefits: {len(data['benefits'])}")
    print(f"✓ Ingredients: {data['ingredients']['count']}")
    print(f"✓ Price: ₹{data['pricing']['price']}")

    return True


def test_comparison_structure():
    """Validate comparison page structure."""
    output_dir = Path(__file__).parent.parent / "output"
    comparison_path = output_dir / "comparison_page.json"

    print("\n" + "=" * 60)
    print("VALIDATION: Comparison Page Structure")
    print("=" * 60)

    with open(comparison_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check required fields
    assert "primary_product" in data, "Missing 'primary_product'"
    assert "comparison_with" in data, "Missing 'comparison_with'"
    assert "comparison_table" in data, "Missing 'comparison_table'"

    print(f"✓ Primary: {data['primary_product']}")
    print(f"✓ Comparing with: {data['comparison_with']}")
    print(f"✓ Comparison table rows: {len(data['comparison_table'])}")

    return True


def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("SYSTEM VALIDATION TESTS")
    print("=" * 60)

    tests = [
        ("JSON Outputs Exist", test_json_outputs_exist),
        ("FAQ Structure", test_faq_structure),
        ("Product Page Structure", test_product_page_structure),
        ("Comparison Structure", test_comparison_structure),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} FAILED: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL VALIDATIONS PASSED - System is working correctly!")
        return 0
    else:
        print(f"\n❌ {total - passed} validation(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
