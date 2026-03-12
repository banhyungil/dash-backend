import { useMemo, useState, useCallback } from 'react';
import Plot from 'react-plotly.js';
import type { CycleData } from '../api/client';

interface VibrationChartProps {
  cycles: CycleData[];
}

// Min-Max Decimation for LOD
function decimateMinMax(timeData: number[], valueData: number[], factor: number): { time: number[], value: number[] } {
  if (factor <= 1 || timeData.length === 0) {
    return { time: timeData, value: valueData };
  }

  const result_time: number[] = [];
  const result_value: number[] = [];

  for (let i = 0; i < timeData.length; i += factor) {
    const end = Math.min(i + factor, timeData.length);

    // Find min and max in this block
    let minVal = valueData[i];
    let maxVal = valueData[i];
    let minIdx = i;
    let maxIdx = i;

    for (let j = i + 1; j < end; j++) {
      if (valueData[j] < minVal) {
        minVal = valueData[j];
        minIdx = j;
      }
      if (valueData[j] > maxVal) {
        maxVal = valueData[j];
        maxIdx = j;
      }
    }

    // Add both min and max points (in time order)
    if (minIdx < maxIdx) {
      result_time.push(timeData[minIdx], timeData[maxIdx]);
      result_value.push(minVal, maxVal);
    } else {
      result_time.push(timeData[maxIdx], timeData[minIdx]);
      result_value.push(maxVal, minVal);
    }
  }

  return { time: result_time, value: result_value };
}

