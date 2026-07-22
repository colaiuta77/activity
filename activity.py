# 사용자별 최근 도서 열람 활동을 대시보드 위젯으로 제공합니다.
import json
import logging
from html import escape
from urllib.parse import quote

from plugins.metadata.base import BaseMetadataProvider

PLUGIN_VERSION = "1.0.3"
logger = logging.getLogger(__name__)


class ActivityMetadataProvider(BaseMetadataProvider):
    """기존 독서 진행 기록을 읽기 전용 활동 목록으로 제공합니다."""

    id = "activity"
    name = "사용자 활동"
    version = PLUGIN_VERSION
    show_overall_summary = False
    is_searchable = False
    config_schema = [
        {
            "key": "ITEMS_PER_USER",
            "label": "사용자별 표시 권수",
            "type": "number",
            "default": 20,
            "required": True,
            "description": "사용자 한 명당 최근 활동에 표시할 최대 도서 수입니다. 1~100권까지 적용됩니다.",
        }
    ]
    dashboard_widget = {
        "title": "최근 사용자 활동",
        "subtitle": "사용자별 도서 진행도와 마지막 열람 시각",
        "provider": "BookOasis",
        "icon": "fa-solid fa-users-viewfinder",
        "limit": 20,
        "all_desk_tab": True,
    }
    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/colaiuta77/activity/main",
        "files": ["activity.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "사용자 활동 플러그인은 메타데이터 적용을 지원하지 않습니다."

    @staticmethod
    def _normalize_limit(limit):
        try:
            return max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            return 20

    @staticmethod
    def _cover_url(cover_image):
        if not cover_image:
            return "/static/images/default_cover.jpg"
        return f"/covers/{quote(str(cover_image), safe='/')}"

    @staticmethod
    def _empty_state_item():
        return {
            "item_type": "metric",
            "metric": "📖 <strong>최근 사용자 활동</strong>",
            "value": "아무도 읽은 책이 없습니다.",
            "description": "도서를 열람하면 사용자별 최근 활동이 여기에 표시됩니다.",
        }

    @staticmethod
    def _error_state_item():
        return {
            "item_type": "metric",
            "metric": "⚠️ <strong>사용자 활동</strong>",
            "value": "사용자 활동을 불러오지 못했습니다.",
            "description": "잠시 후 다시 시도하고 BookOasis 로그를 확인해 주세요.",
        }

    @staticmethod
    def _progress_text(pages_read, total_pages):
        pages = max(0, int(pages_read or 0))
        total = max(0, int(total_pages or 0))
        percent = min(100, round((pages / total) * 100)) if total else 0
        if total and percent >= 100:
            return f"완독 · {pages}/{total}페이지 · 100%"
        if total:
            return f"진행 · {pages}/{total}페이지 · {percent}%"
        return f"진행 · {pages}페이지"

    @staticmethod
    def _progress_html(pages_read, total_pages):
        pages = max(0, int(pages_read or 0))
        total = max(0, int(total_pages or 0))
        percent = min(100, round((pages / total) * 100)) if total else 0
        completed = total and percent >= 100
        label = "완독" if completed else "진행"
        color = "#4ade80" if completed else "#c084fc"
        page_text = f"{pages}/{total}페이지" if total else f"{pages}페이지"
        percent_text = f" {percent}%" if total else ""
        return (
            f'<span style="color:{color};font-weight:700">{label}{percent_text}</span>'
            f"<br><small>{page_text}</small>"
        )

    @staticmethod
    def _format_date(last_read_at):
        value = str(last_read_at or "").replace("T", " ")
        return value[:16]

    def _items_per_user(self, db_type, fallback):
        try:
            config = self.get_plugin_config(db_type, default={})
        except Exception:
            config = {}
        configured_limit = config.get("ITEMS_PER_USER", fallback) if isinstance(config, dict) else fallback
        return self._normalize_limit(configured_limit)

    @staticmethod
    def _get_pending_progress(db_type):
        try:
            from utils.redis_helper import get_redis_client, make_key

            client = get_redis_client()
            if not client:
                return {}

            normalized_db_type = str(db_type or "general").strip()
            pending_key = make_key("sync:progress:pending")
            pending_items = client.smembers(pending_key) or ()
            progress = {}

            for raw_item in pending_items:
                item = raw_item.decode("utf-8") if isinstance(raw_item, bytes) else str(raw_item)
                parts = item.split(":", 2)
                if len(parts) != 3 or parts[0] != normalized_db_type:
                    continue

                try:
                    user_id = int(parts[1])
                    book_id = int(parts[2])
                except (TypeError, ValueError):
                    continue

                try:
                    raw_payload = client.get(make_key(f"user:progress:{normalized_db_type}:{user_id}:{book_id}"))
                    if not raw_payload:
                        continue
                    if isinstance(raw_payload, bytes):
                        raw_payload = raw_payload.decode("utf-8")

                    payload = json.loads(raw_payload)
                    if isinstance(payload, dict):
                        progress[(user_id, book_id)] = payload
                except Exception:
                    continue

            return progress
        except Exception:
            return {}

    @staticmethod
    def _load_pending_row(gateway, user_id, book_id):
        row = gateway.fetch_one(
            """
            SELECT
                p.id AS progress_id,
                u.id AS user_id,
                b.id AS book_id,
                u.username,
                b.title,
                b.series_name,
                b.library_id,
                b.cover_image,
                p.pages_read,
                b.total_pages,
                p.last_read_at,
                (
                    SELECT COUNT(*)
                    FROM user_progress all_progress
                    JOIN books all_books ON all_books.id = all_progress.book_id
                    WHERE all_progress.user_id = u.id AND COALESCE(all_books.is_deleted, 0) = 0
                )
                    AS user_total_activities,
                CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS is_persisted
            FROM users u
            JOIN books b ON b.id = ?
            LEFT JOIN user_progress p ON p.book_id = b.id AND p.user_id = u.id
            WHERE u.id = ? AND COALESCE(b.is_deleted, 0) = 0
            """,
            (book_id, user_id),
        )
        return dict(row) if row else None

    def _merge_pending_progress(self, gateway, rows, pending_progress):
        merged_rows = {}
        user_totals = {}
        cached_only_counts = {}

        for raw_row in rows:
            row = dict(raw_row)
            user_id = int(row["user_id"])
            book_id = int(row["book_id"])
            merged_rows[(user_id, book_id)] = row
            user_totals[user_id] = max(
                user_totals.get(user_id, 0),
                int(row.get("user_total_activities") or 0),
            )

        for (user_id, book_id), payload in pending_progress.items():
            row = merged_rows.get((user_id, book_id))
            if row is None:
                row = self._load_pending_row(gateway, user_id, book_id)
                if row is None:
                    continue
                merged_rows[(user_id, book_id)] = row
                user_totals[user_id] = max(
                    user_totals.get(user_id, 0),
                    int(row.get("user_total_activities") or 0),
                )
                if not int(row.get("is_persisted") or 0):
                    cached_only_counts[user_id] = cached_only_counts.get(user_id, 0) + 1

            try:
                row["pages_read"] = max(0, int(payload.get("pages_read", row.get("pages_read") or 0)))
            except (TypeError, ValueError):
                pass
            if payload.get("last_read_at"):
                row["last_read_at"] = payload["last_read_at"]

        for user_id, cached_only_count in cached_only_counts.items():
            user_totals[user_id] = user_totals.get(user_id, 0) + cached_only_count

        for (user_id, _), row in merged_rows.items():
            row["user_total_activities"] = user_totals.get(user_id, 0)

        return list(merged_rows.values())

    @staticmethod
    def _is_admin_request():
        try:
            from flask import has_request_context, session

            return has_request_context() and session.get("role") == "admin"
        except (ImportError, RuntimeError):
            return False

    def get_dashboard_data(self, db_type, limit=20):
        if not self._is_admin_request():
            return {"success": False, "error": "관리자만 사용자 활동을 조회할 수 있습니다."}

        try:
            return self._build_dashboard_data(db_type, limit)
        except Exception:
            logger.exception("사용자 활동 조회에 실패했습니다.")
            return {"success": True, "items": [self._error_state_item()]}

    def _build_dashboard_data(self, db_type, limit=20):
        safe_limit = self._items_per_user(db_type, limit)
        gateway = self.get_db_gateway(db_type)
        rows = gateway.fetch_all(
            """
            SELECT
                user_id,
                book_id,
                progress_id,
                username,
                title,
                series_name,
                library_id,
                cover_image,
                pages_read,
                total_pages,
                last_read_at,
                user_total_activities
            FROM (
                SELECT
                    p.user_id AS user_id,
                    p.book_id AS book_id,
                    p.id AS progress_id,
                    u.username,
                    b.title,
                    b.series_name,
                    b.library_id,
                    b.cover_image,
                    p.pages_read,
                    b.total_pages,
                    p.last_read_at,
                    COUNT(*) OVER (PARTITION BY p.user_id) AS user_total_activities,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.user_id
                        ORDER BY p.last_read_at DESC, p.id DESC
                    ) AS user_row_number
                FROM user_progress p
                JOIN users u ON u.id = p.user_id
                JOIN books b ON b.id = p.book_id
                WHERE COALESCE(b.is_deleted, 0) = 0
            ) ranked_activity
            WHERE user_row_number <= ?
            ORDER BY username COLLATE NOCASE ASC, last_read_at DESC, progress_id DESC
            """,
            (safe_limit,),
        )

        rows = self._merge_pending_progress(gateway, rows, self._get_pending_progress(db_type))
        all_grouped_rows = {}
        for row in rows:
            all_grouped_rows.setdefault(row["username"], []).append(row)

        grouped_rows = {}
        for username in sorted(all_grouped_rows, key=lambda value: str(value).casefold()):
            user_rows = sorted(
                all_grouped_rows[username],
                key=lambda row: (
                    str(row.get("last_read_at") or ""),
                    int(row.get("progress_id") or row.get("book_id") or 0),
                ),
                reverse=True,
            )
            grouped_rows[username] = user_rows[:safe_limit]

        if not grouped_rows:
            return {"success": True, "items": [self._empty_state_item()]}

        items = []
        if self.show_overall_summary:
            total_activity_count = sum(
                int(user_rows[0]["user_total_activities"] or 0)
                for user_rows in grouped_rows.values()
                if user_rows
            )
            items.append(
                {
                    "item_type": "metric",
                    "metric": "<strong>전체 활동 요약</strong>",
                    "value": (
                        "사용자 "
                        f'<span style="color:#38bdf8;font-weight:700">{len(grouped_rows)}명</span>'
                        " · 열람 기록 "
                        f'<span style="color:#c084fc;font-weight:700">{total_activity_count}건</span>'
                    ),
                    "description": f"사용자별 최근 최대 <strong>{safe_limit}권</strong> 표시",
                }
            )

        for username, user_rows in grouped_rows.items():
            user_total = int(user_rows[0]["user_total_activities"] or 0)
            safe_username = escape(str(username or ""), quote=True)
            items.append(
                {
                    "item_type": "metric",
                    "metric": f"👤 <strong>{safe_username}</strong>",
                    "value": (
                        "최근 "
                        f'<span style="color:#c084fc;font-weight:700">{len(user_rows)}건</span>'
                        f" 표시 <small>/ 전체 {user_total}건</small>"
                    ),
                    "description": "마지막 열람 시각 <strong>내림차순</strong>",
                }
            )
            for row in user_rows:
                items.append(
                    {
                        "title": row["title"],
                        "author": f"👤 {row['username']}",
                        "publisher": self._progress_text(row["pages_read"], row["total_pages"]),
                        "pubDate": self._format_date(row["last_read_at"]),
                        "cover": self._cover_url(row["cover_image"]),
                        "description": self._progress_html(row["pages_read"], row["total_pages"]),
                        "link": "#",
                        "series_name": row["series_name"] or row["title"],
                        "library_id": row["library_id"],
                    }
                )

        return {"success": True, "items": items}
