# Intentionally broken script for demoing PatchPilot. It fails in two stages:
#   BUG 1: ModuleNotFoundError (tabulate isn't installed)  -> expected fix: `pip install tabulate`
#   BUG 2: AttributeError (appears once BUG 1 is fixed)    -> expected fix: rewrite the file without the bad call
import tabulate

print("--- Starting Data Pipeline ---")
print("Initializing connection to remote server...")

def fetch_data():
    """Simulates grabbing data from an API."""
    response = {"status": 200, "data": {"user_id": 101, "score": 85}}
    return response

def process_score(user_data):
    """Simulates a calculation that breaks."""
    print("Processing user score...")

    # BUG 2: tabulate has no function called 'init_pipeline_config'
    tabulate.init_pipeline_config()

    rows = [[user_data["data"]["user_id"], user_data["data"]["score"]]]
    print(tabulate.tabulate(rows, headers=["User ID", "Score"]))

# Execute the pipeline
raw_data = fetch_data()
process_score(raw_data)
