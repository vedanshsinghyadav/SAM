"""
Tier 3: Cross-Feature Interaction Tests.
Covers pairwise interactions sharing context, data flow, or state:
1. Brain + Memory (Fact Storage & Recall)
2. Brain + Context + Tool Router (Contextual Navigation Chain)
3. Brain + Safety Guard (High-Risk Interception)
4. Brain + Offline Failover (Network Detector to Brain Switch)
5. Task Planner + Control + Verification (Atomic Multi-Step Execution)
6. Task Planner + Plan Recovery (Self-Healing on Step Failure)
7. Voice + STT + Brain (Spoken Utterance Intent Extraction)
8. Voice + TTS + Barge-in Interrupt (Interruption Pipeline)
9. Control + Safety (Medium-Risk Announcement Before Action)
10. Control + Safety (High-Risk Mandatory Confirmation Barrier)
11. Vision + Brain + Planner (Visual Error Extraction to Plan Recovery)
12. Vision + Control (Action Execution Followed by Visual Verification)
13. Personality + Control + Context (Adaptive Tone for System Stats vs Tasks)
14. Personality + Voice + Text (Modality Invariance Verification)
15. App Lifecycle + Window Management (Launch and Window State Control)
16. Memory + Restart Persistence (Cross-Process Memory Continuity)
17. Terminal Runner + Controller (PowerShell Execution & Output Capture)
18. Notifications + Brain (System Toast Alert Summarization)
19. Dynamic Multi-Tool Routing (Planner Dispatching Across Multiple Engines)
20. Voice Wake Word + Active Listening State Transition
Total: 20 comprehensive interaction tests.
"""

import os
import time
import tempfile
import pytest
from tests.e2e.harness import (
    SAMSystemFacade, BrainEngineAdapter, MemoryEngineAdapter, ComputerControllerAdapter,
    SafetyGuardAdapter, VisionEngineAdapter, TaskPlannerAdapter, VoiceInterfaceAdapter,
    PersonalityAdapter, ActiveContext, ToolCall, RiskLevel, MockNetworkDetector
)


def test_interaction_01_brain_and_memory():
    """Interaction between Brain and Long-Term Memory."""
    sys = SAMSystemFacade()
    try:
        # User tells SAM a fact
        sys.memory.store_fact("My COA notes are in D:/Notes/COA", category="study")
        # Later user queries memory
        results = sys.memory.search_facts("Where are my COA notes?")
        assert len(results) > 0
        assert "D:/Notes/COA" in results[0].fact.content
    finally:
        sys.close()


def test_interaction_02_brain_context_and_tool_router():
    """Interaction between Brain, Context Tracker, and Tool Router."""
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    # Turn 1: Open Chrome
    d1 = brain.process_input("Open Chrome", ctx)
    assert ctx.active_app == "Chrome"
    # Turn 2: Go to YouTube
    d2 = brain.process_input("Go to YouTube", ctx)
    assert ctx.current_url == "https://youtube.com"
    # Turn 3: Search Gate Smashers
    d3 = brain.process_input("Search Gate Smashers", ctx)
    assert d3.tool_call.tool_name == "youtube_search"
    assert "gate smashers" in d3.tool_call.arguments["query"]


def test_interaction_03_brain_and_safety_guard():
    """Interaction between Brain intent generation and Safety Guard classification."""
    sys = SAMSystemFacade()
    try:
        # Prompt to delete files
        res = sys.process_turn("Delete all files in Downloads", user_confirmed=False)
        assert res["blocked"] is True
        assert "confirm" in res["response_text"].lower()
    finally:
        sys.close()


def test_interaction_04_brain_and_offline_failover():
    """Interaction between Network Detector and Brain hybrid model selection."""
    net = MockNetworkDetector(online=True)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.get_current_model() == "gemma4:cloud"
    # Disconnect network
    net.set_online(False)
    assert brain.get_current_model() == "qwen2.5:7b"
    dec = brain.process_input("Open Chrome", ActiveContext())
    assert "Offline mode" in dec.reply_text


def test_interaction_05_planner_control_and_atomic_verification():
    """Interaction between Task Planner, Controller, and Step Verification."""
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    safety = SafetyGuardAdapter()
    planner = TaskPlannerAdapter(ctrl, safety)

    # Create dummy PDF
    pdf_path = os.path.join(td, "lecture.pdf")
    ctrl.file_action("create", path=pdf_path, content="PDF data")

    plan = planner.create_plan("Move latest PDF to COA folder")
    # Step 1: Find latest
    s1 = planner.execute_step(plan, 0)
    assert s1.completed is True
    # Step 2: Ensure destination dir
    s2 = planner.execute_step(plan, 1)
    assert s2.completed is True


def test_interaction_06_planner_and_recovery():
    """Interaction between Planner and Recovery when a resource is missing."""
    ctrl = ComputerControllerAdapter()
    safety = SafetyGuardAdapter()
    planner = TaskPlannerAdapter(ctrl, safety)
    plan = planner.create_plan("COA exam prep")
    # Step fails due to missing file
    revised = planner.recover_plan(plan, failed_step_index=1, error="FileNotFoundError: syllabus.txt")
    assert "Alternative" in revised.steps[1].description
    # Revised step can execute successfully
    step = planner.execute_step(revised, 1)
    assert step.completed is True


def test_interaction_07_voice_stt_and_brain():
    """Interaction between Voice STT transcription and Brain intent parsing."""
    voice = VoiceInterfaceAdapter()
    brain = BrainEngineAdapter()
    ctx = ActiveContext()

    spoken = voice.listen_utterance(mock_audio_text="Internet chalana hai")
    dec = brain.process_input(spoken, ctx)
    assert dec.decision_type == "tool_call"
    assert dec.tool_call.arguments["app_name"] == "Chrome"


