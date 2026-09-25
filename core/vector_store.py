import os
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai

# Load the secret keys from your .env file
load_dotenv()

# 1. Initialize the Supabase Database Client
supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_ANON_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials missing! Check your .env file.")

supabase: Client = create_client(supabase_url, supabase_key)

# 2. Initialize the Gemini API Client
genai_key = os.getenv("GEMINI_API_KEY")
if not genai_key:
    raise ValueError("Gemini API key missing! Check your .env file.")

client = genai.Client(api_key=genai_key)

def generate_embedding(text: str) -> list[float]:
    """
    Converts a raw string into a 3072-dimensional semantic vector.
    """
    print("Translating error into semantic vector space...")
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text
    )
    return response.embeddings[0].values

def save_to_memory(error_message: str, embedding: list[float], code_fix: str):
    """
    Pushes the error, its vector, and the verified fix to the Supabase database.
    """
    print("Saving solution to permanent memory...")
    
    # Bundle the data into a dictionary that matches our SQL columns
    data = {
        "error_message": error_message,
        "embedding": embedding,
        "code_fix": code_fix
    }
    
    try:
        # Insert the data into the code_memory table
        response = supabase.table("code_memory").insert(data).execute()
        print("Success! Data written to Supabase.")
        return response
    except Exception as e:
        print(f"Database error: {e}")
        return None


def search_memory(error_text: str, threshold: float = 0.90) -> dict | None:
    """
    Embeds an incoming error and searches Supabase for a verified fix.
    """
    print(f"🔍 Searching memory for a fix to: '{error_text}'...")
    
    try:
        # 1. Convert the incoming error into a 3072-dimension vector
        # (inside the try: an embedding failure, e.g. API quota, is treated as a miss and the LLM takes over)
        query_vector = generate_embedding(error_text)

        # 2. Call our custom Supabase SQL function (RPC)
        response = supabase.rpc(
            "match_code_errors",
            {
                "query_embedding": query_vector,
                "match_threshold": threshold,
                "match_count": 1 # We only want the single best match
            }
        ).execute()
        
        # 3. Check if we found anything
        if response.data:
            match = response.data[0]
            print(f"✅ Match Found! (Confidence: {match['similarity']:.2f})")
            print(f"🛠️ Historical Fix: {match['code_fix']}")
            return match
        else:
            print("❌ No matching fix found in memory.")
            return None
            
    except Exception as e:
        print(f"Database search error: {e}")
        return None

# --- Quick Test (needs real keys in .env) ---
if __name__ == "__main__":
    # 1. The bug we caught
    sample_error = "ModuleNotFoundError: No module named pandas"

    # 2. The verified fix we want the agent to remember
    verified_fix = "pip install pandas"

    try:
        # Step A: Generate the vector
        vector = generate_embedding(sample_error)
        print(f"Generated vector with {len(vector)} dimensions.")

        # Step B: Save it to the database
        save_to_memory(sample_error, vector, verified_fix)

        # Step C: Search with an error worded SLIGHTLY differently than the one we just saved
        search_memory("ImportError: cannot find module 'pandas' for initialization")

    except Exception as e:
        print(f"Something went wrong: {e}")