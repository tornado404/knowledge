"""Object storage abstraction for PKOS.

Supports MinIO (production) and local filesystem (development/fallback).
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ObjectStorage(ABC):
    """Abstract object storage interface."""

    @abstractmethod
    def put(self, local_path: str, remote_key: str) -> str:
        """Upload a file to storage.

        Args:
            local_path: Path to the local file to upload.
            remote_key: Remote key (path) to store the file at.

        Returns:
            Publicly accessible URL for the stored file.
        """
        ...

    @abstractmethod
    def get(self, remote_key: str) -> Optional[bytes]:
        """Download a file from storage.

        Args:
            remote_key: Remote key of the file.

        Returns:
            File content as bytes, or None if not found.
        """
        ...

    @abstractmethod
    def delete(self, remote_key: str) -> bool:
        """Delete a file from storage.

        Args:
            remote_key: Remote key of the file.

        Returns:
            True if deleted, False if not found or error.
        """
        ...

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        """List files under a given prefix.

        Args:
            prefix: Optional key prefix to filter by.

        Returns:
            List of remote keys.
        """
        ...

    @abstractmethod
    def get_public_url(self, remote_key: str) -> str:
        """Get the public URL for a stored file.

        Args:
            remote_key: Remote key of the file.

        Returns:
            Publicly accessible URL string.
        """
        ...


class MinioStorage(ObjectStorage):
    """MinIO object storage implementation."""

    def __init__(
        self,
        endpoint: str = "192.168.50.126:9000",
        access_key: str = "",
        secret_key: str = "",
        bucket: str = "pkos",
        region: str = "us-east-1",
        secure: bool = False,
    ):
        from minio import Minio

        self.endpoint = endpoint
        self.secure = secure
        self.bucket = bucket
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, local_path: str, remote_key: str) -> str:
        import os
        from pathlib import Path

        path = Path(local_path)
        content_type = self._guess_content_type(path.suffix)
        self.client.fput_object(
            self.bucket, remote_key, str(path),
            content_type=content_type,
        )
        return self.get_public_url(remote_key)

    def get(self, remote_key: str) -> Optional[bytes]:
        from minio.error import S3Error
        try:
            response = self.client.get_object(self.bucket, remote_key)
            return response.read()
        except S3Error:
            return None

    def delete(self, remote_key: str) -> bool:
        try:
            self.client.remove_object(self.bucket, remote_key)
            return True
        except Exception:
            return False

    def list(self, prefix: str = "") -> list[str]:
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    def get_public_url(self, remote_key: str) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}/{self.bucket}/{remote_key}"

    @staticmethod
    def _guess_content_type(suffix: str) -> str:
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return mapping.get(suffix.lower(), "application/octet-stream")


class LocalStorage(ObjectStorage):
    """Local filesystem storage implementation (development/fallback)."""

    def __init__(self, storage_dir: str = "./pkos_images"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def put(self, local_path: str, remote_key: str) -> str:
        import shutil

        dest = self.storage_dir / remote_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)
        return str(dest)

    def get(self, remote_key: str) -> Optional[bytes]:
        path = self.storage_dir / remote_key
        if path.exists():
            return path.read_bytes()
        return None

    def delete(self, remote_key: str) -> bool:
        path = self.storage_dir / remote_key
        if path.exists():
            path.unlink()
            return True
        return False

    def list(self, prefix: str = "") -> list[str]:
        search_dir = self.storage_dir / prefix if prefix else self.storage_dir
        return [
            str(p.relative_to(self.storage_dir))
            for p in self.storage_dir.rglob("*")
            if p.is_file() and str(p).startswith(str(self.storage_dir / prefix))
        ]

    def get_public_url(self, remote_key: str) -> str:
        return str(self.storage_dir / remote_key)


def create_storage(
    backend: str = "auto",
    endpoint: str = "",
    access_key: str = "",
    secret_key: str = "",
    bucket: str = "pkos",
    storage_dir: str = "./pkos_images",
) -> ObjectStorage:
    """Create a storage backend instance.

    Args:
        backend: "minio" | "local" | "auto"
            auto: prefer MinIO (if configured and reachable), fall back to local.
        endpoint: MinIO endpoint (host:port).
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        bucket: MinIO bucket name.
        storage_dir: Local storage directory (for local/fallback).

    Returns:
        An ObjectStorage instance.
    """
    if backend == "minio":
        return MinioStorage(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
        )
    elif backend == "local":
        return LocalStorage(storage_dir=storage_dir)
    elif backend == "auto":
        if endpoint and access_key and secret_key:
            try:
                store = MinioStorage(
                    endpoint=endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                    bucket=bucket,
                )
                store.list()  # Connectivity test
                return store
            except Exception:
                print("[Storage] MinIO unavailable, falling back to local storage")
        return LocalStorage(storage_dir=storage_dir)
    raise ValueError(f"Unknown storage backend: {backend}")


# Global default storage instance
_default_storage: Optional[ObjectStorage] = None


def get_default_storage() -> ObjectStorage:
    """Get or create the default storage instance (singleton).

    Configuration is read from environment variables:
        PKOS_STORAGE_BACKEND, PKOS_S3_ENDPOINT, PKOS_S3_ACCESS_KEY,
        PKOS_S3_SECRET_KEY, PKOS_S3_BUCKET, PKOS_IMAGE_DIR.
    """
    global _default_storage
    if _default_storage is None:
        _default_storage = create_storage(
            backend=os.getenv("PKOS_STORAGE_BACKEND", "auto"),
            endpoint=os.getenv("PKOS_S3_ENDPOINT", ""),
            access_key=os.getenv("PKOS_S3_ACCESS_KEY", ""),
            secret_key=os.getenv("PKOS_S3_SECRET_KEY", ""),
            bucket=os.getenv("PKOS_S3_BUCKET", "pkos"),
            storage_dir=os.getenv("PKOS_IMAGE_DIR", "./pkos_images"),
        )
    return _default_storage
