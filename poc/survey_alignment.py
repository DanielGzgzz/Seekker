import os
import sys
import json
import logging
import argparse
import random
import numpy as np
from typing import Dict, List

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add parent dir to path so we can import generator.ipf
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator.ipf import perform_ipf

# Determine if we are running in MOCK mode (no Vertex AI credentials available)
parser = argparse.ArgumentParser(description="Proof of Concept: Align synthetic surveys with human baselines.")
parser.add_argument('--mock', action='store_true', help="Run without calling Vertex AI (simulate LLM responses)")
args = parser.parse_args()

MOCK_MODE = args.mock

if not MOCK_MODE:
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
        REGION = os.environ.get("REGION", "us-central1")
        vertexai.init(project=PROJECT_ID, location=REGION)
        generation_model = GenerativeModel("gemini-1.5-pro-preview-0409")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}. Falling back to MOCK_MODE.")
        MOCK_MODE = True


def calculate_divergence(human_dist: Dict[str, float], synth_dist: Dict[str, float]) -> float:
    """Calculate Mean Absolute Error (MAE) between two probability distributions."""
    error = 0.0
    for key, h_val in human_dist.items():
        s_val = synth_dist.get(key, 0.0)
        error += abs(h_val - s_val)
    return error / len(human_dist)


def simulate_llm_response(prompt: str, options: List[str], target_dist: Dict[str, float] = None, iteration: int = 0) -> str:
    """
    Mock function to simulate an LLM choosing an option.
    If target_dist is provided, it simulates the LLM gradually 'learning' to align with the prompt instructions over iterations.
    """
    if target_dist and iteration > 0:
        # As iterations increase, the simulated LLM aligns closer to the target distribution
        # by blending random noise with the target distribution.
        noise = np.random.uniform(0, 1, len(options))
        noise = noise / noise.sum()
        target_probs = np.array([target_dist.get(opt, 0.0) for opt in options])

        # Alpha controls how much 'attention' the mock LLM pays to the tuned prompt.
        alpha = min(0.95, iteration * 0.2)
        probs = (alpha * target_probs) + ((1 - alpha) * noise)
        probs = probs / probs.sum()

        return np.random.choice(options, p=probs)
    else:
        # Baseline iteration or no target: completely random, representing un-tuned LLM behavior
        return random.choice(options)


def poll_profile(profile_constraints: Dict, question: str, options: List[str], tuned_instructions: str, target_dist: Dict, iteration: int) -> str:
    """Ask a single synthetic profile to answer a survey question."""

    prompt = f"""
    You are a person living in Israel with the following demographic traits:
    {json.dumps(profile_constraints, indent=2)}

    {tuned_instructions}

    Based on your profile and worldview, answer the following survey question:
    "{question}"

    You must choose EXACTLY ONE of the following options, and output NOTHING ELSE:
    {json.dumps(options)}
    """

    if MOCK_MODE:
        return simulate_llm_response(prompt, options, target_dist, iteration)
    else:
        try:
            response = generation_model.generate_content(prompt)
            text_resp = response.text.strip()
            # Failsafe: ensure the response is one of the valid options
            for opt in options:
                if opt.lower() in text_resp.lower():
                    return opt
            return random.choice(options) # Fallback if LLM halluciantes
        except Exception as e:
            logger.warning(f"Vertex API error during polling: {e}")
            return random.choice(options)


def generate_tuning_instructions(human_dist: Dict, current_synth_dist: Dict) -> str:
    """
    Analyzes the gap between human and synthetic data and writes an instruction to guide the LLM.
    In a real-world scenario, another LLM call would generate this instruction.
    For this POC, we use a heuristic rules engine to generate the "meta-prompt" tuning.
    """
    instructions = []
    for option, h_val in human_dist.items():
        s_val = current_synth_dist.get(option, 0.0)
        diff = h_val - s_val

        if diff > 0.15: # Synthetic is under-representing this option significantly
            instructions.append(f"Consider that your demographic might be highly inclined to choose '{option}'.")
        elif diff < -0.15: # Synthetic is over-representing this option significantly
            instructions.append(f"Avoid over-selecting '{option}'; think critically if it truly applies to your demographic.")

    if not instructions:
        return "Answer naturally based on your profile."

    meta_prompt = "IMPORTANT METADATA/SYSTEM INSTRUCTION FOR THIS ITERATION:\n" + "\n".join(instructions)
    return meta_prompt


def align_survey_topic(topic: Dict, num_profiles: int = 50, max_iterations: int = 5, tolerance: float = 0.05):
    """
    Runs the iterative alignment loop for a single survey topic.
    """
    logger.info(f"=== Starting Alignment POC for Topic: {topic['id']} ===")
    logger.info(f"Question: {topic['question']}")
    logger.info(f"Target Human Baseline: {json.dumps(topic['human_baseline'], indent=2)}")

    # 1. Generate base demographics once using IPF
    profiles = perform_ipf(num_profiles)

    tuned_instructions = "Answer naturally based on your profile."

    for iteration in range(max_iterations):
        logger.info(f"--- Iteration {iteration} ---")
        logger.info(f"Active Prompt Tuning: {tuned_instructions.strip()}")

        # 2. Poll the profiles
        results = {opt: 0 for opt in topic['options']}

        for profile in profiles:
            choice = poll_profile(profile, topic['question'], topic['options'], tuned_instructions, topic['human_baseline'], iteration)
            if choice in results:
                results[choice] += 1

        # 3. Calculate Distribution
        synth_dist = {opt: count / num_profiles for opt, count in results.items()}
        logger.info(f"Synthetic Distribution: {json.dumps(synth_dist, indent=2)}")

        # 4. Calculate Divergence (MAE)
        mae = calculate_divergence(topic['human_baseline'], synth_dist)
        logger.info(f"Mean Absolute Error (Divergence): {mae:.4f}")

        # 5. Check Termination Condition
        if mae <= tolerance:
            logger.info(f"SUCCESS: Alignment reached within tolerance ({tolerance}) after {iteration} iterations!")
            return True, synth_dist, tuned_instructions

        # 6. Generate new tuning instructions based on the gap
        tuned_instructions = generate_tuning_instructions(topic['human_baseline'], synth_dist)

    logger.warning(f"FAILURE: Could not align within {max_iterations} iterations. Final MAE: {mae:.4f}")
    return False, synth_dist, tuned_instructions


def main():
    if MOCK_MODE:
        logger.info("Running in MOCK mode (No external API calls will be made).")

    # Load human baseline data
    human_data_path = os.path.join(os.path.dirname(__file__), "human_data.json")
    with open(human_data_path, 'r') as f:
        data = json.load(f)

    topics = data.get("topics", [])

    success_count = 0
    for topic in topics:
        success, final_dist, final_prompt = align_survey_topic(topic, num_profiles=100, max_iterations=6, tolerance=0.08)
        if success:
            success_count += 1
        print("\n")

    logger.info(f"POC Complete. Successfully aligned {success_count}/{len(topics)} topics to human baselines.")


if __name__ == "__main__":
    main()
