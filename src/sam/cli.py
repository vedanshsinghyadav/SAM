"""
Command-Line Interface (CLI) for Project SAM.
Provides interactive REPL, voice interaction mode, single-shot prompt execution,
and safe execution confirmation prompts for Windows computer control.

Part of Milestone 7: Full System Integration.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from src.sam import __version__
from src.sam.main import SAMSystem


def render_banner() -> None:
    banner = f"""
======================================================================
               SAM — Local JARVIS Assistant for Windows
                           Version {__version__}
======================================================================
  * Natural Language Reasoning (Cloud + Local Ollama Fallback)
  * Persistent SQLite & Pure-Python Vector Semantic Memory
  * Windows Computer Control & Safety Guard Protection
  * Screen Vision & Multimodal Inspection Engine
  * Autonomous Task Planner & Tool Router
  * Spoken Audio Interaction (STT / TTS / Barge-in Interrupt)
======================================================================
 Type 'exit', 'quit', or press Ctrl+C to close.
"""
    print(banner)


def run_text_repl(sam: SAMSystem) -> None:
    """Run an interactive text session."""
    render_banner()
    print("SAM is ready. How can I assist you today?\n")

    while True:
        try:
            user_input = input("User > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("\nSAM: Shutting down systems. Have a productive day!")
                break

            # Turn 1: Process command
            turn = sam.process_turn(user_input)

            # Check if high-risk action blocked requiring user confirmation
            if turn.get("blocked"):
                confirm_prompt = turn.get("response_text", "High-risk action requires confirmation.")
                print(f"\n[SAFETY GUARD] {confirm_prompt}")
                confirm_ans = input("Confirm execution? [yes/no] > ").strip().lower()
                if confirm_ans in ("yes", "y", "confirm"):
                    turn = sam.process_turn(user_input, user_confirmed=True)
                else:
                    print("SAM: Action cancelled.")
                    continue

            response = turn.get("styled_response") or turn.get("response_text", "Task completed.")
            print(f"\nSAM > {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n\nSAM: Session interrupted. Farewell!")
            break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred: {e}\n")


def run_voice_mode(sam: SAMSystem) -> None:
    """Run interactive voice listening mode."""
    render_banner()
    print("Voice interface activated. Say 'Hey SAM' to activate...\n")

    def _on_wake():
        print("[VOICE] Wake word detected ('Hey SAM')! Listening...")

    try:
        while True:
            response = sam.start_voice_session(on_wake_detected=_on_wake)
            print(f"SAM > {response}\n")
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        print("\n\nSAM: Voice session ended.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SAM - JARVIS Assistant for Windows")
    parser.add_argument(
        "--mode",
        choices=["text", "voice"],
        default="text",
        help="Interaction mode: 'text' (default) or 'voice'"
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        help="Execute a single instruction and exit"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"SAM v{__version__}"
    )
    parser.add_argument(
        "command",
        nargs="*",
        default=[],
        help="Optional prompt or mode ('voice', 'text', or a direct command like 'open chrome')"
    )

    args = parser.parse_args()

    mode = args.mode
    prompt = args.prompt

    if args.command:
        joined_cmd = " ".join(args.command).strip()
        if joined_cmd.lower() == "voice":
            mode = "voice"
        elif joined_cmd.lower() == "text":
            mode = "text"
        elif not prompt:
            prompt = joined_cmd

    sam = SAMSystem()
    try:
        if prompt:
            turn = sam.process_turn(prompt, user_confirmed=True)
            print(turn.get("styled_response") or turn.get("response_text"))
        elif mode == "voice":
            run_voice_mode(sam)
        else:
            run_text_repl(sam)
    finally:
        sam.close()


if __name__ == "__main__":
    main()
