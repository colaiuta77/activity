# 독서 기록이 없거나 조회가 실패할 때 Activity 상태 응답을 검증합니다.
import importlib.util
import sqlite3
import sys
import types
import unittest
from pathlib import Path


class _BaseMetadataProvider:
    def get_db_gateway(self, db_type):
        return self.gateway

    def get_plugin_config(self, db_type, default=None):
        return default


class _Gateway:
    def __init__(self, connection):
        self.connection = connection

    def fetch_all(self, query, params=()):
        cursor = self.connection.execute(query, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class _FailingGateway:
    def fetch_all(self, query, params=()):
        raise sqlite3.DatabaseError("test database error")


def _load_provider_class():
    plugins = types.ModuleType("plugins")
    metadata = types.ModuleType("plugins.metadata")
    base = types.ModuleType("plugins.metadata.base")
    base.BaseMetadataProvider = _BaseMetadataProvider
    sys.modules.update(
        {
            "plugins": plugins,
            "plugins.metadata": metadata,
            "plugins.metadata.base": base,
        }
    )

    module_path = Path(__file__).resolve().parents[1] / "activity.py"
    spec = importlib.util.spec_from_file_location("activity_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ActivityMetadataProvider


class ActivityEmptyStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_class = _load_provider_class()

    def _provider(self, gateway):
        provider = self.provider_class()
        provider.gateway = gateway
        provider._is_admin_request = lambda: True
        provider._get_pending_progress = lambda db_type: {}
        return provider

    def test_returns_empty_message_when_no_progress_exists(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                title TEXT,
                series_name TEXT,
                library_id INTEGER,
                cover_image TEXT,
                total_pages INTEGER,
                is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE user_progress (
                id INTEGER PRIMARY KEY,
                book_id INTEGER,
                user_id INTEGER,
                pages_read INTEGER,
                last_read_at TEXT
            );
            """
        )

        result = self._provider(_Gateway(connection)).get_dashboard_data("book")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["value"], "아무도 읽은 책이 없습니다.")

    def test_returns_visible_error_message_when_query_fails(self):
        with self.assertLogs("activity_under_test", level="ERROR") as captured:
            result = self._provider(_FailingGateway()).get_dashboard_data("book")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["value"], "사용자 활동을 불러오지 못했습니다.")
        self.assertIn("사용자 활동 조회에 실패했습니다.", captured.output[0])


if __name__ == "__main__":
    unittest.main()
