import os
import json
import logging
import vertexai
from typing import Dict, Optional, List
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from core.database import SessionLocal, engine
from core.models import Base, SyntheticProfile
from generator.ipf import perform_ipf

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
REGION = os.environ.get("REGION", "us-central1")
NUM_PROFILES = int(os.environ.get("NUM_PROFILES", "10"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))

try:
    vertexai.init(project=PROJECT_ID, location=REGION)
    generation_model = GenerativeModel("gemini-1.5-pro-preview-0409")
    embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    raise

def generate_profile(constraints: Dict[str, str]) -> Optional[Dict]:
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
        logger.error(f"Error generating or parsing profile: {e}")
        return None

def get_embedding(text_content: str) -> Optional[List[float]]:
    """
    Generate an embedding vector for the demographic traits and profile content.
    """
    try:
        inputs = [TextEmbeddingInput(text_content, "RETRIEVAL_DOCUMENT")]
        embeddings = embedding_model.get_embeddings(inputs)
        return embeddings[0].values
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return None

def process_batch(db_session, batch_constraints: List[Dict]):
    profiles_to_insert = []

    for constraints in batch_constraints:
        logger.info(f"Generating profile with constraints: {constraints}")

        profile = generate_profile(constraints)
        if not profile:
            logger.warning("Skipping due to generation error.")
            continue

        demographic_text = (
            f"Ethnicity: {profile.get('Ethnicity')}, "
            f"Religiosity: {profile.get('Religiosity')}, "
            f"Origin: {profile.get('Origin')}, "
            f"Income: {profile.get('Income')}, "
            f"Occupation: {profile.get('occupation')}, "
            f"Biography: {profile.get('biography')}"
        )

        embedding = get_embedding(demographic_text)
        if not embedding:
            logger.warning("Skipping due to embedding error.")
            continue

        profiles_to_insert.append(
            SyntheticProfile(
                profile_data=profile,
                demographic_embedding=embedding
            )
        )

    if profiles_to_insert:
        try:
            db_session.add_all(profiles_to_insert)
            db_session.commit()
            logger.info(f"Successfully batch inserted {len(profiles_to_insert)} profiles.")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Database insertion error: {e}")

def main():
    logger.info(f"Starting generator job. Target: {NUM_PROFILES} profiles.")

    # Generate constraints using IPF
    constraints_list = perform_ipf(NUM_PROFILES)

    db_session = SessionLocal()
    try:
        # Process in batches
        for i in range(0, len(constraints_list), BATCH_SIZE):
            batch = constraints_list[i:i + BATCH_SIZE]
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}...")
            process_batch(db_session, batch)

    finally:
        db_session.close()

    logger.info("Generator job completed.")

if __name__ == "__main__":
    main()
