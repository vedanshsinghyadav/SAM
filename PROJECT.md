# Project: SAM (JARVIS-Style Local AI Assistant for Windows)

## Architecture

SAM is a modular, local-first intelligent assistant for Windows designed with a decoupled pipeline architecture:
- **Common & Protocols (`src/sam/common/`)**: Shared types, Pydantic schemas, risk definitions, offline detector, event emitter.
- **AI Brain & Context Engine (`src/sam/brain/`)**: Multilingual intent understanding, multi-turn session context tracker (`ConversationContext`), structured decision schema, hybrid Ollama backend (`gemma4:cloud` with auto-failover to local `qwen2.5:7b`).
- **Personality Engine (`src/sam/personality/`)**: Context-aware tone adapter (witty/casual vs. concise/professional), stable persona across speech and text.
- **Memory Engine (`src/sam/memory/`)**: ACID-compliant SQLite storage with NumPy vector cosine similarity embeddings, persistent across restarts, fuzzy semantic retrieval.
- **Computer Control (`src/sam/control/`)**: Windows automation suite (AppOpener, window management, atomic filesystem operations, media/volume/brightness controls, sandboxed PowerShell/Python runner, system toast reader).
- **Safety & Permissions (`src/sam/safety/`)**: Tri-tier risk classifier (`LOW`, `MEDIUM`, `HIGH`). Immediate execution for Low, spoken/text announcement for Medium, strict blocking confirmation guard for High.
- **Vision Engine (`src/sam/vision/`)**: Ultra-fast desktop screenshot capture via `mss`, Ollama multimodal vision analysis (`llama3.2-vision` / `moondream`), action outcome verification.
- **Task Planner & Router (`src/sam/planner/`)**: Complex goal decomposition into atomic verified sub-tasks, multi-tool router, closed-loop verification, dynamic replanning on step failure.
- **Voice Interface (`src/sam/voice/`)**: Real-time audio stream pipeline (`sounddevice`), offline wake word detector ("Hey SAM" via `vosk`), STT engine (`faster-whisper`), TTS engine (`edge-tts` / `pyttsx3`), instant barge-in interrupt engine (`pygame.mixer` halted < 1s).
- **Application Orchestration (`src/sam/main.py`, `src/sam/cli.py`)**: Unified CLI and daemon runner coordinating asynchronous event loops, background threads, and graceful shutdown.

```
                              [ User Input ]
                       /                            \
           [ Spoken Audio: Mic ]               [ Text: CLI / Stdin ]
                     |                                   |
         [ Wake Word: "Hey SAM" ]                        |
                     |                                   |
           [ STT: Transcribe ]                           |
                     \                                  /
                      -----> [ Conversation Context ] <---
                                      |
                             [ Brain Reasoner ] <---> [ Long-Term Memory ]
                                      |
                     [ Structured Decision / Plan ]
                                      |
                       [ Task Planner & Tool Router ]
                                      |
                        [ Safety & Permission Guard ]
                       /              |              \
             [ LOW Risk ]      [ MEDIUM Risk ]    [ HIGH Risk ]
                  |                   |                  |
              Immediate           Announce            Mandatory
              Execute             & Execute          Confirmation
                      \               |              /
                       -----> [ Tool Execution ] <----
                                      |
                     [ Control / Vision / Terminal ]
                                      |
                      [ Step Verification & Recovery ]
                                      |
                       [ Personality Tone Adapter ]
                                      |
                      [ Output: Text + TTS Audio ]
                       (Interruption Handler: < 1s)
```

---

## Feature Inventory

Every feature from the specification survey is cataloged and assigned to a specific milestone:

