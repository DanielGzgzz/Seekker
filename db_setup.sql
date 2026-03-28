-- Task 2: The Database (Cloud SQL) Setup Script

-- Enable the pgvector extension to allow storing and searching vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a table to store the JSON profiles from Task 1, including vector embeddings
CREATE TABLE IF NOT EXISTS synthetic_profiles (
    id SERIAL PRIMARY KEY,
    profile_data JSONB NOT NULL,
    -- Assume we use a 768-dimensional embedding model like textembedding-gecko
    demographic_embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create an HNSW index for faster vector similarity search
CREATE INDEX ON synthetic_profiles USING hnsw (demographic_embedding vector_l2_ops);
