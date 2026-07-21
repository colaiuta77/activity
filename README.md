# BookOasis 사용자 활동

BookOasis에 저장된 독서 진행 기록을 이용해 사용자별 최근 열람 도서와 진행률을 보여주는 독립 설치형 Activity 탭 플러그인입니다.

![전용 사용자 활동 탭](docs/activity-tab.png)

## 버전 및 호환 정보

| 항목 | 값 |
| --- | --- |
| 플러그인 버전 | `1.0.2` |
| 플러그인 ID | `activity` |
| 클래스 | `ActivityMetadataProvider` |
| 모듈 | `plugins.metadata.activity.activity` |
| 유형 | 읽기 전용 대시보드 제공자 |
| 확인한 BookOasis 버전 | `1.2.7` |
| 확인한 BookOasis 커밋 | `b77bb62` |
| 문서 작성일 | `2026-07-21` |

이 플러그인은 BookOasis의 권장 폴더형 플러그인 구조와 `PluginDatabaseGateway`를 사용합니다. BookOasis 공통 UI나 코어 파일을 수정하지 않습니다.

## 주요 기능

- 사용자명 기준으로 활동을 구분합니다.
- 사용자별 최근 열람 도서를 마지막 열람 시각 내림차순으로 표시합니다.
- 도서 제목, 표지, 현재 페이지, 전체 페이지, 진행률과 마지막 열람 시각을 표시합니다.
- 진행 중과 완독 상태를 구분하고 제한적 HTML이 지원되는 화면에서는 색상으로 강조합니다.
- 제목이나 표지를 클릭하면 BookOasis 도서 상세 화면으로 이동합니다.
- 사용자별 표시 제한을 적용하므로 한 사용자의 기록이 다른 사용자를 밀어내지 않습니다.
- Redis에 아직 쌓여 있는 최신 진행률과 첫 열람 기록을 SQLite 결과에 병합합니다.
- 관리자 세션에서만 전체 사용자 활동 데이터를 반환합니다.

## 화면 구성

`activity`는 `all_desk_tab=True`인 전용 탭입니다. 사용자별 요약과 해당 사용자의 최근 도서를 표시하며 전체 활동 요약은 표시하지 않습니다.

