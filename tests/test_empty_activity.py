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

    def test_returns_audiobook_activity_with_listening_progress(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            CREATE TABLE audiobooks (
                id INTEGER PRIMARY KEY,
                library_id INTEGER,
                title TEXT,
                poster TEXT,
                total_duration REAL,
                is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE audiobook_progress (
                id INTEGER PRIMARY KEY,
                audiobook_id INTEGER,
                user_id INTEGER,
                current_time REAL,
                total_progress_pct REAL,
                is_completed INTEGER DEFAULT 0,
                last_listened_at TEXT
            );
            INSERT INTO users VALUES (1, 'listener');
            INSERT INTO audiobooks VALUES (10, 3, '테스트 오디오북', 'poster.webp', 7200, 0);
            INSERT INTO audiobook_progress VALUES (1, 10, 1, 1800, 25, 0, '2026-08-05 09:30:00');
            """
        )

        result = self._provider(_Gateway(connection)).get_dashboard_data("audiobook")
        activity = next(item for item in result["items"] if not item.get("item_type"))

        self.assertTrue(result["success"])
        self.assertEqual("audiobook", activity["media_type"])
        self.assertEqual("/api/media/audiobooks/10/cover", activity["cover"])
        self.assertEqual("청취 · 30분/2시간 · 25%", activity["publisher"])
        self.assertEqual(1800, activity["current_seconds"])
        self.assertEqual(7200, activity["total_seconds"])
        self.assertEqual(1, result["summary"]["in_progress"])

    def test_exposes_category_ui_and_update_assets(self):
        provider = self.provider_class()

        self.assertEqual("1.2.0", provider.version)
        self.assertIsNone(provider.dashboard_widget)
        self.assertEqual("사용자 활동", provider.category_tab["title"])
        self.assertIn("index.html", provider.update_manifest["files"])
        self.assertIn("script.js", provider.update_manifest["files"])

    def test_category_ui_exposes_library_filters_and_summary_icons(self):
        plugin_root = Path(__file__).resolve().parents[1]
        html = (plugin_root / "index.html").read_text(encoding="utf-8")
        script = (plugin_root / "script.js").read_text(encoding="utf-8")

        for db_type in ("general", "adult", "audiobook"):
            self.assertIn(f'data-type="{db_type}"', html)
        for icon in ("fa-user-group", "fa-clock-rotate-left", "fa-book-open-reader", "fa-circle-check"):
            self.assertIn(icon, html)
        self.assertIn("pageState.dbType = nextType", script)
        self.assertIn("encodeURIComponent(pageState.dbType)", script)
        self.assertIn("window.openAudioPlayer(item.book_id)", script)


if __name__ == "__main__":
    unittest.main()
