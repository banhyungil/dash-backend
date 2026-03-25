# MQTT 실시간 데이터 수신 방안

> 작성일: 2026-03-24
> 상태: 검토 대기

---

## 1. 현황 및 목표

**현재**: 라즈베리파이 → CSV 파일 저장 → USB/네트워크 복사 → 수동 적재 → DB → API → 화면

**목표**: 라즈베리파이 → MQTT 실시간 전송 → 백엔드 수신 → DB 저장 → WebSocket → 프론트 실시간 갱신

CSV 파일 중간 단계를 제거하고, 센서 데이터를 실시간으로 수집/표시한다.

---

## 2. 전체 아키텍처

```
┌──────────────────┐     MQTT publish      ┌──────────────┐
│  라즈베리파이 (R1) │ ──────────────────→  │              │
│  라즈베리파이 (R2) │ ──────────────────→  │  Mosquitto   │
│  라즈베리파이 (R3) │ ──────────────────→  │  Broker      │
│  라즈베리파이 (R4) │ ──────────────────→  │  (port 1883) │
└──────────────────┘                       └──────┬───────┘
                                                  │ MQTT subscribe
                                                  ▼
                                           ┌──────────────┐
                                           │  FastAPI      │
                                           │  백엔드       │
                                           │              │
                                           │ ┌──────────┐ │
                                           │ │ MQTT     │ │  ← 수신 + 사이클 조립
                                           │ │ Consumer │ │
                                           │ └────┬─────┘ │
                                           │      │       │
                                           │      ├─→ SQLite (사이클 완료 시 저장)
                                           │      │       │
                                           │      ├─→ WebSocket push (실시간)
                                           │      │       │
                                           │ ┌────▼─────┐ │
                                           │ │ REST API │ │  ← 기존 과거 데이터 조회
                                           │ └──────────┘ │
                                           └──────┬───────┘
                                                  │ WebSocket + REST
                                                  ▼
                                           ┌──────────────┐
                                           │  프론트엔드    │
                                           │  (실시간 차트) │
                                           └──────────────┘
```

---

## 3. MQTT 토픽 설계

```
sensor/{device_id}/pulse    ← PULSE 센서 raw 데이터
sensor/{device_id}/vib      ← VIB 센서 raw 데이터
sensor/{device_id}/status   ← 디바이스 상태 (온라인/오프라인/배터리)
```

### 메시지 포맷 (JSON)

**PULSE 샘플:**
```json
{
  "ts": 1773212400.853,
  "pulse": 5507,
  "accel_x": 0.08,
  "accel_y": 0.98,
  "accel_z": 0.02
}
```

**VIB 샘플:**
```json
{
  "ts": 1773212400.853,
  "accel_x": 0.07,
  "accel_z": 0.02
}
```

**Status:**
```json
{
  "ts": 1773212400,
  "state": "online",
  "battery": 85
}
```

### QoS 설정

| 토픽 | QoS | 이유 |
|------|-----|------|
| pulse/vib | 0 | 대량 고속 데이터, 일부 유실 허용 |
| status | 1 | 상태 변경은 확실히 전달 |

---

## 4. 백엔드 구현

### 4-1. 의존성 추가

```bash
pip install aiomqtt websockets
```

- `aiomqtt`: asyncio 기반 MQTT 클라이언트 (FastAPI와 호환)
- `websockets`: 프론트 실시간 push용 (FastAPI 내장 WebSocket도 가능)

### 4-2. MQTT Consumer 서비스

```python
# services/mqtt_consumer.py

class MqttConsumer:
    """MQTT 수신 → 사이클 조립 → DB 저장 + WebSocket push"""

    def __init__(self):
        self.buffers: dict[str, CycleBuffer] = {}  # device별 샘플 버퍼

    async def start(self, broker_host: str, broker_port: int):
        """MQTT 브로커에 연결하고 토픽 구독."""
        async with aiomqtt.Client(broker_host, broker_port) as client:
            await client.subscribe("sensor/+/pulse")
            await client.subscribe("sensor/+/vib")
            await client.subscribe("sensor/+/status")
            async for message in client.messages:
                await self._handle_message(message)

    async def _handle_message(self, message):
        """토픽별 메시지 처리."""
        topic_parts = str(message.topic).split("/")
        device_id = topic_parts[1]
        data_type = topic_parts[2]  # pulse, vib, status
        payload = json.loads(message.payload)

        if data_type in ("pulse", "vib"):
            await self._buffer_sample(device_id, data_type, payload)
        elif data_type == "status":
            await self._handle_status(device_id, payload)

    async def _buffer_sample(self, device_id, data_type, sample):
        """샘플을 버퍼에 쌓다가 사이클 완료 감지 시 DB 저장."""
        buffer = self.buffers.setdefault(device_id, CycleBuffer(device_id))
        buffer.add(data_type, sample)

        if buffer.is_cycle_complete():
            cycle = buffer.flush()
            await self._save_cycle(cycle)
            await self._push_to_websocket(cycle)
```

