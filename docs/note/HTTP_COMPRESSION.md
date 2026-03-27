# HTTP 응답 압축 (gzip, Brotli)

## 동작 방식

HTTP 버전과 무관하게 HTTP/1.1부터 지원된다.

```
브라우저 → 요청 헤더: Accept-Encoding: gzip, br
서버   → 응답 헤더: Content-Encoding: gzip (또는 br) + 압축된 본문
브라우저 → 자동 해제
```

클라이언트(axios 등)에서 별도 처리 불필요 — 브라우저가 자동으로 요청/해제를 처리한다.

## gzip vs Brotli

| | gzip | Brotli |
|--|------|--------|
| 압축률 | 좋음 | gzip 대비 15~25% 더 좋음 |
| 압축 속도 | 빠름 | 느림 (특히 높은 레벨) |
| HTTP 요구사항 | HTTP/1.1+ | HTTP/1.1+ (HTTPS 필수) |
| 브라우저 지원 | 전체 | 모던 브라우저 전체 |
| Content-Encoding | `gzip` | `br` |
| 적합한 용도 | 동적 API 응답 (실시간 압축) | 정적 파일 사전 압축 (JS, CSS) |

### 선택 기준

- **동적 API 응답** (JSON) → gzip 권장. 압축 속도가 중요하므로 gzip이 유리.
- **정적 파일** (JS, CSS, HTML) → Brotli 권장. 빌드 시 미리 압축해두면 압축 속도 무관.
- **로컬 개발** (HTTP) → gzip만 가능. Brotli는 HTTPS 필수 (브라우저 정책).
- **프로덕션** (HTTPS) → 둘 다 가능. 정적은 Brotli, API는 gzip이 일반적.

## FastAPI 적용

```python
from fastapi.middleware.gzip import GZipMiddleware

# minimum_size: 이 크기(바이트) 이상 응답만 압축
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

- 1KB 미만 소형 응답은 압축 안 함 (오버헤드 방지)
- 파형 데이터 등 대용량 JSON은 50~80% 크기 감소 기대
- DevTools Network 탭에서 `Content-Encoding: gzip` 과 전송 크기로 확인 가능
