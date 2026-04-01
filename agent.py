import os
import sys
import json
import time
import argparse
from typing import List, Dict

# Try importing the IPF generator logic from our project
try:
    from generator.ipf import perform_ipf
except ImportError:
    print("[ERROR] Could not import generator.ipf. Make sure you are running this from the project root.")
    sys.exit(1)

# Argument parsing for Mock Mode
parser = argparse.ArgumentParser(description="Synthetic Market Analysis Agent")
parser.add_argument('--mock', action='store_true', help="Run in mock mode without calling Vertex AI (saves costs/credentials)")
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
        print(f"\n[WARNING] Failed to initialize Vertex AI: {e}")
        print("Falling back to MOCK MODE. No real AI calls will be made.\n")
        MOCK_MODE = True

# --- UI Helpers ---
def print_header(title):
    print("\n" + "="*60)
    print(f" {title.center(58)} ")
    print("="*60)

def print_step(message):
    print(f"\n[*] {message}")

def get_multiline_input(prompt):
    print(f"\n{prompt} (Type 'DONE' on a new line when finished):")
    lines = []
    while True:
        line = input("> ")
        if line.strip().upper() == 'DONE':
            break
        lines.append(line)
    return "\n".join(lines)

# --- Core Logic ---
def analyze_product(product_pitch: str, target_demographic: str, profiles: List[Dict]) -> Dict:
    """
    Passes the pitch and the generated demographic panel to Vertex AI to simulate
    focus group feedback and aggregate statistics.
    """
    if MOCK_MODE:
        time.sleep(2) # Simulate network delay
        return {
            "overall_market_fit_score": 7.5,
            "executive_summary": "[MOCK] The product shows strong potential among secular tech workers but faces skepticism from traditional households regarding price.",
            "demographic_breakdown": [
                {
                    "group_name": "Secular Tech Workers",
                    "affinity_score": 8.5,
                    "key_objections": ["Battery life concerns", "Lack of fast charging stations"],
                    "selling_points": ["Environmental impact", "Cutting-edge tech"],
                    "representative_quote": "[MOCK] 'I love the idea, but I need to know it won't die on my commute to Tel Aviv.'"
                },
                {
                    "group_name": "Traditional Families",
                    "affinity_score": 5.0,
                    "key_objections": ["Too expensive upfront", "Not enough trunk space for kids"],
                    "selling_points": ["Lower long-term maintenance costs"],
                    "representative_quote": "[MOCK] 'It's nice, but I can't justify the price tag right now with three kids.'"
                }
            ]
        }

    # Real Vertex AI Call
    prompt = f"""
    You are an expert product-market fit analyst. I am launching a new product/service.

    Product Pitch:
    "{product_pitch}"

    Target Demographic Idea:
    "{target_demographic}"

    Here is a representative panel of {len(profiles)} synthetic Israeli demographic profiles that fit this target:
    {json.dumps(profiles, indent=2)}

    Please simulate a focus group with this panel. Analyze how well this product fits them,
    what their primary objections would be, and score their affinity.

    You MUST return ONLY a valid JSON object matching this schema exactly:
    {{
      "overall_market_fit_score": 0.0 to 10.0,
      "executive_summary": "1 paragraph summary of the panel's reaction",
      "demographic_breakdown": [
        {{
           "group_name": "e.g. Secular Tech Workers",
           "affinity_score": 0.0 to 10.0,
           "key_objections": ["list", "of", "objections"],
           "selling_points": ["list", "of", "selling", "points"],
           "representative_quote": "A single sentence quote simulating a persona from this group."
        }}
      ]
    }}

    Do not wrap the JSON in markdown blocks (e.g. ```json). Just return the raw JSON string.
    """

    try:
        response = generation_model.generate_content(prompt)
        text_resp = response.text.strip()

        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3].strip()

        return json.loads(text_resp)
    except Exception as e:
        print(f"\n[ERROR] Vertex AI failed to analyze the product: {e}")
        sys.exit(1)

def main():
    print_header("SYNTHETIC MARKET ANALYSIS AGENT")
    print("Welcome! I am your AI Market Research Agent.")
    print("I will help you test your product idea against a simulated population.")
    if MOCK_MODE:
        print("\n[!] Running in MOCK MODE. No real AI calls will be made.")

    time.sleep(1)

    # 1. Conversational Input
    print_step("Let's start with your idea.")
    product_pitch = get_multiline_input("Describe your product, app, or service in detail")

    print_step("Who do you think is your target audience?")
    target_demo = input("> (e.g., 'Young professionals in Tel Aviv', 'Middle-income families'): ")

    while True:
        try:
            panel_size = int(input("\n> How many synthetic profiles should we generate for the focus group? (10-100): "))
            if 10 <= panel_size <= 100:
                break
            print("Please enter a number between 10 and 100.")
        except ValueError:
            print("Please enter a valid integer.")

    # 2. Generate Synthetic Profiles (In-Memory)
    print_step(f"Generating a statistically accurate panel of {panel_size} Israeli profiles using Iterative Proportional Fitting...")
    # We use our existing IPF math to generate the distributions
    profiles = perform_ipf(panel_size)

    # Just to make it feel "real" to the user, we print a sample
    print(f"\n[+] Successfully generated {panel_size} profiles.")
    print("Sample Profile 1:", profiles[0])
    print("Sample Profile 2:", profiles[1])
    time.sleep(2)

    # 3. Simulate Focus Group (Vertex AI)
    print_step("Running the simulation... The Agent is interviewing the synthetic panel...")
    report = analyze_product(product_pitch, target_demo, profiles)

    # 4. Output Statistics
    print_header("FINAL MARKET ANALYSIS REPORT")

    print(f"\nOverall Market Fit Score: {report.get('overall_market_fit_score', 'N/A')} / 10.0")
    print("\nExecutive Summary:")
    print(report.get('executive_summary', 'No summary provided.'))

    print("\n--- Demographic Breakdown ---")
    breakdown = report.get('demographic_breakdown', [])
    for group in breakdown:
        print(f"\nGroup: {group.get('group_name')}")
        print(f"  Affinity Score: {group.get('affinity_score')} / 10.0")
        print(f"  Quote: \"{group.get('representative_quote')}\"")

        print("  Key Objections:")
        for obj in group.get('key_objections', []):
            print(f"    - {obj}")

        print("  Selling Points:")
        for sp in group.get('selling_points', []):
            print(f"    - {sp}")

    print("\n" + "="*60)
    print("Analysis Complete. Thank you for using the Agent!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAgent terminated by user. Goodbye!")
        sys.exit(0)
