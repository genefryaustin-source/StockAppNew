from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .legal_registry import iter_documents


@dataclass(frozen=True)
class PublishResult:
    destination: Path
    copied_files: tuple[str, ...]
    skipped_files: tuple[str, ...]


def publish_legal_documents(destination: str | Path) -> PublishResult:
    destination_path = Path(destination).resolve()
    destination_path.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped: list[str] = []

    for document in iter_documents():
        source = document.source_path

        if not source.exists():
            skipped.append(document.filename)
            continue

        target = destination_path / document.filename
        shutil.copy2(source, target)
        copied.append(document.filename)

    return PublishResult(
        destination=destination_path,
        copied_files=tuple(copied),
        skipped_files=tuple(skipped),
    )
