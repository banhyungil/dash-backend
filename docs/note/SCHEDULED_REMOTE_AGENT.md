# Claude Code Scheduled Remote Agent 가이드

## 개요

Scheduled Remote Agent는 **Anthropic 클라우드에서 cron 스케줄로 자동 실행**되는 Claude Code 에이전트다.
로컬 PC가 꺼져있어도 동작하며, GitHub 레포를 클론해서 코드 분석/변경/커밋/PR 생성까지 자동으로 수행한다.

### 동작 흐름

```
예정된 시간 도달
  → GitHub 저장소 클론 (기본 브랜치)
  → 클라우드 환경 설정 (환경변수, setup script, MCP 커넥터)
  → Claude Code 에이전트 실행 (프롬프트 기반)
  → 결과 커밋 → claude/* 브랜치에 push → PR 생성
```

---

## 설정 방법

### 1. 웹 UI에서 생성

1. https://claude.ai/code/scheduled 방문
2. "New scheduled task" 클릭
3. 설정 항목:
   - **이름**: 작업 식별용
   - **프롬프트**: 에이전트가 수행할 작업 (구체적으로 작성)
   - **저장소**: GitHub 레포 선택
   - **스케줄**: Hourly / Daily / Weekdays / Weekly / Custom
   - **환경**: 네트워크 접근 수준, 환경변수, setup script
   - **MCP 커넥터**: 외부 서비스 연결 (Slack, Linear 등)

### 2. CLI에서 관리

```bash
# 생성 (대화형)
/schedule

# 목록 조회
/schedule list

# 업데이트
/schedule update <task-name>

# 즉시 실행
/schedule run <task-name>

# 삭제는 웹에서만 가능
# https://claude.ai/code/scheduled
```

### 3. Cron Expression

```
┌─────────────── minute (0-59)
│ ┌───────────── hour (0-23, UTC 기준)
│ │ ┌─────────── day of month (1-31)
│ │ │ ┌───────── month (1-12)
│ │ │ │ ┌─────── day of week (0-6, 0=Sunday)
│ │ │ │ │
0 15 * * *      매일 자정 KST (= UTC 15:00)
0 0 * * 1-5     평일 오전 9시 KST (= UTC 00:00)
0 1 * * 0       매주 일요일 오전 10시 KST
```

> KST = UTC + 9시간. 최소 실행 간격은 **1시간**.

---

## 사용 가능한 도구

| 도구 | 용도 |
|------|------|
| Bash | 명령어 실행 (npm, git, python 등) |
| Read / Write / Edit | 파일 읽기/생성/수정 |
| Glob / Grep | 파일 검색 / 텍스트 검색 |
| WebFetch / WebSearch | URL 접근 / 웹 검색 |
| MCP Tools | 연결된 외부 서비스 도구 |

---

## MCP 커넥터 (외부 서비스 연결)

https://claude.ai/settings/connectors 에서 연결 후 task에 추가할 수 있다.

| 서비스 | 활용 예 |
|--------|---------|
| **GitHub** | PR 생성, issue 작성, 코멘트 추가 |
| **Slack** | 채널에 결과 알림 전송 |
| **Linear** | 이슈 생성/상태 업데이트 |
| **Google Drive** | 문서 읽기/작성 |
| **Google Calendar** | 회의 정보 조회 |

---

## 활용 사례

### 1. 리팩터링 로그 자동 기록

```
스케줄: 매일 자정 KST
프롬프트:
  1. REFACTORING_LOG.md의 마지막 정리일 이후 커밋 조회
  2. refactor/feat 커밋을 주제별로 분류
  3. 배경/변경내용/결과 형식으로 섹션 추가
  4. 마지막 정리일 갱신 후 커밋
```

### 2. 코드 리뷰 자동화

```
스케줄: 평일 오전 9시
프롬프트:
  1. 'needs-review' 라벨 PR 조회
  2. 보안 취약점, 성능 이슈, 테스트 커버리지 체크
  3. 인라인 코멘트 작성
  4. #eng-reviews 슬랙 채널에 요약 전송
```

### 3. 의존성 업데이트 체크

```
스케줄: 매주 월요일 오전 10시
프롬프트:
  1. npm outdated / pip list --outdated 실행
  2. 보안 취약점 있는 패키지 식별
  3. patch/minor 업데이트는 자동 PR 생성
  4. major 업데이트는 Linear 이슈 생성
```

### 4. 테스트 실행 및 보고

```
스케줄: 매일 새벽 2시
프롬프트:
  1. 전체 테스트 + 커버리지 실행
  2. 실패 시 원인 분석 → GitHub issue 생성
  3. 커버리지 변동 추적
  4. #qa-automation 슬랙에 결과 전송
```

### 5. 보안 취약점 스캔

```
스케줄: 매주 목요일 새벽 1시
프롬프트:
  1. snyk/bandit 등 보안 스캔 실행
  2. critical/high 이슈는 즉시 슬랙 알림
  3. 상세 리포트 → GitHub issue 생성
```

### 6. 일일 스탠드업 생성

```
스케줄: 평일 오전 7시
커넥터: GitHub, Google Calendar, Slack
프롬프트:
  1. 지난 24시간 GitHub 활동 요약
  2. 오늘 캘린더 일정 조회
  3. CI/CD 실패 현황 체크
  4. #team-standup 채널에 종합 요약 전송
```

---

## 제한사항

