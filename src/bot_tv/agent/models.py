from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    name: str
    display_name: str
    rpm_limit: int
    tpm_limit: int
    rpd_limit: int
    enabled: bool


AVAILABLE_MODELS: dict[str, ModelConfig] = {
    "gemini-3.1-flash-lite": ModelConfig(
        "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", 15, 250_000, 500, True
    ),
    "gemini-2.5-flash-lite": ModelConfig(
        "gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", 10, 250_000, 20, True
    ),
    "gemini-3-flash": ModelConfig(
        "gemini-3-flash", "Gemini 3 Flash", 5, 250_000, 20, True
    ),
    "gemini-3.5-flash": ModelConfig(
        "gemini-3.5-flash", "Gemini 3.5 Flash", 5, 250_000, 20, True
    ),
    "gemini-2.5-flash": ModelConfig(
        "gemini-2.5-flash", "Gemini 2.5 Flash", 5, 250_000, 20, True
    ),
    "gemini-2.5-pro": ModelConfig("gemini-2.5-pro", "Gemini 2.5 Pro", 0, 0, 0, False),
    "gemini-2-flash": ModelConfig("gemini-2-flash", "Gemini 2 Flash", 0, 0, 0, False),
    "gemini-2-flash-lite": ModelConfig(
        "gemini-2-flash-lite", "Gemini 2 Flash Lite", 0, 0, 0, False
    ),
    "gemini-3.1-pro": ModelConfig("gemini-3.1-pro", "Gemini 3.1 Pro", 0, 0, 0, False),
}

DEFAULT_MODEL = "gemini-3.5-flash"


def get_enabled_models() -> dict[str, ModelConfig]:
    """Retorna los modelos habilitados para su uso."""
    return {k: v for k, v in AVAILABLE_MODELS.items() if v.enabled}