| # | Feature ID | Feature Name | Description | Milestone | Source |
|---|------------|--------------|-------------|-----------|--------|
| 1 | FEAT-VOICE-001 | Wake Word Detection | Always-listening detector for "Hey SAM" (<2s activation) | M6 | ORIGINAL_REQUEST lines 15, 44 |
| 2 | FEAT-VOICE-002 | STT Transcription | Speech-to-text supporting English and Hinglish | M6 | ORIGINAL_REQUEST lines 16, 45, 50 |
| 3 | FEAT-VOICE-003 | TTS Audio Synthesis | Spoken audio replies using natural voice | M6 | ORIGINAL_REQUEST lines 16, 46 |
| 4 | FEAT-VOICE-004 | Audio Barge-in Interrupt | Halts TTS playback within 1.0s on "SAM stop" / user speech | M6 | ORIGINAL_REQUEST lines 16, 47 |
| 5 | FEAT-VOICE-005 | Dual-Mode Text Interface | Interactive text prompt mode alongside voice | M6 | ORIGINAL_REQUEST line 16 |
| 6 | FEAT-BRAIN-001 | Multilingual Intent Parser | Understands natural language & Hinglish intents ("Internet chalana hai") | M1 | ORIGINAL_REQUEST lines 19, 50 |
| 7 | FEAT-BRAIN-002 | Multi-Turn Context Tracker | Retains active app, website, task, subject across turns | M1 | ORIGINAL_REQUEST lines 19, 51 |
| 8 | FEAT-BRAIN-003 | Structured Decision Schema | Generates typed JSON replies or tool calls | M1 | ORIGINAL_REQUEST line 19 |
| 9 | FEAT-BRAIN-004 | Hybrid LLM & Offline Fallback| Uses Ollama cloud (gemma4:cloud) with local qwen2.5:7b fallback | M1 | ORIGINAL_REQUEST lines 19, 52 |
| 10 | FEAT-MEM-001 | Persistent Knowledge Store | Stores user facts and preferences persisting across process restarts | M2 | ORIGINAL_REQUEST lines 22, 55 |
| 11 | FEAT-MEM-002 | Semantic Vector Retrieval | Fuzzy vector retrieval (e.g. "project folder" -> exact path) | M2 | ORIGINAL_REQUEST lines 22, 56 |
| 12 | FEAT-CTRL-001 | Windows App Lifecycle | Launches apps by name and terminates running processes | M3 | ORIGINAL_REQUEST lines 25, 50, 60 |
| 13 | FEAT-CTRL-002 | Windows Window Manager | Focuses, maximizes, minimizes, and manages desktop windows | M3 | ORIGINAL_REQUEST line 25 |
| 14 | FEAT-CTRL-003 | File Automation Engine | Find, create, move, copy, rename, delete files & folders | M3 | ORIGINAL_REQUEST lines 25, 59 |
| 15 | FEAT-CTRL-004 | Desktop Screen Capture | Captures full desktop or specific windows into image buffer | M4 | ORIGINAL_REQUEST lines 25, 28 |
| 16 | FEAT-CTRL-005 | Volume & Brightness Control | Queries & adjusts master volume and monitor brightness | M3 | ORIGINAL_REQUEST lines 25, 74 |
| 17 | FEAT-CTRL-006 | Media Playback Controller | Triggers play/pause/track controls on Windows & Spotify | M3 | ORIGINAL_REQUEST lines 25, 60 |
| 18 | FEAT-CTRL-007 | Terminal Command Runner | Executes PowerShell commands & Python scripts with timeouts | M3 | ORIGINAL_REQUEST lines 25, 61 |
| 19 | FEAT-CTRL-008 | Windows Notification Reader | Reads active or recent Windows notifications | M3 | ORIGINAL_REQUEST line 25 |
| 20 | FEAT-CTRL-009 | Atomic Sequential Verify | Executes multi-step actions with atomic post-step verification | M5 | ORIGINAL_REQUEST lines 25, 59 |
| 21 | FEAT-VIS-001 | Screen Understanding & QA | Analyzes screen text and errors via multimodal vision model | M4 | ORIGINAL_REQUEST lines 28, 64 |
| 22 | FEAT-VIS-002 | Visual Action Verifier | Visually verifies that a UI action succeeded via screenshot | M4 | ORIGINAL_REQUEST lines 28, 65 |
| 23 | FEAT-PLAN-001 | Goal Decomposition Planner | Decomposes complex goals into ordered atomic plan steps | M5 | ORIGINAL_REQUEST lines 31, 68 |
| 24 | FEAT-PLAN-002 | Dynamic Multi-Tool Router | Dispatches sub-tasks to appropriate tools | M5 | ORIGINAL_REQUEST line 31 |
| 25 | FEAT-PLAN-003 | Plan Recovery & Resilience | Catches step failures, adapts plan, and retries alternatives | M5 | ORIGINAL_REQUEST lines 31, 69 |
| 26 | FEAT-SAFE-001 | Tri-Tier Risk Classification | Categorizes actions into Low, Medium, and High risk | M3 | ORIGINAL_REQUEST lines 34, 72-74 |
| 27 | FEAT-SAFE-002 | Low-Risk Immediate Dispatch | Executes low-risk actions without user confirmation | M3 | ORIGINAL_REQUEST lines 34, 74 |
| 28 | FEAT-SAFE-003 | Medium-Risk Announcement | Announces medium-risk actions before execution | M3 | ORIGINAL_REQUEST line 34 |
| 29 | FEAT-SAFE-004 | High-Risk Confirmation Guard | Strictly blocks high-risk actions until explicit user confirmation | M3 | ORIGINAL_REQUEST lines 34, 72, 73 |
| 30 | FEAT-PERS-001 | Context-Adaptive Dual-Tone | Witty/casual for conversation, concise/professional for tasks | M1 | ORIGINAL_REQUEST lines 37, 77, 78 |
| 31 | FEAT-PERS-002 | Modality-Invariant Persona | Maintains identical personality across voice and text modes | M1 | ORIGINAL_REQUEST line 37 |

