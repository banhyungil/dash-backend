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
          pulse_x_time.push(absoluteTime);
          pulse_x_data.push(cycle.pulse_accel_x[i] - pulse_x_offset);
        }
        if (i < cycle.pulse_accel_z.length) {
          pulse_z_time.push(absoluteTime);
          pulse_z_data.push(cycle.pulse_accel_z[i] - pulse_z_offset);
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
        vib_x_time.push(time);
        vib_x_data.push(val - vib_x_offset);
      });

      cycle.vib_accel_z.forEach((val, i) => {
        const time = vib_start_hours + (i / VIB_SAMPLE_RATE / 3600);
        vib_z_time.push(time);
        vib_z_data.push(val - vib_z_offset);
      });
    });

    return {
      pulse_x_time, pulse_x_data,
      pulse_z_time, pulse_z_data,
      vib_x_time, vib_x_data,
      vib_z_time, vib_z_data,
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

  // Apply LOD decimation to plot data
  const decimatedData = useMemo(() => {
    const pulse_x = decimateMinMax(plotData.pulse_x_time, plotData.pulse_x_data, decimationFactor);
    const pulse_z = decimateMinMax(plotData.pulse_z_time, plotData.pulse_z_data, decimationFactor);
    const vib_x = decimateMinMax(plotData.vib_x_time, plotData.vib_x_data, decimationFactor);
    const vib_z = decimateMinMax(plotData.vib_z_time, plotData.vib_z_data, decimationFactor);

    return {
      pulse_x_time: pulse_x.time,
      pulse_x_data: pulse_x.value,
      pulse_z_time: pulse_z.time,
      pulse_z_data: pulse_z.value,
      vib_x_time: vib_x.time,
      vib_x_data: vib_x.value,
      vib_z_time: vib_z.time,
      vib_z_data: vib_z.value,
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

  // Create traces based on color mode (using decimated data)
  const traces = colorBySensor ? [
    // Color by sensor type
    {
      x: decimatedData.pulse_x_time,
      y: decimatedData.pulse_x_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'Pulse X',
      line: { color: '#f38ba8', width: 1 },
    },
    {
      x: decimatedData.pulse_z_time,
      y: decimatedData.pulse_z_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'Pulse Z',
      line: { color: '#f9e2af', width: 1 },
    },
    {
      x: decimatedData.vib_x_time,
      y: decimatedData.vib_x_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'VIB X',
      line: { color: '#89b4fa', width: 1 },
    },
    {
      x: decimatedData.vib_z_time,
      y: decimatedData.vib_z_data,
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'VIB Z',
      line: { color: '#a6e3a1', width: 1 },
    },
  ] : [
    // Single color for all
    {
      x: [...decimatedData.pulse_x_time, ...decimatedData.pulse_z_time, ...decimatedData.vib_x_time, ...decimatedData.vib_z_time],
      y: [...decimatedData.pulse_x_data, ...decimatedData.pulse_z_data, ...decimatedData.vib_x_data, ...decimatedData.vib_z_data],
      type: 'scattergl' as const,
      mode: 'lines' as const,
      name: 'All Sensors',
      line: { color: '#89b4fa', width: 1 },
      showlegend: false,
    },
  ];

  return (
    <div style={styles.container}>
      <div style={styles.controls}>
        <button
          onClick={() => setColorBySensor(!colorBySensor)}
          style={{
            ...styles.toggleButton,
            backgroundColor: colorBySensor ? '#89b4fa' : '#45475a',
          }}
        >
          {colorBySensor ? '센서별 색상' : '단일 색상'}
        </button>
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
