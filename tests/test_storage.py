import pytest

from sticker_bot.storage import CACHE_CONTROL, R2Store, require_r2_store

R2_ENV = {
    "R2_ACCOUNT_ID": "acct",
    "R2_ACCESS_KEY_ID": "key",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET": "bucket",
    "R2_PUBLIC_BASE_URL": "https://pub-x.r2.dev/",
}


@pytest.fixture
def r2_env(monkeypatch):
    for k, v in R2_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("R2_JURISDICTION", raising=False)


@pytest.mark.parametrize(
    ("jurisdiction", "endpoint"),
    [("", "https://acct.r2.cloudflarestorage.com"), ("eu", "https://acct.eu.r2.cloudflarestorage.com")],
)
def test_endpoint_follows_jurisdiction(r2_env, monkeypatch, jurisdiction, endpoint):
    monkeypatch.setenv("R2_JURISDICTION", jurisdiction)
    assert R2Store().s3.meta.endpoint_url == endpoint


def test_put_sets_headers_and_returns_public_url(r2_env, tmp_path):
    uploads = []

    class FakeS3:
        def upload_file(self, filename, bucket, key, ExtraArgs):
            uploads.append((bucket, key, ExtraArgs))

    store = R2Store()
    store.s3 = FakeS3()
    url = store.put(tmp_path / "uid.gif", "uid.gif")
    assert url == "https://pub-x.r2.dev/uid.gif"
    assert uploads == [("bucket", "uid.gif", {"ContentType": "image/gif", "CacheControl": CACHE_CONTROL})]


def test_existing_url_maps_404_to_none(r2_env):
    from botocore.exceptions import ClientError

    class FakeS3:
        def head_object(self, Bucket, Key):
            if Key == "there.png":
                return {}
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    store = R2Store()
    store.s3 = FakeS3()
    assert store.existing_url("there.png") == "https://pub-x.r2.dev/there.png"
    assert store.existing_url("missing.png") is None


def test_require_r2_store_names_missing_vars(r2_env, monkeypatch):
    monkeypatch.delenv("R2_BUCKET")
    with pytest.raises(RuntimeError, match="R2_BUCKET"):
        require_r2_store()
