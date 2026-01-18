"""MinIO S3-compatible client for celery-doc storage operations."""

import logging
from pathlib import Path
from typing import Optional, BinaryIO
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioClient:
    """MinIO S3-compatible storage client for Celery workers.

    Provides synchronous operations for file upload, download, and management.
    """

    def __init__(self) -> None:
        """Initialize MinIO client with settings from config."""
        endpoint_url = settings.S3_ENDPOINT

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            use_ssl=False,
        )

        # Default bucket names
        self.bucket_documents = settings.S3_BUCKET
        self.bucket_processed = "processed"
        self.bucket_images = "images"

    def upload_file(
        self,
        file_path: str,
        bucket: str,
        object_key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to MinIO.

        Args:
            file_path: Local file path to upload
            bucket: Target bucket name
            object_key: Object key (path) in bucket
            content_type: Optional MIME type

        Returns:
            Object key of uploaded file
        """
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self._client.upload_file(
                file_path,
                bucket,
                object_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info(f"Uploaded {file_path} to {bucket}/{object_key}")
            return object_key
        except ClientError as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            raise

    def upload_fileobj(
        self,
        file_obj: BinaryIO,
        bucket: str,
        object_key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file-like object to MinIO."""
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self._client.upload_fileobj(
                file_obj,
                bucket,
                object_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info(f"Uploaded fileobj to {bucket}/{object_key}")
            return object_key
        except ClientError as e:
            logger.error(f"Failed to upload fileobj: {e}")
            raise

    def download_file(self, bucket: str, object_key: str, file_path: str) -> str:
        """Download a file from MinIO.

        Args:
            bucket: Source bucket name
            object_key: Object key (path) in bucket
            file_path: Local file path to save to

        Returns:
            Local file path
        """
        try:
            # Ensure parent directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            self._client.download_file(bucket, object_key, file_path)
            logger.info(f"Downloaded {bucket}/{object_key} to {file_path}")
            return file_path
        except ClientError as e:
            logger.error(f"Failed to download {bucket}/{object_key}: {e}")
            raise

    def get_object(self, bucket: str, object_key: str) -> bytes:
        """Get object content as bytes."""
        try:
            response = self._client.get_object(Bucket=bucket, Key=object_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to get {bucket}/{object_key}: {e}")
            raise

    def delete_object(self, bucket: str, object_key: str) -> None:
        """Delete an object from MinIO."""
        try:
            self._client.delete_object(Bucket=bucket, Key=object_key)
            logger.info(f"Deleted {bucket}/{object_key}")
        except ClientError as e:
            logger.error(f"Failed to delete {bucket}/{object_key}: {e}")
            raise

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict]:
        """List objects in a bucket with optional prefix."""
        try:
            response = self._client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            return response.get("Contents", [])
        except ClientError as e:
            logger.error(f"Failed to list {bucket}/{prefix}: {e}")
            raise

    def object_exists(self, bucket: str, object_key: str) -> bool:
        """Check if an object exists."""
        try:
            self._client.head_object(Bucket=bucket, Key=object_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def upload_directory(
        self,
        local_dir: str,
        bucket: str,
        prefix: str,
    ) -> list[str]:
        """Upload all files in a directory to MinIO.

        Args:
            local_dir: Local directory path
            bucket: Target bucket name
            prefix: Object key prefix in bucket

        Returns:
            List of uploaded object keys
        """
        uploaded = []
        local_path = Path(local_dir)

        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                object_key = f"{prefix}/{relative_path}"
                self.upload_file(str(file_path), bucket, object_key)
                uploaded.append(object_key)

        logger.info(f"Uploaded {len(uploaded)} files from {local_dir} to {bucket}/{prefix}")
        return uploaded


# Singleton instance
_minio_client: Optional[MinioClient] = None


def get_minio_client() -> MinioClient:
    """Get or create MinIO client singleton."""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinioClient()
    return _minio_client


def parse_minio_path(minio_path: str) -> tuple[str, str]:
    """Parse a MinIO path (minio://bucket/key) into bucket and key.

    Args:
        minio_path: Path in format minio://bucket/object_key

    Returns:
        Tuple of (bucket, object_key)
    """
    if not minio_path.startswith("minio://"):
        raise ValueError(f"Invalid MinIO path: {minio_path}")

    path = minio_path.replace("minio://", "")
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid MinIO path format: {minio_path}")

    return parts[0], parts[1]
