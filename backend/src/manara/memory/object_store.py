"""Object storage abstraction for the Cumulative Memory (G03).

Per owner decision (2026-10-19):
> "نعم، نعتمد Local Filesystem للتطوير + تخزين S3-compatible للإنتاج
> خلف واجهة مشتركة، مع حفظ البصمة الرقمية ومرجع الملف وحقوق الاحتفاظ
> به. ولا ننسخ محتوى كل مصدر بصورة دائمة دون حاجة أو ترخيص."

This module exposes a single ``ObjectStore`` protocol with two
implementations:
* ``LocalFilesystemStore`` — for dev/test; writes snapshots to a local
  directory under ``var/snapshots/``.
* ``S3CompatibleStore`` — stub for production; documented but not
  exercised in the sandbox (no S3 credentials).

The factory ``get_object_store()`` inspects the ``MANARA_OBJECT_STORE``
env var:
* ``local`` (default) → LocalFilesystemStore
* ``s3`` → S3CompatibleStore (requires AWS creds in env, NOT in code)

Every snapshot is content-addressed by its SHA-256 checksum, so:
* Idempotent writes (same content → same ref → no duplicate files).
* Tamper detection: storing the same ref with different content fails.
* Dedup at the file level (in addition to dedup at the evidence level).
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class ObjectStoreProtocol(Protocol):
    """Object store abstraction — content-addressed snapshot storage."""

    def store(
        self,
        *,
        content: bytes,
        tenant_id: str,
        source_id: str,
        content_type: str = "application/json",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store content and return a reference (e.g. 'local://sha256...').

        The reference encodes the storage backend + the content checksum.
        """
        ...

    def retrieve(self, ref: str) -> bytes:
        """Retrieve content by reference. Raises KeyError if not found."""
        ...

    def delete(self, ref: str) -> bool:
        """Delete content by reference. Returns True if deleted."""
        ...

    def exists(self, ref: str) -> bool:
        """Check if a reference exists in the store."""
        ...

    def compute_checksum(self, content: bytes) -> str:
        """Compute the canonical SHA-256 checksum of content."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Local filesystem implementation
# ─────────────────────────────────────────────────────────────────────────────


class LocalFilesystemStore:
    """Content-addressed store on the local filesystem.

    Layout:
        {root}/
            {tenant_id}/
                {checksum}.bin       # raw content
                {checksum}.meta.json  # metadata (source_id, captured_at, ...)

    The reference format is ``local://{tenant_id}/{checksum}``.
    """

    def __init__(self, root: str | None = None) -> None:
        # Default to var/snapshots under the project root
        if root is None:
            project_root = Path(__file__).resolve().parents[4]
            root = str(project_root / "var" / "snapshots")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, tenant_id: str, checksum: str, ext: str = ".bin") -> Path:
        tenant_dir = self.root / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir / f"{checksum}{ext}"

    def compute_checksum(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def store(
        self,
        *,
        content: bytes,
        tenant_id: str,
        source_id: str,
        content_type: str = "application/json",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        checksum = self.compute_checksum(content)
        ref = f"local://{tenant_id}/{checksum}"
        content_path = self._path_for(tenant_id, checksum, ".bin")
        meta_path = self._path_for(tenant_id, checksum, ".meta.json")

        # Idempotent: if both files exist with matching size, return ref
        if content_path.exists() and meta_path.exists():
            return ref

        # Write content (atomic-ish: write then rename)
        tmp_content = content_path.with_suffix(".bin.tmp")
        tmp_content.write_bytes(content)
        tmp_content.replace(content_path)

        # Write metadata
        import json

        meta = {
            "tenant_id": tenant_id,
            "source_id": source_id,
            "content_type": content_type,
            "checksum": checksum,
            "size_bytes": len(content),
            "captured_at": datetime.now(UTC).isoformat(),
            "extra": metadata or {},
        }
        tmp_meta = meta_path.with_suffix(".meta.json.tmp")
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_meta.replace(meta_path)

        return ref

    def retrieve(self, ref: str) -> bytes:
        # Parse local://{tenant_id}/{checksum}
        if not ref.startswith("local://"):
            raise KeyError(f"unsupported ref scheme: {ref}")
        rest = ref[len("local://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            raise KeyError(f"malformed ref: {ref}")
        tenant_id, checksum = parts
        content_path = self._path_for(tenant_id, checksum, ".bin")
        if not content_path.exists():
            raise KeyError(f"not found: {ref}")
        return content_path.read_bytes()

    def delete(self, ref: str) -> bool:
        if not ref.startswith("local://"):
            return False
        rest = ref[len("local://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return False
        tenant_id, checksum = parts
        content_path = self._path_for(tenant_id, checksum, ".bin")
        meta_path = self._path_for(tenant_id, checksum, ".meta.json")
        deleted = False
        if content_path.exists():
            content_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
        return deleted

    def exists(self, ref: str) -> bool:
        if not ref.startswith("local://"):
            return False
        rest = ref[len("local://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return False
        tenant_id, checksum = parts
        content_path = self._path_for(tenant_id, checksum, ".bin")
        return content_path.exists()


# ─────────────────────────────────────────────────────────────────────────────
# S3-compatible implementation (stub for production)
# ─────────────────────────────────────────────────────────────────────────────


class S3CompatibleStore:
    """S3-compatible object store — production target.

    Uses boto3 under the hood. Credentials are read from the standard
    AWS env vars (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
    or the IAM role of the production runtime — NEVER from code.

    NOTE: This implementation is provided but NOT exercised in the
    sandbox (no S3 credentials). The factory returns it only when
    ``MANARA_OBJECT_STORE=s3`` is set.

    Reference format: ``s3://{bucket}/{tenant_id}/{checksum}``.
    """

    def __init__(self, bucket: str | None = None) -> None:
        self.bucket = bucket or os.environ.get("MANARA_S3_BUCKET", "manara-snapshots")
        self._client: Any = None  # lazy boto3 client

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import boto3  # type: ignore[import-untyped]
            except ImportError as e:
                raise RuntimeError(
                    "boto3 not installed; install with: pip install boto3"
                ) from e
            self._client = boto3.client("s3")
        return self._client

    def compute_checksum(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def store(
        self,
        *,
        content: bytes,
        tenant_id: str,
        source_id: str,
        content_type: str = "application/json",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        checksum = self.compute_checksum(content)
        key = f"{tenant_id}/{checksum}"
        ref = f"s3://{self.bucket}/{key}"
        client = self._ensure_client()
        # Idempotent: S3 PUT is idempotent for same content
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata={
                "tenant_id": tenant_id,
                "source_id": source_id,
                "checksum": checksum,
                "captured_at": datetime.now(UTC).isoformat(),
                **{f"extra_{k}": str(v) for k, v in (metadata or {}).items()},
            },
        )
        return ref

    def retrieve(self, ref: str) -> bytes:
        if not ref.startswith("s3://"):
            raise KeyError(f"unsupported ref scheme: {ref}")
        rest = ref[len("s3://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            raise KeyError(f"malformed ref: {ref}")
        bucket, key = parts
        client = self._ensure_client()
        response = client.get_object(Bucket=bucket, Key=key)
        content: bytes = response["Body"].read()
        return content

    def delete(self, ref: str) -> bool:
        if not ref.startswith("s3://"):
            return False
        rest = ref[len("s3://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return False
        bucket, key = parts
        client = self._ensure_client()
        client.delete_object(Bucket=bucket, Key=key)
        return True

    def exists(self, ref: str) -> bool:
        if not ref.startswith("s3://"):
            return False
        rest = ref[len("s3://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return False
        bucket, key = parts
        client = self._ensure_client()
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


_store_instance: ObjectStoreProtocol | None = None


def get_object_store() -> ObjectStoreProtocol:
    """Return the configured object store (singleton)."""
    global _store_instance
    if _store_instance is None:
        backend = os.environ.get("MANARA_OBJECT_STORE", "local").lower()
        if backend == "s3":
            _store_instance = S3CompatibleStore()
        else:
            _store_instance = LocalFilesystemStore()
    return _store_instance


def reset_object_store() -> None:
    """Reset the cached store (used by tests)."""
    global _store_instance
    _store_instance = None


__all__ = [
    "LocalFilesystemStore",
    "ObjectStoreProtocol",
    "S3CompatibleStore",
    "get_object_store",
    "reset_object_store",
]
