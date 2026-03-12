import { useState, useEffect } from 'react';
import { fetchMonths, fetchDevices, fetchDates, testExport, type MonthInfo, type DateInfo } from '../api/client';

interface DateSelectorProps {
  onDateSelect: (month: string, date: string) => void;
}

export default function DateSelector({ onDateSelect }: DateSelectorProps) {
  const [months, setMonths] = useState<MonthInfo[]>([]);
  const [dates, setDates] = useState<DateInfo[]>([]);

  const [selectedMonth, setSelectedMonth] = useState('');
  const [selectedDate, setSelectedDate] = useState('');

  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  // Load months on mount
  useEffect(() => {
    const loadMonths = async () => {
      try {
        const data = await fetchMonths();
        setMonths(data);
        if (data.length > 0) {
          setSelectedMonth(data[0].month);
        }
      } catch (error) {
        console.error('Failed to load months:', error);
      }
    };
    loadMonths();
  }, []);

  // Load dates when month changes
  useEffect(() => {
    if (!selectedMonth) return;

    const loadDates = async () => {
      try {
        // Get first device to fetch dates
        const devices = await fetchDevices(selectedMonth);
        if (devices.length > 0) {
          const data = await fetchDates(selectedMonth, devices[0]);
          setDates(data);
          setSelectedDate('');
        }
      } catch (error) {
        console.error('Failed to load dates:', error);
      }
    };
    loadDates();
  }, [selectedMonth]);

  const handleLoadClick = () => {
    if (!selectedMonth || !selectedDate) {
      alert('Please select month and date');
      return;
    }

    onDateSelect(selectedMonth, selectedDate);
  };

  const handleTestExport = async () => {
    if (!selectedMonth || !selectedDate) {
      alert('Please select month and date');
      return;
    }

    setTesting(true);

    try {
      const result = await testExport(selectedMonth, selectedDate);
      alert(
        `Test Export Complete!\n\n` +
        `Test Directory: ${result.test_dir}\n` +
        `Raw Files Copied: ${result.raw_files_copied}\n` +
        `Total Cycles: ${result.total_cycles}\n` +
        `Filtered Cycles (Expected): ${result.filtered_cycles}\n\n` +
        `Integrated files created:\n${result.integrated_files.join('\n')}`
      );
    } catch (error) {
      console.error('Test export failed:', error);
      alert('Test export failed. Check console for details.');
    }

    setTesting(false);
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Day Viewer</h1>
        <p style={styles.subtitle}>Select a date to view roll data (Expected filtered)</p>
      </div>

      <div style={styles.form}>
        {/* Month selector */}
        <div style={styles.field}>
          <label style={styles.label}>Month</label>
          <select
            style={styles.select}
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
          >
            {months.map((m) => (
              <option key={m.month} value={m.month}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* Date selector */}
        <div style={styles.field}>
          <label style={styles.label}>Date</label>
          <select
            style={styles.select}
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            disabled={!selectedMonth || dates.length === 0}
          >
            <option value="">-- Select Date --</option>
            {dates.map((d) => (
              <option key={d.date} value={d.date}>
                {d.label || d.date}
              </option>
            ))}
          </select>
        </div>

        {/* Load button */}
        <button
          style={{
            ...styles.button,
            ...((!selectedMonth || !selectedDate) ? styles.buttonDisabled : {}),
          }}
          onClick={handleLoadClick}
          disabled={!selectedMonth || !selectedDate}
        >
          Load Data
        </button>

        {/* Test Export button */}
        <button
          style={{
            ...styles.testButton,
            ...((!selectedMonth || !selectedDate || testing) ? styles.buttonDisabled : {}),
          }}
          onClick={handleTestExport}
          disabled={!selectedMonth || !selectedDate || testing}
        >
          {testing ? 'Exporting...' : 'Test Export (Copy Raw + Create CSV)'}
        </button>
      </div>

      {/* Info panel */}
      {dates.length > 0 && (
        <div style={styles.info}>
          <p style={styles.infoText}>
            Available dates: <strong>{dates.length}</strong>
          </p>
          <p style={styles.infoText}>
            Selected: {selectedMonth} / {selectedDate || '(none)'}
          </p>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: 40,
    background: 'linear-gradient(135deg, #1e1e2e 0%, #181825 100%)',
  },
  header: {
    textAlign: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 48,
    fontWeight: 700,
    color: '#89b4fa',
    marginBottom: 8,
    letterSpacing: -1,
  },
  subtitle: {
    fontSize: 16,
    color: '#a6adc8',
    fontWeight: 400,
  },
  form: {
    background: '#313244',
    borderRadius: 12,
    padding: 32,
    minWidth: 400,
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
  },
  field: {
    marginBottom: 20,
  },
  label: {
    display: 'block',
    fontSize: 13,
    fontWeight: 600,
    color: '#cdd6f4',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  select: {
    width: '100%',
    padding: '10px 12px',
    fontSize: 14,
    background: '#1e1e2e',
    color: '#cdd6f4',
    border: '1px solid #45475a',
    borderRadius: 6,
    cursor: 'pointer',
    outline: 'none',
  },
  button: {
    width: '100%',
    padding: '12px 24px',
    fontSize: 15,
    fontWeight: 600,
    background: '#89b4fa',
    color: '#1e1e2e',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    marginTop: 12,
    transition: 'all 0.2s',
  },
  testButton: {
    width: '100%',
    padding: '10px 24px',
    fontSize: 13,
    fontWeight: 600,
    background: '#a6e3a1',
    color: '#1e1e2e',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    marginTop: 8,
    transition: 'all 0.2s',
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  info: {
    marginTop: 24,
    padding: 16,
    background: '#181825',
    borderRadius: 8,
    minWidth: 400,
  },
  infoText: {
    fontSize: 13,
    color: '#a6adc8',
    marginBottom: 4,
  },
};
