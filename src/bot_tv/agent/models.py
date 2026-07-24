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
    "gemini-2.5-flash": ModelConfig(
        "gemini-2.5-flash", "Gemini 2.5 Flash", 15, 1_000_000, 1_500, True
    ),
    "gemini-2.0-flash": ModelConfig(
        "gemini-2.0-flash", "Gemini 2.0 Flash", 15, 1_000_000, 1_500, True
    ),
    "gemini-3.1-flash-lite": ModelConfig(
        "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", 30, 1_000_000, 1_500, True
    ),
    "gemini-3-flash-preview": ModelConfig(
        "gemini-3-flash-preview", "Gemini 3 Flash (Preview)", 15, 1_000_000, 1_500, True
    ),
    "gemini-flash-latest": ModelConfig(
        "gemini-flash-latest", "Gemini Flash (Latest)", 15, 1_000_000, 1_500, True
    ),
    "gemini-2.5-pro": ModelConfig(
        "gemini-2.5-pro", "Gemini 2.5 Pro", 2, 32_000, 50, False
    ),
}

DEFAULT_MODEL = "gemini-3.1-flash-lite"


def get_enabled_models() -> dict[str, ModelConfig]:
    """Retorna los modelos habilitados para su uso."""
    return {k: v for k, v in AVAILABLE_MODELS.items() if v.enabled}
