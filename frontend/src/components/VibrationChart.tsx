import { useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { CycleData } from '../api/client';

interface VibrationChartProps {
  cycles: CycleData[];
}

export default function VibrationChart({ cycles }: VibrationChartProps) {
  const plotData = useMemo(() => {
    if (cycles.length === 0) {
      return {
        pulse_x_time: [], pulse_x_data: [],
        pulse_y_time: [], pulse_y_data: [],
        pulse_z_time: [], pulse_z_data: [],
        vib_x_time: [], vib_x_data: [],
        vib_z_time: [], vib_z_data: [],
      };
    }

    const pulse_x_time: number[] = [];
    const pulse_x_data: number[] = [];
    const pulse_y_time: number[] = [];
    const pulse_y_data: number[] = [];
    const pulse_z_time: number[] = [];
    const pulse_z_data: number[] = [];
    const vib_x_time: number[] = [];
    const vib_x_data: number[] = [];
    const vib_z_time: number[] = [];
    const vib_z_data: number[] = [];

    const VIB_SAMPLE_RATE = 1000; // Hz

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

      // Pulse accelerometer data (comes first)
      cycle.pulse_timeline.forEach((time, i) => {
        const absoluteTime = cycleStartHours + time / 3600;

        if (i < cycle.pulse_accel_x.length) {
          pulse_x_time.push(absoluteTime);
          pulse_x_data.push(cycle.pulse_accel_x[i]);
        }
        if (i < cycle.pulse_accel_y.length) {
          pulse_y_time.push(absoluteTime);
          pulse_y_data.push(cycle.pulse_accel_y[i]);
        }
        if (i < cycle.pulse_accel_z.length) {
          pulse_z_time.push(absoluteTime);
          pulse_z_data.push(cycle.pulse_accel_z[i]);
        }
      });

      // Calculate pulse duration for VIB offset
      const pulse_duration = cycle.pulse_timeline.length > 0
        ? cycle.pulse_timeline[cycle.pulse_timeline.length - 1]
        : cycle.duration_ms / 1000;

      // VIB accelerometer data (comes after pulse)
      const vib_start_hours = cycleStartHours + pulse_duration / 3600;

      cycle.vib_accel_x.forEach((val, i) => {
        const time = vib_start_hours + (i / VIB_SAMPLE_RATE / 3600);
        vib_x_time.push(time);
        vib_x_data.push(val);
      });

      cycle.vib_accel_z.forEach((val, i) => {
        const time = vib_start_hours + (i / VIB_SAMPLE_RATE / 3600);
        vib_z_time.push(time);
        vib_z_data.push(val);
      });
    });

    return {
      pulse_x_time, pulse_x_data,
      pulse_y_time, pulse_y_data,
      pulse_z_time, pulse_z_data,
      vib_x_time, vib_x_data,
      vib_z_time, vib_z_data,
    };
  }, [cycles]);

  if (cycles.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No vibration data available</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <Plot
        data={[
          // Pulse X
          {
            x: plotData.pulse_x_time,
            y: plotData.pulse_x_data,
            type: 'scattergl',
            mode: 'lines',
            name: 'Pulse X',
            line: { color: '#f38ba8', width: 1 },
          },
          // Pulse Y
          {
            x: plotData.pulse_y_time,
            y: plotData.pulse_y_data,
            type: 'scattergl',
            mode: 'lines',
            name: 'Pulse Y',
            line: { color: '#fab387', width: 1 },
          },
          // Pulse Z
          {
            x: plotData.pulse_z_time,
            y: plotData.pulse_z_data,
            type: 'scattergl',
            mode: 'lines',
            name: 'Pulse Z',
            line: { color: '#f9e2af', width: 1 },
          },
          // VIB X
          {
            x: plotData.vib_x_time,
            y: plotData.vib_x_data,
            type: 'scattergl',
            mode: 'lines',
            name: 'VIB X',
            line: { color: '#89b4fa', width: 1 },
          },
          // VIB Z
          {
            x: plotData.vib_z_time,
            y: plotData.vib_z_data,
            type: 'scattergl',
            mode: 'lines',
            name: 'VIB Z',
            line: { color: '#a6e3a1', width: 1 },
          },
        ]}
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
            range: [0, 24], // 24-hour view
            tickmode: 'linear',
            tick0: 0,
            dtick: 1, // Show every hour
            tickformat: '%H:%M',
            tickvals: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
            ticktext: ['00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00', '07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00', '23:00', '24:00'],
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
