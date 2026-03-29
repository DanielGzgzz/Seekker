from sqlalchemy import Column, Integer, DateTime
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
