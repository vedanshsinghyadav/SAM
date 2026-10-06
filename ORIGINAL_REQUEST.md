# Original User Request

## Initial Request — 2026-10-05T04:51:59Z

Build SAM — a JARVIS-style local AI assistant for Windows that accepts voice and text input, reasons over goals, plans multi-step tasks, controls the computer, remembers the user across sessions, and responds with personality via spoken audio. This is a working prototype: the full architecture must be present and functional end-to-end, but polish is secondary.

Working directory: ./

Integrity mode: benchmark

---

## Requirements

### R1. Voice Interface — STT + TTS + Wake Word
SAM must run as an always-listening process that activates on the wake word "Hey SAM". After activation, it must transcribe the user's spoken input to text (speech-to-text), and convert SAM's replies to natural spoken audio (text-to-speech). The user must also be able to interact via text. Interruption must be supported: if the user speaks while SAM is responding, SAM stops.

### R2. AI Brain — Reasoning, Context, and Intent
SAM must use an LLM as its core reasoning engine. The brain must understand natural language intent (not just exact phrase matching), maintain context across a full conversation (tracking current app, website, task, subject), and produce structured decisions: either a reply, or a specific tool call with arguments. The AI backend must use Ollama cloud (gemma4:cloud) by default and automatically fall back to a local Ollama model (qwen2.5:7b or equivalent) when offline.

### R3. Memory — Persistent Across Sessions
SAM must maintain long-term memory that persists across restarts. Memory must store user preferences, important facts the user has stated, project/file locations, and interaction history. When the user asks something related to a past session, SAM must retrieve and use the relevant memory. Memory must use semantic search (vector embeddings) so that fuzzy queries ("project folder") retrieve exact stored facts ("D:/Projects/SAM").

### R4. Computer Control — File, App, and System Actions
SAM must be able to execute actions on the Windows computer: open and close applications, manage windows, create/move/rename/copy/delete files and folders, take screenshots, control system volume and brightness, play/pause media, run terminal commands (PowerShell/Python), and read system notifications. Multi-step tasks (e.g., "find the latest PDF in Downloads and move it to my COA folder") must be executed as a sequence of atomic actions with verification after each step.

### R5. Vision — Screen Understanding
SAM must be able to capture and interpret the current screen state. When asked about what is on screen (e.g., "what does this error say?"), SAM must screenshot, pass the image to a vision-capable model, and use the result in its reasoning. Vision must also be available as a tool the task planner can invoke to verify the outcome of an action.

### R6. Task Planner and Tool Router
SAM must decompose complex goals into ordered sub-tasks before executing them. For each sub-task, SAM must select the appropriate tool (file tool, browser tool, system tool, terminal tool, vision tool). The planner must handle task failure: if a step fails, SAM must retry or adapt the plan rather than stopping silently.

### R7. Permission and Safety System
Actions must be classified by risk level: low (open apps, search, volume), medium (move files, close programs, install software), high (delete files, send messages, execute sensitive commands). Low-risk actions execute immediately. Medium-risk actions are announced before execution. High-risk actions require explicit user confirmation ("Confirm?" → user says "Confirm"). SAM must never execute a high-risk action without this confirmation step.

### R8. Personality
SAM must have a consistent personality: helpful and mildly witty in casual interactions, concise and professional during task execution. SAM must not be a flat command executor — responses must feel like a person, not a bot. The personality must remain stable across all interaction types.

---

## Acceptance Criteria

### Voice Interface
- [ ] Saying "Hey SAM" (with no keyboard input) activates SAM within 2 seconds
- [ ] Spoken input is transcribed accurately enough for the AI brain to understand intent
- [ ] SAM's replies are spoken aloud via TTS
- [ ] Saying "SAM stop" or "stop" while SAM is speaking halts the audio within 1 second

### AI Brain
- [ ] All of these phrasings result in Chrome opening: "Open Chrome", "Launch the browser", "Internet chalana hai", "Browser kholo"
- [ ] SAM maintains context: after "Open Chrome" → "Go to YouTube" → "Search Gate Smashers", SAM performs the YouTube search without the user repeating the full context
- [ ] When the internet is disconnected, SAM automatically uses the local model and informs the user

### Memory
- [ ] After the user says "My COA notes are in D:/Notes/COA — remember this", the process is restarted, and the user asks "Where are my COA notes?", SAM answers correctly
- [ ] SAM can answer fuzzy queries ("project folder", "my notes") by retrieving semantically similar stored facts

### Computer Control
- [ ] "Move the latest PDF from Downloads to my COA folder" executes correctly end-to-end: SAM finds the file, identifies the destination, moves it, and confirms
- [ ] "Open Spotify and play my playlist" opens the app and triggers playback
- [ ] "Run this Python file" executes a specified file in the terminal and reports the output

### Vision
- [ ] With a visible error dialog on screen, "SAM what does this error say?" returns the error text correctly
- [ ] After SAM performs an action (e.g., opens a file), it can confirm via screenshot that the action succeeded