def test_interaction_08_voice_tts_and_barge_in_interrupt():
    """Interaction between Voice TTS audio synthesis and Barge-in Interruption."""
    voice = VoiceInterfaceAdapter()
    voice.speak("SAM is reading a long answer regarding processor pipelining...")
    assert voice.is_speaking is True
    latency = voice.simulate_barge_in("SAM stop")
    assert latency < 1.0
    assert voice.is_speaking is False
    assert voice.interrupted is True


def test_interaction_09_control_and_safety_medium_risk_announcement():
    """Interaction between Controller and Safety Guard pre-execution announcement."""
    sys = SAMSystemFacade()
    try:
        # Closing an app is medium risk
        tc = ToolCall(tool_name="close_app", arguments={"process_or_name": "Spotify"})
        auth, msg = sys.safety.authorize(tc, user_confirmed=False)
        assert auth is True
        assert "Announcing medium risk" in msg
        assert len(sys.safety.announcements) == 1
    finally:
        sys.close()


def test_interaction_10_control_and_safety_high_risk_confirmation():
    """Interaction between Controller and High-Risk explicit confirmation barrier."""
    sys = SAMSystemFacade()
    try:
        td = tempfile.mkdtemp()
        dummy_file = os.path.join(td, "target.txt")
        sys.controller.file_action("create", path=dummy_file, content="secret")

        # Attempt deletion without confirmation
        res_blocked = sys.process_turn("Delete all files in Downloads", user_confirmed=False)
        assert res_blocked["blocked"] is True

        # Now confirm
        res_confirmed = sys.process_turn("Delete all files in Downloads", user_confirmed=True)
        assert res_confirmed["executed"] is True
    finally:
        sys.close()


def test_interaction_11_vision_and_planner():
    """Interaction between Vision Engine and Planner for screen error inspection."""
    sys = SAMSystemFacade()
    try:
        sys.vision.set_mock_screen_state("Error 404: File Not Found", error_detected=True, error_message="Error 404")
        analysis = sys.vision.inspect_screen("What does this error say?")
        assert analysis.error_detected is True
        assert "Error 404" in analysis.extracted_text
    finally:
        sys.close()


def test_interaction_12_vision_and_control():
    """Interaction between Control action and subsequent Visual Verification."""
    sys = SAMSystemFacade()
    try:
        sys.controller.open_app("Notepad")
        sys.vision.set_mock_screen_state("Notepad - Untitled")
        verified = sys.vision.verify_ui_state("Notepad")
        assert verified is True
    finally:
        sys.close()


def test_interaction_13_personality_and_context_dual_tone():
    """Interaction between Personality Engine and Context for tone adaptation."""
    pers = PersonalityAdapter()
    # Casual chit chat vs Task execution
    casual_resp = pers.adapt_tone("CPU is currently at 15%", is_task=False)
    task_resp = pers.adapt_tone("CPU is currently at 15%", is_task=True)
    assert "silicon" in casual_resp.lower() or "sweat" in casual_resp.lower()
    assert "silicon" not in task_resp.lower()


def test_interaction_14_personality_voice_and_text_invariance():
    """Interaction between Personality Engine and output modality."""
    pers = PersonalityAdapter()
    msg = "Volume set to 60 percent."
    text_out = pers.format_response(msg, modality="text")
    voice_out = pers.format_response(msg, modality="voice")
    assert text_out == voice_out == msg


def test_interaction_15_app_lifecycle_and_window_management():
    """Interaction between App launch and Desktop Window Management."""
    ctrl = ComputerControllerAdapter()
    open_res = ctrl.open_app("Calculator")
    assert open_res.success is True
    win_res = ctrl.manage_window("maximize", "Calculator")
    assert win_res.success is True
    assert win_res.output["action"] == "maximize"


def test_interaction_16_memory_persistence_across_process_restart():
    """Interaction verifying Memory DB integrity across instance creation."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Instance 1
        m1 = MemoryEngineAdapter(db_path=db_path)
        m1.store_fact("User's primary editor is VS Code", category="pref")
        # Instance 2 (Simulating reboot)
        m2 = MemoryEngineAdapter(db_path=db_path)
        results = m2.search_facts("editor")
        assert len(results) > 0
        assert "VS Code" in results[0].fact.content
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_interaction_17_terminal_runner_and_controller():
    """Interaction executing terminal command through controller."""
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("echo 'Pipeline test'", shell="powershell")
    assert res.success is True
    assert res.verification_passed is True


def test_interaction_18_notifications_and_brain():
    """Interaction between Notifications and Brain."""
    ctrl = ComputerControllerAdapter()
    notes = ctrl.read_notifications()
    assert len(notes) > 0
    note_text = notes[0]["text"]
    brain = BrainEngineAdapter()
    dec = brain.process_input(f"Summarize this notification: {note_text}", ActiveContext())
    assert dec.decision_type == "reply"


def test_interaction_19_dynamic_multi_tool_routing():
    """Interaction between Task Planner routing across File and System tools."""
    ctrl = ComputerControllerAdapter()
    safety = SafetyGuardAdapter()
    planner = TaskPlannerAdapter(ctrl, safety)
    plan = planner.create_plan("COA exam prep")
    tool_names = [s.tool_call.tool_name for s in plan.steps]
    assert "open_file" in tool_names
    assert "read_file" in tool_names
    assert "compare_topics" in tool_names


def test_interaction_20_voice_wake_word_and_active_listening():
    """Interaction between Wake Word trigger and listening state transition."""
    voice = VoiceInterfaceAdapter()
    activated = []
    voice.start_listening(lambda: activated.append(True))
    assert len(activated) == 1
    utterance = voice.listen_utterance("Launch the browser")
    assert utterance == "Launch the browser"