### 4-3. 사이클 버퍼

```python
# services/cycle_buffer.py

class CycleBuffer:
    """디바이스별 샘플을 모아서 1 사이클로 조립."""

    CYCLE_GAP_MS = 5000  # 5초 이상 데이터 없으면 사이클 종료 판정

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.pulse_samples = []
        self.vib_samples = []
        self.last_ts = 0
        self.cycle_index = 0

    def add(self, data_type: str, sample: dict):
        if data_type == "pulse":
            self.pulse_samples.append(sample)
        else:
            self.vib_samples.append(sample)
        self.last_ts = sample["ts"]

    def is_cycle_complete(self) -> bool:
        """현재 시각 - 마지막 샘플 시각 > GAP이면 사이클 종료."""
        if not self.pulse_samples:
            return False
        return (time.time() - self.last_ts) > self.CYCLE_GAP_MS / 1000

    def flush(self) -> dict:
        """버퍼를 비우고 사이클 데이터 반환."""
        cycle = {
            "device_id": self.device_id,
            "cycle_index": self.cycle_index,
            "pulse_samples": self.pulse_samples,
            "vib_samples": self.vib_samples,
            "timestamp": self.pulse_samples[0]["ts"],
        }
        self.pulse_samples = []
        self.vib_samples = []
        self.cycle_index += 1
        return cycle
```

### 4-4. FastAPI 통합

```python
# main.py
import asyncio
from services.mqtt_consumer import MqttConsumer

mqtt_consumer = MqttConsumer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # MQTT Consumer를 백그라운드 태스크로 실행
    mqtt_task = asyncio.create_task(
        mqtt_consumer.start("localhost", 1883)
    )
    yield
    mqtt_task.cancel()
```

### 4-5. WebSocket 엔드포인트

```python
# routers/realtime.py

connected_clients: set[WebSocket] = set()

@router.websocket("/ws/live")
async def live_feed(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive
    except WebSocketDisconnect:
        connected_clients.discard(ws)

async def push_to_clients(data: dict):
    """모든 연결된 클라이언트에 데이터 push."""
    for ws in connected_clients.copy():
        try:
            await ws.send_json(data)
        except:
            connected_clients.discard(ws)
```

---

## 5. 프론트엔드 구현

### 5-1. 갱신 전략 — 사이클 완료 이벤트 기준

매 샘플(1ms)마다 화면을 갱신하면 1000Hz × 4채널 = 초당 4000포인트로 Plotly가 버틴다.
**사이클 완료 시점에만 갱신**하면 기존 일일 차트와 동일한 렌더링 비용.

| 표시 항목 | 갱신 시점 | 부하 | 차트 라이브러리 |
|-----------|-----------|------|----------------|
| 디바이스 상태 (온/오프) | 수 초 | 거의 없음 | DOM (텍스트/아이콘) |
| RPM/MPM 수치 | 사이클 완료 (~5초) | 낮음 | DOM (텍스트) |
| 사이클 완료 카운트 | 사이클 완료 | 낮음 | DOM (텍스트) |
| RPM 추세 차트 | 사이클 완료 시 포인트 1개 추가 | 낮음 | Plotly |
| 진동 파형 (최근 사이클) | 사이클 완료 후 해당 사이클만 | 중간 | Plotly |

raw 파형 실시간 스트리밍이 필요한 경우 (이상 감지 등):
- **WebGL 기반**: regl-scatter, deck.gl — GPU 가속으로 수십만 포인트 렌더링
- **Canvas 직접 렌더링**: requestAnimationFrame + OffscreenCanvas
- **Plotly 회피**: Plotly는 SVG 기반이라 대량 포인트에 부적합

→ 현재 단계에서는 사이클 이벤트 기준 갱신으로 충분. raw 스트리밍은 Phase 4로 별도 검토.

### 5-2. WebSocket 메시지 타입

백엔드 → 프론트 push 메시지 구분:

```typescript
type WsMessage =
  | { type: 'cycle_complete'; data: CycleData }     // 사이클 완료 → 차트 포인트 추가
  | { type: 'device_status'; data: DeviceStatus }    // 디바이스 상태 → 인디케이터 갱신
```

### 5-3. WebSocket 연결 hook

```typescript
// hooks/useLiveFeed.ts
export function useLiveFeed(
  onCycle: (cycle: CycleData) => void,
  onStatus?: (status: DeviceStatus) => void
) {
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8001/ws/live');
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'cycle_complete') onCycle(msg.data);
      if (msg.type === 'device_status') onStatus?.(msg.data);
    };
    // 자동 재연결
    ws.onclose = () => setTimeout(() => ws, 3000);
    return () => ws.close();
  }, []);
}
```

### 5-4. 실시간 모니터링 페이지

사이드바에 추가:

