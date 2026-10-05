# Project SAM: End-to-End Testing Infrastructure & Specification

**Document Version**: 1.0.0  
**Author**: `test_writer_e2e_1` (E2E Test Suite Architect)  
**Target System**: Project SAM (JARVIS-Style Local AI Assistant for Windows)  
**Reference Documents**:
- `ORIGINAL_REQUEST.md`: Authoritative User Requirements & Acceptance Criteria
- `PROJECT.md`: Master Architecture, Feature Inventory & Interface Contracts
- `survey_spec.md`: Specification Survey
- `survey_architecture.md`: Architectural Decomposition & Subsystem Lifecycles

---

## 1. Test Philosophy

### 1.1 Opaque-Box E2E Testing Paradigm
The E2E test suite for Project SAM operates under a strict **opaque-box paradigm**:
- Tests interact with the system strictly through **public interfaces**, **CLI entrypoints**, **observable operating system side effects** (filesystem modifications, simulated audio buffers, window events), and **public interface contracts** defined in `PROJECT.md`.
- Internal implementation details of modules are intentionally opaque to tests. Tests do not inspect private attributes or internal helper methods, ensuring that refactoring or backend engine modifications (e.g., swapping STT backends or vector indices) will not break the test suite as long as the contract is preserved.

### 1.2 Progressive Testability & Decoupled Execution
Under the Dual-Track Project Pattern, the E2E testing infrastructure is developed concurrently with the implementation milestones (M1–M6):
- The test harness (`tests/e2e/harness.py`) implements a **dynamic contract-binding layer**. If `src.sam` modules are installed or present in `PYTHONPATH`, the test suite dynamically exercises the live production code.
- If dependencies or hardware devices are unavailable in headless test environments (e.g., no physical microphone, no DDC/CI monitor brightness hardware, no active Ollama server), the harness provides high-fidelity, contract-conforming mockable environment hooks.
- This ensures 100% progressive testability: tests are self-contained, isolated, executable immediately, and will validate the production code without modification once each milestone completes.

### 1.3 Authoritative Output Derivation
Every test case derives its expected output from explicit authoritative specifications:
1. **Direct Acceptance Criteria**: Specified in `ORIGINAL_REQUEST.md` (lines 43–79), such as barge-in audio cutoffs under 1.0s, high-risk deletion blockage without explicit "Confirm", context retention ("Open Chrome" -> "Go to YouTube" -> "Search Gate Smashers"), and cross-restart memory recall.
2. **Interface Contracts**: Data schemas defined in `PROJECT.md` (`RiskLevel`, `BrainDecision`, `ActiveContext`, `MemoryFact`, `ExecutionResult`, `Plan`, `PlanStep`).
3. **Deterministic State Modeling**: For non-deterministic outputs (timestamps, random seeds, temporary file paths), tests assert on semantic invariants, structured JSON fields, and regex matches rather than brittle literal equality.

### 1.4 Adversarial Verification & Integrity
In addition to happy-path execution, the test suite subjects the system to adversarial verification:
- **Encoding & Escaping Integrity**: Testing quotes, backslashes, UTF-8 Hinglish text (`"Internet chalana hai"`, `"Browser kholo"`), control characters, and special shell characters.
- **Resource Stress & Boundary Limits**: Empty strings, nonexistent paths, file locks, infinite execution timeouts, zero volume/brightness, out-of-range bounds.
- **Strict Permission Barriers**: Verifying that zero high-risk actions proceed when confirmation is missing, blank, or rejected.

---

## 2. Feature Inventory Matrix (31 Features)

Every feature cataloged in `PROJECT.md` is covered across Tier 1 (Coverage), Tier 2 (Boundaries), Tier 3 (Interactions), and Tier 4 (Real-World Scenarios).

