import os
import json
import numpy as np
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from sqlalchemy import create_engine, text

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
REGION = os.environ.get("REGION", "us-central1")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "password")
DB_NAME = os.environ.get("DB_NAME", "synthetic_db")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
NUM_PROFILES = int(os.environ.get("NUM_PROFILES", "10"))

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)
generation_model = GenerativeModel("gemini-1.5-pro-preview-0409")
embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

def perform_ipf(num_samples):
    """
    Performs Iterative Proportional Fitting to combine Israeli demographic statistics.
    """
    # Dimensions: Ethnicity (2), Religiosity (4), Origin (4), Income (3)
    # Marginals based on approximate Israeli demographics
    # Ethnicity: Jewish (0.79), Arab (0.21)
    m1 = np.array([0.79, 0.21])
    # Religiosity: Secular (0.45), Traditional (0.25), Religious (0.15), Ultra-Orthodox (0.15)
    m2 = np.array([0.45, 0.25, 0.15, 0.15])
    # Origin (mostly relevant for Jewish pop): Ashkenazi (0.3), Mizrahi (0.4), Sephardic (0.1), Mixed (0.2)
    m3 = np.array([0.3, 0.4, 0.1, 0.2])
    # Income: Low (0.3), Medium (0.5), High (0.2)
    m4 = np.array([0.3, 0.5, 0.2])

    # Initial seed matrix (all ones)
    seed = np.ones((2, 4, 4, 3))

    # IPF Loop
    for _ in range(20):
        # Update dimension 0
        current_m1 = seed.sum(axis=(1, 2, 3))
        seed = seed * (m1 / current_m1)[:, np.newaxis, np.newaxis, np.newaxis]

        # Update dimension 1
        current_m2 = seed.sum(axis=(0, 2, 3))
        seed = seed * (m2 / current_m2)[np.newaxis, :, np.newaxis, np.newaxis]

        # Update dimension 2
        current_m3 = seed.sum(axis=(0, 1, 3))
        seed = seed * (m3 / current_m3)[np.newaxis, np.newaxis, :, np.newaxis]

        # Update dimension 3
        current_m4 = seed.sum(axis=(0, 1, 2))
        seed = seed * (m4 / current_m4)[np.newaxis, np.newaxis, np.newaxis, :]

    # Normalize to probabilities
    prob_matrix = seed / seed.sum()

    # Generate samples based on the joint distribution
    flat_probs = prob_matrix.flatten()
    indices = np.random.choice(len(flat_probs), size=num_samples, p=flat_probs)

    ethnicity_labels = ['Jewish', 'Arab']
    religiosity_labels = ['Secular', 'Traditional', 'Religious', 'Ultra-Orthodox']
    origin_labels = ['Ashkenazi', 'Mizrahi', 'Sephardic', 'Mixed/Other']
    income_labels = ['Low', 'Medium', 'High']

    profiles = []
    for idx in indices:
        i1, i2, i3, i4 = np.unravel_index(idx, prob_matrix.shape)
        # Origin is generally tracked for the Jewish population in these categories
        origin_val = origin_labels[i3] if ethnicity_labels[i1] == 'Jewish' else 'N/A'
        profiles.append({
            "Ethnicity": ethnicity_labels[i1],
            "Religiosity": religiosity_labels[i2],
            "Origin": origin_val,
            "Income": income_labels[i4]
        })

    return profiles

def generate_profile(constraints):
    """
    Pass constraints to Vertex AI Gemini API to generate fully fleshed-out JSON character profiles.
    """
    prompt = f"""
    Generate a fully fleshed-out JSON character profile based on the following demographic constraints:
    {json.dumps(constraints)}

    The character must represent someone from Israel fitting these constraints.
    The JSON should contain ONLY the following fields:
    - first_name
    - last_name
    - age
    - occupation
    - biography (a short paragraph)
    - hobbies (list of strings)

    Respond ONLY with valid JSON, with no markdown formatting.
    """

    try:
        response = generation_model.generate_content(prompt)
        text_resp = response.text.strip()

        # Clean up markdown if present
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3].strip()

        profile_data = json.loads(text_resp)
        # Merge constraints into the final profile
        profile_data.update(constraints)
        return profile_data
    except Exception as e:
        print(f"Error generating or parsing profile: {e}")
        return None

def get_embedding(text_content):
    """
    Generate an embedding vector for the demographic traits and profile content.
    """
    try:
        inputs = [TextEmbeddingInput(text_content, "RETRIEVAL_DOCUMENT")]
        embeddings = embedding_model.get_embeddings(inputs)
        return embeddings[0].values
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def main():
    print(f"Starting generator job. Target: {NUM_PROFILES} profiles.")

    # Database connection setup
    if DB_HOST.startswith("/"):
        # Unix socket connection
        db_url = f"postgresql://{DB_USER}:{DB_PASS}@/{DB_NAME}?host={DB_HOST}"
    else:
        # TCP connection
        db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    engine = create_engine(db_url)

    # Generate constraints using IPF
    constraints_list = perform_ipf(NUM_PROFILES)

    for i, constraints in enumerate(constraints_list):
        print(f"Generating profile {i+1}/{NUM_PROFILES} with constraints: {constraints}")

        # Generate profile using Gemini
        profile = generate_profile(constraints)
        if not profile:
            print("Skipping due to generation error.")
            continue

        # Create text representation for embedding (focusing on demographic traits and bio)
        demographic_text = (
            f"Ethnicity: {profile.get('Ethnicity')}, "
            f"Religiosity: {profile.get('Religiosity')}, "
            f"Origin: {profile.get('Origin')}, "
            f"Income: {profile.get('Income')}, "
            f"Occupation: {profile.get('occupation')}, "
            f"Biography: {profile.get('biography')}"
        )

        # Get embedding vector
        embedding = get_embedding(demographic_text)
        if not embedding:
            print("Skipping due to embedding error.")
            continue

        # Save to database
        try:
            with engine.connect() as conn:
                query = text("""
                    INSERT INTO synthetic_profiles (profile_data, demographic_embedding)
                    VALUES (:profile_data, :embedding)
                """)
                # Convert embedding list to string format recognized by pgvector: '[1.0, 2.0, ...]'
                conn.execute(query, {
                    "profile_data": json.dumps(profile),
                    "embedding": str(embedding)
                })
                conn.commit()
            print(f"Successfully inserted profile for {profile.get('first_name')} {profile.get('last_name')}")
        except Exception as e:
            print(f"Database insertion error: {e}")

if __name__ == "__main__":
    main()
