/**
 * API client for day_viewer backend
 */

const API_BASE = 'http://localhost:8001/api';

export interface MonthInfo {
  month: string;
  label: string;
}

export interface DateInfo {
  date: string;
  label: string;
}

export interface CycleData {
  timestamp: string;
  session: string;
  cycle_index: number;
  date: string;
  rpm_mean: number;
  rpm_min: number;
  rpm_max: number;
  rpm_timeline: number[];
  rpm_data: number[];
  mpm_mean: number;
  mpm_min: number;
  mpm_max: number;
  mpm_data: number[];
  duration_ms: number;
  set_count: number;
  expected_count: number;
  timeline_offset: number;
  // Pulse accelerometer data
  pulse_timeline: number[];
  pulse_accel_x: number[];
  pulse_accel_y: number[];
  pulse_accel_z: number[];
  // VIB accelerometer data
  vib_accel_x: number[];
  vib_accel_z: number[];
}

export interface DailyDataResponse {
  date: string;
  device: string;
  settings: {
    shaft_dia: number;
    pattern_width: number;
    target_rpm: number;
  };
  cycles: CycleData[];
  total_cycles: number;
}

export async function fetchMonths(): Promise<MonthInfo[]> {
  const response = await fetch(`${API_BASE}/months`);
  return response.json();
}

export async function fetchDevices(month: string): Promise<string[]> {
  const response = await fetch(`${API_BASE}/devices?month=${month}`);
  return response.json();
}

export async function fetchDates(month: string, device: string): Promise<DateInfo[]> {
  const response = await fetch(`${API_BASE}/dates?month=${month}&device=${device}`);
  return response.json();
}

export async function fetchDailyData(
  month: string,
  date: string,
): Promise<DailyDataResponse> {
  const response = await fetch(
    `${API_BASE}/daily-data?month=${month}&date=${date}`
  );
  return response.json();
}

export interface TestExportResponse {
  status: string;
  test_dir: string;
  raw_files_copied: number;
  raw_files: string[];
  integrated_files: string[];
  total_cycles: number;
  filtered_cycles: number;
}

export async function testExport(
  month: string,
  date: string,
): Promise<TestExportResponse> {
  const response = await fetch(
    `${API_BASE}/test-export?month=${month}&date=${date}`
  );
  return response.json();
}
