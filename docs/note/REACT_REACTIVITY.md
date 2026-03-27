# React 반응성 모델 — Vue와의 비교

## 핵심 차이

React는 반응형 시스템이 없다. 상태 변경 → 컴포넌트 함수 전체 재실행 → deps 비교로 재계산 여부 판단.

| | Vue | React |
|--|-----|-------|
| 반응성 | 데이터 자체가 반응형 (Proxy) | 상태 변경 시 함수 재실행 |
| 의존성 추적 | 자동 (런타임에 접근한 값 추적) | 수동 (deps 배열 명시) |
| 재계산 트리거 | 참조한 반응형 값 변경 | 컴포넌트 리렌더 + deps 비교 |
| 반응형 선언 | `ref()`, `reactive()` 필수 | 없음 — 일반 변수 |

## Vue — 데이터가 반응형

```js
const count = ref(0)                          // 명시적으로 반응형 선언
const doubled = computed(() => count.value * 2) // 자동 의존성 추적
```

- `ref`/`reactive`로 감싸야 Vue가 변경을 감지 (Proxy 기반)
- `computed`는 내부에서 접근한 반응형 데이터를 **자동으로 의존성 추적**
- deps 배열을 직접 나열할 필요 없음

## React — 리렌더가 반응성

```tsx
const [count, setCount] = useState(0)
const doubled = useMemo(() => count * 2, [count])  // deps 수동 명시
```

- `setState` 호출 → 컴포넌트 함수 전체가 다시 실행
- `useMemo`는 deps 배열의 값을 이전과 비교해서 재계산 여부 결정
- **deps를 직접 나열해야** 하므로 누락 시 버그 발생 가능

## React에서 useQuery 데이터도 deps로 동작하는 이유

```tsx
const { data: dailyData } = useQuery({
  queryKey: ['daily-data', month, date],
  queryFn: () => fetchDailyCycles(month, date),
});

const detail = useMemo(() => {
  return dailyData?.cycles.find(c => c.device_name === deviceName);
}, [dailyData, deviceName]);
```

흐름:
```
캐시 갱신 → useQuery가 새 data 반환 → 컴포넌트 리렌더 → useMemo deps 변경 → 재계산
```

`dailyData`는 특별한 반응형 객체가 아니라 **그냥 변수**다. useQuery가 refetch하면 새 객체 참조를 반환하고, React가 컴포넌트를 리렌더하면서 useMemo의 deps 비교에서 변경이 감지되어 재계산된다.

즉 React에서는 **어떤 값이든** deps에 넣으면 반응형처럼 동작한다 — useState, useQuery, props 모두 동일.