| # | Feature ID | Feature Name | Milestone | Tier 1 Tests | Tier 2 Tests | Tier 3 & 4 Verification |
|---|------------|--------------|-----------|--------------|--------------|--------------------------|
| 1 | FEAT-VOICE-001 | Wake Word Detection | M6 | >= 5 | >= 5 | Scenarios 1, 14 |
| 2 | FEAT-VOICE-002 | STT Transcription | M6 | >= 5 | >= 5 | Scenarios 1, 3, 4 |
| 3 | FEAT-VOICE-003 | TTS Audio Synthesis | M6 | >= 5 | >= 5 | Scenarios 1, 15 |
| 4 | FEAT-VOICE-004 | Audio Barge-in Interrupt | M6 | >= 5 | >= 5 | Scenario 7 |
| 5 | FEAT-VOICE-005 | Dual-Mode Text Interface | M6 | >= 5 | >= 5 | Scenario 16 |
| 6 | FEAT-BRAIN-001 | Multilingual Intent Parser | M1 | >= 5 | >= 5 | Scenarios 3, 8 |
| 7 | FEAT-BRAIN-002 | Multi-Turn Context Tracker | M1 | >= 5 | >= 5 | Scenario 4 |
| 8 | FEAT-BRAIN-003 | Structured Decision Schema | M1 | >= 5 | >= 5 | Scenarios 3, 5, 8 |
| 9 | FEAT-BRAIN-004 | Hybrid LLM & Offline Fallback | M1 | >= 5 | >= 5 | Scenario 6 |
| 10 | FEAT-MEM-001 | Persistent Knowledge Store | M2 | >= 5 | >= 5 | Scenario 11 |
| 11 | FEAT-MEM-002 | Semantic Vector Retrieval | M2 | >= 5 | >= 5 | Scenario 12 |
| 12 | FEAT-CTRL-001 | Windows App Lifecycle | M3 | >= 5 | >= 5 | Scenarios 3, 8 |
| 13 | FEAT-CTRL-002 | Windows Window Manager | M3 | >= 5 | >= 5 | Scenario 10 |
| 14 | FEAT-CTRL-003 | File Automation Engine | M3 | >= 5 | >= 5 | Scenario 2 |
| 15 | FEAT-CTRL-004 | Desktop Screen Capture | M4 | >= 5 | >= 5 | Scenarios 9, 10 |
| 16 | FEAT-CTRL-005 | Volume & Brightness Control | M3 | >= 5 | >= 5 | Scenario 13 |
| 17 | FEAT-CTRL-006 | Media Playback Controller | M3 | >= 5 | >= 5 | Scenario 8 |
| 18 | FEAT-CTRL-007 | Terminal Command Runner | M3 | >= 5 | >= 5 | Scenario 9 |
| 19 | FEAT-CTRL-008 | Windows Notification Reader | M3 | >= 5 | >= 5 | Interactions |
| 20 | FEAT-CTRL-009 | Atomic Sequential Verify | M5 | >= 5 | >= 5 | Scenarios 1, 2 |
| 21 | FEAT-VIS-001 | Screen Understanding & QA | M4 | >= 5 | >= 5 | Scenario 10 |
| 22 | FEAT-VIS-002 | Visual Action Verifier | M4 | >= 5 | >= 5 | Scenario 10 |
| 23 | FEAT-PLAN-001 | Goal Decomposition Planner | M5 | >= 5 | >= 5 | Scenario 1 |
| 24 | FEAT-PLAN-002 | Dynamic Multi-Tool Router | M5 | >= 5 | >= 5 | Scenario 1 |
| 25 | FEAT-PLAN-003 | Plan Recovery & Resilience | M5 | >= 5 | >= 5 | Scenario 1 |
| 26 | FEAT-SAFE-001 | Tri-Tier Risk Classification | M3 | >= 5 | >= 5 | Scenarios 2, 5, 13 |
| 27 | FEAT-SAFE-002 | Low-Risk Immediate Dispatch | M3 | >= 5 | >= 5 | Scenario 13 |
| 28 | FEAT-SAFE-003 | Medium-Risk Announcement | M3 | >= 5 | >= 5 | Scenario 14 |
| 29 | FEAT-SAFE-004 | High-Risk Confirmation Guard | M3 | >= 5 | >= 5 | Scenario 5 |
| 30 | FEAT-PERS-001 | Context-Adaptive Dual-Tone | M1 | >= 5 | >= 5 | Scenario 15 |
| 31 | FEAT-PERS-002 | Modality-Invariant Persona | M1 | >= 5 | >= 5 | Scenario 16 |

