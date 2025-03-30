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
        print("Thread read started")
        self.stop = False
        self.q_to_process = q_to_process
        self.history_data = []
        super().__init__()

    def run(self):
        CHUNK = config.chunk
        FORMAT = config.FORMAT
        read_channels = config.read_channels
        rate = config.rate
        input_device_index = config.input_device_index
 
        turn_to_offline = False

        if config.online_reader == True:
            try:
                audio = pyaudio.PyAudio()
                stream = audio.open(
                    format=FORMAT,
                    channels=read_channels,
                    rate=rate,
                    input=True,
                    input_device_index=input_device_index,  # 设置声卡设备索引
                    frames_per_buffer=CHUNK,
                )
                print("online reader")
            except Exception as e:
                print("online reader fails to initialize.")
                print(f"{e}")
                turn_to_offline = True

        if config.online_reader == False or turn_to_offline == True:
            stream = offline_reader(
                format=FORMAT,
                channels=read_channels,
                rate=rate,
                input=True,
                input_device_index=input_device_index,  # 设置声卡设备索引
                frames_per_buffer=CHUNK,
            )
            print("offline reader started.")

        while True:
            data = stream.read(CHUNK)
            if config.online_reader == True and not turn_to_offline == True:
                channel_data = dict()
                audio_data = np.frombuffer(data, dtype=np.float32)
                for i in range(read_channels):
                    channel_data[i] = audio_data[i::read_channels]
            else:
                channel_data = dict()
                for i in range(read_channels):
                    channel_data[i] = data[i]

            
            for i in range(read_channels):
                channel_data[i] = channel_data[i] * config.amplification_factor
            channel_data[3] = abs(channel_data[3])
            rpm = self.get_rpm(channel_data[3])
            channel_data["rpm"] = rpm
            self.q_to_process.put(channel_data)
            # print(rpm)

            if self.stop:
                try:
                    if isinstance(audio, pyaudio.PyAudio):
                        stream.stop_stream()
                        stream.close()
                        audio.terminate()
                    break
                except:
                    pass
            self.read_data.emit()
        print("read thread over")

    def set_stop(self, is_stop):
        """
        only called when the process ends.
        """
        self.stop = is_stop
        print("read thread stop")

    def get_rpm(self, data=None):
        # data = np.ones((10000,))
        # the data will be like:
        
        '''
            _____
            丨 丨
            丨 丨
        ____丨 丨_____
        
        '''
        try:
            if config.rotate_smooth:
                data = mean_filter(data, config.smooth_d)
                
            if len(self.history_data) <= int(config.rpm_cal_duration / 0.2) + 1:
                self.history_data.append(data)
            else:
                self.history_data.pop(0)
                self.history_data.append(data)
            
            len_sig = int(config.rpm_cal_duration * config.rate)
            data = np.concatenate(self.history_data)[-int(len_sig) : -1]
            # print(f"sig duration:{len(data)/config.rate:.2f}")
            data_a = np.where(data < config.rpm_threshold, 1, 0)[:-1]
            data_b = np.where(data > config.rpm_threshold, 1, 0)[1:]

            descending_edge_data = np.logical_and(data_a, data_b) # 此刻是低且下一刻是高
            
            indexes = np.argwhere(descending_edge_data == 1).reshape(-1)

            diff_indexes = indexes[1:] - indexes[:-1]

            freqs = config.rate / diff_indexes

            rpm = freqs * 60
            
            if len(rpm) == 0:
                return 0
            else:
                return float(f"{np.mean(rpm):.2f}")
        except:
            return 0


