'''
Created on Dec 7, 2025

@author: matze
'''
#arch: python-scipy, debian: python3-scipy,python3-numpy,python3-pyqt6,python3-mpv
import numpy as np
from scipy.fft import rfft, rfftfreq
from PyQt6.QtCore import QThread, pyqtSignal

class MPVAudioAnalyzer(QThread):
    """
    Reads PCM audio from mpv via FIFO and emits frequency band data.
    """
    frequency_data = pyqtSignal(list)
    
    def __init__(self, fifo_path, sample_rate=48000, channels=2, bands=10):
        super().__init__()
        self.fifo_path = fifo_path
        self.sample_rate = sample_rate
        self.channels = channels
        self.bands = bands
        self.running = True
        self.chunk_size = 2048
        
    def run(self):
        try:
            print("start run")
            # Open FIFO for reading (blocking until mpv opens for writing)
            with open(self.fifo_path, 'rb') as fifo:
                while self.running:
                    # Read audio chunk (s16le = 16-bit signed little-endian)
                    bytes_to_read = self.chunk_size * self.channels * 2
                    print("readbytes:",bytes_to_read)
                    data = fifo.read(bytes_to_read)
                    
                    if len(data) < bytes_to_read:
                        if not self.running:
                            break
                        continue
                    
                    # Convert to numpy array and normalize
                    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # Convert stereo to mono by averaging channels
                    if self.channels == 2:
                        audio = audio.reshape(-1, 2).mean(axis=1)
                    
                    # Compute FFT
                    fft_data = np.abs(rfft(audio))
                    freqs = rfftfreq(len(audio), 1/self.sample_rate)
                    
                    # Extract frequency bands
                    band_values = self.extract_bands(fft_data, freqs)
                    self.frequency_data.emit(band_values)
                    
        except Exception as e:
            print(f"Audio analyzer error: {e}")
    
    def extract_bands(self, fft_data, freqs):
        """Extract logarithmically-spaced frequency bands (20Hz - 20kHz)"""
        band_edges = np.logspace(np.log10(20), np.log10(20000), self.bands + 1)
        band_values = []
        
        for i in range(self.bands):
            mask = (freqs >= band_edges[i]) & (freqs < band_edges[i+1])
            if np.any(mask):
                band_values.append(np.mean(fft_data[mask]))
            else:
                band_values.append(0)
        
        # Normalize to 0-1 range
        max_val = max(band_values) if max(band_values) > 0 else 1
        return [v / max_val for v in band_values]
    
    def stop(self):
        self.running = False
