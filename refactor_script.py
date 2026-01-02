import os
import re
import shutil
from pathlib import Path

# Configuration: Mapping files to their new destinations
MOVES = {
    "core": [
        "orchestrator.py",
        "proposals.py",
        "state_manager.py",
        "models.py",
        "workflow_graph.py",
    ],
    "actors": [
        "agents.py",
        "agent_implementations.py",
        "delegator.py",
        "verifier.py",
        "workers.py",
    ],
    "security": [
        "guardrails.py",
        "agent_identity.py",
        "credential_shim.py",
        "action_validator.py",
        "hitl.py",
        "emergency_controls.py",
        "token_exchange.py",
    ],
    "cognition": ["reasoning.py", "reflection.py", "memory.py"],
    "infrastructure": [
        "llm_client.py",
        "tracer.py",
        "agent_monitor.py",
        "failure_detector.py",
        "aql.py",
    ],
}

ROOT = Path("f:/kasparro-content-generation")
SYSTEM_DIR = ROOT / "skincare_agent_system"


def setup_directories():
    print(" Creating directories...")
    for subdir in MOVES.keys():
        target_dir = SYSTEM_DIR / subdir
        target_dir.mkdir(exist_ok=True)
        # Create __init__.py for each subdir
        (target_dir / "__init__.py").touch()


def move_files():
    print(" Moving files...")
    for subdir, files in MOVES.items():
        for filename in files:
            src = SYSTEM_DIR / filename
            dst = SYSTEM_DIR / subdir / filename
            if src.exists():
                print(f"  Moving {filename} -> {subdir}/")
                shutil.move(str(src), str(dst))
            else:
                print(f"  WARNING: {filename} not found in source.")


def update_imports():
    print(" Updating imports...")

    # Invert map for easy lookup: filename -> subdir
    file_map = {}
    for subdir, files in MOVES.items():
        for f in files:
            module_name = f.replace(".py", "")
            file_map[module_name] = subdir

    # Walk through all python files
    for path in ROOT.rglob("*.py"):
        if "venv" in str(path) or ".git" in str(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Regex to find imports
        # 1. from skincare_agent_system.X import ... -> from skincare_agent_system.SUBDIR.X import ...
        # 2. from .X import ... (inside skincare_agent_system) -> needing fixes

        # Strategy: Replace exact module references
        for module, subdir in file_map.items():
            # Pattern 1: Absolute imports
            # from skincare_agent_system.core.models import
            pattern_abs = f"from skincare_agent_system.{module}"
            replacement_abs = f"from skincare_agent_system.{subdir}.{module}"
            content = content.replace(pattern_abs, replacement_abs)

            # Pattern 2: Relative imports from root of skincare_agent_system
            # This is tricky because it depends on WHERE the file is.
            # But we moved files. So if we are processing a file that WAS in root and is now in SUBDIR...
            # It's safer to use absolute imports everywhere for clarity in this refactor.

            pattern_rel = f"from .{module} import"
            replacement_rel = f"from skincare_agent_system.{subdir}.{module} import"
            content = content.replace(pattern_rel, replacement_rel)

            # Also handle: import skincare_agent_system.core.models as ...
            pattern_imp = f"import skincare_agent_system.{module}"
            replacement_imp = f"import skincare_agent_system.{subdir}.{module}"
            content = content.replace(pattern_imp, replacement_imp)

        # Fix intra-module references (e.g. models -> core.models)
        # Scan for "from . import models" or similar usages?
        # The above replacements cover "from skincare_agent_system.core.models import"

        # Handle cases where multiple modules are imported: from . import agents, models
        # This is hard with simple replace. Assuming most imports are standard.

        if content != original_content:
            print(f"  Patching {path.name}")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)


if __name__ == "__main__":
    setup_directories()
    move_files()
    update_imports()
    print("Refactoring complete.")
