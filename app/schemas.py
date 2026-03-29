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
