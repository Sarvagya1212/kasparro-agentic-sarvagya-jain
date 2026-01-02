import sys
import traceback
from pathlib import Path

# Add root to sys.path
root = Path("f:/kasparro-content-generation")
sys.path.insert(0, str(root))

print(f"Added {root} to sys.path")

try:
    print("Attempting to import skincare_agent_system.actors.agent_implementations...")
    from skincare_agent_system.actors import agent_implementations

    print("Import successful!")
except Exception:
    print("Import failed with exception:")
    traceback.print_exc()
