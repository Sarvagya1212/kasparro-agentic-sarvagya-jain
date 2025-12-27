"""
Main entry point for the Skincare Content Generation System.
Demonstrates all system capabilities with examples.
"""
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent))

from generate_content import main as run_pipeline


def main():
    """
    Main entry point - runs the content generation pipeline.
    """
    print("\n" + "="*70)
    print("SKINCARE CONTENT GENERATION SYSTEM")
    print("="*70)
    print("\nRunning content generation pipeline...")
    print("This will generate 3 JSON files using logic blocks and templates.\n")
    
    # Run the pipeline
    run_pipeline()


if __name__ == "__main__":
    main()
