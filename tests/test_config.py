"""Test configuration and settings."""

import pytest
from mcp_gateway.core.config import Settings


class TestSettings:
    """Test configuration settings."""
    
    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()
        
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 8000
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_FORMAT == "json"
    
    def test_settings_from_env(self, monkeypatch):
        """Test that settings can be loaded from environment variables."""
        monkeypatch.setenv("HOST", "0.0.0.0")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("DEBUG", "true")
        
        settings = Settings()
        
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 9000
        assert settings.DEBUG is True
