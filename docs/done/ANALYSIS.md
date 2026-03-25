# dash-backend 기능 분석

## 1. 프로젝트 개요
- FastAPI 기반 백엔드 (포트 8001)
- CSV 파일 기반 산업용 센서 데이터 뷰어
- 4개 디바이스(R1~R4)의 PULSE/VIB 데이터를 수집·분석·시각화

## 2. 기술 스택
- FastAPI + Uvicorn
- numpy, scipy (신호 처리)
- msgpack (캐싱)
- CORS 전체 허용, 인증 없음

## 3. 프로젝트 구조
```
dash-backend/
├── main.py                  # 앱 진입점
├── config.py                # 상수/설정 (환경변수 지원)
├── device_settings.json     # 디바이스별 파라미터
├── routers/
│   └── data_router.py       # API 엔드포인트
└── services/
    ├── cache_manager.py     # msgpack 캐시
    ├── cached_csv_parser.py # 캐싱 CSV 파서
    ├── csv_parser.py        # PULSE/VIB CSV 파싱
    ├── expected_filter.py   # 예상 펄스 수 검증
    ├── folder_scanner.py    # 파일시스템 스캔
    ├── rpm_service.py       # RPM 계산/분석
    ├── session_merger.py    # 멀티세션 병합
    ├── signal_service.py    # FFT/스펙트로그램/RMS
    └── test_export.py       # 디버그용 데이터 내보내기
```

## 4. API 엔드포인트 (prefix: `/api`)
| 엔드포인트 | 메서드 | 설명 | 파라미터 |
|---|---|---|---|
| `/api/months` | GET | 사용 가능한 월 목록 | - |
| `/api/devices` | GET | 월별 디바이스 목록 | `month` |
| `/api/dates` | GET | 날짜별 사이클 수 | `month`, `device` |
| `/api/daily-data` | GET | 일별 데이터 (필터링+병합) | `month`, `date`, `shaft_dia?`, `pattern_width?`, `target_rpm?` |
| `/api/test-export` | GET | 디버그용 CSV 내보내기 | `month`, `date`, `shaft_dia?`, `pattern_width?`, `target_rpm?` |

## 5. 핵심 기능
- **RPM 계산**: 펄스 지속시간 → RPM 변환, 에지 마스킹, 허용 범위(10/20/30%) 상태 판정
- **MPM 계산**: RPM × 롤 지름(140mm)으로 미터/분 산출
- **Expected 필터링**: 예상 펄스 수 대비 10% 이내 사이클만 유효 판정
- **세션 병합**: 4개 디바이스 데이터를 타임스탬프 기준 병합, 연속 타임라인 오프셋 계산
- **캐싱**: msgpack 기반, 소스 파일 mtime/size 기반 무효화
- **신호 분석**: FFT, 스펙트로그램, RMS, 다운샘플링 (현재 엔드포인트 미연결)

## 6. 데이터 흐름
```
API 요청 → 폴더 스캔 → CSV 파싱(캐싱) → RPM 계산 → Expected 검증
→ 세션 병합 → 타임라인 오프셋 → VIB 데이터 매칭 → JSON 응답
```

## 7. 환경변수
| 변수명 | 설명 | 기본값 |
|---|---|---|
| `DATA_DIR` | CSV 데이터 디렉토리 | `./data` |
| `CACHE_DIR` | 캐시 디렉토리 | `./.cache` |
| `SETTINGS_FILE` | 디바이스 설정 파일 | `./device_settings.json` |
