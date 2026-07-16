# 사용자별 최근 도서 열람 활동을 대시보드 위젯으로 제공합니다.
from html import escape
from urllib.parse import quote

from plugins.metadata.base import BaseMetadataProvider


class ActivityMetadataProvider(BaseMetadataProvider):
    """기존 독서 진행 기록을 읽기 전용 활동 목록으로 제공합니다."""

    id = "activity"
    name = "사용자 활동"
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
    def _is_admin_request():
        try:
            from flask import has_request_context, session

            return has_request_context() and session.get("role") == "admin"
        except (ImportError, RuntimeError):
            return False

    def get_dashboard_data(self, db_type, limit=20):
        if not self._is_admin_request():
            return {"success": False, "error": "관리자만 사용자 활동을 조회할 수 있습니다."}

        safe_limit = self._items_per_user(db_type, limit)
        gateway = self.get_db_gateway(db_type)
        rows = gateway.fetch_all(
            """
            SELECT
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
                    u.username,
                    b.title,
                    b.series_name,
                    b.library_id,
                    b.cover_image,
                    p.pages_read,
                    b.total_pages,
                    p.last_read_at,
                    p.id,
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
            ORDER BY username COLLATE NOCASE ASC, last_read_at DESC, id DESC
            """,
            (safe_limit,),
        )

        grouped_rows = {}
        for row in rows:
            grouped_rows.setdefault(row["username"], []).append(row)

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
