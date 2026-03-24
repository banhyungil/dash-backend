# Chrome DevTools 꿀팁

## 열기

| 단축키 | 설명 |
|--------|------|
| `F12` / `Ctrl+Shift+I` | DevTools 열기 |
| `Ctrl+Shift+J` | Console 탭으로 바로 열기 |
| `Ctrl+Shift+C` | 요소 선택 모드로 열기 |
| `Ctrl+Shift+P` | Command Palette (모든 기능 검색) |

---

## 1. Elements 탭 — DOM/CSS 디버깅

**요소 선택**
- `Ctrl+Shift+C` → 화면에서 클릭하면 해당 DOM 요소로 이동
- 선택된 요소는 Console에서 `$0`으로 접근 가능

**CSS 실시간 편집**
- Styles 패널에서 값 클릭 → 바로 수정, 실시간 반영
- `+` 버튼으로 새 CSS 규칙 추가
- `:hov` 버튼으로 hover/focus/active 상태 강제 적용

**Computed 탭**
- 최종 적용된 CSS 값 확인 (Tailwind 디버깅에 유용)
- Box Model 시각화 (margin/padding/border)

**꿀팁**
- 요소 우클릭 → `Break on` → DOM 변경 시 자동 브레이크포인트
- `h` 키: 선택한 요소 숨기기/보이기 토글
- `Ctrl+Z`: CSS 변경 되돌리기

---

## 2. Console 탭 — JS 실행/로그

**기본**
- `console.log()` 출력 확인
- JS 코드 직접 실행 가능
- `$0`: Elements에서 선택한 요소
- `$_`: 마지막 실행 결과

**유용한 console API**
```javascript
console.table(array)         // 배열/객체를 테이블로 출력
console.time('label')        // 시간 측정 시작
console.timeEnd('label')     // 시간 측정 종료 + 출력
console.count('label')       // 호출 횟수 카운트
console.group('label')       // 로그 그룹핑
console.trace()              // 호출 스택 출력
```

**필터링**
- 상단 드롭다운으로 log level 필터 (Error, Warning, Info)
- 텍스트 필터로 특정 메시지만 표시

---

## 3. Network 탭 — API 디버깅

**기본 사용**
- API 요청/응답 확인 (Headers, Payload, Response, Timing)
- Status 코드 색상: 빨강(4xx/5xx), 초록(2xx)

**필터**
- `Fetch/XHR`: API 요청만 필터
- `WS`: WebSocket만
- 텍스트 필터: URL에 포함된 키워드로 필터 (예: `cycles`)
- `is:running`: 진행 중인 요청만

**꿀팁**
- 요청 우클릭 → `Copy as cURL`: curl 명령어로 복사 (Postman 없이 재현)
- 요청 우클릭 → `Replay XHR`: 같은 요청 재전송
- `Throttling`: 느린 네트워크 시뮬레이션 (Slow 3G 등)
- `Preserve log`: 페이지 이동해도 로그 유지
- 하단 `transferred` vs `resources`: 실제 전송량 vs 압축 전 크기

---

## 4. Sources 탭 — JS 디버깅

**브레이크포인트**
- 라인 번호 클릭 → 브레이크포인트 설정
- 조건부 브레이크포인트: 라인 우클릭 → `Add conditional breakpoint`
- `debugger;` 코드에 삽입하면 해당 위치에서 자동 중단

**중단 시 조작**
| 단축키 | 설명 |
|--------|------|
| `F8` | Resume (계속 실행) |
| `F10` | Step over (다음 라인) |
| `F11` | Step into (함수 내부로) |
| `Shift+F11` | Step out (함수 밖으로) |

**Watch / Scope**
- Watch: 특정 변수/표현식 실시간 감시
- Scope: 현재 스코프의 모든 변수 확인
- Call Stack: 호출 경로 확인

---

## 5. Performance 탭 — 렌더링 성능

**프로파일링**
1. `Ctrl+E`로 녹화 시작
2. 느린 동작 수행
3. 녹화 중지 → 타임라인 분석

**확인 포인트**
- **Main**: JS 실행 시간 (긴 노란색 바 = 병목)
- **Frames**: 60fps 미달 구간 (빨간 바)
- **Summary**: 각 작업 시간 비율 (Scripting, Rendering, Painting)

**꿀팁**
- `Ctrl+Shift+P` → `Show rendering` → **Paint flashing**: 다시 그려지는 영역 녹색 표시
- **FPS meter**: 실시간 프레임 레이트 표시
- CPU throttling: 4x/6x slowdown으로 저사양 환경 시뮬레이션

---

## 6. Memory 탭 — 메모리 분석

**Heap Snapshot**
1. Memory 탭 → `Heap snapshot` 선택 → `Take snapshot`
2. 특정 동작 수행
3. 다시 `Take snapshot`
4. 두 스냅샷 비교 (`Comparison` 뷰)

**확인 포인트**
- `Shallow Size`: 객체 자체 크기
- `Retained Size`: 객체가 해제되면 회수 가능한 총 크기
- `Detached HTMLDivElement` 등: 메모리 릭 의심 (DOM에서 제거됐지만 참조가 남은 노드)

**메모리 릭 찾기**
1. 스냅샷 A 촬영
2. 의심 동작 반복 수행 (예: 모달 열고 닫기 10번)
3. 스냅샷 B 촬영
4. Comparison에서 `#Delta`가 계속 증가하는 객체 확인

---

## 7. Application 탭 — 저장소 확인

- **Local Storage / Session Storage**: key-value 확인 및 편집
- **Cookies**: 도메인별 쿠키 관리
- **Cache Storage**: Service Worker 캐시 확인
- **Clear storage**: 전부 초기화 (디버깅 초기화 시 유용)

---

## 8. Performance Monitor — 실시간 모니터링

`Ctrl+Shift+P` → "Performance Monitor" 검색

실시간 그래프로 표시:
- **CPU usage**: JS CPU 사용률
- **JS heap size**: 메모리 사용량
- **DOM Nodes**: DOM 노드 수 (증가하면 릭 의심)
- **Layouts/sec**: 레이아웃 재계산 빈도

---

## 9. 자주 쓰는 Command Palette 명령

`Ctrl+Shift+P`로 열고 검색:

| 명령 | 설명 |
|------|------|
| `Screenshot` | 화면 캡처 (전체/노드/영역) |
| `Show rendering` | 렌더링 디버깅 옵션 |
| `Performance Monitor` | 실시간 성능 모니터 |
| `Coverage` | 사용하지 않는 CSS/JS 비율 확인 |
| `Disable JavaScript` | JS 비활성화 |
| `Dark mode` | DevTools 다크모드 |

---

## 10. React DevTools (확장 프로그램)

Chrome에 `React Developer Tools` 설치 시 추가되는 탭:

**Components 탭**
- 컴포넌트 트리 탐색
- props, state, hooks 값 실시간 확인 및 수정
- 컴포넌트 렌더링 원인 확인 (Highlight updates)

**Profiler 탭**
- 어떤 컴포넌트가 왜 리렌더됐는지 추적
- 각 렌더의 소요 시간 flame chart
- `Record why each component rendered` 옵션 활성화 권장
