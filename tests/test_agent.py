"""
Offline check of the full LangGraph loop: Execute -> Think -> (pause) -> Approve/Reject -> Heal -> Execute.
Gemini and Supabase are faked, so no API keys or network are needed.

Run:  python -m pytest tests   (or: python tests/test_agent.py)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Dummy credentials so the core modules import; every network call is faked below
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "header.payload.signature")

import core.agent as agent

FIX = 'print("fixed")\n'
saved = []
agent.search_memory = lambda error: None                  # RAG miss
agent.generate_code_fix = lambda error, path: FIX         # "LLM" answer
agent.generate_embedding = lambda text: [0.0]
agent.save_to_memory = lambda error, vector, fix: saved.append(fix)

def run_until_pause(script, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    state = {"file_path": script, "error_traceback": "", "proposed_fix": "", "is_approved": False, "source": ""}
    agent.app.invoke(state, config)
    paused = agent.app.get_state(config)
    assert paused.next == ("Approve",)  # frozen for the human
    assert "ZeroDivisionError" in paused.values["error_traceback"]
    assert paused.values["source"] == "LLM"
    return config

def make_broken_script(folder):
    script = os.path.join(folder, "broken.py")
    with open(script, "w") as f:
        f.write("1 / 0\n")
    return script

def test_approve_heals_verifies_and_memorizes():
    saved.clear()
    with tempfile.TemporaryDirectory() as tmp:
        script = make_broken_script(tmp)
        config = run_until_pause(script, "approve")
        assert saved == []  # nothing memorized before the fix is verified

        agent.app.update_state(config, {"is_approved": True})
        agent.app.invoke(None, config)

        done = agent.app.get_state(config)
        assert done.next == ()
        assert done.values["error_traceback"] == ""  # re-run passed
        assert open(script).read() == FIX
        assert saved == [FIX]  # memorized only after the re-run passed

def test_fix_that_does_not_work_is_not_memorized():
    saved.clear()
    agent.generate_code_fix = lambda error, path: "1 / 0\n"  # "fix" that keeps the same crash
    try:
        with tempfile.TemporaryDirectory() as tmp:
            script = make_broken_script(tmp)
            config = run_until_pause(script, "bad-fix")

            agent.app.update_state(config, {"is_approved": True})
            agent.app.invoke(None, config)

            assert agent.app.get_state(config).next == ("Approve",)  # still failing, asks the human again
            assert saved == []
    finally:
        agent.generate_code_fix = lambda error, path: FIX

def test_reject_leaves_file_untouched():
    saved.clear()
    with tempfile.TemporaryDirectory() as tmp:
        script = make_broken_script(tmp)
        config = run_until_pause(script, "reject")

        agent.app.update_state(config, {"is_approved": False})
        agent.app.invoke(None, config)

        assert agent.app.get_state(config).next == ()
        assert open(script).read() == "1 / 0\n"
        assert saved == []

if __name__ == "__main__":
    test_approve_heals_verifies_and_memorizes()
    test_fix_that_does_not_work_is_not_memorized()
    test_reject_leaves_file_untouched()
    print("All checks passed.")