*Cross-Check Verification: Exactly 31 features cataloged. 100% of features have an assigned milestone.*

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Foundation, Brain & Personality | Common types, Offline detector, LLM Brain (`gemma4:cloud` / `qwen2.5:7b`), Context tracking, Personality tone engine (FEAT-BRAIN-001..004, FEAT-PERS-001..002) | none | PLANNED |
| M2 | Persistent Memory Engine | SQLite persistence, Vector embeddings, Cosine similarity search, Cross-restart recall (FEAT-MEM-001..002) | M1 contracts | PLANNED |
| M3 | Windows Control Suite & Safety Guard | Windows app/window/file/volume/media/terminal automation, Tri-tier safety classifier, Mandatory high-risk confirmation guard (FEAT-CTRL-001..003, 005..008, FEAT-SAFE-001..004) | M1 contracts | PLANNED |
| M4 | Screen Vision & Visual Perception | MSS screenshot capture, Multimodal screen QA, Visual action verification (FEAT-CTRL-004, FEAT-VIS-001..002) | M1, M3 contracts | PLANNED |
| M5 | Autonomous Task Planner & Tool Router | Goal decomposition, Multi-tool routing, Atomic sequential verification, Self-recovery & replanning (FEAT-CTRL-009, FEAT-PLAN-001..003) | M1, M2, M3, M4 | PLANNED |
| M6 | Voice Interface & Barge-in Audio Loop | Audio capture (`sounddevice`), Wake word ("Hey SAM"), STT, TTS, Instant interrupt (<1s on "SAM stop"), Text CLI fallback (FEAT-VOICE-001..005) | M1 | PLANNED |
| M7 | Integration, 100% E2E Pass & Hardening | Full daemon & CLI integration (`src/sam/main.py`), 100% E2E test pass (Tiers 1-4), Adversarial hardening (Tier 5) | M1-M6, E2E Test Suite Ready | PLANNED |

*In parallel: **E2E Testing Track** designs and implements the opaque-box test suite (`tests/e2e/`), publishing `TEST_READY.md`.*

---

## Interface Contracts

### Common Data Contracts (`src/sam/common/types.py`)

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ActionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CANCELLED = "CANCELLED"

class ToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Optional[RiskLevel] = None

class BrainDecision(BaseModel):
    decision_type: str  # "reply" | "tool_call" | "plan"
    reply_text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    plan_goal: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None

class ConversationTurn(BaseModel):
    user_input: str
    agent_response: str
    timestamp: float

class ActiveContext(BaseModel):
    active_app: Optional[str] = None
    current_url: Optional[str] = None
    active_task: Optional[str] = None
    active_subject: Optional[str] = None
    history: List[ConversationTurn] = Field(default_factory=list)