export default function VibrationChart({ cycles }: VibrationChartProps) {
  const [colorBySensor, setColorBySensor] = useState(true);
  const [xRange, setXRange] = useState<[number, number]>([6, 20]);
  const plotData = useMemo(() => {
    if (cycles.length === 0) {
      return {
        pulse_x_time: [], pulse_x_data: [],
        pulse_z_time: [], pulse_z_data: [],
        vib_x_time: [], vib_x_data: [],
        vib_z_time: [], vib_z_data: [],
        highVibEvents: [],
      };
    }

    const pulse_x_time: number[] = [];
    const pulse_x_data: number[] = [];
    const pulse_z_time: number[] = [];
    const pulse_z_data: number[] = [];
    const vib_x_time: number[] = [];
    const vib_x_data: number[] = [];
    const vib_z_time: number[] = [];
    const vib_z_data: number[] = [];
    const highVibEvents: Array<{ time: number; value: number; mpm: number; timestamp: string }> = [];

    const VIB_SAMPLE_RATE = 1000; // Hz

    // Gravity offset correction based on sensor mounting direction
    const getGravityOffset = (session: string, axis: 'x' | 'z'): number => {
      if (axis === 'x') return 0; // All X axes are horizontal
      // Z axis offsets due to sensor mounting
      if (session === 'R1') return 1;   // Upward facing (+1g)
      if (session === 'R2') return -1;  // Downward facing (-1g)
      return 0; // R3, R4 horizontal (0g)
    };

    // Convert timestamp to hours from midnight
    const getHoursFromMidnight = (timestamp: string): number => {
      const date = new Date(timestamp);
      const hours = date.getHours();
      const minutes = date.getMinutes();
      const seconds = date.getSeconds();
      const ms = date.getMilliseconds();
      return hours + minutes / 60 + seconds / 3600 + ms / 3600000;
    };

    cycles.forEach((cycle) => {
      const cycleStartHours = getHoursFromMidnight(cycle.timestamp);
      const session = cycle.session;

      // Get gravity offsets for this session
      const pulse_x_offset = getGravityOffset(session, 'x');
      const pulse_z_offset = getGravityOffset(session, 'z');

      // Pulse accelerometer data (comes first)
      cycle.pulse_timeline.forEach((time, i) => {
        const absoluteTime = cycleStartHours + time / 3600;

        if (i < cycle.pulse_accel_x.length) {
          const correctedVal = cycle.pulse_accel_x[i] - pulse_x_offset;
          pulse_x_time.push(absoluteTime);
          pulse_x_data.push(correctedVal);

          // Check for high vibration (> 0.3g)
          if (Math.abs(correctedVal) > 0.3) {
            highVibEvents.push({
              time: absoluteTime,
              value: correctedVal,
              mpm: cycle.mpm_mean,
              timestamp: cycle.timestamp
            });
          }
        }
        if (i < cycle.pulse_accel_z.length) {
          const correctedVal = cycle.pulse_accel_z[i] - pulse_z_offset;
          pulse_z_time.push(absoluteTime);
          pulse_z_data.push(correctedVal);

          // Check for high vibration (> 0.3g)
          if (Math.abs(correctedVal) > 0.3) {
            highVibEvents.push({
              time: absoluteTime,
              value: correctedVal,
              mpm: cycle.mpm_mean,
              timestamp: cycle.timestamp
            });
          }
        }
      });

      // Calculate pulse duration for VIB offset
      const pulse_duration = cycle.pulse_timeline.length > 0
        ? cycle.pulse_timeline[cycle.pulse_timeline.length - 1]
        : cycle.duration_ms / 1000;

      // VIB accelerometer data (comes after pulse)
      const vib_start_hours = cycleStartHours + pulse_duration / 3600;

      // Get gravity offsets for VIB (same as pulse for same sensor)
      const vib_x_offset = getGravityOffset(session, 'x');
      const vib_z_offset = getGravityOffset(session, 'z');

      cycle.vib_accel_x.forEach((val, i) => {
        const time = vib_start_hours + (i / VIB_SAMPLE_RATE / 3600);
        const correctedVal = val - vib_x_offset;
        vib_x_time.push(time);
        vib_x_data.push(correctedVal);

        // Check for high vibration (> 0.3g)
        if (Math.abs(correctedVal) > 0.3) {
          highVibEvents.push({
            time: time,
            value: correctedVal,
            mpm: cycle.mpm_mean,
            timestamp: cycle.timestamp
          });
        }
      });

      cycle.vib_accel_z.forEach((val, i) => {
        const time = vib_start_hours + (i / VIB_SAMPLE_RATE / 3600);
        const correctedVal = val - vib_z_offset;
        vib_z_time.push(time);
        vib_z_data.push(correctedVal);

        // Check for high vibration (> 0.3g)
        if (Math.abs(correctedVal) > 0.3) {
          highVibEvents.push({
            time: time,
            value: correctedVal,
            mpm: cycle.mpm_mean,
            timestamp: cycle.timestamp
          });
        }
      });
    });

    return {
      pulse_x_time, pulse_x_data,
      pulse_z_time, pulse_z_data,
      vib_x_time, vib_x_data,
      vib_z_time, vib_z_data,
      highVibEvents,
    };
  }, [cycles]);

  // Calculate decimation factor based on zoom level
  const decimationFactor = useMemo(() => {
    const timeSpan = xRange[1] - xRange[0];

    if (timeSpan >= 12) {
      // Full view (12+ hours): heavy decimation
      return 1000;
    } else if (timeSpan >= 4) {
      // 4-12 hours: moderate decimation
      return 200;
    } else if (timeSpan >= 1) {
      // 1-4 hours: light decimation
      return 50;
    } else if (timeSpan >= 0.5) {
      // 30 min - 1 hour: minimal decimation
      return 10;
    } else {
      // < 30 min: no decimation
      return 1;
    }
  }, [xRange]);

  // Insert null breaks for gaps > 15 minutes
  const insertGapBreaks = (timeData: number[], valueData: number[]): { time: (number | null)[], value: (number | null)[] } => {
    if (timeData.length === 0) {
      return { time: [], value: [] };
    }

    const result_time: (number | null)[] = [];
    const result_value: (number | null)[] = [];

    for (let i = 0; i < timeData.length; i++) {
      result_time.push(timeData[i]);
      result_value.push(valueData[i]);

      // Check gap to next point
      if (i < timeData.length - 1) {
        const gap = timeData[i + 1] - timeData[i];
        if (gap > 0.25) { // 15 minutes = 0.25 hours
          // Insert null to break the line
          result_time.push(null);
          result_value.push(null);
        }
      }
    }

    return { time: result_time, value: result_value };
  };

  // Apply LOD decimation to plot data
  const decimatedData = useMemo(() => {
    const pulse_x = decimateMinMax(plotData.pulse_x_time, plotData.pulse_x_data, decimationFactor);
    const pulse_z = decimateMinMax(plotData.pulse_z_time, plotData.pulse_z_data, decimationFactor);
    const vib_x = decimateMinMax(plotData.vib_x_time, plotData.vib_x_data, decimationFactor);
    const vib_z = decimateMinMax(plotData.vib_z_time, plotData.vib_z_data, decimationFactor);

    // Insert gap breaks
    const pulse_x_gapped = insertGapBreaks(pulse_x.time, pulse_x.value);
    const pulse_z_gapped = insertGapBreaks(pulse_z.time, pulse_z.value);
    const vib_x_gapped = insertGapBreaks(vib_x.time, vib_x.value);
    const vib_z_gapped = insertGapBreaks(vib_z.time, vib_z.value);

    return {
      pulse_x_time: pulse_x_gapped.time,
      pulse_x_data: pulse_x_gapped.value,
      pulse_z_time: pulse_z_gapped.time,
      pulse_z_data: pulse_z_gapped.value,
      vib_x_time: vib_x_gapped.time,
      vib_x_data: vib_x_gapped.value,
      vib_z_time: vib_z_gapped.time,
      vib_z_data: vib_z_gapped.value,
    };
  }, [plotData, decimationFactor]);

  // Handle zoom/pan events
  const handleRelayout = useCallback((event: any) => {
    if (event['xaxis.range[0]'] !== undefined && event['xaxis.range[1]'] !== undefined) {
      setXRange([event['xaxis.range[0]'], event['xaxis.range[1]']]);
    } else if (event['xaxis.autorange']) {
      setXRange([6, 20]); // Reset to default range
    }
  }, []);

  if (cycles.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No vibration data available</p>
      </div>
    );
  }

  // Sample high vibration events for visibility (take every 100th event to avoid overcrowding)
  const sampledHighVibEvents = plotData.highVibEvents.filter((_, i) => i % 100 === 0);

  // Create traces based on color mode (using decimated data)
  const traces = colorBySensor ? [
    // Color by sensor type (using Palette colors)
    {
      x: decimatedData.pulse_x_time,
      y: decimatedData.pulse_x_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'Pulse X',
      line: { color: '#EF4444', width: 1 }, // Alert Red
      connectgaps: false,
    },
    {
      x: decimatedData.pulse_z_time,
      y: decimatedData.pulse_z_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'Pulse Z',
      line: { color: '#F49E0A', width: 1 }, // Trend Orange
      connectgaps: false,
    },
    {
      x: decimatedData.vib_x_time,
      y: decimatedData.vib_x_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'VIB X',
      line: { color: '#2563EB', width: 1 }, // Brand Blue
      connectgaps: false,
    },
    {
      x: decimatedData.vib_z_time,
      y: decimatedData.vib_z_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'VIB Z',
      line: { color: '#0FB880', width: 1 }, // Green Accent
      connectgaps: false,
    },
    // High vibration markers
    {
      x: sampledHighVibEvents.map(e => e.time),
      y: sampledHighVibEvents.map(e => e.value),
      type: 'scattergl' as const,
      mode: 'markers' as const,
      name: 'High Vib (>0.3g)',
      marker: {
        symbol: 'diamond',
        size: 10,
        color: '#EF4444',
        line: {
          color: '#FFFFFF',
          width: 1
        }
      },
      text: sampledHighVibEvents.map(e => {
        const hours = Math.floor(e.time);
        const minutes = Math.floor((e.time - hours) * 60);
        return `High Vibration Event<br>Time: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}<br>Value: ${e.value.toFixed(3)}g<br>MPM: ${e.mpm.toFixed(1)}<br>Timestamp: ${e.timestamp}`;
      }),
      hoverinfo: 'text' as const,
    },
  ] : [
    // Single color for all
    {
      x: [...decimatedData.pulse_x_time, ...decimatedData.pulse_z_time, ...decimatedData.vib_x_time, ...decimatedData.vib_z_time],
      y: [...decimatedData.pulse_x_data, ...decimatedData.pulse_z_data, ...decimatedData.vib_x_data, ...decimatedData.vib_z_data],
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'All Sensors',
      line: { color: '#2563EB', width: 1 }, // Brand Blue
      showlegend: false,
      connectgaps: false,
    },
    // High vibration markers
    {
      x: sampledHighVibEvents.map(e => e.time),
      y: sampledHighVibEvents.map(e => e.value),
      type: 'scattergl' as const,
      mode: 'markers' as const,
      name: 'High Vib (>0.3g)',
      marker: {
        symbol: 'diamond',
        size: 10,
        color: '#EF4444',
        line: {
          color: '#FFFFFF',
          width: 1
        }
      },
      text: sampledHighVibEvents.map(e => {
        const hours = Math.floor(e.time);
        const minutes = Math.floor((e.time - hours) * 60);
        return `High Vibration Event<br>Time: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}<br>Value: ${e.value.toFixed(3)}g<br>MPM: ${e.mpm.toFixed(1)}<br>Timestamp: ${e.timestamp}`;
      }),
      hoverinfo: 'text' as const,
    },
  ];

  const totalHighVibEvents = plotData.highVibEvents.length;

  return (
    <div style={styles.container}>
      <div style={styles.controls}>
        <button
          onClick={() => setColorBySensor(!colorBySensor)}
          style={{
            ...styles.toggleButton,
            backgroundColor: colorBySensor ? '#2563EB' : '#475569', // Brand Blue / Body Text
          }}
        >
          {colorBySensor ? '센서별 색상' : '단일 색상'}
        </button>
        {totalHighVibEvents > 0 && (
          <div style={{
            ...styles.toggleButton,
            backgroundColor: '#EF4444',
            cursor: 'default',
            fontWeight: 600
          }}>
            ⚠️ 고진동 이벤트: {totalHighVibEvents.toLocaleString()}건
          </div>
        )}
      </div>
      <Plot
        data={traces}
        layout={{
          autosize: true,
          margin: { l: 60, r: 40, t: 40, b: 60 },
          paper_bgcolor: '#1e1e2e',
          plot_bgcolor: '#181825',
          font: { color: '#cdd6f4', family: 'Segoe UI, Noto Sans KR, sans-serif' },
          xaxis: {
            title: 'Time',
            gridcolor: '#313244',
            zeroline: false,
            range: xRange, // Use dynamic range
            tickmode: 'linear',
            tick0: 6,
            dtick: 1, // Show every hour
            tickformat: '%H:%M',
            tickvals: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            ticktext: ['06:00', '07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00'],
          },
          yaxis: {
            title: 'Acceleration (g)',
            gridcolor: '#313244',
            zeroline: true,
            zerolinecolor: '#45475a',
          },
          shapes: [
            // Threshold line at +0.3g
            {
              type: 'line' as const,
              xref: 'paper' as const,
              yref: 'y' as const,
              x0: 0,
              x1: 1,
              y0: 0.3,
              y1: 0.3,
              line: {
                color: '#EF4444',
                width: 2,
                dash: 'dash' as const,
              },
              opacity: 0.6,
            },
            // Threshold line at -0.3g
            {
              type: 'line' as const,
              xref: 'paper' as const,
              yref: 'y' as const,
              x0: 0,
              x1: 1,
              y0: -0.3,
              y1: -0.3,
              line: {
                color: '#EF4444',
                width: 2,
                dash: 'dash' as const,
              },
              opacity: 0.6,
            },
          ],
          annotations: [
            // Label for +0.3g threshold
            {
              x: 0.02,
              y: 0.3,
              xref: 'paper' as const,
              yref: 'y' as const,
              text: '0.3g threshold',
              showarrow: false,
              font: {
                size: 10,
                color: '#EF4444',
              },
              yshift: 10,
              xanchor: 'left',
            },
            // Label for -0.3g threshold
            {
              x: 0.02,
              y: -0.3,
              xref: 'paper' as const,
              yref: 'y' as const,
              text: '-0.3g threshold',
              showarrow: false,
              font: {
                size: 10,
                color: '#EF4444',
              },
              yshift: -10,
              xanchor: 'left',
            },
          ],
          hovermode: 'x unified',
          showlegend: true,
          legend: {
            x: 1,
            xanchor: 'right',
            y: 1,
          },
        }}
        config={{
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        }}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler
        onRelayout={handleRelayout}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
  },
  controls: {
    position: 'absolute',
    top: 10,
    right: 10,
    zIndex: 1000,
    display: 'flex',
    gap: 8,
  },
  toggleButton: {
    padding: '6px 12px',
    border: 'none',
    borderRadius: 4,
    color: '#cdd6f4',
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.2s',
    fontFamily: 'Segoe UI, Noto Sans KR, sans-serif',
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#6c7086',
    fontSize: 14,
  },
};
