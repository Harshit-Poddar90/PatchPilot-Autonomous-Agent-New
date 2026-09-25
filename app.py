import streamlit as st
import os
import uuid
from core.agent import app as agent_app

# Uploaded scripts live here, so a user file named e.g. app.py can't overwrite PatchPilot itself
UPLOAD_DIR = "uploads"

# Configure the Streamlit page
st.set_page_config(page_title="PatchPilot", layout="wide")
st.title("PatchPilot: Autonomous Code-Healing Agent")

# --- 1. SESSION STATE INITIALIZATION ---
if "thread_id" not in st.session_state:
    # One LangGraph thread per browser session, so two open tabs don't share agent state
    st.session_state.thread_id = str(uuid.uuid4())
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Start completely empty. No default file.
if "target_file" not in st.session_state:
    st.session_state.target_file = None 
    
if "editor_refresh_key" not in st.session_state:
    st.session_state.editor_refresh_key = 0

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# --- 2. SIDEBAR: FILE UPLOAD ---
st.sidebar.header("📁 Upload Configuration")
st.sidebar.write("Upload a broken script for the agent to heal.")

uploaded_file = st.sidebar.file_uploader("Choose a .py or .txt file", type=["py", "txt"])

if uploaded_file is not None:
    file_path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded_file.name))
    # Only save and refresh if it is a brand new upload
    if st.session_state.target_file != file_path or not os.path.exists(file_path):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.target_file = file_path
        
        st.session_state.editor_refresh_key += 1
        st.sidebar.success(f"Successfully loaded: {file_path}")

target_file = st.session_state.target_file

# --- SIDEBAR: DOWNLOAD LOCAL PACKAGE ---
st.sidebar.markdown("---")
st.sidebar.subheader("💻 Run PatchPilot Locally")
st.sidebar.write(
    "Want the agent to automatically install missing packages "
    "and overwrite files on your actual machine? Download the local agent."
)

github_zip_url = "https://github.com/Harshit-Poddar90/PatchPilot-Autonomous-Agent/archive/refs/heads/main.zip"

st.sidebar.link_button("⬇️ Download Desktop Agent (.zip)", github_zip_url, use_container_width=True)

st.sidebar.caption("Requires Python 3.10+ and your own API keys.")


# --- 3. SPLIT SCREEN UI ---
col_code, col_agent = st.columns([1, 1], gap="large")

# LEFT SCREEN: Live Editor & Download
with col_code:
    # Empty state
    if target_file is None:
        st.info("👈 Please upload a .py or .txt file from the sidebar to begin.")
    else:
        st.subheader(f"Target Script: {target_file}")
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                current_code = f.read()
            
            edited_code = st.text_area(
                "Live Code Editor:", 
                value=current_code, 
                height=450,
                key=f"editor_{st.session_state.editor_refresh_key}"
            )
            
            if edited_code != current_code:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(edited_code)
                st.caption("✍️ Manual edits auto-saved.")

            st.download_button(
                label="⬇️ Download Healed Script",
                data=edited_code,
                file_name=f"fixed_{os.path.basename(target_file)}",
                mime="text/plain",
                type="primary"
            )
            
        except FileNotFoundError:
            st.error(f"File '{target_file}' not found. Please upload again.")

# RIGHT SCREEN: The Agent's Brain & Controls
with col_agent:
    st.subheader("Agent Control Panel")

    # Disable the Run button until a file is uploaded
    if target_file is None:
        st.warning("Upload a file to enable the AI agent.")
        st.button("🚀 Run PatchPilot Pipeline", disabled=True, use_container_width=True)
    else:
        if st.button("🚀 Run PatchPilot Pipeline", use_container_width=True):
            st.session_state.is_running = True
            
            initial_state = {
                "file_path": target_file,
                "error_traceback": "",
                "proposed_fix": "",
                "is_approved": False,
                "source": ""
            }
            
            with st.spinner("Agent is running the code..."):
                for output in agent_app.stream(initial_state, config):
                    pass 
            st.rerun() 

    current_state = agent_app.get_state(config)
    
    # Handle the Breakpoint
    if current_state.next and "Approve" in current_state.next:
        st.warning("⚠️ Agent Paused: Human Approval Required")
        
        state_values = current_state.values
        fix_source = state_values.get('source', 'Unknown')
        proposed_fix = state_values.get('proposed_fix', '')
        error_traceback = state_values.get('error_traceback', '')
        
        with st.expander("View Caught Error Traceback", expanded=False):
            st.code(error_traceback, language="bash")
            
        st.info(f"Proposed Fix (Generated by {fix_source})")
        st.code(proposed_fix, language="python")
        
        # THE APPROVAL BUTTON
        if st.button("✅ Approve & Heal File"):
            agent_app.update_state(config, {"is_approved": True})
            with st.spinner("Applying fix and looping back for verification..."):
                for output in agent_app.stream(None, config):
                    pass
            
            st.session_state.editor_refresh_key += 1
            st.rerun()

        # THE REJECT BUTTON: resumes with is_approved=False, so the graph ends without touching the file
        if st.button("❌ Reject Fix"):
            agent_app.update_state(config, {"is_approved": False})
            agent_app.invoke(None, config)
            st.rerun()

    # Final State
    elif st.session_state.is_running and target_file is not None:
        state_values = current_state.values
        if state_values and not state_values.get("error_traceback"):
            st.success("✨ Script executed successfully! No errors found.")
        elif state_values:
            st.error("Fix rejected. Edit the script manually or run the pipeline again.")