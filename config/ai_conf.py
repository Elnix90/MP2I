from dataclasses import dataclass, field
from pathlib import Path

import json5


@dataclass
class AIConfig:
    enabled: bool = True
    allowed_channels: list[int] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    api_url: str = ""
    system_prompt: str = ""
    streaming: bool = True
    memory_max_history: int = 15
    tools: list[str] = field(default_factory=list)

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def model(self) -> str:
        return self.models[0] if self.models else ""


def load_ai_config(file: Path | None = None) -> AIConfig:
    path = file or Path("config/ai_config.json5")
    with open(path) as f:
        raw = json5.load(f)

    ai_raw = raw.get("ai", raw)
    system_prompt = Path(ai_raw["system_prompt_path"]).read_text().strip()

    models = ai_raw.get("models", [])
    # backward compat with a single "model" entry
    single_model = ai_raw.get("model")
    if single_model and single_model not in models:
        models.insert(0, single_model)

    return AIConfig(
        enabled=ai_raw.get("enabled", True),
        allowed_channels=ai_raw.get("allowed_channels", []),
        models=models,
        api_url=ai_raw.get("api_url", ""),
        system_prompt=system_prompt,
        streaming=ai_raw.get("streaming", True),
        memory_max_history=ai_raw.get("memory_max_history", 15),
        tools=ai_raw.get("tools", []),
    )