```

### Brain Interface (`src/sam/brain/interface.py`)

```python
from typing import Protocol
from src.sam.common.types import BrainDecision, ActiveContext

class IBrain(Protocol):
    def process_input(self, user_text: str, context: ActiveContext) -> BrainDecision:
        """Process user input with context, return structured decision."""
        ...

    def is_online(self) -> bool:
        """Check whether online connectivity is active."""
        ...

    def get_current_model(self) -> str:
        """Return currently active model name."""
        ...
```

### Memory Interface (`src/sam/memory/interface.py`)

```python
from typing import List, Protocol
from pydantic import BaseModel

class MemoryFact(BaseModel):
    id: Optional[int] = None
    content: str
    category: str
    metadata: dict = {}
    timestamp: float

class MemorySearchResult(BaseModel):
    fact: MemoryFact
    similarity_score: float

class IMemoryEngine(Protocol):
    def store_fact(self, content: str, category: str = "general", metadata: dict = {}) -> int:
        """Store fact with persistent vector embedding."""
        ...

    def search_facts(self, query: str, top_k: int = 5, min_score: float = 0.4) -> List[MemorySearchResult]:
        """Perform fuzzy semantic search over stored facts."""
        ...

    def retrieve_exact(self, key: str) -> Optional[str]:
        """Retrieve exact key-value preference."""
        ...
```

### Safety Guard Interface (`src/sam/safety/interface.py`)

```python
from typing import Protocol, Tuple
from src.sam.common.types import ToolCall, RiskLevel

class ISafetyGuard(Protocol):
    def classify_risk(self, tool_call: ToolCall) -> RiskLevel:
        """Classify tool risk level into LOW, MEDIUM, HIGH."""
        ...

    def authorize(self, tool_call: ToolCall, user_confirmed: bool = False) -> Tuple[bool, str]:
        """Verify if action can proceed. Returns (is_authorized, reason_or_prompt)."""
        ...
```

### Computer Controller Interface (`src/sam/control/interface.py`)

```python
from typing import Any, Dict, List, Protocol
from pydantic import BaseModel

class ExecutionResult(BaseModel):
    success: bool
    output: Any
    error_message: Optional[str] = None
    verification_passed: bool = True

class IComputerController(Protocol):
    def open_app(self, app_name: str) -> ExecutionResult: ...
    def close_app(self, process_or_name: str) -> ExecutionResult: ...
    def manage_window(self, action: str, window_title: Optional[str] = None) -> ExecutionResult: ...
    def file_action(self, action: str, **kwargs) -> ExecutionResult: ...
    def control_volume(self, level: Optional[int] = None, delta: Optional[int] = None) -> ExecutionResult: ...
    def control_brightness(self, level: Optional[int] = None) -> ExecutionResult: ...
    def control_media(self, command: str) -> ExecutionResult: ...
    def run_terminal(self, command: str, shell: str = "powershell", timeout: int = 30) -> ExecutionResult: ...
    def get_system_stats(self) -> Dict[str, Any]: ...
```

### Vision Interface (`src/sam/vision/interface.py`)

```python
from typing import Protocol
from pydantic import BaseModel

class VisionAnalysis(BaseModel):
    extracted_text: str
    description: str
    error_detected: bool
    error_message: Optional[str] = None

class IVisionEngine(Protocol):
    def capture_screen(self, output_path: Optional[str] = None) -> str: ...
    def inspect_screen(self, query: str) -> VisionAnalysis: ...
    def verify_ui_state(self, expected_description: str) -> bool: ...
```

### Task Planner Interface (`src/sam/planner/interface.py`)

```python
from typing import List, Protocol
from pydantic import BaseModel
from src.sam.common.types import ToolCall

class PlanStep(BaseModel):
    step_id: int
    description: str
    tool_call: ToolCall
    verification_criteria: str
    completed: bool = False
    result: Optional[str] = None

class Plan(BaseModel):
    goal: str
    steps: List[PlanStep]
    current_step_index: int = 0
    is_completed: bool = False

