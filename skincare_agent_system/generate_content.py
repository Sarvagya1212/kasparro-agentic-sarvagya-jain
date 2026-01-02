#!/usr/bin/env python3
"""
Generate Content: Entry point for content generation workflow.
This is an alias for main.py to support legacy/CI scripts.
"""

import os
import sys

# Add project root to sys.path to resolve package imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skincare_agent_system.main import main  # noqa: E402

if __name__ == "__main__":
    main()
