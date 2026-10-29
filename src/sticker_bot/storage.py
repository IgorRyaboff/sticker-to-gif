"""Where converted files go: Cloudflare R2 if configured, else a local folder."""

import os
import shutil
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

CONTENT_TYPES = {"png": "image/png", "gif": "image/gif"}

# Keys are content-stable (file_unique_id), so objects never change.
CACHE_CONTROL = "public, max-age=31536000, immutable"

R2_REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL")

REPO_ROOT = Path(__file__).resolve().parents[2]


class R2Store:
    def __init__(self) -> None:
        self.bucket = os.environ["R2_BUCKET"]
        self.base_url = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")
        # Buckets created with a jurisdiction (e.g. "eu") have their own endpoint;
        # the default one answers AccessDenied for them.
        jurisdiction = os.environ.get("R2_JURISDICTION", "").strip()
        host = f"{jurisdiction}.r2.cloudflarestorage.com" if jurisdiction else "r2.cloudflarestorage.com"
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.{host}",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            # Newer boto3 sends extra checksum headers by default; keep requests plain.
            config=Config(request_checksum_calculation="when_required", response_checksum_validation="when_required"),
        )

    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    def existing_url(self, key: str) -> str | None:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return self.url(key)

    def put(self, path: Path, key: str) -> str:
        ext = key.rsplit(".", 1)[-1]
        self.s3.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": CONTENT_TYPES[ext], "CacheControl": CACHE_CONTROL},
        )
        return self.url(key)


class LocalStore:
    """Fallback for trying conversions before R2 is set up."""

    def __init__(self) -> None:
        self.dir = REPO_ROOT / "out"
        self.dir.mkdir(exist_ok=True)

    def existing_url(self, key: str) -> str | None:
        path = self.dir / key
        return path.as_uri() if path.exists() else None

    def put(self, path: Path, key: str) -> str:
        dst = self.dir / key
        shutil.copyfile(path, dst)
        return dst.as_uri()


def make_store() -> R2Store | LocalStore:
    """Local runs: R2 when configured, else a local folder."""
    if all(os.environ.get(k) for k in R2_REQUIRED):
        return R2Store()
    return LocalStore()


def require_r2_store() -> R2Store:
    """Deployed webhook: R2 or nothing, never silently write to the function's disk."""
    if missing := [k for k in R2_REQUIRED if not os.environ.get(k)]:
        raise RuntimeError(f"R2 is not configured, missing: {', '.join(missing)}")
    return R2Store()
