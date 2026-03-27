# TanStack React Query (@tanstack/react-query)

## 핵심 철학

**서버 상태(server state)와 클라이언트 상태(client state)는 본질적으로 다르다.**

| | 클라이언트 상태 | 서버 상태 |
|--|----------------|-----------|
| 소유자 | 프론트엔드 | 백엔드 (DB) |
| 예시 | 모달 열림, 선택된 탭 | 사이클 목록, 설정값 |
| 특징 | 동기적, 항상 최신 | 비동기, 캐시 필요, 시간 지나면 stale |
| 관리 도구 | useState, Zustand | React Query |

기존 방식(useState + useEffect로 API 호출)의 문제:
- 로딩/에러 상태를 매번 직접 관리
- 캐싱 없음 — 같은 데이터를 페이지 이동할 때마다 재요청
- 중복 요청 방지 없음
- 백그라운드 갱신 없음

React Query는 이 모든 걸 선언적으로 해결한다.

## 핵심 기능

### 1. useQuery — 데이터 조회 (GET)

```tsx
const { data, isLoading, error } = useQuery({
  queryKey: ['cycles', date],     // 캐시 키 (이 키로 캐시 식별)
  queryFn: () => fetchCycles(date), // 실제 API 호출 함수
  staleTime: 5 * 60 * 1000,       // 5분간 fresh → 재요청 안 함
});
```

- `queryKey`가 변경되면 자동으로 새 데이터 fetch
- 같은 `queryKey`로 여러 컴포넌트가 호출해도 요청 1번만 (deduplication)
- 컴포넌트 언마운트/리마운트 시 캐시에서 즉시 반환

### 2. useMutation — 데이터 변경 (POST/PUT/DELETE)

```tsx
const mutation = useMutation({
  mutationFn: (value) => updateSetting(key, value),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['settings'] }); // 관련 캐시 무효화
  },
});

mutation.mutate(newValue);
```

- 변경 후 관련 쿼리를 invalidate하면 자동으로 최신 데이터 refetch

### 3. 캐시 생명주기

```
fresh (staleTime 이내)
  → 캐시에서 즉시 반환, 네트워크 요청 없음
stale (staleTime 초과)
  → 캐시에서 즉시 반환 + 백그라운드에서 refetch
  → refetch 완료되면 UI 자동 업데이트
inactive (해당 쿼리를 구독하는 컴포넌트 없음)
  → gcTime(기본 5분) 후 캐시에서 제거
```

### 4. 자동 refetch 트리거

| 트리거 | 기본값 | 설명 |
|--------|--------|------|
| 윈도우 포커스 | ON | 탭 전환 후 돌아오면 stale 데이터 자동 갱신 |
| 네트워크 재연결 | ON | 오프라인 → 온라인 시 자동 갱신 |
| 마운트 시 | ON | 컴포넌트 마운트 시 stale이면 refetch |
| 인터벌 | OFF | `refetchInterval: 5000` 으로 폴링 가능 |

### 5. invalidateQueries — 수동 캐시 무효화

```tsx
// 특정 키 무효화 → 해당 쿼리를 구독하는 모든 컴포넌트가 자동 refetch
queryClient.invalidateQueries({ queryKey: ['settings'] });

// 부분 매칭 — ['cycles']로 시작하는 모든 쿼리 무효화
queryClient.invalidateQueries({ queryKey: ['cycles'] });
```

## useState + useEffect 비교

### Before (직접 관리)
```tsx
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  setLoading(true);
  fetchCycles(date)
    .then(setData)
    .catch(setError)
    .finally(() => setLoading(false));
}, [date]);
```

### After (React Query)
```tsx
const { data, isLoading, error } = useQuery({
  queryKey: ['cycles', date],
  queryFn: () => fetchCycles(date),
});
```

얻는 것:
- 로딩/에러 상태 자동 관리
- 캐싱 + 중복 요청 방지
- 백그라운드 갱신
- 윈도우 포커스 시 자동 refetch

## queryKey 설계

queryKey는 **의존성 배열**처럼 동작한다. 값이 바뀌면 새 쿼리로 인식.

```tsx
['months']                    // 전체 월 목록 (파라미터 없음)
['dates', '2603']             // 특정 월의 날짜 목록
['cycles', '2603', '260311']  // 특정 월+날짜의 사이클
['settings']                  // 전체 설정
```

invalidate 시 부분 매칭:
- `invalidateQueries({ queryKey: ['cycles'] })` → cycles로 시작하는 모든 쿼리 무효화

## 현재 프로젝트 적용

| hook | queryKey | 용도 |
|------|----------|------|
| useSettings | `['settings']` | 전체 설정 조회 (staleTime: 10분) |
| useCalendarData | `['months']`, `['dates', month]` | 월/날짜 목록 |
| useCycleDetail | `['cycleDetail', date, device, index]` | 사이클 상세 |
| IngestStatus | `['ingest-status']` | 적재 현황 (적재 완료 시 invalidate) |
