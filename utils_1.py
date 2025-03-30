import time
from Config import config
import numpy as np

class DataBuffer:
    def __init__(self) -> None:
        self.data = []
        for _ in range(config.read_channels):
            self.data.append([])
        
    def save(self, data_dict):
        for i in range(config.read_channels):
            self.data[i].append(data_dict[i])
        
    def read(self):
        # print(len(self.data[0]))
        return [np.concatenate(data) for data in self.data]

        
    def clear(self):
        for data in self.data:
            data.clear()
        self.data.clear()
        self.data = []
        for _ in range(config.read_channels):
            self.data.append([])
            
    def __len__(self):
        return len(self.data[0])
        
        
def time_cal(func):
    def wrapper(*args, **kwargs):
        s = time.time()
        result = func(*args, **kwargs)
        e = time.time()
        print(f"{func} use time:{e-s:.5f}")
        return result
    return wrapper


class RPM_Queue:
    def __init__(self) -> None:
        self.arr:list[float] = [0.0]
        self.length = config.rpm_queue_lenght
        
    def push(self,num):
        self.arr.append(num)
        if len(self.arr) > self.length:
            self.arr.pop(0)
            
    def get(self):
        return self.arr[0]
    

