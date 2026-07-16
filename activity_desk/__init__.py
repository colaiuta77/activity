# 공통 플러그인 데스크용 사용자 활동 클래스를 패키지 외부에 노출합니다.
from .activity_desk import PLUGIN_VERSION, ActivityDeskMetadataProvider

__all__ = ["ActivityDeskMetadataProvider", "PLUGIN_VERSION"]
