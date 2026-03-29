import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "password")
DB_NAME = os.environ.get("DB_NAME", "synthetic_db")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")

if DB_HOST.startswith("/"):
    # Unix socket connection
    db_url = f"postgresql://{DB_USER}:{DB_PASS}@/{DB_NAME}?host={DB_HOST}"
    logger.info("Configuring DB connection using Unix sockets.")
else:
    # TCP connection
    db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    logger.info("Configuring DB connection using TCP.")

# Create engine
engine = create_engine(
    db_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()

def get_db():
    """Dependency to get a database session for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
