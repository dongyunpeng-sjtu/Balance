
from algorithm_wave import process_w as wave_process
from algorithm_vector import process_v as vector_process
import sys
from PyQt5.QtCore import QThread, pyqtSignal
from Config import Ctx

class Thread_wave(QThread):
    finished_signal = pyqtSignal(list)
    def __init__(self) -> None:
        super().__init__()
        
    def set(self,ctx,data,one_plane,page_num):
        self.ctx:Ctx = ctx
        self.data = data
        self.one_plane = one_plane
        self.page_num = page_num
        
    def run(self):
        res = wave_process(
            data = self.data,
            one_plane = self.one_plane,
        )
        # 参考res数据类型和数据结构
        # onepale:res=[(np.float64(36.627241510873716), np.float64(0.10739785804164376), np.float64(-2.7654990439494695))]
        # twopale:res=[(np.float64(36.62374821173105), np.float64(0.10428248779212426), np.float64(-2.725666012375624)),
        #              (np.float64(36.62374821173105), np.float64(0.06465597937538073), np.float64(2.170313798034526))
        #               ]

        self.finished_signal.emit([res,self.page_num])
        
class Thread_vector(QThread):
    finished_signal = pyqtSignal(list)
    def __init__(self) -> None:
        super().__init__()
        
    def set(self,ctx, pipe_line,after_measure):
        self.ctx:Ctx = ctx
        self.pipe_line = pipe_line
        self.after_measure = after_measure
        
    def run(self):
        res = vector_process(
            self.ctx,self.pipe_line,self.after_measure
        )
        self.finished_signal.emit(res)