```
📊 일일 차트       → /
📡 실시간 모니터링  → /live     ← 신규
📁 데이터 관리      → /manager
⚙️ 설정            → /settings
```

페이지 구성:

```
┌─────────────────────────────────────────────────┐
│  디바이스 상태                                    │
│  [R1 🟢 온라인] [R2 🟢 온라인] [R3 🔴] [R4 🟢]   │
├─────────────────────────────────────────────────┤
│  실시간 KPI                                      │
│  [현재 RPM: 152] [현재 MPM: 67] [사이클: 42]     │
├─────────────────────────────────────────────────┤
│  RPM 추세 (rolling 30분)                         │
│  ───────────/\──/\───/\──── ← 사이클 완료마다    │
│                                포인트 1개 추가    │
├─────────────────────────────────────────────────┤
│  최근 사이클 진동 파형                            │
│  ~~~~~~~~~~~~~~~~~~~~~ ← 직전 완료된 사이클 파형   │
└─────────────────────────────────────────────────┘
```

---

## 6. 개발 환경 (라즈베리파이 없이 테스트)

### 6-1. MQTT 브로커

```bash
# Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# 또는 Windows
winget install EclipseMosquitto.Mosquitto
```

### 6-2. 가짜 센서 시뮬레이터

기존 CSV 데이터를 읽어서 MQTT로 재생:

```python
# tools/fake_sensor.py
"""기존 CSV를 읽어서 MQTT로 실시간 재생하는 시뮬레이터."""
import paho.mqtt.client as mqtt
import json, time
from services.csv_parser import parse_pulse_csv, parse_vib_csv

client = mqtt.Client()
client.connect("localhost", 1883)

device_id = "0013A20041F71B01"
cycles = parse_pulse_csv("data/PULSE_250920.csv")

for cycle in cycles:
    for sample in cycle["data"]:
        client.publish(f"sensor/{device_id}/pulse", json.dumps({
            "ts": time.time(),
            **sample
        }))
        time.sleep(0.001)  # 1000Hz 시뮬레이션

    time.sleep(5)  # 사이클 간 갭
```

### 6-3. 테스트 시나리오

| 시나리오 | 검증 항목 |
|----------|-----------|
| 정상 수신 | 시뮬레이터 → MQTT → 백엔드 → DB 저장 확인 |
| 실시간 표시 | WebSocket → 프론트 차트 업데이트 확인 |
| 네트워크 끊김 | 브로커 중지 → 재시작 → 메시지 복구 확인 |
| 다중 디바이스 | R1~R4 동시 전송 → 디바이스별 분리 확인 |
| 부하 테스트 | 4채널 × 1000Hz = 초당 4000 메시지 처리 확인 |

---

## 7. 기존 CSV 적재와 공존

MQTT 실시간 수신과 기존 CSV 배치 적재를 병행:

```
실시간 데이터 → MQTT Consumer → DB 저장 (동일 t_cycle 테이블)
과거 데이터   → CSV 적재 (기존 /api/ingest)
```

동일 DB/테이블을 사용하므로 차트 조회 API는 변경 없음. 데이터 소스가 다를 뿐 결과 형식은 동일.

---

## 8. 라즈베리파이 측 변경

현재 CSV 저장 코드 → MQTT publish 코드로 교체:

```python
# 현재 (CSV 저장)
with open(f"PULSE_{date}.csv", "a") as f:
    f.write(f"{timestamp}, {json.dumps(samples)}\n")

# 변경 (MQTT 전송)
for sample in samples:
    client.publish(f"sensor/{device_id}/pulse", json.dumps({
        "ts": time.time(),
        **sample
    }))
```

오프라인 대비 로컬 버퍼:
```python
# 네트워크 끊김 시 로컬 큐에 저장, 복구 시 재전송
from paho.mqtt.client import Client
client = Client()
client.max_queued_messages_set(100000)  # 오프라인 버퍼
client.connect("backend_server", 1883)
```

---

## 9. 구현 순서

```
Phase 1. 인프라 + 백엔드 수신 (CSV 공존)
  Step 1. Mosquitto 브로커 설치 (Docker)
  Step 2. mqtt_consumer.py + cycle_buffer.py 구현
  Step 3. FastAPI lifespan에 MQTT 태스크 등록
  Step 4. fake_sensor.py 시뮬레이터 작성
  Step 5. DB 저장 확인 (기존 t_cycle에 저장)

Phase 2. 실시간 프론트엔드
  Step 6. WebSocket 엔드포인트 (/ws/live)
  Step 7. useLiveFeed hook
  Step 8. 실시간 모니터링 페이지 (/live)

Phase 3. 라즈베리파이 연동
  Step 9. 라즈베리파이 MQTT publish 코드
  Step 10. 현장 테스트 (실제 센서 데이터)
```

Phase 1~2는 라즈베리파이 없이 로컬에서 완료 가능.
