import os
from dotenv import load_dotenv
from google import genai

# Load the secret keys
load_dotenv()

# Initialize the Gemini API Client
genai_key = os.getenv("GEMINI_API_KEY")
if not genai_key:
    raise ValueError("Gemini API key missing! Check your .env file.")

client = genai.Client(api_key=genai_key)

def generate_code_fix(error_traceback: str, file_path: str = "examples/demo_broken_script.py") -> str:
    """
    Reads the broken code, passes it to Gemini with the error,
    and demands a full file rewrite or a terminal command.
    """
    print("🧠 No match in memory. Booting up Gemini 2.5 Flash for reasoning...")

    # 1. Read the broken source code
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            source_code = file.read()
    except FileNotFoundError:
        return "ERROR: Could not find the source file to read."

    # 2. Give the LLM strict instructions to return ONLY pure code or a pure command
    prompt = f"""
    You are an autonomous debugging agent. Analyze the Python traceback and the Source Code.
    
    If the fix requires a terminal command (like pip install), output ONLY the command (e.g., pip install requests).
    If the fix requires a code change, rewrite the ENTIRE script with the fix applied. 
    
    CRITICAL RULES:
    - Output ONLY the raw text to be executed or saved.
    - DO NOT use markdown formatting (no ```python blocks).
    - DO NOT explain your reasoning.
    
    Source Code:
    {source_code}
    
    Traceback:
    {error_traceback}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        fix = response.text.strip()
        # The model sometimes wraps code in ``` fences despite the rules; they would break the script on disk
        if fix.startswith("```") and "\n" in fix:
            fix = fix.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        print("✅ Gemini successfully generated a solution.")
        return fix
        
    except Exception as e:
        print(f"❌ LLM Generation Error: {e}")
        return "ERROR: Could not generate fix."

# --- Quick Test ---
if __name__ == "__main__":
    # Let's test it with a completely new error that the database has never seen
    test_error = "IndexError: list index out of range at line 14"
    
    generate_code_fix(test_error)