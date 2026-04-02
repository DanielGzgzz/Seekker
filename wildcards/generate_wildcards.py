import os
import json
import logging
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator.ipf import perform_ipf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    TARGET_WILDCARDS = 10000
    OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "israeli_population_10k.json")

    logger.info(f"Starting generation of {TARGET_WILDCARDS} synthetic wildcards...")

    # Use the existing IPF algorithm to ensure statistically accurate marginals
    # while leveraging the expanded probabilistic assignments for rich attributes
    profiles = perform_ipf(TARGET_WILDCARDS)

    # Save the generated wildcards to JSON
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(profiles, f, indent=2)

    logger.info(f"Successfully generated {TARGET_WILDCARDS} wildcards.")
    logger.info(f"Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