---

## 3. Test Architecture & Directory Structure

```
tests/e2e/
├── __init__.py
├── conftest.py                      # Global pytest fixtures, cleanup & environment hooks
├── fixtures.py                      # Test dataset generators, dummy directories & state mocks
├── harness.py                       # Opaque-box SAM facade & dynamic contract-binding layer
├── runner.py                        # Unified test runner with tier filtering & summary report
├── tier1_features/                  # Tier 1: Single Feature Coverage (>=5 tests per feature)
│   ├── __init__.py
│   ├── test_voice_features.py       # FEAT-VOICE-001..005 (25 tests)
│   ├── test_brain_features.py       # FEAT-BRAIN-001..004 (20 tests)
│   ├── test_memory_features.py      # FEAT-MEM-001..002   (10 tests)
│   ├── test_control_features.py     # FEAT-CTRL-001..009  (45 tests)
│   ├── test_vision_features.py      # FEAT-VIS-001..002   (10 tests)
│   ├── test_planner_features.py     # FEAT-PLAN-001..003  (15 tests)
│   ├── test_safety_features.py      # FEAT-SAFE-001..004  (20 tests)
│   └── test_personality_features.py # FEAT-PERS-001..002  (10 tests)
├── tier2_boundaries/                # Tier 2: Boundary & Corner Cases (>=5 tests per feature)
│   ├── __init__.py
│   ├── test_voice_boundaries.py     # Boundaries for VOICE-001..005 (25 tests)
│   ├── test_brain_boundaries.py     # Boundaries for BRAIN-001..004 (20 tests)
│   ├── test_memory_boundaries.py    # Boundaries for MEM-001..002   (10 tests)
│   ├── test_control_boundaries.py   # Boundaries for CTRL-001..009  (45 tests)
│   ├── test_vision_boundaries.py    # Boundaries for VIS-001..002   (10 tests)
│   ├── test_planner_boundaries.py   # Boundaries for PLAN-001..003  (15 tests)
│   ├── test_safety_boundaries.py    # Boundaries for SAFE-001..004  (20 tests)
│   └── test_personality_boundaries.py # Boundaries for PERS-001..002 (10 tests)
├── tier3_interactions/              # Tier 3: Cross-Feature Interactions
│   ├── __init__.py
│   └── test_cross_feature_interactions.py # Pairwise cross-module combinations (20 tests)
└── tier4_scenarios/                 # Tier 4: Real-World Complex Application Workloads
    ├── __init__.py
    └── test_real_world_scenarios.py       # 16 comprehensive end-to-end user workflows
```

---

## 4. Real-World Application Scenarios (Tier 4)

Derived directly from `ORIGINAL_REQUEST.md` Acceptance Criteria (lines 43–79):

1. **Scenario 1: Complex Exam Prep Decomposition & Recovery** (lines 68–69):  
   User asks: *"SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do"*. SAM decomposes the complex goal into ordered sub-steps, locates notes, checks syllabus, extracts topics, handles missing files via plan recovery, and compiles the result.
2. **Scenario 2: Atomic Sequential File Move with Verification** (lines 59):  
   User asks: *"Move the latest PDF from Downloads to my COA folder"*. SAM scans Downloads, sorts by modification time, verifies target directory, executes atomic move, and verifies target existence.
3. **Scenario 3: Multilingual Hinglish Intent Parsing to App Launch** (lines 50):  
   User variations: `"Open Chrome"`, `"Launch the browser"`, `"Internet chalana hai"`, `"Browser kholo"`. All parse into canonical browser launch decisions without user confusion.
4. **Scenario 4: Multi-Turn Conversation Context Retention** (lines 51):  
   Turn 1: `"Open Chrome"` -> Turn 2: `"Go to YouTube"` -> Turn 3: `"Search Gate Smashers"`. Turn 3 executes YouTube search retaining browser and site context without re-querying the user.
