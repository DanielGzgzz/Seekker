from pydantic import BaseModel, Field
from typing import List

class GenerateRequest(BaseModel):
    """
    Request payload schema for the /generate endpoint.
    """
    query: str = Field(..., description="The user's core query or market research question.")
    target_demographic: str = Field(..., description="A string describing the target demographic.")
    num_profiles: int = Field(default=5, ge=1, le=20, description="Number of synthetic profiles to analyze.")

class MarketReportResponse(BaseModel):
    """
    Response payload schema containing the generated market report.
    """
    query: str
    target_demographic: str
    profiles_analyzed: int
    report: str

class WebhookResponse(BaseModel):
    """
    Standard status response for webhooks.
    """
    status: str

class CheckoutResponse(BaseModel):
    """
    Response containing the Stripe Checkout Session URL for the customer.
    """
    checkout_url: str
    session_id: str

class PaymentStatusResponse(BaseModel):
    """
    Response indicating if the payment succeeded and returning the API key if provisioned.
    """
    status: str
    api_key: str | None = None

class DemographicSentiment(BaseModel):
    """
    Detailed sentiment for a specific demographic group.
    """
    group_name: str
    affinity_score: float = Field(..., description="0.0 to 10.0 scale of how likely they are to engage/buy")
    key_objections: List[str]
    selling_points: List[str]
    representative_quote: str

class MultimodalAnalysisResponse(BaseModel):
    """
    Structured response for the frontend dashboard after analyzing a product idea.
    """
    product_description: str
    has_image: bool
    overall_market_fit_score: float = Field(..., description="0.0 to 10.0 scale")
    executive_summary: str
    demographic_breakdown: List[DemographicSentiment]
