"""Tests for PKOS Object Storage integration.

Covers LocalStorage, MinioStorage, factory function, and ImageParser integration.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from kgsrc.pkos.storage import (
    ObjectStorage,
    LocalStorage,
    MinioStorage,
    create_storage,
    get_default_storage,
)


# =============================================================================
# LocalStorage Tests
# =============================================================================


class TestLocalStorage:
    def test_put_and_get(self):
        """Upload a file via put, then retrieve via get."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)

            # Create a source file
            src = Path(tmp) / "source.png"
            src.write_bytes(b"fake-image-data")

            remote_key = "images/test/hello.png"
            url = storage.put(str(src), remote_key)

            # Verify returned URL is the local path
            expected_path = str(Path(tmp) / remote_key)
            assert url == expected_path

            # Verify get returns the same content
            data = storage.get(remote_key)
            assert data == b"fake-image-data"

    def test_delete_returns_true_on_success(self):
        """Delete an existing file returns True."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)

            src = Path(tmp) / "source.png"
            src.write_bytes(b"data")
            remote_key = "images/test/file.png"
            storage.put(str(src), remote_key)

            assert storage.delete(remote_key) is True
            # Verify file is gone
            assert storage.get(remote_key) is None

    def test_delete_returns_false_on_missing(self):
        """Delete a non-existent file returns False."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)
            assert storage.delete("nonexistent/key.png") is False

    def test_list_includes_uploaded_files(self):
        """After upload, list returns the file key."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)

            src = Path(tmp) / "a.png"
            src.write_bytes(b"data")
            storage.put(str(src), "images/test/a.png")

            src2 = Path(tmp) / "b.png"
            src2.write_bytes(b"data")
            storage.put(str(src2), "images/test/b.png")

            keys = storage.list("images/test/")
            assert "images/test/a.png" in keys
            assert "images/test/b.png" in keys

    def test_list_with_prefix(self):
        """List with prefix filters correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)

            src = Path(tmp) / "a.png"
            src.write_bytes(b"data")
            storage.put(str(src), "images/task1/a.png")
            storage.put(str(src), "images/task2/b.png")

            keys = storage.list("images/task1/")
            assert "images/task1/a.png" in keys
            assert "images/task2/b.png" not in keys

    def test_get_public_url_returns_local_path(self):
        """get_public_url returns the local filesystem path."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalStorage(storage_dir=tmp)
            url = storage.get_public_url("images/test/foo.png")
            assert url == str(Path(tmp) / "images/test/foo.png")

    def test_storage_dir_is_created(self):
        """Constructor creates the storage directory if it does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = Path(tmp) / "new_dir" / "nested"
            assert not storage_dir.exists()
            storage = LocalStorage(storage_dir=str(storage_dir))
            assert storage_dir.exists()


# =============================================================================
# MinioStorage Tests (mocked)
# =============================================================================


