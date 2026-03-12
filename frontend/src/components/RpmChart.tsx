import { useMemo, useState } from 'react';
import Plot from 'react-plotly.js';
import type { CycleData } from '../api/client';

interface RpmChartProps {
  cycles: CycleData[];
  targetRpm: number;
}

export default function RpmChart({ cycles }: RpmChartProps) {
  const [colorByDevice, setColorByDevice] = useState(true);
  const plotData = useMemo(() => {
    if (cycles.length === 0) {
      return {};
    }

    // Device color mapping
    const deviceColors: Record<string, string> = {
      'R1': '#f38ba8', // red/pink
      'R2': '#fab387', // orange
      'R3': '#a6e3a1', // green
      'R4': '#89b4fa', // blue
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

    // Group by session
    const sessionData: Record<string, { x: number[]; y: number[]; text: string[] }> = {};

    cycles.forEach((cycle) => {
      const session = cycle.session;
      if (!sessionData[session]) {
        sessionData[session] = { x: [], y: [], text: [] };
      }

      const cycleStartHours = getHoursFromMidnight(cycle.timestamp);
      const avgMpm = cycle.mpm_mean;

      // Format time for hover text
      const hours = Math.floor(cycleStartHours);
      const minutes = Math.floor((cycleStartHours - hours) * 60);
      const seconds = Math.floor(((cycleStartHours - hours) * 60 - minutes) * 60);
      const timeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

      sessionData[session].x.push(cycleStartHours);
      sessionData[session].y.push(avgMpm);
      sessionData[session].text.push(
        `Time: ${timeStr}<br>` +
        `MPM: ${avgMpm.toFixed(2)}<br>` +
        `RPM: ${cycle.rpm_mean.toFixed(1)}<br>` +
        `Session: ${session}<br>` +
        `Timestamp: ${cycle.timestamp}<br>` +
        `Expected: ${cycle.expected_count} (Actual: ${cycle.set_count})`
      );
    });

    return { sessionData, deviceColors };
  }, [cycles]);

  if (cycles.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No data available</p>
      </div>
    );
  }

  // Create combined time-ordered line trace
  const allPoints: Array<{ x: number; y: number; text: string; session: string }> = [];
  Object.entries(plotData.sessionData || {}).forEach(([session, data]) => {
    data.x.forEach((x, i) => {
      allPoints.push({
        x,
        y: data.y[i],
        text: data.text[i],
        session,
      });
    });
  });

  // Sort by time
  allPoints.sort((a, b) => a.x - b.x);

  // Create line trace (all sessions connected by time)
  const lineTrace = {
    x: allPoints.map(p => p.x),
    y: allPoints.map(p => p.y),
    type: 'scattergl' as const,
    mode: 'lines' as const,
    line: {
      color: '#45475a',
      width: 1,
    },
    hoverinfo: 'skip' as const,
    showlegend: false,
  };

  let traces;
  if (colorByDevice) {
    // Create marker traces for each session (for coloring)
    const markerTraces = Object.entries(plotData.sessionData || {}).map(([session, data]) => ({
      x: data.x,
      y: data.y,
      type: 'scattergl' as const,
      mode: 'markers' as const,
      marker: {
        size: 6,
        color: plotData.deviceColors?.[session] || '#cdd6f4',
      },
      text: data.text,
      hoverinfo: 'text' as const,
      name: session,
      showlegend: true,
    }));
    traces = [lineTrace, ...markerTraces];
  } else {
    // Single color mode - all points in one trace
    const singleTrace = {
      x: allPoints.map(p => p.x),
      y: allPoints.map(p => p.y),
      type: 'scattergl' as const,
      mode: 'markers' as const,
      marker: {
        size: 6,
        color: '#89b4fa',
      },
      text: allPoints.map(p => p.text),
      hoverinfo: 'text' as const,
      name: 'All',
      showlegend: false,
    };
    traces = [lineTrace, singleTrace];
  }

  return (
    <div style={styles.container}>
      <div style={styles.controls}>
        <button
          onClick={() => setColorByDevice(!colorByDevice)}
          style={{
            ...styles.toggleButton,
            backgroundColor: colorByDevice ? '#89b4fa' : '#45475a',
          }}
        >
          {colorByDevice ? 'Device별 색상' : '단일 색상'}
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
            range: [6, 20], // 06:00 ~ 20:00 view
            tickmode: 'linear',
            tick0: 6,
            dtick: 1, // Show every hour
            tickformat: '%H:%M',
            tickvals: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            ticktext: ['06:00', '07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00'],
          },
          yaxis: {
            title: 'MPM (Meter Per Minute)',
            gridcolor: '#313244',
            zeroline: false,
          },
          hovermode: 'closest',
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