class ITaskPlanner(Protocol):
    def create_plan(self, goal: str) -> Plan: ...
    def execute_step(self, plan: Plan, step_index: int) -> PlanStep: ...
    def recover_plan(self, plan: Plan, failed_step_index: int, error: str) -> Plan: ...
```

### Voice Interface (`src/sam/voice/interface.py`)

```python
from typing import Callable, Protocol

class IVoiceInterface(Protocol):
    def start_listening(self, wake_word_callback: Callable[[], None]) -> None: ...
    def listen_utterance(self) -> str: ...
    def speak(self, text: str, on_interrupt: Optional[Callable[[], None]] = None) -> None: ...
    def stop_speaking(self) -> None: ...
```

---

## Code Layout
```
sam/
├── PROJECT.md                      # Project master architecture & milestone registry
├── requirements.txt                # Pinned production dependencies
├── setup.py / pyproject.toml       # Package metadata
├── src\
│   └── sam\
│       ├── __init__.py
│       ├── main.py                 # Main entry point daemon
│       ├── cli.py                  # Interactive CLI interface
│       ├── common\
│       │   ├── __init__.py
│       │   ├── types.py            # Pydantic schemas & enums
│       │   ├── network.py          # Fast sub-ms offline TCP detector
│       │   └── config.py           # Configuration loader
│       ├── brain\
│       │   ├── __init__.py
│       │   ├── interface.py        # IBrain protocol
│       │   ├── context.py          # Multi-turn context tracker
│       │   ├── intent.py           # Multilingual intent parser
│       │   └── ollama_client.py    # Hybrid cloud/local Ollama reasoning engine
│       ├── personality\
│       │   ├── __init__.py
│       │   ├── interface.py        # IPersonality protocol
│       │   └── adapter.py          # Tone & personality adapter
│       ├── memory\
│       │   ├── __init__.py
│       │   ├── interface.py        # IMemoryEngine protocol
│       │   ├── store.py            # SQLite persistent knowledge store
│       │   └── vector.py           # NumPy cosine similarity vector search
│       ├── control\
│       │   ├── __init__.py
│       │   ├── interface.py        # IComputerController protocol
│       │   ├── app.py              # Windows app launcher & taskkill
│       │   ├── window.py           # Desktop window management
│       │   ├── file.py             # File system atomic operations
│       │   ├── system.py           # Volume, brightness, media & system stats
│       │   └── terminal.py         # Sandboxed PowerShell & Python runner
│       ├── safety\
│       │   ├── __init__.py
│       │   ├── interface.py        # ISafetyGuard protocol
│       │   └── guard.py            # Tri-tier risk classifier & confirmation guard
│       ├── vision\
│       │   ├── __init__.py
│       │   ├── interface.py        # IVisionEngine protocol
│       │   ├── capture.py          # Fast mss screen capture
│       │   └── analyzer.py         # Multimodal vision inspection & UI verifier
│       ├── planner\
│       │   ├── __init__.py
│       │   ├── interface.py        # ITaskPlanner protocol
│       │   ├── planner.py          # Goal decomposition & tool router
│       │   └── recovery.py         # Dynamic replanning & error recovery
│       └── voice\
│           ├── __init__.py
│           ├── interface.py        # IVoiceInterface protocol
│           ├── wake_word.py        # "Hey SAM" Vosk detector (<2s)
│           ├── stt.py              # Speech-to-text transcriber
│           ├── tts.py              # Text-to-speech audio synthesizer
│           └── interrupt.py        # Barge-in interrupt controller (<1s audio halt)
├── tests\
│   ├── unit\                       # Implementation track unit tests
│   └── e2e\                        # Opaque-box E2E test suite (Tiers 1-5)
│       ├── runner.py               # E2E test runner
│       ├── tier1_features\         # Tier 1: Single feature coverage (>= 5 per feat)
│       ├── tier2_boundaries\       # Tier 2: Boundary & corner cases (>= 5 per feat)
│       ├── tier3_interactions\     # Tier 3: Cross-feature pairwise interactions
│       ├── tier4_scenarios\        # Tier 4: Real-world complex application workloads
│       └── tier5_adversarial\      # Tier 5: White-box adversarial hardening
└── data\
    └── sam_memory.db               # Default local database location
```