### Task Planner
- [ ] "SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do" results in SAM producing a structured plan and executing it step by step
- [ ] If a step fails (e.g., file not found), SAM reports the failure and attempts an alternative rather than crashing

### Permission System
- [ ] "Delete all files in Downloads" triggers a confirmation prompt listing what will be deleted before any action is taken
- [ ] Without confirmation, no deletion occurs
- [ ] Low-risk commands (open Chrome, change volume) execute without any confirmation prompt

### Personality
- [ ] CPU usage query returns a response with at least mild personality, not just a raw number
- [ ] Task execution responses are concise and professional, not chatty


## Follow-up — 2026-10-05T14:43:24Z

The server restarted and all agents were stopped. Please resume SAM build from where you left off.

Last known state before restart:
- Milestone 1 COMPLETE and gated (90 unit + 37 adversarial tests passing, unanimous reviewer approval)
- Milestone 2 (Persistent Memory Engine) was JUST starting — 3 exploratory agents (explorer_m2_1, explorer_m2_2, spec_miner_m2_3) had been dispatched for SQLite ACID storage, vector embeddings/cosine search, and memory specifications

Please resume from Milestone 2. Check your internal state (plan.md, progress.md in .agents/) to see what the explorers delivered before the restart. If explorer results are present, proceed to dispatch the implementation worker for M2. If not, re-dispatch the explorers.

Working directory: C:\Users\vedan\Downloads\sam
Continue: M2 (memory/) → M3 (control/ + safety/) → M4 (vision/) → M5 (planner/) → M6 (voice/) → M7 (full integration + E2E)

## Follow-up — 2026-10-05T15:37:38Z

Build SAM — a JARVIS-style local AI assistant for Windows that accepts voice and text input, reasons over goals, plans multi-step tasks, controls the computer, remembers the user across sessions, and responds with personality via spoken audio. This is a working prototype: the full architecture must be present and functional end-to-end, but polish is secondary.

Working directory: C:\Users\vedan\Downloads\sam

Integrity mode: benchmark

Current State:
- Milestone 1 (Foundation, Brain, Context, Personality) is COMPLETE and verified (100% tests pass).
- Milestone 2 (Persistent SQLite Store, Vector Cosine Search) is COMPLETE and verified (100% unit tests & E2E tests pass).
- Source repository is synced with GitHub (branch: main).
- Proceed directly to Milestone 3 (Windows Control Suite & Safety Guard: src/sam/control/, src/sam/safety/), then Milestone 4 (Screen Vision & Multimodal Inspection), Milestone 5 (Autonomous Task Planner & Tool Router), Milestone 6 (Voice Interface & Wake Word), and Milestone 7 (Full System Integration & End-to-End Hardening).

---

## Requirements

### R1. Voice Interface — STT + TTS + Wake Word
SAM must run as an always-listening process that activates on the wake word "Hey SAM". After activation, it must transcribe the user's spoken input to text (speech-to-text), and convert SAM's replies to natural spoken audio (text-to-speech). The user must also be able to interact via text. Interruption must be supported: if the user speaks while SAM is responding, SAM stops.

### R2. AI Brain — Reasoning, Context, and Intent
SAM must use an LLM as its core reasoning engine. The brain must understand natural language intent (not just exact phrase matching), maintain context across a full conversation (tracking current app, website, task, subject), and produce structured decisions: either a reply, or a specific tool call with arguments. The AI backend must use Ollama cloud (gemma4:cloud) by default and automatically fall back to a local Ollama model (qwen2.5:7b or equivalent) when offline.

### R3. Memory — Persistent Across Sessions
SAM must maintain long-term memory that persists across restarts. Memory must store user preferences, important facts the user has stated, project/file locations, and interaction history. When the user asks something related to a past session, SAM must retrieve and use the relevant memory. Memory must use semantic search (vector embeddings) so that fuzzy queries ("project folder") retrieve exact stored facts ("D:/Projects/SAM").

### R4. Computer Control — File, App, and System Actions
SAM must be able to execute actions on the Windows computer: open and close applications, manage windows, create/move/rename/copy/delete files and folders, take screenshots, control system volume and brightness, play/pause media, run terminal commands (PowerShell/Python), and read system notifications. Multi-step tasks (e.g., "find the latest PDF in Downloads and move it to my COA folder") must be executed as a sequence of atomic actions with verification after each step.

### R5. Vision — Screen Understanding
SAM must be able to capture and interpret the current screen state. When asked about what is on screen (e.g., "what does this error say?"), SAM must screenshot, pass the image to a vision-capable model, and use the result in its reasoning. Vision must also be available as a tool the task planner can invoke to verify the outcome of an action.

### R6. Task Planner and Tool Router
SAM must decompose complex goals into ordered sub-tasks before executing them. For each sub-task, SAM must select the appropriate tool (file tool, browser tool, system tool, terminal tool, vision tool). The planner must handle task failure: if a step fails, SAM must retry or adapt the plan rather than stopping silently.

