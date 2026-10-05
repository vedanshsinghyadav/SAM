"""
Tier 1: Feature Coverage Tests for Voice Interface (R1).
Covers:
- FEAT-VOICE-001: Wake Word Detection (5 tests)
- FEAT-VOICE-002: STT Transcription (5 tests)
- FEAT-VOICE-003: TTS Audio Synthesis (5 tests)
- FEAT-VOICE-004: Audio Barge-in Interrupt (5 tests)
- FEAT-VOICE-005: Dual-Mode Text Interface (5 tests)
Total: 25 tests.
"""

import time
import pytest
from tests.e2e.harness import VoiceInterfaceAdapter, BrainEngineAdapter, ActiveContext


# ---------------------------------------------------------------------------
# FEAT-VOICE-001: Wake Word Detection
# ---------------------------------------------------------------------------

def test_feat_voice_001_wake_word_activates_under_2_seconds():
    voice = VoiceInterfaceAdapter()
    triggered = []
    t0 = time.time()
    voice.start_listening(lambda: triggered.append(True))
    latency = time.time() - t0
    assert len(triggered) == 1
    assert latency < 2.0, f"Wake word activation took {latency:.3f}s, expected < 2.0s"


def test_feat_voice_001_wake_word_sets_listening_state():
    voice = VoiceInterfaceAdapter()
    assert not voice.is_listening
    voice.start_listening(lambda: None)
    assert voice.is_listening


def test_feat_voice_001_wake_word_callback_invoked_cleanly():
    voice = VoiceInterfaceAdapter()
    events = []
    voice.start_listening(lambda: events.append("wake_detected"))
    assert events == ["wake_detected"]


def test_feat_voice_001_wake_word_multiple_triggers():
    voice = VoiceInterfaceAdapter()
    counter = 0
    def on_wake():
        nonlocal counter
        counter += 1
    voice.start_listening(on_wake)
    voice.start_listening(on_wake)
    assert counter == 2


def test_feat_voice_001_wake_word_idle_when_not_started():
    voice = VoiceInterfaceAdapter()
    assert voice.is_listening is False
    assert voice.is_speaking is False


# ---------------------------------------------------------------------------
# FEAT-VOICE-002: STT Transcription
# ---------------------------------------------------------------------------

def test_feat_voice_002_stt_transcribes_english_command():
    voice = VoiceInterfaceAdapter()
    utterance = voice.listen_utterance(mock_audio_text="Open Chrome")
    assert utterance == "Open Chrome"
    assert len(utterance.strip()) > 0


def test_feat_voice_002_stt_transcribes_hinglish_command():
    voice = VoiceInterfaceAdapter()
    utterance = voice.listen_utterance(mock_audio_text="Internet chalana hai")
    assert utterance == "Internet chalana hai"
    assert "internet" in utterance.lower()


def test_feat_voice_002_stt_transcribes_punctuation_and_casing():
    voice = VoiceInterfaceAdapter()
    utterance = voice.listen_utterance(mock_audio_text="SAM, where are my COA notes?")
    assert "COA" in utterance
    assert utterance.endswith("?")


def test_feat_voice_002_stt_preserves_technical_terms():
    voice = VoiceInterfaceAdapter()
    utterance = voice.listen_utterance(mock_audio_text="Run script.py with powershell")
    assert "script.py" in utterance
    assert "powershell" in utterance


def test_feat_voice_002_stt_ensures_non_empty_output():
    voice = VoiceInterfaceAdapter()
    utterance = voice.listen_utterance(mock_audio_text="Launch the browser")
    assert isinstance(utterance, str)
    assert len(utterance) > 0


# ---------------------------------------------------------------------------
# FEAT-VOICE-003: TTS Audio Synthesis
# ---------------------------------------------------------------------------

def test_feat_voice_003_tts_synthesizes_spoken_reply():
    voice = VoiceInterfaceAdapter()
    voice.speak("Opening Chrome for you.")
    assert voice.is_speaking
    assert voice.last_spoken_text == "Opening Chrome for you."


