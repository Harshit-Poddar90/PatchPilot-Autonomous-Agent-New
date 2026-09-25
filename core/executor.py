import subprocess
import sys

def execute_code(file_path: str) -> dict:
    """Runs a Python script and captures any tracebacks if it fails."""
    print(f"Running {file_path} in a separate subprocess...\n")

    # Execute the target script with the same interpreter/venv PatchPilot runs in
    result = subprocess.run(
        [sys.executable, file_path],
        capture_output=True, 
        text=True
    )
    
    # Check the return code (0 means success, anything else means a crash)
    if result.returncode != 0:
        print("Script crashed! Intercepting traceback...")
        return {
            "status": "error", 
            "error_traceback": result.stderr
        }
    
    print("Script executed successfully!")
    return {
        "status": "success", 
        "error_traceback": ""
    }

# --- Test the Executor ---
if __name__ == "__main__":
    # Point the executor at our intentionally broken script
    agent_state = execute_code("examples/demo_broken_script.py")
    
    if agent_state["status"] == "error":
        print("\n--- RAW TRACEBACK CAPTURED FOR EMBEDDING ---")
        print(agent_state["error_traceback"])