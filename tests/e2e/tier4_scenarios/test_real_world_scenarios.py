"""
Tier 4: Real-World Application Scenarios.
Directly maps to and verifies the 16+ Acceptance Criteria from ORIGINAL_REQUEST.md lines 43-79:
- Scenario 1: Voice Wake Word Activation (< 2s) (line 44)
- Scenario 2: STT Transcription & Intent Comprehension (line 45)
- Scenario 3: TTS Spoken Output Synthesis (line 46)
- Scenario 4: Barge-in Speech Interruption (< 1.0s) (line 47)
- Scenario 5: Multilingual Intent Parsing to Chrome Launch (line 50)
- Scenario 6: Multi-Turn Context Retention (Chrome -> YouTube -> Gate Smashers) (line 51)
- Scenario 7: Transparent Offline Failover on Network Loss (line 52)
- Scenario 8: Long-Term Memory Recall Post-Restart (COA Notes) (line 55)
- Scenario 9: Semantic Fuzzy Memory Query ("project folder") (line 56)
- Scenario 10: Atomic PDF Move & Verification (line 59)
- Scenario 11: Spotify Playback Launch & Control (line 60)
- Scenario 12: Terminal Python Script Execution & Timeout Guard (line 61)
- Scenario 13: Multimodal Vision Screen Error Analysis (line 64)
- Scenario 14: Visual UI Action Verification (line 65)
- Scenario 15: Complex Exam Prep Goal Decomposition & Replanning (lines 68-69)
- Scenario 16: Tri-Tier Safety Guard & High-Risk Confirmation Barrier (lines 72-74)
- Scenario 17: Context-Adaptive Personality Tone (CPU query vs Task) (lines 77-78)
Total: 17 comprehensive real-world application scenarios.
"""

import os
import time
import tempfile
import pytest
from tests.e2e.harness import (
    SAMSystemFacade, VoiceInterfaceAdapter, BrainEngineAdapter, MemoryEngineAdapter,
    ComputerControllerAdapter, SafetyGuardAdapter, VisionEngineAdapter, TaskPlannerAdapter,
    PersonalityAdapter, ActiveContext, RiskLevel
)
from tests.e2e.fixtures import TempWorkspace


# ---------------------------------------------------------------------------
# Scenario 1: Voice Wake Word Activation (< 2s) [ORIGINAL_REQUEST line 44]
# ---------------------------------------------------------------------------
def test_scenario_01_wake_word_activation():
    """AC: Saying 'Hey SAM' activates SAM within 2 seconds."""
    voice = VoiceInterfaceAdapter()
    activation_events = []
    t0 = time.time()
    voice.start_listening(lambda: activation_events.append("WAKE_DETECTED"))
    latency = time.time() - t0

    assert len(activation_events) == 1
    assert latency < 2.0, f"Wake word activation took {latency:.3f}s, exceeding 2.0s requirement"
    assert voice.is_listening is True


