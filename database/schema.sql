-- Step 1 of 2: run this in the Supabase SQL Editor, then run init.sql

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop any broken iterations
DROP TABLE IF EXISTS code_memory;

-- Recreate the table to natively store the 3072-dimension vectors
CREATE TABLE code_memory (
    id SERIAL PRIMARY KEY,
    error_message TEXT NOT NULL,
    embedding VECTOR(3072),
    code_fix TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- The app reads/writes with the anon key, so Row Level Security stays off (fine for a personal project)
ALTER TABLE code_memory DISABLE ROW LEVEL SECURITY;

-- Note: We are deliberately NOT creating an ivfflat/hnsw index (pgvector caps those at 2000 dimensions).
-- Supabase will execute exact nearest neighbour searches instead, which is fast enough for a few thousand rows.
