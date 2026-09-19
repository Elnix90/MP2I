from dataclasses import dataclass, field
from pathlib import Path

import json5


@dataclass
class AIConfig:
    enabled: bool = True
    allowed_channels: list[int] = field(default_factory=list)
    model: str = ""
    api_url: str = ""
    system_prompt: str = ""

    @property
    def is_enabled(self) -> bool:
        return self.enabled


def load_ai_config(file: Path | None = None) -> AIConfig:
    path = file or Path("config/ai_config.json5")
    with open(path, "r") as f:
        raw = json5.load(f)

    ai_raw = raw.get("ai", raw)
    system_prompt = Path(ai_raw["system_prompt_path"]).read_text().strip()

    return AIConfig(
        enabled=ai_raw.get("enabled", True),
        allowed_channels=ai_raw.get("allowed_channels", []),
        model=ai_raw.get("model", ""),
        api_url=ai_raw.get("api_url", ""),
        system_prompt=system_prompt,
    )