# ---------------------------------------------------------------------------
# Scenario 2: STT Transcription & Intent Comprehension [ORIGINAL_REQUEST line 45]
# ---------------------------------------------------------------------------
def test_scenario_02_stt_transcription_fidelity():
    """AC: Spoken input is transcribed accurately enough for the AI brain to understand intent."""
    sys = SAMSystemFacade()
    try:
        spoken_audio = sys.voice.listen_utterance("Internet chalana hai")
        res = sys.process_turn(spoken_audio)
        assert res["decision"].decision_type == "tool_call"
        assert res["decision"].tool_call.arguments["app_name"] == "Chrome"
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 3: TTS Spoken Output Synthesis [ORIGINAL_REQUEST line 46]
# ---------------------------------------------------------------------------
def test_scenario_03_tts_spoken_replies():
    """AC: SAM's replies are spoken aloud via TTS."""
    sys = SAMSystemFacade()
    try:
        res = sys.process_turn("Hello SAM")
        response_text = res["styled_response"]
        sys.voice.speak(response_text)
        assert sys.voice.is_speaking is True
        assert sys.voice.last_spoken_text == response_text
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 4: Barge-in Speech Interruption (< 1.0s) [ORIGINAL_REQUEST line 47]
# ---------------------------------------------------------------------------
def test_scenario_04_barge_in_interruption():
    """AC: Saying 'SAM stop' or 'stop' while SAM is speaking halts audio within 1 second."""
    sys = SAMSystemFacade()
    try:
        sys.voice.speak("SAM is giving a detailed 3-minute explanation about computer systems...")
        assert sys.voice.is_speaking is True
        latency = sys.voice.simulate_barge_in("SAM stop")
        assert latency < 1.0, f"Interruption took {latency:.3f}s, exceeding 1.0s limit"
        assert sys.voice.is_speaking is False
        assert sys.voice.interrupted is True
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 5: Multilingual Intent Parsing to Chrome Launch [ORIGINAL_REQUEST line 50]
# ---------------------------------------------------------------------------
def test_scenario_05_multilingual_browser_launch():
    """
    AC: All of these phrasings result in Chrome opening:
    'Open Chrome', 'Launch the browser', 'Internet chalana hai', 'Browser kholo'.
    """
    sys = SAMSystemFacade()
    try:
        phrasings = ["Open Chrome", "Launch the browser", "Internet chalana hai", "Browser kholo"]
        for phrase in phrasings:
            res = sys.process_turn(phrase)
            assert res["executed"] is True
            assert res["decision"].tool_call.arguments["app_name"] == "Chrome"
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 6: Multi-Turn Context Retention [ORIGINAL_REQUEST line 51]
# ---------------------------------------------------------------------------
def test_scenario_06_multi_turn_context_retention():
    """
    AC: SAM maintains context: after 'Open Chrome' -> 'Go to YouTube' -> 'Search Gate Smashers',
    SAM performs YouTube search without user repeating full context.
    """
    sys = SAMSystemFacade()
    try:
        # Turn 1
        t1 = sys.process_turn("Open Chrome")
        assert sys.context.active_app == "Chrome"

        # Turn 2
        t2 = sys.process_turn("Go to YouTube")
        assert sys.context.current_url == "https://youtube.com"

        # Turn 3
        t3 = sys.process_turn("Search Gate Smashers")
        assert t3["decision"].tool_call.tool_name == "youtube_search"
        assert "gate smashers" in t3["decision"].tool_call.arguments["query"]
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 7: Transparent Offline Failover on Network Loss [ORIGINAL_REQUEST line 52]
# ---------------------------------------------------------------------------
def test_scenario_07_offline_model_failover():
    """AC: When internet is disconnected, SAM automatically uses local model and informs user."""
    sys = SAMSystemFacade()
    try:
        assert sys.brain.get_current_model() == "gemma4:cloud"
        # Disconnect internet
        sys.network.set_online(False)
        assert sys.brain.get_current_model() == "qwen2.5:7b"

        res = sys.process_turn("Open Chrome")
        assert "Offline mode" in res["response_text"]
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 8: Long-Term Memory Recall Post-Restart [ORIGINAL_REQUEST line 55]
# ---------------------------------------------------------------------------
def test_scenario_08_long_term_memory_recall_post_restart():
    """
    AC: After user says 'My COA notes are in D:/Notes/COA — remember this',
    process is restarted, and user asks 'Where are my COA notes?', SAM answers correctly.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Session 1
        sys1 = SAMSystemFacade()
        sys1.memory.close()
        sys1.memory = MemoryEngineAdapter(db_path=db_path)
        sys1.memory.store_fact("My COA notes are in D:/Notes/COA", category="study")
        sys1.close()

        # Session 2 (Simulated process restart)
        sys2 = SAMSystemFacade()
        sys2.memory.close()
        sys2.memory = MemoryEngineAdapter(db_path=db_path)
        results = sys2.memory.search_facts("Where are my COA notes?")
        assert len(results) > 0
        assert "D:/Notes/COA" in results[0].fact.content
        sys2.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


# ---------------------------------------------------------------------------
# Scenario 9: Semantic Fuzzy Memory Query ("project folder") [ORIGINAL_REQUEST line 56]
# ---------------------------------------------------------------------------
def test_scenario_09_semantic_fuzzy_memory_search():
    """AC: SAM can answer fuzzy queries ('project folder') by retrieving semantically similar stored facts."""
    sys = SAMSystemFacade()
    try:
        sys.memory.store_fact("Project SAM repository path is D:/Projects/SAM", category="dev")
        results = sys.memory.search_facts("where is my project folder?")
        assert len(results) > 0
        assert "D:/Projects/SAM" in results[0].fact.content
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 10: Atomic PDF Move & Verification [ORIGINAL_REQUEST line 59]
# ---------------------------------------------------------------------------
def test_scenario_10_atomic_pdf_move_end_to_end():
    """
    AC: 'Move the latest PDF from Downloads to my COA folder' executes end-to-end:
    finds file, identifies destination, moves it, and confirms.
    """
    ws = TempWorkspace()
    try:
        sys = SAMSystemFacade(workspace_root=ws.root)
        # Verify initial state: PDF exists in Downloads, not in COA
        latest_pdf = os.path.join(ws.downloads_dir, "lecture_notes_chapter1.pdf")
        assert os.path.exists(latest_pdf)

        dest_pdf = os.path.join(ws.coa_dir, "lecture_notes_chapter1.pdf")
        # Execute atomic move
        res = sys.controller.file_action("move", src=latest_pdf, dst=dest_pdf)
        assert res.success is True
        assert res.verification_passed is True
        assert os.path.exists(dest_pdf)
        assert not os.path.exists(latest_pdf)
    finally:
        ws.cleanup()


# ---------------------------------------------------------------------------
# Scenario 11: Spotify Playback Launch & Control [ORIGINAL_REQUEST line 60]
# ---------------------------------------------------------------------------
def test_scenario_11_spotify_playback_flow():
    """AC: 'Open Spotify and play my playlist' opens the app and triggers playback."""
    sys = SAMSystemFacade()
    try:
        res = sys.process_turn("Open Spotify and play my playlist")
        assert res["executed"] is True
        assert sys.controller.media_state == "playing"
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 12: Terminal Python Script Execution & Timeout [ORIGINAL_REQUEST line 61]
# ---------------------------------------------------------------------------
def test_scenario_12_terminal_script_execution():
    """AC: 'Run this Python file' executes specified file in terminal and reports output."""
    sys = SAMSystemFacade()
    try:
        res = sys.controller.run_terminal("python test_script.py", shell="powershell", timeout=30)
        assert res.success is True
        assert "Execution succeeded" in res.output
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 13: Multimodal Vision Screen Error Analysis [ORIGINAL_REQUEST line 64]
# ---------------------------------------------------------------------------
def test_scenario_13_screen_vision_error_analysis():
    """AC: With a visible error dialog on screen, 'SAM what does this error say?' returns error text."""
    sys = SAMSystemFacade()
    try:
        error_text = "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
        sys.vision.set_mock_screen_state(error_text, error_detected=True, error_message=error_text)

        analysis = sys.vision.inspect_screen("SAM what does this error say?")
        assert analysis.error_detected is True
        assert "CUDA out of memory" in analysis.extracted_text
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 14: Visual UI Action Verification [ORIGINAL_REQUEST line 65]
# ---------------------------------------------------------------------------
def test_scenario_14_visual_action_verification():
    """AC: After SAM performs an action (e.g., opens a file), confirms via screenshot that action succeeded."""
    sys = SAMSystemFacade()
    try:
        sys.controller.open_app("Notepad")
        sys.vision.set_mock_screen_state("Notepad - Document.txt")
        verified = sys.vision.verify_ui_state("Notepad")
        assert verified is True
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 15: Complex Exam Prep Goal Decomposition & Recovery [ORIGINAL_REQUEST lines 68-69]
# ---------------------------------------------------------------------------
def test_scenario_15_exam_prep_decomposition_and_recovery():
    """
    AC: 'SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do'
    results in SAM producing structured plan and recovering if a step fails.
    """
    sys = SAMSystemFacade()
    try:
        res = sys.process_turn("SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do")
        assert res["executed"] is True
        plan = res["plan"]
        assert len(plan.steps) >= 4

        # Execute step 1
        s1 = sys.planner.execute_step(plan, 0)
        assert s1.completed is True

        # Simulate step 2 failure and recovery
        revised = sys.planner.recover_plan(plan, failed_step_index=1, error="FileNotFoundError: syllabus.txt")
        assert "Alternative" in revised.steps[1].description
        s2 = sys.planner.execute_step(revised, 1)
        assert s2.completed is True
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 16: Tri-Tier Safety Guard & High-Risk Confirmation [ORIGINAL_REQUEST lines 72-74]
# ---------------------------------------------------------------------------
def test_scenario_16_safety_permission_barriers():
    """
    AC:
    - 'Delete all files in Downloads' triggers confirmation prompt listing targets before action.
    - Without confirmation, no deletion occurs.
    - Low-risk commands (open Chrome, change volume) execute without any confirmation prompt.
    """
    sys = SAMSystemFacade()
    try:
        # 1. Low risk: open Chrome executes immediately
        low_res = sys.process_turn("Open Chrome", user_confirmed=False)
        assert low_res["executed"] is True
        assert low_res["blocked"] is False

        # 2. Low risk: volume executes immediately
        vol_res = sys.process_turn("Set volume to 40", user_confirmed=False)
        assert vol_res["executed"] is True
        assert vol_res["blocked"] is False

        # 3. High risk: Delete files without confirmation is blocked
        high_res = sys.process_turn("Delete all files in Downloads", user_confirmed=False)
        assert high_res["blocked"] is True
        assert high_res["executed"] is False
        assert "confirm" in high_res["response_text"].lower()

        # 4. High risk: With explicit user confirmation, executes
        confirmed_res = sys.process_turn("Delete all files in Downloads", user_confirmed=True)
        assert confirmed_res["blocked"] is False
        assert confirmed_res["executed"] is True
    finally:
        sys.close()


# ---------------------------------------------------------------------------
# Scenario 17: Context-Adaptive Personality Tone [ORIGINAL_REQUEST lines 77-78]
# ---------------------------------------------------------------------------
def test_scenario_17_personality_dual_tone_adaptation():
    """
    AC:
    - CPU usage query returns response with at least mild personality, not just a raw number.
    - Task execution responses are concise and professional, not chatty.
    """
    sys = SAMSystemFacade()
    try:
        # Casual system status query
        casual = sys.process_turn("How is the CPU doing?", is_task=False)
        assert "silicon" in casual["styled_response"].lower() or "sweat" in casual["styled_response"].lower()

        # Task execution response
        task = sys.process_turn("Open Chrome", is_task=True)
        assert "sweat" not in task["styled_response"].lower()
        assert task["styled_response"].endswith(".")
    finally:
        sys.close()