### R7. Permission and Safety System
Actions must be classified by risk level: low (open apps, search, volume), medium (move files, close programs, install software), high (delete files, send messages, execute sensitive commands). Low-risk actions execute immediately. Medium-risk actions are announced before execution. High-risk actions require explicit user confirmation ("Confirm?" → user says "Confirm"). SAM must never execute a high-risk action without this confirmation step.

### R8. Personality
SAM must have a consistent personality: helpful and mildly witty in casual interactions, concise and professional during task execution. SAM must not be a flat command executor — responses must feel like a person, not a bot. The personality must remain stable across all interaction types.

---

## Acceptance Criteria

### Voice Interface
- [ ] Saying "Hey SAM" (with no keyboard input) activates SAM within 2 seconds
- [ ] Spoken input is transcribed accurately enough for the AI brain to understand intent
- [ ] SAM's replies are spoken aloud via TTS
- [ ] Saying "SAM stop" or "stop" while SAM is responding halts the audio within 1 second

### AI Brain (Verified M1)
- [x] All of these phrasings result in Chrome opening: "Open Chrome", "Launch the browser", "Internet chalana hai", "Browser kholo"
- [x] SAM maintains context: after "Open Chrome" → "Go to YouTube" → "Search Gate Smashers", SAM performs the YouTube search without the user repeating the full context
- [x] When the internet is disconnected, SAM automatically uses the local model and informs the user

### Memory (Verified M2)
- [x] After the user says "My COA notes are in D:/Notes/COA — remember this", the process is restarted, and the user asks "Where are my COA notes?", SAM answers correctly
- [x] SAM can answer fuzzy queries ("project folder", "my notes") by retrieving semantically similar stored facts

### Computer Control (Target M3)
- [ ] "Move the latest PDF from Downloads to my COA folder" executes correctly end-to-end: SAM finds the file, identifies the destination, moves it, and confirms
- [ ] "Open Spotify and play my playlist" opens the app and triggers playback
- [ ] "Run this Python file" executes a specified file in the terminal and reports the output

### Vision (Target M4)
- [ ] With a visible error dialog on screen, "SAM what does this error say?" returns the error text correctly
- [ ] After SAM performs an action (e.g., opens a file), it can confirm via screenshot that the action succeeded

### Task Planner (Target M5)
- [ ] "SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do" results in SAM producing a structured plan and executing it step by step
- [ ] If a step fails (e.g., file not found), SAM reports the failure and attempts an alternative rather than crashing

### Permission System (Target M3)
- [ ] "Delete all files in Downloads" triggers a confirmation prompt listing what will be deleted before any action is taken
- [ ] Without confirmation, no deletion occurs
- [ ] Low-risk commands (open Chrome, change volume) execute without any confirmation prompt

### Personality (Verified M1)
- [x] CPU usage query returns a response with at least mild personality, not just a raw number
- [x] Task execution responses are concise and professional, not chatty

## Follow-up — 2026-10-06T11:45:56Z

Milestone 3 (Windows Control Suite & Safety Guard) is fully complete, verified (all 281 unit tests + 130 E2E control/safety tests pass), and pushed to GitHub main (commit 83226f2).

Please proceed immediately with Milestone 4 (Screen Vision & Multimodal Inspection):
- Implement src/sam/vision/ adhering to IVisionEngine (capture_screen, analyze_screen, verify_action_result).
- Support multimodal vision using FreeLLMAPI (http://127.0.0.1:31415/v1) with fallback to local Ollama vision.
- Bind production VisionEngine into tests/e2e/harness.py.
- Author comprehensive unit tests in tests/unit/test_vision.py.
- Validate against Tier 1 and Tier 2 vision test suites.

## Follow-up — 2026-10-06T12:18:56Z

Milestones 5 (Planner & Router), 6 (Voice Interface & Wake Word), and 7 (Full System Integration & Runner CLI) are implemented, verified (678/678 tests pass: 331 unit + 347 E2E), committed (d95cf6d), and pushed to origin main. Zero leaked keys verified.

## Follow-up — 2026-10-06T12:27:18Z

=== VICTORY AUDIT REPORT ===
VERDICT: VICTORY CONFIRMED

PHASE A — TIMELINE: PASS (Commit d95cf6d on main, clean working tree, synced with origin/main)
PHASE B — INTEGRITY CHECK: PASS (Zero mocks/stubs/fakes in src/sam/, zero leaked secrets, genuine algorithms across all subsystems)
PHASE C — INDEPENDENT TEST EXECUTION: PASS (347/347 E2E tests passed 100%, 357 unit tests passed, live CLI execution verified)
REQUIREMENTS & ACCEPTANCE CRITERIA: R1-R8 ALL PASS
Report: .agents/teamwork/victory_auditor_1/handoff.md
