import os
import json
import logging
import stripe
import vertexai
from fastapi import FastAPI, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from google.cloud import apikeys_v2
from google.cloud.apikeys_v2 import Key

from core.database import get_db, engine
from core.models import Base
from app.schemas import GenerateRequest, MarketReportResponse, WebhookResponse

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
REGION = os.environ.get("REGION", "us-central1")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_...")
stripe.api_key = os.environ.get("STRIPE_API_KEY", "sk_test_...")

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=REGION)
    generation_model = GenerativeModel("gemini-1.5-pro-preview-0409")
    embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    logger.info("Vertex AI models initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")

# FastAPI app setup
app = FastAPI(
    title="Synthetic Market Data API",
    description="SaaS Backend for generating synthetic demographic profiles and market reports.",
    version="1.0.0"
)

def get_embedding(text_content: str) -> list:
    """
    Generate a vector embedding using Vertex AI TextEmbeddingModel.
    """
    try:
        inputs = [TextEmbeddingInput(text_content, "RETRIEVAL_DOCUMENT")]
        embeddings = embedding_model.get_embeddings(inputs)
        return embeddings[0].values
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return None

def provision_api_key(customer_email: str) -> str:
    """
    Provisions a new API key via Google Cloud API Keys API.
    """
    client = apikeys_v2.ApiKeysClient()

    key = Key()
    key.display_name = f"API Key for {customer_email}"

    request = apikeys_v2.CreateKeyRequest(
        parent=f"projects/{PROJECT_ID}/locations/global",
        key=key,
    )

    logger.info(f"Initiating API key creation for {customer_email}...")
    operation = client.create_key(request=request)
    response = operation.result()

    key_string_request = apikeys_v2.GetKeyStringRequest(name=response.name)
    key_string_response = client.get_key_string(request=key_string_request)

    return key_string_response.key_string

@app.post("/generate", response_model=MarketReportResponse)
async def generate_market_report(req: GenerateRequest, db: Session = Depends(get_db)):
    """
    Accepts user input, performs vector search in Cloud SQL to find relevant profiles,
    and uses Vertex AI to generate a segmented market report.
    """
    logger.info(f"Received generation request. Query: {req.query}, Target: {req.target_demographic}")

    # 1. Get embedding for the target demographic
    query_embedding = get_embedding(req.target_demographic)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for target demographic.")

    # 2. Vector search in Cloud SQL using pgvector
    profiles = []
    try:
        # Using pgvector L2 distance operator (<->)
        sql = text("""
            SELECT profile_data, demographic_embedding <-> :embedding AS distance
            FROM synthetic_profiles
            ORDER BY distance ASC
            LIMIT :limit
        """)

        result = db.execute(sql, {
            "embedding": str(query_embedding),
            "limit": req.num_profiles
        })

        for row in result:
            profiles.append(row[0]) # profile_data

        logger.info(f"Retrieved {len(profiles)} profiles from database.")
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to query database for profiles.")

    if not profiles:
        raise HTTPException(status_code=404, detail="No relevant profiles found in database.")

    # 3. Use Vertex AI to generate market report based on retrieved profiles
    prompt = f"""
    You are a market research analyst. Based on the following user query:
    "{req.query}"

    And focusing on the target demographic:
    "{req.target_demographic}"

    Analyze the following representative synthetic user profiles to generate a segmented market report:
    {json.dumps(profiles, indent=2)}

    Your report should include:
    1. Executive Summary
    2. Demographic Segmentation
    3. Potential Needs & Pain Points based on the profiles
    4. Strategic Recommendations
    """

    try:
        logger.info("Calling Vertex AI for report generation...")
        response = generation_model.generate_content(prompt)
        report = response.text

        return MarketReportResponse(
            query=req.query,
            target_demographic=req.target_demographic,
            profiles_analyzed=len(profiles),
            report=report
        )
    except Exception as e:
        logger.error(f"Vertex AI generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate market report.")

@app.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(request: Request):
    """
    Listens for a Stripe payment webhook and automatically provisions
    a Google API Gateway key for the purchasing user.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.warning(f"Invalid payload received in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"Invalid signature in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            logger.info(f"Payment successful for {customer_email}. Provisioning API Key...")
            try:
                api_key = provision_api_key(customer_email)
                logger.info(f"Successfully provisioned API key for {customer_email}")
                # Note: Integration with an email service (SendGrid, etc) would happen here.
            except Exception as e:
                logger.error(f"Failed to provision API key: {e}")
                # Depending on business logic, you might raise here so Stripe retries
        else:
            logger.warning("No customer email found in checkout session.")

    return WebhookResponse(status="success")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
