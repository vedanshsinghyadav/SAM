"""
SAM Configuration Management Engine.
Provides tiered configuration for Ollama models, network settings,
Windows file paths, safety rules, voice interface, and personality.
Supports defaults -> JSON/YAML -> SAM_* env vars -> runtime overrides.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field

from src.sam.common.types import CompatibleBaseModel

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ============================================================================
# Sub-Configuration Models
# ============================================================================

class OllamaConfig(CompatibleBaseModel):
    """Configuration for Ollama local and cloud inference."""
    url: str = Field(default="http://localhost:11434")
    cloud_model: str = Field(default="gemma4:cloud")
    local_model: str = Field(default="qwen2.5:7b")
    vision_model: str = Field(default="llama3.2-vision")
    embedding_model: str = Field(default="nomic-embed-text")
    request_timeout: float = Field(default=30.0)
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=2048)


class NetworkConfig(CompatibleBaseModel):
    """Configuration for network probing and offline failover."""
    probe_host: str = Field(default="8.8.8.8")
    probe_port: int = Field(default=53)
    probe_timeout: float = Field(default=1.0)
    cache_ttl: float = Field(default=3.0)
    monitor_interval: float = Field(default=5.0)


class PathConfig(CompatibleBaseModel):
    """Configuration for filesystem locations and working directories."""
    data_dir: str = Field(default="data")
    memory_db_path: str = Field(default="data/sam_memory.db")
    notes_default_dir: str = Field(default="D:/Notes")
    downloads_dir: str = Field(default_factory=lambda: str(Path.home() / "Downloads"))
    screenshots_dir: str = Field(default="data/screenshots")
    logs_dir: str = Field(default="data/logs")


class SafetyConfig(CompatibleBaseModel):
    """Configuration for tri-tier risk classification and confirmation gates."""
    confirmation_timeout: float = Field(default=15.0)
    confirmation_keyword: str = Field(default="Confirm")
    strict_mode: bool = Field(default=True)
    allow_terminal_execution: bool = Field(default=True)
    terminal_timeout_seconds: int = Field(default=30)


class VoiceConfig(CompatibleBaseModel):
    """Configuration for audio capture, wake word, STT, and TTS."""
    wake_word: str = Field(default="Hey SAM")
    wake_word_model_path: str = Field(default="models/vosk-model-small-en-us")
    stt_model: str = Field(default="base.en")
    stt_compute_type: str = Field(default="int8")
    online_tts_voice: str = Field(default="en-GB-RyanNeural")
    offline_tts_voice: str = Field(default="David")
    interrupt_timeout_ms: int = Field(default=1000)
    sample_rate: int = Field(default=16000)
    silence_threshold_seconds: float = Field(default=1.2)


class PersonalityConfig(CompatibleBaseModel):
    """Configuration for SAM persona and adaptive tone."""
    assistant_name: str = Field(default="SAM")
    default_mode: str = Field(default="casual")
    witty_metrics: bool = Field(default=True)
    british_wit_enabled: bool = Field(default=True)


# ============================================================================
# Root Configuration Model
# ============================================================================

class SamConfig(CompatibleBaseModel):
    """Root configuration aggregator for SAM."""
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    personality: PersonalityConfig = Field(default_factory=PersonalityConfig)

    def to_json(self, indent: int = 2) -> str:
        """Serialize configuration to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save configuration to JSON or YAML based on file extension."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()

        if ext in (".yaml", ".yml") and HAS_YAML:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.to_json())

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "SamConfig":
        """Load configuration from JSON or YAML file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        content = path.read_text(encoding="utf-8")
        ext = path.suffix.lower()

        if ext in (".yaml", ".yml") and HAS_YAML:
            data = yaml.safe_load(content) or {}
        else:
            data = json.loads(content)

        return cls.from_dict(data)

    def apply_env_overrides(self) -> None:
        """Apply environment variables prefixed with SAM_* to override settings."""
        # Ollama overrides
        if "SAM_OLLAMA_URL" in os.environ:
            self.ollama.url = os.environ["SAM_OLLAMA_URL"]
        if "SAM_CLOUD_MODEL" in os.environ:
            self.ollama.cloud_model = os.environ["SAM_CLOUD_MODEL"]
        if "SAM_LOCAL_MODEL" in os.environ:
            self.ollama.local_model = os.environ["SAM_LOCAL_MODEL"]
        if "SAM_VISION_MODEL" in os.environ:
            self.ollama.vision_model = os.environ["SAM_VISION_MODEL"]

        # Network overrides
        if "SAM_PROBE_HOST" in os.environ:
            self.network.probe_host = os.environ["SAM_PROBE_HOST"]
        if "SAM_PROBE_PORT" in os.environ:
            try:
                self.network.probe_port = int(os.environ["SAM_PROBE_PORT"])
            except ValueError:
                pass

        # Path overrides
        if "SAM_MEMORY_DB" in os.environ:
            self.paths.memory_db_path = os.environ["SAM_MEMORY_DB"]
        if "SAM_DOWNLOADS_DIR" in os.environ:
            self.paths.downloads_dir = os.environ["SAM_DOWNLOADS_DIR"]

        # Safety overrides
        if "SAM_STRICT_SAFETY" in os.environ:
            self.safety.strict_mode = os.environ["SAM_STRICT_SAFETY"].lower() in ("1", "true", "yes")

        # Personality & Voice overrides
        if "SAM_TTS_VOICE" in os.environ:
            self.voice.online_tts_voice = os.environ["SAM_TTS_VOICE"]
        if "SAM_DEFAULT_MODE" in os.environ:
            self.personality.default_mode = os.environ["SAM_DEFAULT_MODE"]


# ============================================================================
# Global Singleton Accessor
# ============================================================================

_CONFIG_LOCK = threading.Lock()
_GLOBAL_CONFIG: Optional[SamConfig] = None


def get_config(reload: bool = False, config_path: Optional[Union[str, Path]] = None) -> SamConfig:
    """
    Retrieve global SamConfig singleton.
    Loads from file (if found), applies environment variables, and caches.
    """
    global _GLOBAL_CONFIG
    with _CONFIG_LOCK:
        if _GLOBAL_CONFIG is None or reload:
            config = None
            # Search order for config file
            search_paths = []
            if config_path:
                search_paths.append(Path(config_path))
            search_paths.extend([
                Path("sam_config.yaml"),
                Path("sam_config.json"),
                Path.home() / ".sam" / "config.yaml",
                Path.home() / ".sam" / "config.json"
            ])

            for p in search_paths:
                if p.exists():
                    try:
                        config = SamConfig.load_from_file(p)
                        break
                    except Exception:
                        pass

            if config is None:
                config = SamConfig()

            config.apply_env_overrides()
            _GLOBAL_CONFIG = config

        return _GLOBAL_CONFIG


def set_config(config: SamConfig) -> None:
    """Explicitly assign global SamConfig singleton."""
    global _GLOBAL_CONFIG
    with _CONFIG_LOCK:
        _GLOBAL_CONFIG = config


def reset_config() -> None:
    """Reset global configuration singleton to uninitialized state."""
    global _GLOBAL_CONFIG
    with _CONFIG_LOCK:
        _GLOBAL_CONFIG = None
