-- Step 2 of 2: run this after schema.sql
-- Create a custom function to calculate Cosine Similarity on our 3072-dimension vectors
CREATE OR REPLACE FUNCTION match_code_errors (
  query_embedding VECTOR(3072),
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (
  id INT,
  error_message TEXT,
  code_fix TEXT,
  similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    code_memory.id,
    code_memory.error_message,
    code_memory.code_fix,
    -- Calculate similarity (1 minus distance)
    1 - (code_memory.embedding <=> query_embedding) AS similarity
  FROM code_memory
  -- Only return matches above our required confidence threshold
  WHERE 1 - (code_memory.embedding <=> query_embedding) > match_threshold
  -- Order by closest match first
  ORDER BY code_memory.embedding <=> query_embedding
  LIMIT match_count;
$$;