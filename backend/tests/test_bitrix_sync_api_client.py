import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if "PIL" not in sys.modules:
    pil_module = types.ModuleType("PIL")
    pil_module.Image = types.SimpleNamespace(open=None)

    class _UnidentifiedImageError(Exception):
        pass

    pil_module.UnidentifiedImageError = _UnidentifiedImageError
    sys.modules["PIL"] = pil_module

from src.integrations.bitrix.client import BitrixSyncApiClient


def test_build_body_sorts_and_deduplicates_user_ids():
    client = BitrixSyncApiClient(endpoint="https://example.com/app_sync.php", app_key="sync-key", app_secret="sync-secret")

    body = client._build_body([42, 7, 42, 5])

    assert body == '{"user_ids":[5,7,42]}'


def test_build_signature_matches_expected_sha256_hmac():
    client = BitrixSyncApiClient(endpoint="https://example.com/app_sync.php", app_key="sync-key", app_secret="sync-secret")

    signature = client._build_signature(method="POST", timestamp="1710000000", body='{"user_ids":[5,7,42]}')

    assert signature == "88012416a14df19446de30126a17a99478d36c7bc9cc271ab5339600bec0fa17"


def test_parse_batch_result_returns_snapshots_and_errors():
    client = BitrixSyncApiClient(endpoint="https://example.com/app_sync.php", app_key="sync-key", app_secret="sync-secret")

    result = client._parse_batch_result({"ok": True, "data": {"42": {"user": {"id": 42}}}, "errors": {"77": "user_not_found"}})

    assert result.snapshots == {42: {"user": {"id": 42}}}
    assert result.errors == {77: "user_not_found"}


def test_parse_batch_result_allows_empty_list_for_empty_data():
    client = BitrixSyncApiClient(endpoint="https://example.com/app_sync.php", app_key="sync-key", app_secret="sync-secret")

    result = client._parse_batch_result({"ok": True, "data": [], "errors": {"77": "user_not_found"}})

    assert result.snapshots == {}
    assert result.errors == {77: "user_not_found"}


def test_build_timestamp_uses_unix_epoch_seconds():
    with patch("src.integrations.bitrix.client.time.time", return_value=1710000000.9):
        assert BitrixSyncApiClient._build_timestamp() == "1710000000"