5. **Scenario 5: Mandatory High-Risk Deletion Confirmation Barrier** (lines 72–73):  
   User requests: *"Delete all files in Downloads"*. Safety guard classifies as `HIGH` risk, strictly halts execution, lists affected targets, and executes deletion *only* after explicit `"Confirm"` input. If unconfirmed or rejected, zero files are deleted.
6. **Scenario 6: Transparent Offline Failover on Network Loss** (lines 52):  
   Network detector senses disconnect. SAM switches from cloud LLM (`gemma4:cloud`) to local model (`qwen2.5:7b`), announces the offline mode, and continues answering user prompts.
7. **Scenario 7: Low-Latency Speech Interruption (Barge-in)** (lines 47):  
   While SAM is synthesizing spoken TTS audio, user utters `"SAM stop"` or `"stop"`. TTS audio halts within 1.0 second and the buffer is cleared.
8. **Scenario 8: App Launch & Media Playback Control** (lines 60):  
   User asks: *"Open Spotify and play my playlist"*. SAM launches Spotify process, verifies process readiness, and triggers playback control.
9. **Scenario 9: Sandboxed Terminal Execution & Timeout Guard** (lines 61):  
   User asks: *"Run this Python file"*. Terminal runner executes script, captures stdout/stderr, and terminates infinite loops safely within timeout.
10. **Scenario 10: Screen Capture & Multimodal Visual Error Inspection** (lines 64–65):  
    User asks: *"SAM what does this error say?"*. SAM captures desktop screenshot, passes image to vision model, and extracts the visible error text.
11. **Scenario 11: Cross-Restart Long-Term Memory Recall** (lines 55):  
    Turn 1: *"My COA notes are in D:/Notes/COA — remember this"*. Process restarts (new session instance). User asks: *"Where are my COA notes?"*. SAM retrieves exact stored fact from SQLite knowledge store.
12. **Scenario 12: Semantic Fuzzy Memory Search** (lines 56):  
    User asks fuzzy query: *"Where is my project folder?"*. Vector cosine similarity engine retrieves exact stored path `"D:/Projects/SAM"` despite textual variation.
13. **Scenario 13: Low-Risk Immediate System Control Dispatch** (lines 74):  
    Commands: `"Open Chrome"`, `"Set volume to 50%"`, `"Set brightness to 80%"`. Classified as `LOW` risk; executed immediately without interactive confirmation prompts.
14. **Scenario 14: Medium-Risk Pre-Execution Announcement** (lines 34):  
    Action: Moving files or terminating running apps (`taskkill`). Classified as `MEDIUM` risk; spoken/text announcement emitted prior to action execution.
15. **Scenario 15: Context-Adaptive Personality Dual-Tone** (lines 77–78):  
    Casual query (CPU usage / chit-chat) returns a mildly witty, human response. Task execution outputs concise, professional operational summaries.
16. **Scenario 16: Modality-Invariant Persona Stability** (lines 37):  
    Verifies identical persona traits, tone markers, and stylistic character whether operating in Voice mode (TTS) or Dual Text mode (CLI).

---

## 5. Coverage Thresholds & Quality Gates

| Metric | Target Requirement | Status |
|---|---|---|
| **Feature Coverage** | 100% of 31 cataloged features | Enforced |
| **Tier 1 Tests** | >= 5 test cases per feature (>= 155 tests) | Enforced |
| **Tier 2 Tests** | >= 5 test cases per feature (>= 155 tests) | Enforced |
| **Tier 3 Tests** | >= 20 cross-feature interaction test cases | Enforced |
| **Tier 4 Tests** | >= 16 real-world application scenarios | Enforced |
| **Total Test Count** | >= 346 test cases | Enforced |
| **Runner Exit Code** | `0` on 100% pass | Enforced |
| **Test Execution Time**| < 30 seconds for complete test suite | Enforced |

---

## 6. Test Runner Command

To execute the test suite:
```bash
# Execute full E2E test suite across all 4 tiers:
python tests/e2e/runner.py

# Execute specific tier:
python tests/e2e/runner.py --tier 1
python tests/e2e/runner.py --tier 2
python tests/e2e/runner.py --tier 3
python tests/e2e/runner.py --tier 4

# Or via pytest:
pytest tests/e2e/ -v
```