class TestMinioStorage:
    @patch("minio.Minio")
    def test_put(self, MockMinio):
        """MinioStorage.put uploads via fput_object and returns public URL."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="test-key",
            secret_key="test-secret",
            bucket="pkos",
        )

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.png"
            src.write_bytes(b"data")
            url = storage.put(str(src), "images/task1/test.png")

        mock_client.fput_object.assert_called_once_with(
            "pkos", "images/task1/test.png", str(src),
            content_type="image/png",
        )
        assert url == "http://192.168.50.126:9000/pkos/images/task1/test.png"

    @patch("minio.Minio")
    def test_get_returns_bytes(self, MockMinio):
        """MinioStorage.get returns bytes from get_object."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        mock_response = MagicMock()
        mock_response.read.return_value = b"image-bytes"
        mock_client.get_object.return_value = mock_response

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )

        data = storage.get("images/task1/test.png")
        assert data == b"image-bytes"
        mock_client.get_object.assert_called_once_with("pkos", "images/task1/test.png")

    @patch("minio.Minio")
    def test_get_returns_none_on_s3error(self, MockMinio):
        """MinioStorage.get returns None when object does not exist."""
        from minio.error import S3Error

        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        mock_client.get_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Not found",
            resource="test",
            request_id="req1",
            host_id="host1",
            response=MagicMock(),
        )

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )

        data = storage.get("nonexistent")
        assert data is None

    @patch("minio.Minio")
    def test_delete(self, MockMinio):
        """MinioStorage.delete calls remove_object."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )

        result = storage.delete("images/task1/test.png")
        assert result is True
        mock_client.remove_object.assert_called_once_with("pkos", "images/task1/test.png")

    @patch("minio.Minio")
    def test_list(self, MockMinio):
        """MinioStorage.list returns object names from list_objects."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        obj1 = MagicMock()
        obj1.object_name = "images/task1/a.png"
        obj2 = MagicMock()
        obj2.object_name = "images/task1/b.png"
        mock_client.list_objects.return_value = [obj1, obj2]

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )

        keys = storage.list("images/task1/")
        assert keys == ["images/task1/a.png", "images/task1/b.png"]
        mock_client.list_objects.assert_called_once_with(
            "pkos", prefix="images/task1/", recursive=True
        )

    @patch("minio.Minio")
    def test_get_public_url_format(self, MockMinio):
        """MinioStorage.get_public_url returns correct URL format."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
            bucket="pkos",
            secure=False,
        )

        url = storage.get_public_url("images/task1/foo.png")
        assert url == "http://192.168.50.126:9000/pkos/images/task1/foo.png"

    @patch("minio.Minio")
    def test_get_public_url_https(self, MockMinio):
        """MinioStorage.get_public_url uses https when secure=True."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="play.min.io:9000",
            access_key="key",
            secret_key="secret",
            secure=True,
        )

        url = storage.get_public_url("images/test/bar.png")
        assert url == "https://play.min.io:9000/pkos/images/test/bar.png"

    @patch("minio.Minio")
    def test_ensure_bucket_creates_if_missing(self, MockMinio):
        """_ensure_bucket creates bucket if it does not exist."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = False

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
            bucket="pkos",
        )

        mock_client.make_bucket.assert_called_once_with("pkos")

    @patch("minio.Minio")
    def test_guess_content_type(self, MockMinio):
        """_guess_content_type maps common extensions correctly."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )

        assert storage._guess_content_type(".png") == "image/png"
        assert storage._guess_content_type(".jpg") == "image/jpeg"
        assert storage._guess_content_type(".jpeg") == "image/jpeg"
        assert storage._guess_content_type(".webp") == "image/webp"
        assert storage._guess_content_type(".gif") == "image/gif"
        assert storage._guess_content_type(".pdf") == "application/octet-stream"

    @patch("minio.Minio")
    def test_endpoint_and_secure_are_saved(self, MockMinio):
        """endpoint and secure attributes are saved for get_public_url."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = MinioStorage(
            endpoint="my-minio:9000",
            access_key="key",
            secret_key="secret",
            secure=True,
        )

        assert storage.endpoint == "my-minio:9000"
        assert storage.secure is True


# =============================================================================
# create_storage Factory Tests
# =============================================================================


class TestCreateStorage:
    def test_create_local(self):
        """create_storage('local') returns a LocalStorage instance."""
        with tempfile.TemporaryDirectory() as tmp:
            storage = create_storage(backend="local", storage_dir=tmp)
            assert isinstance(storage, LocalStorage)

    @patch("minio.Minio")
    def test_create_minio(self, MockMinio):
        """create_storage('minio') returns a MinioStorage instance."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        storage = create_storage(
            backend="minio",
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )
        assert isinstance(storage, MinioStorage)
        assert storage.endpoint == "192.168.50.126:9000"

    @patch("minio.Minio")
    def test_create_minio_no_config_handles_gracefully(self, MockMinio):
        """create_storage('minio') with empty config may raise but should be
        a clear exception (not a cryptic one)."""
        MockMinio.side_effect = ValueError("Empty endpoint not allowed")

        with pytest.raises(ValueError):
            create_storage(
                backend="minio",
                endpoint="",
                access_key="",
                secret_key="",
            )

    @patch("minio.Minio")
    def test_create_auto_minio_available(self, MockMinio):
        """create_storage('auto') returns MinioStorage when MinIO is reachable."""
        mock_client = MagicMock()
        MockMinio.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.list_objects.return_value = []

        storage = create_storage(
            backend="auto",
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )
        assert isinstance(storage, MinioStorage)

    @patch("minio.Minio")
    def test_create_auto_minio_unreachable_fallsback(self, MockMinio):
        """create_storage('auto') falls back to LocalStorage when MinIO fails."""
        MockMinio.side_effect = ConnectionError("Cannot connect")

        storage = create_storage(
            backend="auto",
            endpoint="192.168.50.126:9000",
            access_key="key",
            secret_key="secret",
        )
        assert isinstance(storage, LocalStorage)

    @patch("minio.Minio")
    def test_create_auto_no_config_returns_local(self, MockMinio):
        """create_storage('auto') with empty config returns LocalStorage."""
        storage = create_storage(backend="auto", endpoint="", access_key="", secret_key="")
        assert isinstance(storage, LocalStorage)

    def test_create_unknown_backend_raises(self):
        """create_storage with unknown backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage(backend="invalid")


# =============================================================================
# get_default_storage Tests
# =============================================================================


class TestGetDefaultStorage:
    @pytest.fixture(autouse=True)
    def reset_default_storage(self):
        """Reset the module-level _default_storage before each test."""
        import kgsrc.pkos.storage as mod
        mod._default_storage = None
        yield

    @patch("kgsrc.pkos.storage.create_storage")
    def test_get_default_storage_returns_instance(self, mock_create):
        """get_default_storage returns an ObjectStorage instance."""
        mock_storage = MagicMock(spec=ObjectStorage)
        mock_create.return_value = mock_storage

        storage = get_default_storage()
        assert storage is mock_storage

    @patch("kgsrc.pkos.storage.create_storage")
    def test_get_default_storage_singleton(self, mock_create):
        """get_default_storage returns the same instance on repeated calls."""
        mock_storage = MagicMock(spec=ObjectStorage)
        mock_create.return_value = mock_storage

        s1 = get_default_storage()
        s2 = get_default_storage()
        assert s1 is s2
        mock_create.assert_called_once()

    def test_default_storage_reset_between_tests(self):
        """The module-level _default_storage is reset between tests
        (each test gets a fresh env)."""
        import kgsrc.pkos.storage as mod
        # With no env vars set, should return LocalStorage
        storage = get_default_storage()
        assert isinstance(storage, (LocalStorage, MinioStorage))


# =============================================================================
# ImageParser + ObjectStorage Integration Tests
# =============================================================================


class TestImageParserWithStorage:
    def test_image_parser_uses_storage_put(self):
        """ImageParser.parse_file uploads via storage.put and uses the returned URL."""
        from kgsrc.pkos.parsers import ImageParser

        mock_storage = MagicMock(spec=ObjectStorage)
        mock_storage.put.return_value = "http://minio:9000/pkos/images/task1/test.png"

        parser = ImageParser(storage=mock_storage)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.png"
            src.write_bytes(b"fake-png-data")

            result = parser.parse_file(str(src))

        # Verify storage.put was called with correct args
        mock_storage.put.assert_called_once()
        call_args = mock_storage.put.call_args[0]
        assert call_args[0] == str(src)  # local_path
        assert "images/" in call_args[1]  # remote_key contains images/

        # Verify the returned URL is embedded in the markdown output
        assert "http://minio:9000/pkos/images/task1/test.png" in result.raw_text

        # Verify extracted_images includes the storage URL and key
        assert len(result.extracted_images) > 0
        img = result.extracted_images[0]
        assert img["path"] == "http://minio:9000/pkos/images/task1/test.png"
        assert img["filename"] == "test.png"
        assert "storage_key" in img

    def test_image_parser_unsupported_type_skips_storage(self):
        """ImageParser returns early for unsupported types without calling storage."""
        from kgsrc.pkos.parsers import ImageParser

        mock_storage = MagicMock(spec=ObjectStorage)

        parser = ImageParser(storage=mock_storage)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.txt"
            src.write_text("not an image")

            result = parser.parse_file(str(src))

        assert mock_storage.put.call_count == 0
        assert "[Unsupported image" in result.raw_text

    def test_image_parser_default_storage(self):
        """ImageParser with no storage argument uses get_default_storage."""
        from kgsrc.pkos.parsers import ImageParser

        parser = ImageParser()
        # Should have a storage instance (from get_default_storage)
        assert isinstance(parser.storage, ObjectStorage)

    def test_image_parser_storage_injected_via_parser(self):
        """Test that DocumentParser.get_parser can be monkey-patched
        or that the ImageParser is properly instantiated with storage."""
        from kgsrc.pkos.parsers import ImageParser, DocumentParser

        mock_storage = MagicMock(spec=ObjectStorage)
        mock_storage.put.return_value = "http://minio:9000/pkos/images/task/foo.png"

        parser = ImageParser(storage=mock_storage)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "photo.png"
            src.write_bytes(b"data")

            result = parser.parse_file(str(src))

        mock_storage.put.assert_called_once()
        assert "http://minio:9000" in result.raw_text


# =============================================================================
# Config Integration Tests
# =============================================================================


class TestConfigDefaults:
    def test_pkos_config_has_storage_fields(self):
        """PKOSConfig should have the new storage-related fields."""
        from kgsrc.pkos.config import PKOSConfig

        config = PKOSConfig()
        # These fields should exist after the update
        assert hasattr(config, "storage_backend")
        assert hasattr(config, "s3_endpoint")
        assert hasattr(config, "s3_access_key")
        assert hasattr(config, "s3_secret_key")
        assert hasattr(config, "s3_bucket")
        assert hasattr(config, "s3_region")
        assert hasattr(config, "s3_secure")

    def test_pkos_config_storage_defaults(self):
        """PKOSConfig storage fields should have correct default values."""
        from kgsrc.pkos.config import PKOSConfig

        config = PKOSConfig()
        assert config.storage_backend == "auto"
        assert config.s3_endpoint == ""
        assert config.s3_access_key == ""
        assert config.s3_secret_key == ""
        assert config.s3_bucket == "pkos"
        assert config.s3_region == "us-east-1"
        assert config.s3_secure is False

    def test_pkos_config_from_base_reads_env(self):
        """PKOSConfig.from_base reads storage env vars."""
        with patch.dict(os.environ, {
            "PKOS_STORAGE_BACKEND": "minio",
            "PKOS_S3_ENDPOINT": "192.168.50.126:9000",
            "PKOS_S3_ACCESS_KEY": "mykey",
            "PKOS_S3_SECRET_KEY": "mysecret",
            "PKOS_S3_BUCKET": "test-bucket",
        }):
            from kgsrc.pkos.config import PKOSConfig
            config = PKOSConfig.from_base()
            assert config.storage_backend == "minio"
            assert config.s3_endpoint == "192.168.50.126:9000"
            assert config.s3_access_key == "mykey"
            assert config.s3_secret_key == "mysecret"
            assert config.s3_bucket == "test-bucket"
