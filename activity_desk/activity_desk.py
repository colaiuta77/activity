# 사용자 활동을 공통 플러그인 데스크의 세로 스크롤 목록으로 제공합니다.
from plugins.metadata.activity.activity import PLUGIN_VERSION, ActivityMetadataProvider


class ActivityDeskMetadataProvider(ActivityMetadataProvider):
    """Activity 데이터를 공통 플러그인 데스크에도 표시합니다."""

    id = "activity_desk"
    name = "사용자 활동 데스크"
    version = PLUGIN_VERSION
    show_overall_summary = True
    config_schema = []
    dashboard_widget = {
        "title": "최근 사용자 활동",
        "subtitle": "사용자별 도서 진행도와 마지막 열람 시각",
        "provider": "BookOasis",
        "icon": "fa-solid fa-users-viewfinder",
        "limit": 20,
        "all_desk_tab": False,
    }

    def get_plugin_config(self, db_type, default=None):
        """전용 탭 Activity의 사용자별 표시 권수 설정을 공유합니다."""
        gateway = self.get_db_gateway(db_type)
        return gateway.get_plugin_config(ActivityMetadataProvider.id, default=default)
