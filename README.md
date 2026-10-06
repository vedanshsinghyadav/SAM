# SAM (Smart Autonomous Machine)
### JARVIS-Style Local AI Assistant for Windows

SAM is an autonomous, local-first conversational AI companion built specifically for Windows. It combines natural voice and text interaction, multi-lingual intent understanding (English, Hindi, Hinglish), persistent long-term semantic memory, Windows desktop automation, screen vision inspection, and multi-step autonomous task planning with a built-in safety guard.

---

## Architecture Overview

```
                      +-----------------------------+
                      |      SAM Conversational     |
                      |          Interface          |
                      |    (Voice STT/TTS & Text)   |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |       AI Brain Engine       |
                      |  (Ollama Hybrid Cloud/Local |
                      |    + Multilingual Intent)   |
                      +--------------+--------------+
                                     |
          +--------------------------+--------------------------+
          |                          |                          |
          v                          v                          v
+-------------------+      +-------------------+      +-------------------+
|  Task Planner &   |      |  Persistent Long- |      | Screen Vision &   |
|   Tool Router     |      |    Term Memory    |      | Multimodal Engine |
| (Goal Decomp &    |      | (SQLite WAL Mode  |      | (Screen Capture & |
|  Dynamic Recovery)|      |  + Vector Search) |      | Local Inspection) |
+---------+---------+      +-------------------+      +-------------------+
          |
          v
+-------------------+
|   Safety Guard    |
| (LOW, MEDIUM, HIGH|
|   Authorization)  |
+---------+---------+
          |
          v
+-------------------+
| Windows Computer  |
| Control Suite     |
| (Apps, Windows,   |
| Files, Shell, Sys)|
+-------------------+
```

---

## Key Subsystems

### 1. Voice Interface & Wake Word (`src/sam/voice/`)
- **Wake Word Detection**: Sub-2s activation on *"Hey SAM"* or *"SAM"*.
- **Speech-to-Text (STT)**: Transcribes spoken speech preserving casing, punctuation, technical identifiers, and Hinglish.
- **Text-to-Speech (TTS)**: Natural spoken audio synthesis with non-blocking execution.
- **Barge-in Interruption**: Halts speech output in `< 10ms` when the user says *"SAM stop"* or *"stop"*.

### 2. AI Brain & Reasoning (`src/sam/brain/`)
- **Hybrid Cloud / Local Ollama**: Primary cloud reasoning (`gemma4:cloud`) with automatic zero-downtime failover to local offline model (`qwen2.5:7b`).
- **Multilingual Intent Parser**: Understands natural English, Hindi, and Hinglish commands (*"Internet chalana hai"*, *"Downloads se saare files uda do"*, *"Browser kholo"*).
- **Context Tracker**: Multi-turn conversation tracking with anaphora resolution and pronoun chaining.

### 3. Persistent Long-Term Memory (`src/sam/memory/`)
- **ACID-Compliant SQLite Store**: Uses WAL mode and parameterized queries for bulletproof persistence across restarts.
- **Semantic Vector Engine**: Fuzzy search using pure-Python cosine similarity fallback (`VectorMemoryEngine`) so no heavy C++ dependencies are required for offline vector lookups.
- **Exact Key-Value Preferences**: Direct persistence for fast fact storage and retrieval.

### 4. Windows Computer Control Suite (`src/sam/control/`)
- **Application Manager**: Launch and terminate Windows apps (`Chrome`, `Spotify`, `Notepad`, etc.).
- **Window Manager**: Minimize, maximize, restore, focus, and query active windows.
- **File System Automation**: Create, copy, move, rename, and delete files/directories with path containment.
- **System Controls**: Adjust volume, brightness, media play/pause, and read system metrics/notifications.
- **Terminal Runner**: Secure PowerShell and Python script execution with timeout and output capture.

### 5. Permission & Safety Guard (`src/sam/safety/`)
- **3-Tier Risk Model**:
  - `LOW`: Read-only queries, app opening, volume control (executes immediately).
  - `MEDIUM`: App closing, file movement, settings alteration (logged and announced).
  - `HIGH`: File deletion, terminal script execution (blocked until explicit user confirmation).

### 6. Screen Vision & Multimodal Inspection (`src/sam/vision/`)
- **Screen Capture**: High-DPI, multi-monitor screenshot capture with absolute path guarantees.
- **Visual Inspection**: Multimodal OCR/inspection for analyzing error dialogues and UI state.
- **Action Verification**: Confirms visual state changes after computer control actions.

### 7. Autonomous Task Planner (`src/sam/planner/`)
- **Goal Decomposition**: Breaks high-level goals into atomic, ordered execution steps.
- **Safety Authorization**: Verifies each step through `SafetyGuard` before execution.
- **Dynamic Recovery**: Gracefully handles step failures (missing files, closed apps) and retries alternative paths rather than stopping silently.

### 8. Context-Adaptive Personality (`src/sam/personality/`)
- **Dual-Tone Switching**:
  - *Casual Mode*: Mildly witty, helpful, and JARVIS-like during conversation and hardware metric reporting.
  - *Task Mode*: Concise, professional, and direct during automation and computer control.

---

## Installation & Quick Start

### Prerequisites
- Windows 10 / 11
- Python 3.10+ (tested on Python 3.14)
- (Optional) [Ollama](https://ollama.com/) for local offline LLM inference (`ollama run qwen2.5:7b`)

### Setup
```powershell
# Clone the repository
git clone https://github.com/vedanshsinghyadav/SAM.git
cd SAM

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## Quick Start & Global Access

### Register Global `sam` Command (Windows)
Run the global launcher installer to enable typing `sam` directly in any CMD, PowerShell, or Windows Terminal window:
```powershell
.\scripts\install_global.bat
```
*(This also places a convenient `SAM.bat` launcher on your Desktop).*

---

## Usage

### 1. Global Terminal Access (from anywhere)
```powershell
# Interactive Assistant
sam

# Spoken Audio Voice Mode
sam voice

# Direct One-Shot Command Execution
sam "Open Chrome and go to YouTube"
sam open chrome
```

### 2. Standard Python Invocation
```powershell
# Interactive Text REPL
python -m src.sam.cli

# Voice Mode
python -m src.sam.cli --mode voice

# Single Command Execution
python -m src.sam.cli --prompt "Open Chrome and go to YouTube"
```

---

## Verification & Test Suite

SAM includes a comprehensive test suite of **678 automated tests** (331 unit tests + 347 opaque-box end-to-end tests) covering 100% of functional requirements and edge cases.

```powershell
# Run all unit tests (331 tests)
python -m pytest tests/unit/

# Run complete opaque-box E2E suite (347 tests)
python tests/e2e/runner.py

# Run by tier
python tests/e2e/runner.py --tier 1  # Feature coverage
python tests/e2e/runner.py --tier 2  # Boundary & corner cases
python tests/e2e/runner.py --tier 3  # Cross-feature interactions
python tests/e2e/runner.py --tier 4  # Real-world scenarios
```

---

## License
MIT License. Built with privacy and local-first autonomy in mind.