class online_reader:
    """
    This thread keeps reading the data and send the data to process thread through the queue
    """

    def __init__(
        self,
        #  q_to_process:queue.Queue,
        #  config:dict
    ) -> None:
        self.stop = False
        # self.q_to_process = q_to_process
        self.history_data = []
        super().__init__()

    def run(self):
        CHUNK = config.CHUNK
        FORMAT = config.FORMAT
        channels = config.channels
        rate = config.rate
        input_device_index = config.input_device_index

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=input_device_index,  # 设置声卡设备索引
            frames_per_buffer=CHUNK * 8,
        )
        print("online reader")

        while True:
            data = stream.read(CHUNK)
            channel_data = dict()
            audio_data = np.frombuffer(data, dtype=np.float32)
            for i in range(channels):
                channel_data[i] = audio_data[i::channels]

            rpm = self.get_rpm(channel_data[3])
            channel_data["rpm"] = rpm

            print(rpm)

    def get_rpm(self, data=None):
        # data = np.ones((10000,))
        if len(self.history_data) <= 1:
            self.history_data.append(data)
        else:
            self.history_data.pop(0)
            self.history_data.append(data)

        data = np.concatenate(self.history_data)[-int(44200 * 1.0) : -1]

        data_a = np.where(data < config.rpm_threshold, 1, 0)[:-1]
        data_b = np.where(data > config.rpm_threshold, 1, 0)[1:]

        descending_edge_data = np.logical_and(data_a, data_b)
        indexes = np.argwhere(descending_edge_data == 1).reshape(-1)

        diff_indexes = indexes[1:] - indexes[:-1]

        freqs = config.rate / diff_indexes

        rpm = freqs * 60
        # weight = np.logspace(len(rpm)-1, 0,len(rpm),base=1-alpha)
        # weight = weight * alpha
        # weighted_rpm =  rpm*weight

        # return np.sum(weighted_rpm)
        if len(rpm) == 0:
            return 0
        else:
            return np.mean(rpm)


class offline_reader:
    def __init__(
        self,
        format=pyaudio.paFloat32,
        channels=4,
        rate=44100,
        input=True,
        input_device_index=None,  # 设置声卡设备索引
        frames_per_buffer=1024 * 8,
    ) -> None:
        root = r"./data"

        roots = [f"{root}/{i}.npy" for i in range(4)]
        # roots = [f'{root}/channel{i}.npy' for i in range(4)]

        self.data = [np.load(file_root) for file_root in roots]
        self.cnt = 0
        self.len = len(self.data[0])

    def read(self, x: int):
        if self.cnt + x > self.len:
            # raise Exception('finish reading')
            self.cnt = 0

        read_data = [data[self.cnt : self.cnt + x] for data in self.data]
        self.cnt += x
        time.sleep(0.2)
        return read_data


def get_rpm(data, alpha):
    sample_rate = 44100
    threshold = -0.5
    data_a = np.where(data < threshold, 1, 0)[:-1]
    data_b = np.where(data > threshold, 1, 0)[1:]

    descending_edge_data = np.logical_and(data_a, data_b)
    indexes = np.argwhere(descending_edge_data == 1).reshape(-1)

    # print(indexes.shape)
    diff_indexes = indexes[1:] - indexes[:-1]
    freqs = sample_rate / diff_indexes

    rpm = freqs * 60
    # weight = np.logspace(len(rpm)-1, 0,len(rpm),base=1-alpha)
    # weight = weight * alpha
    # weighted_rpm =  rpm*weight

    # return np.sum(weighted_rpm)
    avg_rpm = np.mean(rpm)
    if len(rpm) == 0:
        return 0
    else:
        return avg_rpm
    return np.mean(rpm)


def online_test():
    r = online_reader()
    r.run()


def offline_test():
    r = offline_reader()
    cnt = 0
    while True:
        try:
            data = r.read(8820)
            # print(data[3].shape)
            rpm = get_rpm(data[3], 0.9)
            cnt += 0.2
            print(rpm)
        except Exception as e:
            print(e.args)
            print(str(e))
            print(repr(e))
            break

def mean_filter(signal, d):
    res_sig = np.zeros_like(signal, dtype=np.float32)
    N = len(signal)
    for i in range(N):
        current_part = signal[max(0,i-d//2):min(N, i+d//2)+1]
        # print(i,i-d//2,i+d//2+1,current_part)
        res_sig[i] = np.mean(current_part)
        
    return res_sig

if __name__ == "__main__":
    online_test()