공통 플러그인 데스크에서도 같은 활동을 표시하려면 별도 [Activity Desk 플러그인](https://github.com/colaiuta77/activity_desk)을 추가로 설치하세요.

## 설정

| 키 | UI 유형 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `ITEMS_PER_USER` | number | `20` | 사용자 한 명당 표시할 최근 도서 수. 허용 범위 1~100 |

설정은 `환경설정 > 플러그인 설정 > 사용자 활동`에서 저장합니다. 별도 Activity Desk 플러그인도 이 값을 공유합니다.

## 설치

최종 폴더 구조는 다음과 같습니다.

```text
plugins/metadata/
└── activity/
    ├── __init__.py
    ├── activity.py
    └── VERSION
```

BookOasis의 `plugins/metadata/`에서 다음 명령을 실행합니다.

```bash
git clone https://github.com/colaiuta77/activity.git activity
```

1. BookOasis 서버를 재시작합니다.
2. `환경설정 > 플러그인 설정`에서 `사용자 활동`을 활성화합니다.
3. 라이브러리의 플러그인 화면에서 전용 Activity 탭을 확인합니다.

업데이트할 때는 BookOasis의 `plugins/metadata/`에서 다음 명령을 실행합니다.

```bash
git -C activity pull --ff-only
```

### 자동 업데이트

버전 1.0.2부터 BookOasis의 `update_manifest` 계약과 `VERSION` 파일을 지원합니다. `환경설정 > 플러그인 설정 > 사용자 활동`에 표시되는 업데이트 버튼으로 GitHub `main`의 `activity.py`, `__init__.py`, `VERSION`을 갱신할 수 있습니다.

1.0.1 이하 설치본에는 업데이트 선언과 `VERSION` 파일이 없으므로 위 `git pull` 방식으로 1.0.2 이상을 한 번 설치해야 합니다. 이후에는 GitHub 버전이 현재 버전보다 높을 때만 자동 업데이트가 실행됩니다.

Docker 환경에서는 BookOasis 소스가 연결된 호스트 볼륨 또는 컨테이너의 동일한 경로에 설치해야 합니다. BookOasis 업데이트 후에도 플러그인 폴더가 유지되는지 확인하세요.

## 데이터와 보안

- `users`, `user_progress`, `books` 테이블을 DB Gateway를 통해 읽기 전용으로 조회합니다.
- BookOasis 1.2.1의 `sync:progress:pending`과 `user:progress` Redis 키를 읽기 전용으로 병합합니다.
- Redis를 사용할 수 없거나 데이터가 손상된 경우 해당 항목을 건너뛰고 SQLite 결과를 사용합니다.
- 삭제된 도서는 활동 목록에서 제외합니다.
- 위젯 데이터 요청 시 Flask 세션의 관리자 역할을 다시 확인합니다.
- 사용자명은 제한적 HTML 필드에 넣기 전에 HTML 이스케이프합니다.
- 메타데이터 검색과 적용은 지원하지 않습니다.

## 제한 사항

- 이 화면은 실시간 접속 목록이 아니라 SQLite `user_progress`와 아직 flush되지 않은 Redis 진행률을 기준으로 한 최근 활동입니다.
- BookOasis가 저장하지 않는 IP, 브라우저, 운영체제, 클라이언트 종류와 온라인 상태는 표시할 수 없습니다.
- 상세 이동에는 대시보드 플러그인 클릭 계약이 포함된 BookOasis 버전이 필요합니다.
- 제한적 HTML은 `metric`, `value`, `description` 등 BookOasis가 허용한 필드에서만 사용합니다. 임의 HTML 레이아웃, CSS 파일과 JavaScript 삽입은 지원되지 않습니다.
- BookOasis의 플러그인 계약 또는 DB 스키마가 변경되면 호환성 업데이트가 필요할 수 있습니다.

## 검증

```powershell
python -m py_compile __init__.py activity.py
```

## 변경 이력

### 1.0.2 - 2026-07-21

- BookOasis 플러그인 자동 업데이트용 `update_manifest` 추가.
- 공식 규격의 `VERSION` 파일과 `plugin version` 키 추가.
- GitHub `main`의 런타임 파일만 갱신하도록 업데이트 범위 제한.

### 1.0.1 - 2026-07-20

- 저장소 루트를 `plugins/metadata/activity`에 직접 clone할 수 있는 단일 플러그인 구조로 변경.
- Activity Desk를 별도 저장소로 분리.
- BookOasis 1.2.1의 Redis 비동기 진행률 저장 방식 지원.
- SQLite에 아직 반영되지 않은 최신 페이지와 마지막 열람 시각을 Redis pending 데이터로 보정.
- Redis에만 존재하는 첫 열람 도서도 사용자별 최근 활동과 전체 건수에 포함.
- Redis 데이터 병합 후 사용자별 날짜 내림차순과 표시 권수 제한을 다시 적용.
- Redis 미사용, 연결 실패와 손상된 JSON에서 기존 SQLite 조회로 안전하게 폴백.

### 1.0.0 - 2026-07-16

- 사용자별 최근 독서 활동 전용 탭 추가.
- 공통 플러그인 데스크용 세로 스크롤 위젯 추가.
- 사용자별 표시 권수 설정과 날짜 내림차순 정렬 추가.
- 제목과 표지의 도서 상세 이동 계약 지원.
- 전체 및 사용자별 요약과 진행·완독 상태 표시 추가.
- 제한적 HTML 강조와 사용자명 HTML 이스케이프 적용.
- 관리자 세션 확인과 삭제 도서 제외 처리 추가.

## 라이선스

이 저장소의 [LICENSE](LICENSE)를 따릅니다.
