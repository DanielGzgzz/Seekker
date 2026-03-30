from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base

class SyntheticProfile(Base):
    __tablename__ = "synthetic_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_data = Column(JSONB, nullable=False)
    # 768-dimensional embedding from textembedding-gecko
    demographic_embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    stripe_session_id = Column(String, unique=True, index=True, nullable=False)
    customer_email = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)
    api_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
