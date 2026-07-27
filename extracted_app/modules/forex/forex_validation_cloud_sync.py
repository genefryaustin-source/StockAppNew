from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _get_user_value(user: Any, key: str, default: Any = None) -> Any:
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)

class ForexValidationCloudSync:
    """Portable cloud-sync adapter for Forex validation artifacts.

    This implementation is intentionally provider-neutral. It creates local
    sync manifests that can later be pushed to S3, GCS, Azure Blob, GitHub
    Actions artifacts, or another deployment target.
    """

    def __init__(self, sync_dir: Optional[str] = None):
        self.sync_dir = Path(sync_dir or "data/forex_validation/cloud_sync")
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.sync_dir / "sync_manifest.jsonl"

    def _append_manifest(self, event: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(event)
        payload.setdefault("sync_id", _new_id("fx_val_sync"))
        payload.setdefault("created_at", _utc_now())
        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
        return payload

    def export_latest_run(self) -> Dict[str, Any]:
        Persistence = _safe_import(
            "modules.forex.forex_validation_persistence",
            "ForexValidationPersistence",
        )
        latest = Persistence().latest_run()
        output_path = self.sync_dir / f"latest_validation_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.write_text(json.dumps(latest, indent=2, default=str), encoding="utf-8")

        return self._append_manifest({
            "status": "exported",
            "artifact_type": "latest_validation_run",
            "local_path": str(output_path),
            "provider": "local",
        })

    def export_snapshot(self) -> Dict[str, Any]:
        Ops = _safe_import(
            "modules.forex.forex_validation_operations_center",
            "ForexValidationOperationsCenter",
        )
        snapshot = Ops().snapshot()
        output_path = self.sync_dir / f"validation_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")

        return self._append_manifest({
            "status": "exported",
            "artifact_type": "validation_snapshot",
            "local_path": str(output_path),
            "provider": "local",
        })

    def sync_report_package(self) -> Dict[str, Any]:
        Center = _safe_import(
            "modules.forex.forex_validation_center",
            "ForexValidationCenter",
        )
        payload = Center().run_full_validation()
        reports = Center().generate_reports(payload)

        return self._append_manifest({
            "status": "synced",
            "artifact_type": "report_package",
            "provider": "local",
            "reports": reports,
        })

    def list_sync_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.manifest_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-int(limit):]

    def status(self) -> Dict[str, Any]:
        events = self.list_sync_events(limit=100)
        return {
            "status": "ready",
            "provider": "local",
            "sync_dir": str(self.sync_dir),
            "event_count": len(events),
            "latest_event": events[-1] if events else None,
            "checked_at": _utc_now(),
        }


def sync_forex_validation_reports() -> Dict[str, Any]:
    return ForexValidationCloudSync().sync_report_package()
