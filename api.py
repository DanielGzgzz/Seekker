import os
import json
import stripe
import vertexai
from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from google.cloud import apikeys_v2
from google.cloud.apikeys_v2 import Key

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
REGION = os.environ.get("REGION", "us-central1")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "password")
DB_NAME = os.environ.get("DB_NAME", "synthetic_db")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_...")

stripe.api_key = os.environ.get("STRIPE_API_KEY", "sk_test_...")

# Database setup
if DB_HOST.startswith("/"):
    # Unix socket connection
    db_url = f"postgresql://{DB_USER}:{DB_PASS}@/{DB_NAME}?host={DB_HOST}"
else:
    # TCP connection
    db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
engine = create_engine(db_url)

# Vertex AI setup
vertexai.init(project=PROJECT_ID, location=REGION)
generation_model = GenerativeModel("gemini-1.5-pro-preview-0409")
embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

# FastAPI app setup
app = FastAPI(title="Synthetic Market Data API")

class GenerateRequest(BaseModel):
    query: str
    target_demographic: str
    num_profiles: int = 5

def get_embedding(text_content):
    try:
        inputs = [TextEmbeddingInput(text_content, "RETRIEVAL_DOCUMENT")]
        embeddings = embedding_model.get_embeddings(inputs)
        return embeddings[0].values
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def provision_api_key(customer_email):
    """
    Provisions a new API key via Google Cloud API Keys API.
    """
    client = apikeys_v2.ApiKeysClient()

    key = Key()
    key.display_name = f"API Key for {customer_email}"

    # Initialize request argument(s)
    request = apikeys_v2.CreateKeyRequest(
        parent=f"projects/{PROJECT_ID}/locations/global",
        key=key,
    )

    # Make the request
    operation = client.create_key(request=request)
    print("Waiting for API key creation operation to complete...")
    response = operation.result()

    # Note: To get the actual key string, another API call is needed,
    # but for simplicity, we return the generated name here.
    # In a real app, you would retrieve the key string and email it to the user.
    key_string_request = apikeys_v2.GetKeyStringRequest(name=response.name)
    key_string_response = client.get_key_string(request=key_string_request)

    return key_string_response.key_string

# Task 3: The API & API Gateway Endpoint
@app.post("/generate")
async def generate_market_report(req: GenerateRequest):
    """
    Accepts user input, performs vector search in Cloud SQL to find relevant profiles,
    and uses Vertex AI to generate a segmented market report.
    Note: Security is configured at the API Gateway level, so this internal endpoint
    assumes requests coming through the gateway are authenticated.
    """
    # 1. Get embedding for the target demographic
    query_embedding = get_embedding(req.target_demographic)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for target demographic.")

    # 2. Vector search in Cloud SQL using pgvector
    profiles = []
    try:
        with engine.connect() as conn:
            # Using the <-> operator for L2 distance, ordering by nearest
            # Assuming the demographic_embedding column has an hnsw index
            sql = text("""
                SELECT profile_data, demographic_embedding <-> :embedding AS distance
                FROM synthetic_profiles
                ORDER BY distance ASC
                LIMIT :limit
            """)
            result = conn.execute(sql, {
                "embedding": str(query_embedding),
                "limit": req.num_profiles
            })

            for row in result:
                profiles.append(row[0]) # profile_data
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to query database for profiles.")

    if not profiles:
        raise HTTPException(status_code=404, detail="No relevant profiles found.")

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
        response = generation_model.generate_content(prompt)
        report = response.text
        return {
            "query": req.query,
            "target_demographic": req.target_demographic,
            "profiles_analyzed": len(profiles),
            "report": report
        }
    except Exception as e:
        print(f"Vertex AI generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate market report.")

# Task 4: Stripe Integration Webhook
@app.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Listens for a Stripe payment and automatically provisions/activates a
    Google API Gateway key for the purchasing user.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Retrieve the customer email
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            print(f"Payment successful for {customer_email}. Provisioning API Key...")
            try:
                # Provision API Key
                api_key = provision_api_key(customer_email)
                print(f"Successfully provisioned API key for {customer_email}")

                # In a real-world scenario, you would securely send this key to the user
                # via email (e.g., using SendGrid, Mailgun, etc.)
                # send_email(customer_email, api_key)

            except Exception as e:
                print(f"Failed to provision API key: {e}")
                # Consider raising or handling this so Stripe can retry if necessary,
                # but typically you want to acknowledge the webhook and handle fulfillment async.
        else:
            print("No customer email found in session.")

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
