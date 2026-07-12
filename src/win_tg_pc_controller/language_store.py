from __future__ import annotations

import json
import os
from pathlib import Path

from .i18n import Language, is_supported_language


class LanguageStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._languages = self._load()

    def get(self, user_id: int) -> Language | None:
        return self._languages.get(str(user_id))

    def set(self, user_id: int, language: Language) -> None:
        self._languages[str(user_id)] = language
        self._save()

    def _load(self) -> dict[str, Language]:
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError(f"{self._path} must contain a JSON object")

        languages: dict[str, Language] = {}
        for user_id, language in raw.items():
            if isinstance(user_id, str) and isinstance(language, str) and is_supported_language(language):
                languages[user_id] = language
        return languages

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(self._languages, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, self._path)
