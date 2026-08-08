# 사용자별 최근 도서 열람 활동을 대시보드 위젯으로 제공합니다.
import json
import logging
from html import escape
from urllib.parse import quote

from plugins.metadata.base import BaseMetadataProvider

PLUGIN_VERSION = "1.3.0"
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
        },
        {
            "key": "DESK_ITEM_LIMIT",
            "label": "공통 데스크 표시 권수",
            "type": "number",
            "default": 5,
            "required": True,
            "description": "Activity Desk에 최근 활동을 최대 몇 건 표시할지 지정합니다. 1~20건까지 적용됩니다.",
        },
        {
            "key": "DEFAULT_SORT",
            "label": "기본 정렬",
            "type": "select",
            "default": "recent",
            "options": [
                {"value": "recent", "label": "최근 열람순"},
                {"value": "progress", "label": "진행률 높은 순"},
                {"value": "username", "label": "사용자명순"},
            ],
        },
        {
            "key": "SHOW_COMPLETED",
            "label": "완독 도서 표시",
            "type": "checkbox",
            "default": True,
        },
        {
            "key": "SHOW_USER_SUMMARY",
            "label": "사용자별 요약 표시",
            "type": "checkbox",
            "default": True,
        },
    ]
    dashboard_widget = None
    category_tab = {
        "title": "사용자 활동",
        "icon": "fa-solid fa-users-viewfinder",
        "order": 80,
    }
    update_manifest = {
        "enabled": True,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/colaiuta77/activity/main",
        "files": ["activity.py", "__init__.py", "VERSION", "index.html", "style.css", "script.js"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": True,
    }

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "사용자 활동 플러그인은 메타데이터 적용을 지원하지 않습니다."

    def get_context_menu_items(self, db_type, context):
        context = context or {}
        if not self._is_admin_request() or not context.get("book_id"):
            return []
        return [
            {
                "id": "show_book_activity",
                "label": "이 책의 열람 활동 요약",
                "icon": "fa-solid fa-users-viewfinder",
            }
        ]

    def run_context_menu_action(self, db_type, action_id, context):
        context = context or {}
        if action_id != "show_book_activity":
            return {"success": False, "error": "지원하지 않는 사용자 활동 메뉴입니다."}
        if not self._is_admin_request():
            return {"success": False, "error": "관리자만 사용자 활동을 조회할 수 있습니다."}

        try:
            book_id = int(context.get("book_id"))
        except (TypeError, ValueError):
            return {"success": False, "error": "도서 식별자가 올바르지 않습니다."}

        normalized_db_type = self._normalize_db_type(db_type)
        rows = self.get_db_gateway(normalized_db_type).fetch_all(
            """
            SELECT p.user_id, p.pages_read, b.total_pages, p.last_read_at
            FROM user_progress p
            JOIN books b ON b.id = p.book_id
            WHERE p.book_id = ? AND COALESCE(b.is_deleted, 0) = 0
            ORDER BY p.last_read_at DESC, p.id DESC
            """,
            (book_id,),
        )
        if not rows:
            return {"success": True, "message": "이 책의 열람 활동이 아직 없습니다."}

        usernames_by_id = self._load_general_usernames()
        summaries = []
        for row in rows[:5]:
            user_id = int(row["user_id"])
            username = usernames_by_id.get(user_id) or f"사용자 #{user_id}"
            summaries.append(
                f"{username} · {self._progress_text(row['pages_read'], row['total_pages'])}"
            )
        remainder = len(rows) - len(summaries)
        message = "\n".join(summaries)
        if remainder > 0:
            message += f"\n외 {remainder}명"
        return {"success": True, "message": message}

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
    def _audiobook_cover_url(audiobook_id):
        return f"/api/media/audiobooks/{int(audiobook_id)}/cover"

    @staticmethod
    def _empty_state_item(is_audiobook=False):
        if is_audiobook:
            return {
                "item_type": "metric",
                "metric": "<strong>최근 사용자 활동</strong>",
                "value": "아무도 청취한 오디오북이 없습니다.",
                "description": "오디오북을 청취하면 사용자별 최근 활동이 여기에 표시됩니다.",
            }
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
    def _duration_text(seconds):
        total_seconds = max(0, int(float(seconds or 0)))
        if total_seconds < 60:
            return f"{total_seconds}초"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes}분"
        hours, remaining_minutes = divmod(minutes, 60)
        return f"{hours}시간 {remaining_minutes}분" if remaining_minutes else f"{hours}시간"

    @classmethod
    def _audio_progress_text(cls, current_seconds, total_seconds, progress_percent, completed):
        label = "완청" if completed else "청취"
        current = cls._duration_text(current_seconds)
        total = cls._duration_text(total_seconds)
        duration = f"{current}/{total}" if int(float(total_seconds or 0)) > 0 else current
        return f"{label} · {duration} · {progress_percent}%"

    @classmethod
    def _audio_progress_html(cls, current_seconds, total_seconds, progress_percent, completed):
        label = "완청" if completed else "청취"
        color = "#4ade80" if completed else "#c084fc"
        current = cls._duration_text(current_seconds)
        total = cls._duration_text(total_seconds)
        duration = f"{current}/{total}" if int(float(total_seconds or 0)) > 0 else current
        return (
            f'<span style="color:{color};font-weight:700">{label} {progress_percent}%</span>'
            f"<br><small>{duration}</small>"
        )

    @staticmethod
    def _format_date(last_read_at):
        value = str(last_read_at or "").replace("T", " ")
        return value[:16]

    def _plugin_config(self, db_type):
        try:
            config = self.get_plugin_config(db_type, default={})
        except Exception:
            config = {}
        return config if isinstance(config, dict) else {}

    def _items_per_user(self, db_type, fallback, config=None):
        config = config if isinstance(config, dict) else self._plugin_config(db_type)
        configured_limit = config.get("ITEMS_PER_USER", fallback) if isinstance(config, dict) else fallback
        return self._normalize_limit(configured_limit)

    @staticmethod
    def _normalize_desk_limit(value):
        try:
            return max(1, min(int(value), 20))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _config_bool(config, key, default=True):
        value = config.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", ""}
        return bool(value)

    @staticmethod
    def _normalize_db_type(db_type):
        normalized = str(db_type or "general").strip().lower()
        return normalized if normalized in {"general", "adult", "audiobook"} else "general"

    def _load_general_usernames(self):
        rows = self.get_db_gateway("general").fetch_all(
            "SELECT id, username FROM users ORDER BY id ASC"
        ) or []
        return {
            int(row["id"]): str(row.get("username") or "")
            for row in (dict(raw_row) for raw_row in rows)
        }

    def _attach_usernames(self, rows):
        usernames_by_id = self._load_general_usernames()
        for row in rows:
            user_id = int(row["user_id"])
            row["username"] = usernames_by_id.get(user_id) or f"사용자 #{user_id}"
        return rows

    @staticmethod
    def _progress_percent(pages_read, total_pages):
        pages = max(0, int(pages_read or 0))
        total = max(0, int(total_pages or 0))
        return min(100, round((pages / total) * 100)) if total else 0

    @classmethod
    def _row_progress_percent(cls, row):
        override = row.get("progress_percent_override")
        if override is not None:
            try:
                return max(0, min(100, round(float(override))))
            except (TypeError, ValueError):
                pass
        return cls._progress_percent(row.get("pages_read"), row.get("total_pages"))

    @classmethod
    def _row_is_completed(cls, row):
        return bool(int(row.get("is_completed") or 0) or cls._row_progress_percent(row) >= 100)

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
                ? AS user_id,
                b.id AS book_id,
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
                    WHERE all_progress.user_id = ? AND COALESCE(all_books.is_deleted, 0) = 0
                )
                    AS user_total_activities,
                CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS is_persisted
            FROM books b
            LEFT JOIN user_progress p ON p.book_id = b.id AND p.user_id = ?
            WHERE b.id = ? AND COALESCE(b.is_deleted, 0) = 0
            """,
            (user_id, user_id, user_id, book_id),
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
        normalized_db_type = self._normalize_db_type(db_type)
        config = self._plugin_config(normalized_db_type)
        safe_limit = self._items_per_user(normalized_db_type, limit, config=config)
        default_sort = str(config.get("DEFAULT_SORT", "recent") or "recent").strip().lower()
        if default_sort not in {"recent", "progress", "username"}:
            default_sort = "recent"
        show_completed = self._config_bool(config, "SHOW_COMPLETED", True)
        show_user_summary = self._config_bool(config, "SHOW_USER_SUMMARY", True)
        gateway = self.get_db_gateway(normalized_db_type)
        is_audiobook = normalized_db_type == "audiobook"
        if is_audiobook:
            rows = gateway.fetch_all(
                """
                SELECT
                    user_id,
                    book_id,
                    progress_id,
                    title,
                    series_name,
                    library_id,
                    cover_image,
                    pages_read,
                    total_pages,
                    last_read_at,
                    user_total_activities,
                    progress_percent_override,
                    is_completed,
                    media_type
                FROM (
                    SELECT
                        p.user_id AS user_id,
                        p.audiobook_id AS book_id,
                        p.id AS progress_id,
                        a.title,
                        a.title AS series_name,
                        a.library_id,
                        a.poster AS cover_image,
                        p.current_time AS pages_read,
                        a.total_duration AS total_pages,
                        p.last_listened_at AS last_read_at,
                        p.total_progress_pct AS progress_percent_override,
                        p.is_completed,
                        'audiobook' AS media_type,
                        COUNT(*) OVER (PARTITION BY p.user_id) AS user_total_activities,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.user_id
                            ORDER BY p.last_listened_at DESC, p.id DESC
                        ) AS user_row_number
                    FROM audiobook_progress p
                    JOIN audiobooks a ON a.id = p.audiobook_id
                    WHERE COALESCE(a.is_deleted, 0) = 0
                ) ranked_activity
                WHERE user_row_number <= ?
                ORDER BY user_id ASC, last_read_at DESC, progress_id DESC
                """,
                (safe_limit,),
            )
        else:
            rows = gateway.fetch_all(
                """
                SELECT
                    user_id,
                    book_id,
                    progress_id,
                    title,
                    series_name,
                    library_id,
                    cover_image,
                    pages_read,
                    total_pages,
                    last_read_at,
                    user_total_activities,
                    NULL AS progress_percent_override,
                    0 AS is_completed,
                    'book' AS media_type
                FROM (
                    SELECT
                        p.user_id AS user_id,
                        p.book_id AS book_id,
                        p.id AS progress_id,
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
                    JOIN books b ON b.id = p.book_id
                    WHERE COALESCE(b.is_deleted, 0) = 0
                ) ranked_activity
                WHERE user_row_number <= ?
                ORDER BY user_id ASC, last_read_at DESC, progress_id DESC
                """,
                (safe_limit,),
            )

        rows = [dict(row) for row in rows]
        if not is_audiobook:
            rows = self._merge_pending_progress(
                gateway,
                rows,
                self._get_pending_progress(normalized_db_type),
            )
        rows = self._attach_usernames(rows)
        all_user_totals = {}
        for row in rows:
            user_id = int(row["user_id"])
            all_user_totals[user_id] = max(
                all_user_totals.get(user_id, 0),
                int(row.get("user_total_activities") or 0),
            )

        if not show_completed:
            rows = [
                row
                for row in rows
                if not self._row_is_completed(row)
            ]

        all_grouped_rows = {}
        for row in rows:
            all_grouped_rows.setdefault(row["username"], []).append(row)

        grouped_rows = {}
        for username in sorted(all_grouped_rows, key=lambda value: str(value).casefold()):
            if default_sort == "progress":
                sort_key = lambda row: (
                    self._row_progress_percent(row),
                    str(row.get("last_read_at") or ""),
                )
            else:
                sort_key = lambda row: (
                    str(row.get("last_read_at") or ""),
                    int(row.get("progress_id") or row.get("book_id") or 0),
                )
            user_rows = sorted(all_grouped_rows[username], key=sort_key, reverse=True)
            grouped_rows[username] = user_rows[:safe_limit]

        if not grouped_rows:
            return {
                "success": True,
                "items": [self._empty_state_item(is_audiobook=is_audiobook)],
                "summary": {
                    "users": len(all_user_totals),
                    "total_activities": sum(all_user_totals.values()),
                    "displayed_activities": 0,
                    "in_progress": 0,
                    "completed": 0,
                },
                "preferences": {
                    "default_sort": default_sort,
                    "show_completed": show_completed,
                    "show_user_summary": show_user_summary,
                },
            }

        items = []
        activity_rows = [row for user_rows in grouped_rows.values() for row in user_rows]
        completed_count = sum(
            1
            for row in activity_rows
            if self._row_is_completed(row)
        )
        summary = {
            "users": len(all_user_totals),
            "total_activities": sum(all_user_totals.values()),
            "displayed_activities": len(activity_rows),
            "in_progress": len(activity_rows) - completed_count,
            "completed": completed_count,
        }
        if self.show_overall_summary:
            activity_label = "청취 기록" if is_audiobook else "열람 기록"
            items.append(
                {
                    "item_type": "metric",
                    "metric": "<strong>전체 활동 요약</strong>",
                    "value": (
                        "사용자 "
                        f'<span style="color:#38bdf8;font-weight:700">{summary["users"]}명</span>'
                        f" · {activity_label} "
                        f'<span style="color:#c084fc;font-weight:700">{summary["total_activities"]}건</span>'
                    ),
                    "description": f"사용자별 최근 최대 <strong>{safe_limit}권</strong> 표시",
                }
            )

        for username, user_rows in grouped_rows.items():
            user_total = int(user_rows[0]["user_total_activities"] or 0)
            safe_username = escape(str(username or ""), quote=True)
            if show_user_summary:
                items.append(
                    {
                        "item_type": "metric",
                        "metric": f"👤 <strong>{safe_username}</strong>",
                        "value": (
                            "최근 "
                            f'<span style="color:#c084fc;font-weight:700">{len(user_rows)}건</span>'
                            f" 표시 <small>/ 전체 {user_total}건</small>"
                        ),
                        "description": "사용자 활동 요약",
                    }
                )
            for row in user_rows:
                progress_percent = self._row_progress_percent(row)
                completed = self._row_is_completed(row)
                if row.get("media_type") == "audiobook":
                    progress_text = self._audio_progress_text(
                        row["pages_read"], row["total_pages"], progress_percent, completed
                    )
                    progress_html = self._audio_progress_html(
                        row["pages_read"], row["total_pages"], progress_percent, completed
                    )
                    cover_url = self._audiobook_cover_url(row["book_id"])
                else:
                    progress_text = self._progress_text(row["pages_read"], row["total_pages"])
                    progress_html = self._progress_html(row["pages_read"], row["total_pages"])
                    cover_url = self._cover_url(row["cover_image"])
                items.append(
                    {
                        "title": row["title"],
                        "author": f"👤 {row['username']}",
                        "publisher": progress_text,
                        "pubDate": self._format_date(row["last_read_at"]),
                        "cover": cover_url,
                        "description": progress_html,
                        "link": "#",
                        "series_name": row["series_name"] or row["title"],
                        "library_id": row["library_id"],
                        "book_id": row["book_id"],
                        "username": str(row["username"] or ""),
                        "pages_read": max(0, int(row["pages_read"] or 0)),
                        "total_pages": max(0, int(row["total_pages"] or 0)),
                        "progress_percent": progress_percent,
                        "is_completed": completed,
                        "last_read_at": str(row["last_read_at"] or ""),
                        "user_total_activities": user_total,
                        "media_type": row.get("media_type") or "book",
                        "db_type": normalized_db_type,
                        "current_seconds": max(0, int(float(row["pages_read"] or 0))) if is_audiobook else 0,
                        "total_seconds": max(0, int(float(row["total_pages"] or 0))) if is_audiobook else 0,
                    }
                )

        return {
            "success": True,
            "items": items,
            "summary": summary,
            "preferences": {
                "default_sort": default_sort,
                "show_completed": show_completed,
                "show_user_summary": show_user_summary,
            },
        }
