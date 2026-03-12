import math
import numpy as np
from scipy import signal as sp_signal
from config import VIB_SAMPLE_RATE


def compute_rms(data: list[float]) -> float:
    """Compute root-mean-square of a data array."""
    if not data:
        return 0.0
    return math.sqrt(sum(x * x for x in data) / len(data))


def compute_fft(data: list[float], sample_rate: float = VIB_SAMPLE_RATE) -> tuple[list[float], list[float]]:
    """Compute FFT and return (frequencies, magnitudes)."""
    n = len(data)
    if n == 0:
        return [], []
    fft_vals = np.fft.rfft(data)
    fft_mag = (np.abs(fft_vals) * 2 / n).tolist()
    freqs = np.fft.rfftfreq(n, 1 / sample_rate).tolist()
    return freqs, fft_mag


def downsample_vib(data: list[float], max_points: int = 20000) -> list[float]:
    """Downsample VIB time-domain data using simple interval sampling.
    Preserves first and last points."""
    n = len(data)
    if n <= max_points:
        return data
    step = n / max_points
    indices = [int(i * step) for i in range(max_points)]
    # Ensure last point included
    if indices[-1] != n - 1:
        indices[-1] = n - 1
    return [data[i] for i in indices]


def compute_spectrogram(data: list[float], sample_rate: float = VIB_SAMPLE_RATE) -> tuple[list[float], list[float], list[list[float]]]:
    """Compute spectrogram using STFT.
    Returns (times, frequencies, power_db) as nested lists.
    """
    data_arr = np.array(data)
    n = len(data_arr)
    if n == 0:
        return [], [], []

    # Ensure minimum data length for spectrogram
    if n < 4:
        return [], [], []

    nperseg = min(256, n)
    # For small datasets, use smaller window to get more time bins
    if n < 128:
        nperseg = max(4, n // 4)

    # Ensure noverlap is strictly less than nperseg
    noverlap = max(0, nperseg // 2 - 1)

    # Final validation: ensure noverlap < nperseg
    if noverlap >= nperseg:
        noverlap = nperseg - 1

    # Safety check: if nperseg is too small or invalid, skip spectrogram
    if nperseg < 2:
        return [], [], []

    frequencies, times, sxx = sp_signal.spectrogram(
        data_arr, fs=sample_rate, nperseg=nperseg, noverlap=noverlap
    )

    # Convert to dB, transpose for [freq_bins x time_bins]
    sxx_db = 10 * np.log10(sxx + 1e-10)

    # Downsample if too large (keep max 128 freq bins x 128 time bins)
    max_bins = 128
    if sxx_db.shape[0] > max_bins:
        step = sxx_db.shape[0] // max_bins
        sxx_db = sxx_db[::step, :]
        frequencies = frequencies[::step]
    if sxx_db.shape[1] > max_bins:
        step = sxx_db.shape[1] // max_bins
        sxx_db = sxx_db[:, ::step]
        times = times[::step]

    return times.tolist(), frequencies.tolist(), sxx_db.tolist()
