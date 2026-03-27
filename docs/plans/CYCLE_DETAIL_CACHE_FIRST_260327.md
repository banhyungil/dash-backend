# CycleDetailModal: React Query 캐시 우선 조회로 전환

## Context
CycleDetailModal이 열릴 때 `/cycles/detail` API를 별도 호출하지만, 반환 데이터(timestamp, rpm_mean 등)는 이미 `/cycles/daily` 응답의 `CycleData`에 모두 포함되어 있다. ChartsPage에서 모달을 열 때 daily-data는 이미 React Query에 캐시된 상태이므로, 캐시에서 먼저 찾고 없을 때만 detail API를 fallback으로 호출하는 방식으로 변경한다.

## 변경 범위

### Frontend (`dash-front`)

**1. `src/hooks/useCycleDetail.ts` 수정**
- `useQueryClient().getQueryData()` 로 `['daily-data', month, date]` 캐시에서 해당 사이클 조회
- 캐시 hit 시 → detail API 호출 skip (`enabled: !cachedCycle`)
- 캐시 miss 시 → 기존 `fetchCycleDetail` fallback
- month 파라미터 추가 필요 (daily-data 쿼리키에 month 포함)

**2. `src/components/CycleDetailModal.tsx` 수정**
- `useCycleDetail` 호출 시 `month` 파라미터 추가 전달

**3. `src/pages/ChartsPage.tsx` 수정**
- CycleDetailModal에 `month` prop 전달 (useDateStore에서 이미 사용 중)

### Backend — 변경 없음
- `/cycles/detail` 엔드포인트는 그대로 유지 (독립 진입점 fallback용)

## 주요 파일
- `src/hooks/useCycleDetail.ts`
- `src/components/CycleDetailModal.tsx`
- `src/pages/ChartsPage.tsx`
- `src/api/types.ts` (참조만)

## 검증
- ChartsPage에서 모달 열 때 Network 탭에서 `/cycles/detail` 호출 없는지 확인
- daily-data 캐시 없는 상태에서 모달 열면 detail API fallback 동작 확인
