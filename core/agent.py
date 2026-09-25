import subprocess
import sys
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # Allows the graph to pause for the web UI
import mlflow

# Import the standalone tools
from core.executor import execute_code
from core.vector_store import search_memory, save_to_memory, generate_embedding
from core.llm_engine import generate_code_fix

# --- MLflow Configuration ---
mlflow.set_experiment("PatchPilot-Agent-Tracing")
mlflow.langchain.autolog() # Traces the LangGraph nodes
mlflow.gemini.autolog()    # Traces the Gemini calls (prompts, responses, token usage)

class AgentState(TypedDict):
    file_path: str
    error_traceback: str
    proposed_fix: str
    is_approved: bool
    source: str

def execute_node(state: AgentState):
    """Node 1: Runs the code and catches errors."""
    print("\n--- NODE: Execute Code ---")
    result = execute_code(state["file_path"])

    # Coming back from Heal: if the original error is gone, the LLM fix is verified -> memorize it.
    if state.get("source") == "LLM" and result["error_traceback"] != state["error_traceback"]:
        try:
            vector = generate_embedding(state["error_traceback"])
            save_to_memory(state["error_traceback"], vector, state["proposed_fix"])
        except Exception as e:
            print(f"Could not memorize the fix (the healed file is kept): {e}")

    return {"error_traceback": result["error_traceback"]}

def retrieve_or_generate_node(state: AgentState):
    """Node 2: Tries RAG first, falls back to the LLM."""
    print("\n--- NODE: Retrieve / Generate ---")
    error = state["error_traceback"]
    file_path = state["file_path"]

    match = search_memory(error)
    if match:
        return {"proposed_fix": match["code_fix"], "source": "RAG"}

    fix = generate_code_fix(error, file_path)
    return {"proposed_fix": fix, "source": "LLM"}

def human_approval_node(state: AgentState):
    """
    Node 3: The graph freezes right before this node (interrupt_before).
    The Streamlit UI injects 'is_approved: True' into the state and resumes it.
    """
    print("\n--- ⚠️ UI BREAKPOINT PASSED ---")
    return state

def heal_node(state: AgentState):
    """Node 4: Applies the approved fix (a pip command or a full-file rewrite)."""
    print("\n--- NODE: Heal ---")

    if state["proposed_fix"].startswith("ERROR:"):
        return state

    fix = state["proposed_fix"]
    target_file = state["file_path"]

    if fix.startswith("pip install"):
        try:
            # Install into the interpreter that runs the scripts, not whatever `pip` is on PATH
            subprocess.run([sys.executable, "-m", *fix.split()], check=True)
        except subprocess.CalledProcessError:
            return state
    else:
        try:
            with open(target_file, "w", encoding="utf-8") as file:
                file.write(fix)
        except Exception:
            return state

    return state

# --- Graph Routing Logic ---
def route_after_execution(state: AgentState):
    if state.get("error_traceback"):
        return "Think"
    return END

def route_after_approval(state: AgentState):
    if state.get("is_approved"):
        return "Heal"
    return END

# --- Build the Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("Execute", execute_node)
workflow.add_node("Think", retrieve_or_generate_node)
workflow.add_node("Approve", human_approval_node)
workflow.add_node("Heal", heal_node)

workflow.set_entry_point("Execute")
workflow.add_conditional_edges("Execute", route_after_execution)
workflow.add_edge("Think", "Approve")
workflow.add_conditional_edges("Approve", route_after_approval)
workflow.add_edge("Heal", "Execute") # Loop back to verify the fix

# We attach a memory saver and tell the graph to freeze right before the Approve node
memory = MemorySaver()
app = workflow.compile(checkpointer=memory, interrupt_before=["Approve"])
