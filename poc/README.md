# Proof of Concept: Human Survey Alignment

This directory contains a Proof of Concept (POC) demonstrating how to align synthetic demographic responses with baseline human survey data.

## Goal
To automatically tune the prompts given to our synthetic profiles (generated via Iterative Proportional Fitting and Vertex AI) until the distribution of their answers on specific topics matches real human survey results within an acceptable margin of error.

## Architecture

1.  **`human_data.json`**: Acts as our "ground truth". Contains baseline percentage distributions of human answers across three distinct topics: EV Adoption, Remote Work, and AI Trust.
2.  **`survey_alignment.py`**: The main execution script.
    *   **Generates Profiles**: Uses our `generator.ipf` module to spin up a batch of synthetic demographic profiles.
    *   **Polls the Cohort**: Asks the cohort a survey question via Vertex AI.
    *   **Calculates Divergence**: Uses Mean Absolute Error (MAE) to measure the gap between the synthetic results and the human baseline.
    *   **Iterative Tuning**: If the MAE is above the tolerance (e.g., 8%), it generates a "meta-prompt" instruction (e.g., "Consider that your demographic might be highly inclined to choose 'Very Likely'") and restarts the polling process. This continues until alignment is reached or max iterations are hit.

## How to Run

### Option 1: Mock Mode (Recommended for testing without GCP Credentials)
Mock mode simulates the LLM's responses, gradually responding to the tuning instructions to demonstrate the iterative convergence loop.

```bash
python poc/survey_alignment.py --mock
```

### Option 2: Live Mode (Requires GCP Authentication)
Live mode actually calls Vertex AI (Gemini 1.5 Pro) to generate responses for every profile on every iteration. This is slower and incurs API costs.

Ensure your environment variables (`PROJECT_ID`, `REGION`) are set, and you are authenticated with GCP.

```bash
python poc/survey_alignment.py
```
