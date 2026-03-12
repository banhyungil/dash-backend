import { useState } from 'react';
import DateSelector from './pages/DateSelector';
import RpmChart from './components/RpmChart';
import VibrationChart from './components/VibrationChart';
import { fetchDailyData, type DailyDataResponse } from './api/client';

type Tab = 'rpm' | 'vibration';

export default function App() {
  const [showSelector, setShowSelector] = useState(true);
  const [dailyData, setDailyData] = useState<DailyDataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('rpm');

  const handleDateSelect = async (month: string, date: string) => {
    setLoading(true);
    setShowSelector(false);

    try {
      const data = await fetchDailyData(month, date);
      setDailyData(data);
    } catch (error) {
      console.error('Failed to load daily data:', error);
      alert('Failed to load data. Please try again.');
      setShowSelector(true);
    }

    setLoading(false);
  };

  const handleBack = () => {
    setShowSelector(true);
    setDailyData(null);
    setActiveTab('rpm');
  };

  if (showSelector) {
    return <DateSelector onDateSelect={handleDateSelect} />;
  }

  if (loading) {
    return (
      <div style={styles.loading}>
        <div style={styles.spinner} />
        <p>Loading data...</p>
      </div>
    );
  }

  if (!dailyData) {
    return (
      <div style={styles.loading}>
        <p>No data loaded</p>
      </div>
    );
  }

  // Format date with day of week
  const formatDateWithDayOfWeek = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      const days = ['일', '월', '화', '수', '목', '금', '토'];
      const dayOfWeek = days[date.getDay()];
      return `${dateStr} (${dayOfWeek}) 생산 리포트`;
    } catch {
      return `${dateStr} 생산 리포트`;
    }
  };

  return (
    <div style={styles.app}>
      {/* Header */}
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={handleBack}>
          ← Back
        </button>
        <div style={styles.headerInfo}>
          <h2 style={styles.title}>{formatDateWithDayOfWeek(dailyData.date)}</h2>
          <p style={styles.subtitle}>
            Device: {dailyData.device} | Cycles: {dailyData.total_cycles} (Expected filtered)
          </p>
        </div>
        <div style={styles.tabs}>
          <button
            style={{
              ...styles.tab,
              ...(activeTab === 'rpm' ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab('rpm')}
          >
            RPM Timeline
          </button>
          <button
            style={{
              ...styles.tab,
              ...(activeTab === 'vibration' ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab('vibration')}
          >
            Vibration
          </button>
        </div>
      </div>

      {/* Chart area */}
      <div style={styles.chartArea}>
        {activeTab === 'rpm' && (
          <RpmChart
            cycles={dailyData.cycles}
            targetRpm={dailyData.settings.target_rpm}
          />
        )}
        {activeTab === 'vibration' && (
          <VibrationChart cycles={dailyData.cycles} />
        )}
      </div>

      {/* Info footer */}
      <div style={styles.footer}>
        <span style={styles.footerText}>
          Settings: Shaft Dia = {dailyData.settings.shaft_dia}mm, Pattern Width = {dailyData.settings.pattern_width}mm, Target RPM = {dailyData.settings.target_rpm}
        </span>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    width: '100vw',
    overflow: 'hidden',
    background: '#1e1e2e',
    color: '#cdd6f4',
  },
  loading: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    gap: 16,
    color: '#a6adc8',
  },
  spinner: {
    width: 40,
    height: 40,
    border: '4px solid #313244',
    borderTop: '4px solid #2563EB', // Brand Blue
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 20px',
    background: '#181825',
    borderBottom: '1px solid #313244',
  },
  backBtn: {
    padding: '8px 16px',
    background: '#313244',
    color: '#cdd6f4',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  headerInfo: {
    flex: 1,
    textAlign: 'center',
  },
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: '#3B82F6', // Accent Blue
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 12,
    color: '#a6adc8',
  },
  tabs: {
    display: 'flex',
    gap: 8,
  },
  tab: {
    padding: '8px 20px',
    background: '#313244',
    color: '#a6adc8',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  tabActive: {
    background: '#2563EB', // Brand Blue
    color: '#FFFFFF',
  },
  chartArea: {
    flex: 1,
    padding: 16,
    overflow: 'hidden',
  },
  footer: {
    padding: '8px 20px',
    background: '#181825',
    borderTop: '1px solid #313244',
    textAlign: 'center',
  },
  footerText: {
    fontSize: 11,
    color: '#6c7086',
  },
};

// Add CSS animation for spinner
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;
document.head.appendChild(styleSheet);