| 항목 | 내용 |
|------|------|
| 최소 간격 | 1시간 (그 이하 불가) |
| 로컬 접근 | 불가 (로컬 파일, 환경변수, DB 등) |
| 네트워크 | 기본은 allowlist 도메인만 (설정으로 확장 가능) |
| 브랜치 push | 기본적으로 `claude/*` 브랜치만 |
| 상태 유지 | 불가 (매 실행마다 새로 클론) |
| 사용자 입력 | 불가 (완전 자동 실행) |
| 삭제 | 웹 UI에서만 가능 |
| Git 호스팅 | GitHub만 지원 |

---

## 스케줄 옵션 비교

| | Cloud Scheduled | Desktop Scheduled | /loop (CLI) |
|---|---|---|---|
| 실행 위치 | Anthropic 클라우드 | 로컬 머신 | 현재 세션 |
| PC 켜짐 필요 | X | O | O |
| 로컬 파일 접근 | X | O | O |
| 최소 간격 | 1시간 | 1분 | 1분 |
| 재시작 후 지속 | O | O | X |
| 권장 용도 | 무인 자동화 | 로컬 의존 작업 | 디버깅/테스트 |

---

## 멀티 에이전트 패턴

여러 agent를 목적별로 나누어 운영하면, 각자 역할에 집중하면서 **공유 채널**(GitHub issue/PR, Slack, 파일)을 통해 협업할 수 있다.

### 핵심 원리

```
각 agent는 독립 실행 (서로 직접 통신 불가)
  → 공유 매개체를 통해 간접 협업
  → GitHub issue, PR, branch, Slack 채널, 특정 파일 등
```

### 패턴 1: 파이프라인 (순차 처리)

앞 agent의 산출물을 뒤 agent가 이어받는 구조.

```
[Agent A: 분석] 매일 01:00
  → 코드 변경 분석 → GitHub issue 생성 (label: needs-review)

[Agent B: 리뷰] 매일 03:00
  → 'needs-review' 라벨 issue 조회 → 코드 리뷰 → 코멘트 작성

[Agent C: 보고] 매일 07:00
  → 리뷰 완료된 issue 취합 → Slack에 일일 보고 전송
```

> 시간차를 두어 앞 agent가 끝난 후 다음이 실행되도록 스케줄 조정

### 패턴 2: 역할 분담 (병렬 처리)

각 agent가 서로 다른 영역을 담당.

```
[Agent: 프론트엔드 감시] 평일 09:00
  → src/components/** 변경 감지
  → UI 테스트 실행, 스크린샷 비교

[Agent: 백엔드 감시] 평일 09:00
  → api/** 변경 감지
  → API 테스트 실행, 응답 스키마 검증

[Agent: 인프라 감시] 매일 06:00
  → Dockerfile, docker-compose, CI 설정 변경 감지
  → 보안 스캔, 빌드 테스트
```

### 패턴 3: 감시자 + 실행자

한 agent가 상황을 판단하고, 다른 agent가 실행.

```
[Agent: 감시자] 매 1시간
  → 의존성 취약점 체크
  → 발견 시 GitHub issue 생성 (label: auto-fix)

[Agent: 실행자] 매 2시간
  → 'auto-fix' 라벨 issue 조회
  → 자동 패치 가능하면 PR 생성
  → 불가능하면 issue에 분석 코멘트 추가
```

### 패턴 4: 문서화 + 품질관리 분리

```
[Agent: 문서화] 매일 자정
  → 새 커밋 분석 → REFACTORING_LOG.md 업데이트
  → API 변경 시 → API_DOCS.md 업데이트
  → CHANGELOG.md 갱신

[Agent: 품질관리] 매일 새벽 2시
  → 테스트 커버리지 체크
  → 타입 에러 검사 (pyright, tsc)
  → 린트 위반 체크
  → 결과 → GitHub issue + Slack 알림
```

### 실전 예시: 우리 프로젝트에 적용한다면

```
[Agent 1: 리팩터링 기록] 매일 자정 KST
  → 새 커밋 → REFACTORING_LOG.md 자동 갱신 → PR 생성

[Agent 2: 타입 검증] 평일 오전 8시 KST
  → pyright 실행 → 에러 발견 시 issue 생성

[Agent 3: 주간 리포트] 매주 월요일 오전 9시 KST
  → 지난주 커밋/PR/issue 취합
  → 주간 개발 리포트 생성 → Slack 전송
```

### 설계 시 주의사항

| 항목 | 설명 |
|------|------|
| **시간차 확보** | 파이프라인이면 앞 agent 완료 후 충분한 간격 (1~2시간) |
| **공유 규약** | label, 파일명, branch 네이밍 등 agent 간 약속 통일 |
| **멱등성** | 같은 작업 중복 실행해도 문제없도록 설계 |
| **실패 격리** | 한 agent 실패가 다른 agent에 영향 주지 않도록 |
| **모니터링** | 각 agent 실행 결과를 한 곳(Slack 채널 등)에 모아 확인 |

---

## 프롬프트 작성 팁

**좋은 프롬프트:**
- 구체적인 작업 단계 나열
- 성공 기준 명시
- 에러 시 대응 방법 포함
- 외부 서비스 동작 명시 (PR 생성, 슬랙 알림 등)

**피해야 할 것:**
- 모호한 지시 ("코드 좀 봐줘")
- 사용자 입력 기대 ("어떤 PR을 리뷰할까요?")
- 로컬 경로 참조 ("~/.aws/credentials 사용")
- 종료 조건 없는 작업
