from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
import queue
from matplotlib.table import Cell
import numpy as np
import pyaudio
import time
from Config import config


class Thread_read(QThread):
    """
    This thread keeps reading the data and send the data to process thread through the queue
    """

    read_data = pyqtSignal()

    def __init__(
        self,
        q_to_process: queue.Queue,
    ) -> None:
        print("Thread send started")
        self.stop = False
        self.q_to_process = q_to_process # send bool
        
        DURATION = config.high_duration  # 总时长2秒，包括1秒高平和1秒低平
        HIGH_AMPLITUDE =config.high_amplitude
        
        signal = np.ones(int(DURATION * config.rate)) * HIGH_AMPLITUDE

        
        self.audio_data = signal.astype(np.float32).tobytes()
        self.p = pyaudio.PyAudio()
        
        # 打开音频流
        try:
            self.stream = self.p.open(
                format=config.FORMAT,
                channels=config.send_channels,
                rate=config.rate,
                output=True)
        except:
            print('error in open stream.')
            raise
        super().__init__()

    def run(self):
        while True:
            sig = self.q_to_process.get()
            if sig:
                self.stream.write(self.audio_data)

    def set_stop(self, is_stop):
        """
        only called when the process ends.
        """
        self.stop = is_stop
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

        print("read thread stop")

  








if __name__ == "__main__":
    pass
