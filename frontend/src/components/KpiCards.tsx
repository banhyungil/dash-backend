import React from 'react';
import { CycleData } from '../api/client';

interface KpiCardsProps {
  cycles: CycleData[];
}

const KpiCards: React.FC<KpiCardsProps> = ({ cycles }) => {
  // 총 가동시간 계산 (시간 단위)
  const totalOperationTime = cycles.reduce((sum, cycle) => sum + cycle.duration_ms, 0) / (1000 * 60 * 60);

  // 평균 MPM 계산
  const avgMpm = cycles.length > 0
    ? cycles.reduce((sum, cycle) => sum + cycle.mpm_mean, 0) / cycles.length
    : 0;

  // 최고 MPM 계산
  const maxMpm = cycles.length > 0
    ? Math.max(...cycles.map(cycle => cycle.mpm_max))
    : 0;

  // 진동 이벤트 계산 (0.3g 이상)
  const vibrationEvents = cycles.reduce((count, cycle) => {
    // Pulse accelerometer 체크
    const pulseHighVib = [
      ...cycle.pulse_accel_x,
      ...cycle.pulse_accel_y,
      ...cycle.pulse_accel_z
    ].some(val => Math.abs(val) > 0.3);

    // VIB accelerometer 체크
    const vibHighVib = [
      ...cycle.vib_accel_x,
      ...cycle.vib_accel_z
    ].some(val => Math.abs(val) > 0.3);

    return count + (pulseHighVib || vibHighVib ? 1 : 0);
  }, 0);

  const cards = [
    {
      label: '총 가동시간',
      value: `${totalOperationTime.toFixed(1)}h`,
      color: '#2563EB'
    },
    {
      label: '평균 MPM',
      value: `${avgMpm.toFixed(1)} m/m`,
      color: '#0FB880'
    },
    {
      label: '최고 MPM',
      value: `${maxMpm.toFixed(1)} m/m`,
      color: '#F49E0A'
    },
    {
      label: '진동 이벤트',
      value: `${vibrationEvents}건`,
      color: vibrationEvents > 0 ? '#EF4444' : '#64748B'
    }
  ];

  return (
    <div style={{
      display: 'flex',
      gap: '16px',
      marginBottom: '24px',
      flexWrap: 'wrap'
    }}>
      {cards.map((card, index) => (
        <div
          key={index}
          style={{
            flex: '1 1 200px',
            minWidth: '200px',
            background: '#F0F4F9',
            border: '1px solid #E2E8EF',
            borderRadius: '12px',
            padding: '20px',
            textAlign: 'center',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          }}
        >
          <div style={{
            fontSize: '13px',
            color: '#64748B',
            fontWeight: 600,
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            fontFamily: 'Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
          }}>
            {card.label}
          </div>
          <div style={{
            fontSize: '32px',
            fontWeight: 700,
            color: card.color,
            fontFamily: 'Pretendard, -apple-system, BlinkMacSystemFont, system-ui, monospace'
          }}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
};

export default KpiCards;
