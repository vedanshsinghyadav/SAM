"""
Unit tests for src/sam/common/config.py.
Validates hierarchical configuration cascade: defaults, JSON/YAML persistence,
SAM_* environment overrides, and singleton management.
"""

import json
import os
from pathlib import Path
import tempfile
import pytest

from src.sam.common.config import (
    SamConfig,
    OllamaConfig,
    get_config,
    set_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def cleanup_config_singleton():
    reset_config()
    yield
    reset_config()


class TestSamConfigDefaults:
    def test_default_models_and_urls(self):
        cfg = SamConfig()
        assert cfg.ollama.url == "http://localhost:11434"
        assert cfg.ollama.cloud_model == "gemma4:cloud"
        assert cfg.ollama.local_model == "qwen2.5:7b"
        assert cfg.ollama.vision_model == "llama3.2-vision"

    def test_default_paths(self):
        cfg = SamConfig()
        assert "sam_memory.db" in cfg.paths.memory_db_path
        assert cfg.paths.notes_default_dir == "D:/Notes"

    def test_default_safety_and_personality(self):
        cfg = SamConfig()
        assert cfg.safety.confirmation_timeout == 15.0
        assert cfg.safety.confirmation_keyword == "Confirm"
        assert cfg.personality.assistant_name == "SAM"
        assert cfg.personality.default_mode == "casual"


class TestConfigPersistence:
    def test_json_roundtrip(self):
        cfg = SamConfig()
        cfg.ollama.local_model = "custom-qwen"
        json_str = cfg.to_json()

        data = json.loads(json_str)
        assert data["ollama"]["local_model"] == "custom-qwen"

        loaded = SamConfig.from_dict(data)
        assert loaded.ollama.local_model == "custom-qwen"

    def test_file_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test_config.json"
            cfg = SamConfig()
            cfg.voice.online_tts_voice = "custom-voice"
            cfg.save_to_file(file_path)

            assert file_path.exists()
            loaded = SamConfig.load_from_file(file_path)
            assert loaded.voice.online_tts_voice == "custom-voice"


class TestEnvOverrides:
    def test_apply_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SAM_OLLAMA_URL", "http://192.168.1.50:11434")
        monkeypatch.setenv("SAM_CLOUD_MODEL", "my-cloud-llm")
        monkeypatch.setenv("SAM_LOCAL_MODEL", "my-local-llm")
        monkeypatch.setenv("SAM_MEMORY_DB", "custom_dir/mem.db")
        monkeypatch.setenv("SAM_STRICT_SAFETY", "false")

        cfg = SamConfig()
        cfg.apply_env_overrides()

        assert cfg.ollama.url == "http://192.168.1.50:11434"
        assert cfg.ollama.cloud_model == "my-cloud-llm"
        assert cfg.ollama.local_model == "my-local-llm"
        assert cfg.paths.memory_db_path == "custom_dir/mem.db"
        assert cfg.safety.strict_mode is False


class TestConfigSingleton:
    def test_singleton_retrieval_and_reset(self):
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

        custom = SamConfig()
        custom.ollama.local_model = "singleton-override"
        set_config(custom)

        assert get_config().ollama.local_model == "singleton-override"

        reset_config()
        new_cfg = get_config()
        assert new_cfg is not custom
        assert new_cfg.ollama.local_model == "qwen2.5:7b"
