import os
import json
import logging
import stripe
import vertexai
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from google.cloud import apikeys_v2
from google.cloud.apikeys_v2 import Key

from core.database import get_db, engine
from core.models import Base, PaymentTransaction
from app.schemas import GenerateRequest, MarketReportResponse, WebhookResponse, CheckoutResponse, PaymentStatusResponse, MultimodalAnalysisResponse

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

def get_embedding(text_content: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list:
    """
    Generate a vector embedding using Vertex AI TextEmbeddingModel.
    """
    try:
        inputs = [TextEmbeddingInput(text_content, task_type)]
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
    query_embedding = get_embedding(req.target_demographic, task_type="RETRIEVAL_QUERY")
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for target demographic.")

    # 2. Vector search in Cloud SQL using pgvector
    profiles = []
    try:
        # Using pgvector L2 distance operator (<->)
        sql = text("""
            SELECT profile_data, demographic_embedding <-> CAST(:embedding AS vector) AS distance
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

@app.post("/analyze_product", response_model=MultimodalAnalysisResponse)
async def analyze_product(
    product_description: str = Form(..., description="A detailed textual description of the product or service."),
    target_demographic: str = Form(..., description="The demographic target (used to fetch the closest synthetic profiles)."),
    image: UploadFile | None = File(None, description="An optional image of the product."),
    num_profiles: int = Form(10, description="Number of synthetic profiles to analyze."),
    db: Session = Depends(get_db)
):
    """
    Multimodal endpoint designed for a high-end frontend dashboard.
    Accepts text and images, queries the database for matching profiles,
    and returns a structured JSON evaluation scoring the product fit.
    """
    # 1. Fetch relevant profiles via pgvector
    query_embedding = get_embedding(target_demographic, task_type="RETRIEVAL_QUERY")
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to embed target demographic.")

    profiles = []
    try:
        sql = text("""
            SELECT profile_data, demographic_embedding <-> CAST(:embedding AS vector) AS distance
            FROM synthetic_profiles
            ORDER BY distance ASC
            LIMIT :limit
        """)
        result = db.execute(sql, {
            "embedding": str(query_embedding),
            "limit": num_profiles
        })
        for row in result:
            profiles.append(row[0])
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to query profiles.")

    if not profiles:
        raise HTTPException(status_code=404, detail="No relevant profiles found.")

    # 2. Build the multimodal prompt
    prompt_text = f"""
    You are an expert product-market fit analyst. I am launching a new product/service.

    Product Description:
    "{product_description}"

    Target Demographic Idea:
    "{target_demographic}"

    Here is a representative panel of {len(profiles)} synthetic Israeli demographic profiles that fit this target:
    {json.dumps(profiles, indent=2)}

    Please analyze how well this product fits this panel. If an image is attached, take its visual appeal into account.

    You MUST return ONLY a valid JSON object matching this schema exactly:
    {{
      "product_description": "short summary",
      "has_image": true/false,
      "overall_market_fit_score": 0.0 to 10.0,
      "executive_summary": "1 paragraph summary",
      "demographic_breakdown": [
        {{
           "group_name": "e.g. Secular Tech Workers",
           "affinity_score": 0.0 to 10.0,
           "key_objections": ["list", "of", "objections"],
           "selling_points": ["list", "of", "selling", "points"],
           "representative_quote": "A single sentence quote from this persona."
        }}
      ]
    }}

    Do not wrap the JSON in markdown blocks (e.g. ```json). Just return the raw JSON string.
    """

    contents = [prompt_text]
    has_image = False

    # 3. Handle image attachment for Gemini
    if image and image.content_type.startswith("image/"):
        has_image = True
        try:
            image_bytes = await image.read()
            image_part = Part.from_data(
                mime_type=image.content_type,
                data=image_bytes
            )
            contents.append(image_part)
        except Exception as e:
            logger.error(f"Failed to process image upload: {e}")
            raise HTTPException(status_code=400, detail="Invalid image file.")

    # 4. Generate the structured report
    try:
        logger.info("Calling Gemini for multimodal product analysis...")
        response = generation_model.generate_content(contents)
        text_resp = response.text.strip()

        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3].strip()

        report_data = json.loads(text_resp)

        # Enforce image flag based on actual upload status
        report_data["has_image"] = has_image

        return report_data
    except Exception as e:
        logger.error(f"Vertex AI parsing error: {e}")
        logger.error(f"Raw response was: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to generate structured market report.")

@app.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(db: Session = Depends(get_db)):
    """
    Creates a Stripe Checkout Session for purchasing an API Key.
    Returns the URL where the user should securely enter their payment details.
    """
    try:
        # In a real app, define the price_id from your Stripe Dashboard
        # For POC, we create a generic 1-time session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Synthetic Market API Key',
                        'description': 'Grants access to generate synthetic demographic market reports.'
                    },
                    'unit_amount': 5000, # $50.00
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://example.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://example.com/cancel',
        )

        # Record the transaction status as pending in our DB
        transaction = PaymentTransaction(
            stripe_session_id=session.id,
            status="pending"
        )
        db.add(transaction)
        db.commit()

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id
        )
    except Exception as e:
        logger.error(f"Error creating Stripe checkout session: {e}")
        raise HTTPException(status_code=500, detail="Could not create checkout session")


@app.get("/status/{session_id}", response_model=PaymentStatusResponse)
async def check_payment_status(session_id: str, db: Session = Depends(get_db)):
    """
    Polling endpoint for clients to check if their payment succeeded
    and retrieve their provisioned API key.
    """
    transaction = db.query(PaymentTransaction).filter(PaymentTransaction.stripe_session_id == session_id).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    return PaymentStatusResponse(
        status=transaction.status,
        api_key=transaction.api_key
    )


@app.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
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
        session_id = session.get('id')
        customer_email = session.get('customer_details', {}).get('email')

        # Look up transaction
        transaction = db.query(PaymentTransaction).filter(PaymentTransaction.stripe_session_id == session_id).first()

        if customer_email:
            logger.info(f"Payment successful for {customer_email}. Provisioning API Key...")
            try:
                api_key = provision_api_key(customer_email)
                logger.info(f"Successfully provisioned API key for {customer_email}")

                if transaction:
                    transaction.status = "completed"
                    transaction.customer_email = customer_email
                    transaction.api_key = api_key
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to provision API key: {e}")
                if transaction:
                    transaction.status = "failed"
                    db.commit()
        else:
            logger.warning("No customer email found in checkout session.")

    return WebhookResponse(status="success")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
