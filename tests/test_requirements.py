import os

import pytest


def test_no_hardcoded_data():
    # check critical files for hardcoded strings
    root = "skincare_agent_system"
    files_to_check = [
        os.path.join(root, "actors", "workers.py"),
        os.path.join(root, "core", "orchestrator.py"),
    ]

    suspicious_terms = ["Serum X", "Product Y", "competitor_brand", "hardcoded_result"]

    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                for term in suspicious_terms:
                    assert (
                        term not in content
                    ), f"Found suspicious hardcoded term '{term}' in {file_path}"