def test_feat_voice_003_tts_handles_multiline_speech():
    voice = VoiceInterfaceAdapter()
    text = "First sentence.\nSecond sentence.\nThird sentence."
    voice.speak(text)
    assert voice.last_spoken_text == text


def test_feat_voice_003_tts_sets_start_timestamp():
    voice = VoiceInterfaceAdapter()
    voice.speak("System volume set to fifty percent.")
    assert voice.speech_start_time > 0.0


def test_feat_voice_003_tts_normal_completion_clears_state():
    voice = VoiceInterfaceAdapter()
    voice.speak("Done.")
    assert voice.is_speaking
    voice.stop_speaking()
    assert not voice.is_speaking


def test_feat_voice_003_tts_synthesizes_numbers_and_symbols():
    voice = VoiceInterfaceAdapter()
    voice.speak("Volume at 100%, CPU at 25.5%.")
    assert "100%" in voice.last_spoken_text
    assert "25.5%" in voice.last_spoken_text


# ---------------------------------------------------------------------------
# FEAT-VOICE-004: Audio Barge-in Interrupt
# ---------------------------------------------------------------------------

def test_feat_voice_004_barge_in_stops_speech_under_1_second():
    voice = VoiceInterfaceAdapter()
    voice.speak("This is a very long response explaining quantum mechanics in detail...")
    latency = voice.simulate_barge_in("SAM stop")
    assert latency < 1.0, f"Interrupt latency was {latency:.3f}s, expected < 1.0s"
    assert not voice.is_speaking
    assert voice.interrupted


def test_feat_voice_004_barge_in_on_single_word_stop():
    voice = VoiceInterfaceAdapter()
    voice.speak("Playing playlist on Spotify.")
    voice.simulate_barge_in("stop")
    assert not voice.is_speaking
    assert voice.interrupted


def test_feat_voice_004_barge_in_does_not_halt_on_unrelated_speech():
    voice = VoiceInterfaceAdapter()
    voice.speak("Continuing playback.")
    voice.simulate_barge_in("carry on please")
    # Should not interrupt if stop phrase is absent
    assert voice.is_speaking
    assert not voice.interrupted


def test_feat_voice_004_barge_in_resets_interrupted_flag_on_new_speech():
    voice = VoiceInterfaceAdapter()
    voice.speak("First statement.")
    voice.simulate_barge_in("stop")
    assert voice.interrupted
    voice.speak("Second statement.")
    assert not voice.interrupted


def test_feat_voice_004_barge_in_timing_precision():
    voice = VoiceInterfaceAdapter()
    voice.speak("Reading notification...")
    t0 = time.time()
    voice.simulate_barge_in("SAM stop")
    t1 = time.time()
    assert (t1 - t0) < 0.5


# ---------------------------------------------------------------------------
# FEAT-VOICE-005: Dual-Mode Text Interface
# ---------------------------------------------------------------------------

def test_feat_voice_005_text_mode_processes_input():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    decision = brain.process_input("Open Chrome", ctx)
    assert decision.decision_type == "tool_call"
    assert decision.tool_call.arguments["app_name"] == "Chrome"


def test_feat_voice_005_text_mode_handles_empty_whitespace():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    decision = brain.process_input("   ", ctx)
    assert decision.decision_type == "reply"


def test_feat_voice_005_text_mode_accepts_unicode_characters():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    decision = brain.process_input("Browser kholo कृपया", ctx)
    assert decision.decision_type == "tool_call"


def test_feat_voice_005_text_mode_does_not_require_audio_hardware():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    decision = brain.process_input("Set volume to 40", ctx)
    assert decision.tool_call.tool_name == "control_volume"


def test_feat_voice_005_text_mode_returns_structured_reply():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    decision = brain.process_input("Hello SAM", ctx)
    assert decision.reply_text is not None
    assert len(decision.reply_text) > 0
