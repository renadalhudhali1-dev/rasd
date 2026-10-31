"""Camera + optical sensor abstraction.

IMPORTANT: a real thermal camera needs real hardware + vendor SDK. An ordinary
RGB webcam CANNOT measure temperature. Everything marked Simulated* below
produces DEMO data only. Real adapters must implement the same interface.
"""
import math
import random
from abc import ABC, abstractmethod
from typing import List, Optional


# ---------------------------------------------------------------- Thermal camera
class ThermalCameraAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def read_skin_temperature(self) -> Optional[float]:
        """Return skin-surface temperature in °C, or None if no valid face/frame."""


class SimulatedThermalAdapter(ThermalCameraAdapter):
    name = "simulated-thermal"

    def __init__(self, scenario: dict):
        self.s = scenario

    def read_skin_temperature(self):
        t = self.s.get("temp")
        return None if t is None else round(t + random.uniform(-0.15, 0.15), 1)


class RealThermalAdapter(ThermalCameraAdapter):
    """Placeholder for real hardware (USB / RTSP / HTTP stream / vendor SDK).
    Put the vendor SDK or stream decoding HERE, e.g.:
      - RTSP/HTTP: open the stream, take the radiometric frame, read ROI (forehead)
      - SDK: call the vendor's temperature-at-point API
    """
    name = "real-thermal"

    def __init__(self, url: str = ""):
        self.url = url

    def read_skin_temperature(self):
        raise NotImplementedError("Connect your thermal camera SDK/stream here.")


class ThermalCameraService:
    def __init__(self, adapter: ThermalCameraAdapter):
        self.adapter = adapter

    def capture(self):
        return self.adapter.read_skin_temperature(), self.adapter.name


# ---------------------------------------------------------------- Optical (PPG)
class PPGSensorAdapter(ABC):
    name = "abstract"
    fs = 25  # Hz

    @abstractmethod
    def read_samples(self, seconds: int = 10) -> List[float]:
        """Return raw PPG samples (Serial / BLE / USB adapters implement this)."""


class SimulatedPPGAdapter(PPGSensorAdapter):
    name = "simulated-ppg"

    def __init__(self, scenario: dict):
        self.s = scenario

    def read_samples(self, seconds=10):
        f = self.s["hr"] / 60.0
        n = self.fs * seconds
        out = []
        for i in range(n):
            t = i / self.fs
            # pulse-like wave + simulated motion/noise
            out.append(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t)
                       + random.gauss(0, self.s.get("noise", 0.1)))
        return out


class SerialPPGAdapter(PPGSensorAdapter):
    """Placeholder for a real PPG module (e.g. MAX30102 over Serial/BLE).
    Read the device's raw samples here (pyserial / bleak) and return a list."""
    name = "serial-ppg"

    def read_samples(self, seconds=10):
        raise NotImplementedError("Connect your PPG device (Serial/BLE/USB) here.")


def process_ppg(samples: List[float], fs: int):
    """Signal processing: peak detection -> heart rate + signal quality.
    quality = regularity of beat intervals (low variability -> high quality)."""
    n = len(samples)
    mean = sum(samples) / n
    std = (sum((x - mean) ** 2 for x in samples) / n) ** 0.5 or 1e-9
    peaks, min_gap = [], int(0.3 * fs)
    for i in range(1, n - 1):
        if samples[i] > samples[i - 1] and samples[i] >= samples[i + 1] and samples[i] > mean + 0.5 * std:
            if not peaks or i - peaks[-1] >= min_gap:
                peaks.append(i)
    if len(peaks) < 4:
        return None, 0.0
    iv = [(b - a) / fs for a, b in zip(peaks, peaks[1:])]
    m = sum(iv) / len(iv)
    cv = (sum((x - m) ** 2 for x in iv) / len(iv)) ** 0.5 / m
    return round(60.0 / m, 0), round(max(0.0, min(1.0, 1 - 2 * cv)), 2)


class OpticalSensorService:
    def __init__(self, adapter: PPGSensorAdapter):
        self.adapter = adapter

    def measure(self):
        hr, q = process_ppg(self.adapter.read_samples(), self.adapter.fs)
        return hr, q, self.adapter.name
