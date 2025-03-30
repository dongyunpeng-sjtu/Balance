from copy import copy, deepcopy

import Config
from Ui_main_window_stack import Ui_MainWindow
from PyQt5.QtWidgets import (
    QStyleFactory,
    QAbstractItemView,
    QLabel,
    QHeaderView,
    QMessageBox,
    QInputDialog,
    QMainWindow,
)
from PyQt5.QtGui import QPixmap, QFont, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QPoint, QEvent, QRect, QModelIndex

import os
import time
import math
import logging
import pyautogui
import numpy as np
import scipy.signal as signal
from itertools import product
from functools import partial

from Config import *
from queue import Queue
from thread_read import Thread_read
from thread_process import Thread_wave
from utils import DataBuffer, RPM_Queue
from algorithm_vector import process_v as vector_process

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import pickle
import shelve
from report_gen import create_docx_1, create_docx_2

matplotlib.rcParams["figure.max_open_warning"] = 50


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        global config
        
        if os.path.exists('config.pkl'):
            try:
                with open('config.pkl', 'rb') as f:
                    config = pickle.load(f)
            except:
                config = Config()
        else:
            config = Config
        
        self.ctx = Ctx()

        self.log_init()

        self.logger.debug(f'current config {config}')
        self.main_window = Ui_MainWindow()

        self.main_window.setupUi(self)
        self.m = self.main_window

        self.pipe_line = 0
        self.set_pipeline()
        self.m.content_stack.setCurrentIndex(0)
        self.m.button_stack.setCurrentIndex(0)

        self.read_queue = Queue()
        self.read_thread = Thread_read(self.read_queue)
        self.read_thread.start()

        self.collecting = False
        self.databuffer = DataBuffer()
        self.fft_databuffer = DataBuffer()
        self.read_thread.read_data.connect(self.receive_data)
        self.read_thread.read_data.connect(self.fft_receive_data)
        self.collect_cnt = 0
        self.rpm_queue = RPM_Queue()

        self.block_next_page_on_tw = False

        # do detect检测是否当前页在测试页。
        self.in_tolorance = False
        self.in_tolorance_cnt = 0
        self.measure_ready_collect = False
        self.start_collecting = False
        self.name_checking = False

        self.fft_receive_data_on = False
        self.fft_collecting = False
        self.fft_can_process = False
        self.fft_can_draw_raw_data = False
        self.processing_data_before_res = False

        self.figure = plt.figure()

        self.fft_canvas = FigureCanvas(self.figure)
        self.fft_canvas.setGeometry(QRect(20, 100, 821, 491))
        self.fft_canvas.setObjectName("fft_canvas")

        self.fft_toolbar = NavigationToolbar(self.fft_canvas, self)
        self.fft_toolbar.setGeometry(QRect(20, 20, 821, 71))
        self.fft_toolbar.setObjectName("fft_toolbar")
        self.m.fft_verticalLayout.addWidget(self.fft_toolbar)
        self.m.fft_verticalLayout.addWidget(self.fft_canvas)

        self.current_params = dict()

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self.set_new_rotor_disable()

        self.build_connections()

        # self.init_all_qcustom_plot()

        self.install_all_event_filter()

        self.detection_done = False
        self.m.new_rotor_one_plane_button.setChecked(True)
        self.m.new_rotor_gmm_button.setChecked(True)
        self.m.new_rotor_g_button.setChecked(False)
        self.m.new_rotor_norm_tab.setCurrentIndex(0)

        self.m.rotors_gmm_button.setChecked(True)
        self.m.rotors_g_button.setChecked(False)
        self.m.rotors_norm_tab.setCurrentIndex(0)

        for i in range(4, 18 + 1):
            getattr(self.m, f"tabWidget_{i}").setCurrentIndex(0)
        self.data_root = r"./data/data.csv"
        pixmap = QPixmap(config.example_img_root)
        self.m.label_img.setPixmap(pixmap)

        self.init_all_polar_plot_new()
        self.level_enable()

        # self.rotors_page_index = 0
        self.rotors_state = 2  # 不在当前界面是0,Init是1,Edit是2

        self.rotors_cur_row = None
        self.rotor_cur_index = None

        # 用于检测怎么翻转.
        self.cor_weight_btn_clicked = False

        # 用于检测是否存在rpm_{t-1} < threshold < rpm_{t}
        self.res_restart1 = False
        # 用于检测res的rpm是否稳定
        self.res_restart2 = False
        # 两个变量在测量后均设置为False，在receive data时动态测量
        
        # 以下是用于记录测量的变量
        self.last_rpm = 0  # 记录上一次的rpm,用于在res界面restart
        self.history_rpm_bool_queue: list[bool] = (
            []
        )  # 记录过去一段时间的rpm是否符合toloration范围,长度由config.tolorance_cnt_max给出
        self.history_rpm_data_queue: list[bool] = []
        self.is_collecting = False

        self.rotors_findres = []
        self.rotors_cur_pipeline = 0
        self.load_all_data_from_pkl()
        self.init_table()
            
        self.model_stastic = None
        self.statistic_data_show = []
        self.load_statistic_data_from_pkl()
        self.init_statistics_table()
        
        self.restore_all_data()
        
        self.password = '123456'
        self.developer_options = False
        self.m.measure_tab.setTabVisible(1, self.developer_options)

    def log_init(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level=config.logging_level)

        os.makedirs(os.path.dirname(config.logging_file), exist_ok=True)
        handler = logging.FileHandler(filename=config.logging_file, mode="w")
        handler.setLevel(config.logging_level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s-%(levelname)s-%(lineno)d-%(message)s")
        )

        console = logging.StreamHandler()
        console.setFormatter(
            logging.Formatter("%(asctime)s-%(levelname)s-%(lineno)d-%(message)s")
        )
        console.setLevel(level=config.logging_level)

        self.logger.addHandler(handler)
        self.logger.addHandler(console)
        self.logger.debug("log init finish")

    def build_connections(self):
        """
        Most of the connections are built here.
        """

        def set_content_button_index(i1, i2):
            self.m.content_stack.setCurrentIndex(i1)
            self.m.button_stack.setCurrentIndex(i2)

        set_index = set_content_button_index

        # new rotor
        self.m.home_new_rotor_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_NEWROTOR, INDEX_BUTTON_NEWROTOR)
        )

        # rotors
        self.m.home_rotors_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_ROTORS, INDEX_BUTTON_ROTORS)
        )
        self.m.home_rotors_button.clicked.connect(self.rotors_init_state)

        # measure
        # self.m.rotors_measure_button.clicked.connect(
        #     partial(set_index, INDEX_CONTENT_RES, INDEX_BUTTON_MEASURE)
        # )
        self.m.rotors_measure_button.clicked.connect(self.rotors_clicked_measure)
        # self.m.rotors_measure_button.clicked.connect(
        #     self.switch_to_fake_mea
        # )
        self.m.home_measure_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_RES, INDEX_BUTTON_MEASURE)
        )
        self.m.home_measure_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_RES, INDEX_BUTTON_MEASURE)
        )
        self.m.measure_start_button.clicked.connect(lambda: self.switch_to_fake_mea())
        self.m.measure_continue_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_RES, INDEX_BUTTON_MEASURE)
        )
        self.m.rotors_exit_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_HOME, INDEX_BUTTON_HOME)
        )
        self.m.measure_close_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_HOME, INDEX_BUTTON_HOME)
        )
        self.m.new_rotor_close_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_HOME, INDEX_BUTTON_HOME)
        )

        # FFT
        self.m.home_fft_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_FFT, INDEX_BUTTON_FFT)
        )
        self.m.fft_close_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_HOME, INDEX_BUTTON_HOME)
        )
        self.m.fft_close_button.clicked.connect(partial(self.fft_set_receive_on, False))

        # exit
        self.m.home_exit_button.clicked.connect(self.close_window)
        self.m.shutdown.clicked.connect(self.close_window)

        self.m.new_rotor_auto_rpm_button.clicked.connect(
            lambda: self.m.nr_rpm.setText(self.m.new_rotor_auto_rpm_button.text())
        )
        self.m.settings_close_button.clicked.connect(
            partial(set_index, INDEX_CONTENT_HOME, INDEX_BUTTON_HOME)
        )

        self.m.new_rotor_one_plane_button.clicked.connect(self.set_new_rotor_disable)
        self.m.new_rotor_two_plane_button.clicked.connect(self.set_new_rotor_disable)
        self.m.new_rotor_s_button.toggled.connect(self.set_level_packed)
        self.m.new_rotor_d_button.toggled.connect(self.set_level_packed)
        self.m.new_rotor_ds_button.toggled.connect(self.set_level_packed)

        self.m.new_rotor_gmm_button.clicked.connect(
            lambda: (
                self.m.new_rotor_gmm_button.setChecked(True),
                self.m.new_rotor_g_button.setChecked(False),
                self.m.new_rotor_norm_tab.setCurrentIndex(0),
            )
        )
        self.m.new_rotor_g_button.clicked.connect(
            lambda: (
                self.m.new_rotor_gmm_button.setChecked(False),
                self.m.new_rotor_g_button.setChecked(True),
                self.m.new_rotor_norm_tab.setCurrentIndex(1),
            )
        )

        self.m.rotors_gmm_button.clicked.connect(
            lambda: (
                self.m.rotors_gmm_button.setChecked(True),
                self.m.rotors_g_button.setChecked(False),
                self.m.rotors_norm_tab.setCurrentIndex(0),
            )
        )
        self.m.rotors_g_button.clicked.connect(
            lambda: (
                self.m.rotors_gmm_button.setChecked(False),
                self.m.rotors_g_button.setChecked(True),
                self.m.rotors_norm_tab.setCurrentIndex(1),
            )
        )

        self.m.new_rotor_continue_button.clicked.connect(self.next_page)
        self.m.new_rotor_back_button.clicked.connect(self.prev_page)

        def init_progressBar(content_id):
            if content_id in [
                INDEX_CONTENT_IR,
                INDEX_CONTENT_FP,
                INDEX_CONTENT_SP,
                INDEX_CONTENT_MEASURE,
            ]:
                names = ["s", "d", "ds"]

                if content_id == INDEX_CONTENT_IR:
                    page = "ir"
                elif content_id == INDEX_CONTENT_FP:
                    page = "fp"
                elif content_id == INDEX_CONTENT_SP:
                    page = "sp"
                elif content_id == INDEX_CONTENT_MEASURE:
                    page = "m"

                self.logger.debug(f"update progress bar:{0}")
                getattr(self.m, f"{page}_{names[self.pipe_line]}_progressBar").setValue(
                    0
                )

        self.m.content_stack.currentChanged.connect(init_progressBar)
        self.m.content_stack.currentChanged.connect(self.reset_collection_on_condition)
        self.m.content_stack.currentChanged.connect(self.save_test_weight)

        # '''
        #     Tool Buttons on test weight 1 page
        # '''
        self.m.tw1_tool_Button_num0.clicked.connect(
            lambda: self.edit_input_lineedit("0")
        )
        self.m.tw1_tool_Button_num1.clicked.connect(
            lambda: self.edit_input_lineedit("1")
        )
        self.m.tw1_tool_Button_num2.clicked.connect(
            lambda: self.edit_input_lineedit("2")
        )
        self.m.tw1_tool_Button_num3.clicked.connect(
            lambda: self.edit_input_lineedit("3")
        )
        self.m.tw1_tool_Button_num4.clicked.connect(
            lambda: self.edit_input_lineedit("4")
        )
        self.m.tw1_tool_Button_num5.clicked.connect(
            lambda: self.edit_input_lineedit("5")
        )
        self.m.tw1_tool_Button_num6.clicked.connect(
            lambda: self.edit_input_lineedit("6")
        )
        self.m.tw1_tool_Button_num7.clicked.connect(
            lambda: self.edit_input_lineedit("7")
        )
        self.m.tw1_tool_Button_num8.clicked.connect(
            lambda: self.edit_input_lineedit("8")
        )
        self.m.tw1_tool_Button_num9.clicked.connect(
            lambda: self.edit_input_lineedit("9")
        )
        self.m.tw1_tool_Button_dot.clicked.connect(
            lambda: self.edit_input_lineedit(".")
        )

        # self.m.tw1_tool_Button_backspace.clicked.connect(lambda: self.edit_input_lineedit(delete_one_char=True))
        self.m.tw1_tool_Button_C.clicked.connect(
            lambda: self.edit_input_lineedit(delete_all=True)
        )
        # self.m.tw1_tool_Button_enter.clicked.connect(lambda: self.shift_input_lineedit('test_weight_1'))
        self.m.tw1_tool_Button_backspace.clicked.connect(
            lambda: pyautogui.press("backspace")
        )
        # self.m.tw1_tool_Button_C.clicked.connect(lambda: pyautogui.press)
        self.m.tw1_tool_Button_enter.clicked.connect(
            lambda: self.shift_input_lineedit("test_weight_1")
        )

        # '''
        #     Tool Buttons on test weight 2 page
        # '''
        self.m.tw2_tool_Button_num0.clicked.connect(
            lambda: self.edit_input_lineedit("0")
        )
        self.m.tw2_tool_Button_num1.clicked.connect(
            lambda: self.edit_input_lineedit("1")
        )
        self.m.tw2_tool_Button_num2.clicked.connect(
            lambda: self.edit_input_lineedit("2")
        )
        self.m.tw2_tool_Button_num3.clicked.connect(
            lambda: self.edit_input_lineedit("3")
        )
        self.m.tw2_tool_Button_num4.clicked.connect(
            lambda: self.edit_input_lineedit("4")
        )
        self.m.tw2_tool_Button_num5.clicked.connect(
            lambda: self.edit_input_lineedit("5")
        )
        self.m.tw2_tool_Button_num6.clicked.connect(
            lambda: self.edit_input_lineedit("6")
        )
        self.m.tw2_tool_Button_num7.clicked.connect(
            lambda: self.edit_input_lineedit("7")
        )
        self.m.tw2_tool_Button_num8.clicked.connect(
            lambda: self.edit_input_lineedit("8")
        )
        self.m.tw2_tool_Button_num9.clicked.connect(
            lambda: self.edit_input_lineedit("9")
        )
        self.m.tw2_tool_Button_dot.clicked.connect(
            lambda: self.edit_input_lineedit(".")
        )

        self.m.tw2_tool_Button_backspace.clicked.connect(
            lambda: self.edit_input_lineedit(delete_one_char=True)
        )
        self.m.tw2_tool_Button_C.clicked.connect(
            lambda: self.edit_input_lineedit(delete_all=True)
        )
        self.m.tw2_tool_Button_enter.clicked.connect(
            lambda: self.shift_input_lineedit("test_weight_2")
        )

        self.m.tableView.clicked.connect(self.on_cell_clicked)

        ...
        # FFT plot

        self.m.home_fft_button.clicked.connect(self.fft_init)
        self.m.fft_sample_button.clicked.connect(self.fft_sample)
        self.m.fft_process_button.clicked.connect(self.fft_process)

        self.m.fft_checkBox_1.stateChanged.connect(self.fft_update_plot)
        self.m.fft_checkBox_2.stateChanged.connect(self.fft_update_plot)
        self.m.fft_checkBox_3.stateChanged.connect(self.fft_update_plot)
        self.m.fft_checkBox_4.stateChanged.connect(self.fft_update_plot)

        self.m.res_cor_weight_s.clicked.connect(self.res_set_cor_weight_btn)
        self.m.res_cor_weight_d.clicked.connect(self.res_set_cor_weight_btn)
        self.m.res_cor_weight_ds.clicked.connect(self.res_set_cor_weight_btn)

        # rotors
        def rotors_pagedown():
            max_v = self.m.tableView.verticalScrollBar().maximum()
            cur_v = self.m.tableView.verticalScrollBar().value()
            self.m.tableView.verticalScrollBar().setSliderPosition(min(max_v, cur_v + 5))
            # TODO: this
            ...

        def rotors_pageup():
            min_v = 0
            cur_v = self.m.tableView.verticalScrollBar().value()
            self.m.tableView.verticalScrollBar().setSliderPosition(max(min_v, cur_v - 5))
            # TODO: this
            ...

        self.m.rotors_pageup.clicked.connect(rotors_pageup)
        self.m.rotors_pagedown.clicked.connect(rotors_pagedown)

        self.m.rotors_edit.clicked.connect(self.rotors_clicked_edit)
        self.m.rotors_save.clicked.connect(self.rotors_clicked_save)
        self.m.rotors_delete.clicked.connect(self.rotors_clicked_delete)
        self.m.rotors_cancel.clicked.connect(self.rotors_clicked_cancel)
        # self.m.rotors_find.clicked.connect(self.rotors_clicked_find)
        self.m.rotors_findname.textChanged.connect(self.rotors_findname)

        self.m.home_settings_button.clicked.connect(
            lambda: self.m.content_stack.setCurrentIndex(INDEX_CONTENT_SETTINGS)
        )
        self.m.home_settings_button.clicked.connect(
            lambda: self.m.button_stack.setCurrentIndex(INDEX_BUTTON_SETTINGS)
        )
        self.m.home_settings_button.clicked.connect(
            self.update_configs_to_window
        )

        self.m.settings_system_button.clicked.connect(
            lambda: self.m.settings.setCurrentIndex(0)
        )
        self.m.settings_measure_button.clicked.connect(
            lambda: self.m.settings.setCurrentIndex(1)
        )
        self.m.settings_statistics_button.clicked.connect(
            lambda: self.m.settings.setCurrentIndex(2)
        )

        self.m.settings_save_button.clicked.connect(
            self.settings_save_clicked
        )
        # self.m.tableView.
        
        
        self.m.measure_add_statistic_button.clicked.connect(self.add_item_to_statistic_data)
        self.m.settings_statistics_button.clicked.connect(self.init_statistics_table)
        
        self.m.statistics_find_button.clicked.connect(self.statistic_find_button_clicked)
        self.m.statistics_export_button.clicked.connect(self.statistic_export_button_clicked)
        
        self.m.settings_developer_options.clicked.connect(self.settings_enable_developer_options_press)

    def set_pipeline(self):
        """
        The pipeline must be consistent.
        """
        self.pipe_line = self.ctx.pipeline
        self.logger.debug(f"set pipeline:{self.ctx.pipeline}")
        self.m.ir_meter.setCurrentIndex(self.ctx.pipeline)
        self.m.ir_polar.setCurrentIndex(self.ctx.pipeline)
        self.m.fp_meter.setCurrentIndex(self.ctx.pipeline)
        self.m.fp_polar.setCurrentIndex(self.ctx.pipeline)
        self.m.sp_meter.setCurrentIndex(self.ctx.pipeline)
        self.m.sp_polar.setCurrentIndex(self.ctx.pipeline)
        self.m.res_meter.setCurrentIndex(self.ctx.pipeline)
        self.m.res_polar.setCurrentIndex(self.ctx.pipeline)
        self.m.measure_meter.setCurrentIndex(self.ctx.pipeline)
        self.m.measure_polar.setCurrentIndex(self.ctx.pipeline)

    #################################################
    # FFT界面相关函数

    def fft_set_receive_on(self, state: bool):
        self.fft_receive_data_on = state

    def fft_init(self):
        """
        FFT init will start once entering the page
        all the old drawing will be cleared.
        """
        self.logger.debug("fft init")

        self.fft_receive_data_on = False
        self.fft_can_draw_raw_data = False
        self.fft_can_process = False

        self.fft_plot_data()

    def fft_plot_data(self):
        self.figure.clear()
        ax = self.figure.add_subplot(4, 1, 1)
        ax.set_title("Original Signal")
        ax = self.figure.add_subplot(4, 1, 2)
        ax.set_title("Filtered Signal")
        ax = self.figure.add_subplot(4, 1, 3)
        ax.set_title("Frequency Domain (before filter)")
        ax = self.figure.add_subplot(4, 1, 4)
        ax.set_title("Frequency Domain (after filter)")
        self.figure.canvas.draw()

        self.figure.tight_layout()

        self.logger.debug("self plot data")

    def fft_receive_data(self):
        """
        this function ignores the Tolorance factor
        """

        # TODO
        if self.fft_receive_data_on == False:
            return

        data_dict = self.read_queue.get()
        self.set_real_rpm(data_dict["rpm"])

        self.collect_cnt += 1
        self.fft_databuffer.save(data_dict)
        self.update_progress_bar()

        if self.collect_cnt >= config.MAX_COLLECT_CNT:
            # self.process_data_wave()
            self.data = self.fft_databuffer.read()

            self.fft_can_draw_raw_data = True
            self.fft_can_process = True
            self.fft_receive_data_on = False

            self.fft_plot_raw_data()
            self.collect_cnt = 0
            self.fft_databuffer.clear()

    def fft_plot_raw_data(self):
        data_length = len(self.data[0])
        data_x = np.linspace(0, config.duration, data_length, endpoint=True)
        axes = self.figure.get_axes()
        axes[0].clear()
        self.logger.debug("fft plot raw data")
        for i, d in enumerate(self.data):
            if getattr(self.m, f"fft_checkBox_{i+1}").isChecked():
                axes[0].plot(data_x, d, label=f"Channel{i+1}")
            msg = f"Channel{i+1}"+f" {len(d)} "+ str(getattr(self.m, f"fft_checkBox_{i+1}").isChecked())
            self.logger.debug(msg)
        axes[0].legend()
        self.figure.canvas.draw()

    def fft_sample(self):
        self.logger.debug("fft sample")
        self.fft_receive_data_on = True
        self.fft_can_process = True

    def fft_process(self):
        if self.fft_can_process == False:
            return

        axes = self.figure.get_axes()
        for i in range(1, 3 + 1):
            axes[i].clear()

        fs = config.rate  # 采样率
        t = np.arange(0, config.duration, 1 / fs)  # 1秒钟的时间序列
        lowcut = float(self.m.fft_FPass_low.text())
        highcut = float(self.m.fft_FPass_high.text())
        x_range = float(self.m.fft_xrange.text())
        nyquist = 0.5 * fs
        low = lowcut / nyquist
        high = highcut / nyquist

        b, a = signal.butter(N=2, Wn = [low, high], btype="band")


        window_function = np.hamming(len(t))
        window_function = window_function * 2 / np.sum(window_function)

        for index, signal_combined in enumerate(self.data):
            if getattr(self.m, f"fft_checkBox_{index+1}").isChecked() == False:
                continue
            # 应用滤波器
            filtered_signal = signal.filtfilt(b, a, signal_combined)
            # filtered_signal = signal_combined
            
            
            raw_fft_result = np.fft.fft(signal_combined) * 2 / len(filtered_signal)
            raw_freqs = np.fft.fftfreq(len(raw_fft_result), 1 / fs)

            raw_fft_result = raw_fft_result[raw_freqs >= 0]
            raw_freqs = raw_freqs[raw_freqs >= 0]
            
            
            # 计算FFT
            fft_result = np.fft.fft(filtered_signal * window_function)
            # fft_result = np.fft.fft(filtered_signal)
            freqs = np.fft.fftfreq(len(fft_result), 1 / fs)

            fft_result = fft_result[freqs >= 0]
            freqs = freqs[freqs >= 0]

            N = len(signal_combined)
            self.logger.debug(f"N:{N}")

            # 绘制滤波后的信号图
            # plt.subplot(4, 1, 2)
            ax = axes[1]
            ax.plot(t, filtered_signal, label=f"Channel{index+1}")
            ax.legend()

            ax = axes[2]
            ax.plot(
                raw_freqs, 2 * np.abs(raw_fft_result) / N, label=f"Channel{index+1}"
            )
            ax.legend()
            ax.set_xlim(0, x_range)

            ax = axes[3]

            ax.plot(freqs, 2 * np.abs(fft_result) / N, label=f"Channel{index+1}")
            ax.set_xlim(0, x_range)
            ax.legend()

        self.figure.canvas.draw()

    def fft_update_plot(self):
        if self.fft_can_draw_raw_data == True:
            self.fft_plot_raw_data()
        if self.fft_can_process == True:
            self.fft_process()

    #################################################
    # rotors界面相关函数

    def init_table(self):
        self.logger.debug("init table")

        # if hasattr(self, "model"):
        #     return

        # 7 items to show.
        self.show_items = [
            "Number",
            "Rotor Name",
            "Date of calibriation",
            "RPM",
            "Balance type",
            "Correction weight",
            "State",
        ]

        self.show_items_index = [0, 1, 39, 2, 14, 15, 40]

        if not hasattr(self, "model"):
            self.model = QStandardItemModel(
                len(self.show_items), len(self.show_items), self
            )
            self.m.tableView.setModel(self.model)
            self.m.tableView.setSelectionMode(QAbstractItemView.SingleSelection)

            # 点击单元格时选中整行
            self.m.tableView.setSelectionBehavior(QAbstractItemView.SelectRows)

            # self.m.tableView.setItemDelegate(NoEditDelegate())
            # 设置表头文字
            for i, text in enumerate(self.show_items):
                self.model.setHeaderData(i, Qt.Horizontal, text)

            # 设置表头字体
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)
            self.m.tableView.horizontalHeader().setFont(font)

            # 设置表头对齐方式
            self.m.tableView.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)

            # 设置表头背景颜色
            self.m.tableView.horizontalHeader().setStyleSheet(
                "background-color: lightgray;"
            )
            self.m.tableView.verticalHeader().setVisible(False)
            # self.m.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.m.tableView.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch
            )
            self.m.tableView.horizontalHeader().setStretchLastSection(True)
            self.m.tableView.horizontalHeader().setMinimumSectionSize(int(1000 / 7))
        # set the size of the header section
        # self.m.tableView.horizontalHeader().setSectionResizeMode( )
        # self.m.tableView.horizontalHeader().scrollTo(QModelIndex(0, 0))
        print("set_rotors_table_content")
        self.set_rotors_table_content()
        print("set_rotors_table_content finish")
        self.logger.info("init table finished")

    def set_rotors_table_content(self):
        self.rotors_clear_table()
        # show_indexs
        if len(self.rotors_findres) == 0 and len(self.m.rotors_findname.text()) == 0:
            show_index = range(len(self.all_data))
        else:
            show_index = self.rotors_findres
        
        for table_i, index in enumerate(show_index):
            ctx:Ctx = self.all_data[index]['core_data']
            show_items = [
                table_i+1, # line number
                ctx.calibration_name.file_name,
                ctx.date_of_calibration,
                ctx.calibration_name.rpm,
                ctx.balancing.balance_type,
                ctx.balancing.correction_weight,
                ctx.other,
            ]
            print(f"{table_i=},{index=},{show_items=},{ctx=}")
            for j in range(len(show_items)):
                item = QStandardItem(str(show_items[j]))
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | ~Qt.ItemIsEditable)
                self.model.setItem(table_i, j, item)

    def rotors_clear_table(self):
        while self.model.rowCount() > 0:
            self.model.removeRow(0)

    def on_cell_clicked(self, index):
        """
        In Rotors, when click one cell, this function will read the related data, put the data on the corresponding place and select the whole line.
        """
        r = index.row()
        # if self.
        r = int(self.model.data(self.model.index(r, 0))) -1
        self.rotor_cur_index = index
        self.rotors_cur_row = r
        # r = self.rotors_cur_row
        if r > len(self.all_data):
            return
        tmp_ctx:Ctx = self.all_data[r]['core_data']
        # rotor name
        self.rotors_cur_pipeline = tmp_ctx.pipeline  # 0,1,2

        self.m.rotors_rn.setText(tmp_ctx.calibration_name.file_name)

        # diameters
        self.m.rotors_d1.setText(str(tmp_ctx.geometric_dimensions.diameter1))
        if self.rotors_cur_pipeline >= 1:
            self.m.rotors_d2.setText(str(tmp_ctx.geometric_dimensions.diameter2))
        if self.rotors_cur_pipeline >= 2:
            self.m.rotors_d3.setText(str(tmp_ctx.geometric_dimensions.diameter3))

        # Balance Mode
        if tmp_ctx.balancing.balance_type in [
            "dynamic",
            "dynamic static",
        ]:
            self.m.rotors_bm.setText("Two plane")
        else:
            self.m.rotors_bm.setText("One plane")

        self.m.rotors_bt.setText(tmp_ctx.balancing.balance_type)

        # correction weight: added or removed
        if tmp_ctx.balancing.correction_weight == "added":
            self.m.rotors_added.setChecked(True)
            self.m.rotors_removed.setChecked(False)
        else:
            self.m.rotors_added.setChecked(False)
            self.m.rotors_removed.setChecked(True)

        # rpm
        self.m.rotors_crpm.setText(str(tmp_ctx.calibration_name.rpm))

        # rotor mass
        self.m.rotors_rm.setText(str(tmp_ctx.norm.rotor_mass))
        self.m.rotors_nrpm.setText(str(tmp_ctx.norm.nominal_rpm))

        self.m.rotors_gmm_button.setChecked(
            tmp_ctx.norm.gmm == "1"
        )
        self.m.rotors_g_button.setChecked(
            tmp_ctx.norm.G == "1"
        )

        if tmp_ctx.norm.gmm == "1":
            self.m.rotors_gmm_button.setChecked(True)
            self.m.rotors_g_button.setChecked(False)
            self.m.rotors_norm_tab.setCurrentIndex(0)
        else:
            self.m.rotors_gmm_button.setChecked(False)
            self.m.rotors_g_button.setChecked(True)
            self.m.rotors_norm_tab.setCurrentIndex(1)

        # set the G values

        # set all un-checked
        # then set the selected one True

        if tmp_ctx.norm.gmm == "1":
            for i in range(1, 9):
                getattr(self.m, f"rs_g{i}").setChecked(False)
        else:
            # index = g2index[tmp_ctx.norm.G_value]
            # try:
            #     getattr(self.m, f"rs_g{index}").setChecked(True)
            # except:
            #     pass

            # for i in range(1, 9):
            #     if i == index:
            #         continue
            #     getattr(self.m, f"rs_g{i}").setChecked(False)
            self.m.rotors_ru1.setText(str(tmp_ctx.norm.residual_unbalance_1))
            self.m.rotors_ru2.setText(str(tmp_ctx.norm.residual_unbalance_2))
            self.m.rotors_ru3.setText(str(tmp_ctx.norm.residual_unbalance_3))



    def rotors_init_state(self):
        self.init_table()
        self.rotors_state = 1
        self.rotors_in_edit(False)

    def rotors_set_buttons(self, enable: bool):
        """
        enable 为True,进入edit状态.
        enable 为False,不在edit状态
        """
        self.m.rotors_save.setEnabled(enable)
        self.m.rotors_cancel.setEnabled(enable)

        self.m.rotors_pageup.setEnabled(not enable)
        self.m.rotors_pagedown.setEnabled(not enable)
        self.m.rotors_edit.setEnabled(not enable)
        self.m.rotors_refresh.setEnabled(not enable)
        self.m.rotors_delete.setEnabled(not enable)

    def rotors_set_lineedit(self, enable: bool):
        """
        enable 为True,进入edit状态.
        enable 为False,不在edit状态
        """
        self.m.rotors_bm.setEnabled(False)
        self.m.rotors_bt.setEnabled(False)
        self.m.rotors_crpm.setEnabled(False)

        self.m.rotors_rn.setEnabled(enable)

        self.m.rotors_d1.setEnabled(enable)
        self.m.rotors_ru1.setEnabled(enable)
        if self.rotors_cur_pipeline >= 1:
            self.m.rotors_d2.setEnabled(enable)
            self.m.rotors_ru2.setEnabled(enable)
        else:
            self.m.rotors_d2.setEnabled(False)
            self.m.rotors_ru2.setEnabled(False)
            
        if self.rotors_cur_pipeline >= 2:
            self.m.rotors_d3.setEnabled(enable)
            self.m.rotors_ru3.setEnabled(enable)
        else:
            self.m.rotors_d3.setEnabled(False)
            self.m.rotors_ru3.setEnabled(False)

        self.m.rotors_added.setEnabled(enable)
        self.m.rotors_removed.setEnabled(enable)

        self.m.rotors_gmm_button.setEnabled(enable)
        self.m.rotors_g_button.setEnabled(enable)

        self.m.rs_g1.setEnabled(enable)
        self.m.rs_g2.setEnabled(enable)
        self.m.rs_g3.setEnabled(enable)
        self.m.rs_g4.setEnabled(enable)
        self.m.rs_g5.setEnabled(enable)
        self.m.rs_g6.setEnabled(enable)
        self.m.rs_g7.setEnabled(enable)
        self.m.rs_g8.setEnabled(enable)

        self.m.rotors_rm.setEnabled(enable)
        self.m.rotors_nrpm.setEnabled(enable)

    def rotors_in_edit(self, inedit: bool):
        self.m.tableView.setEnabled(not inedit)
        self.rotors_set_buttons(inedit)
        self.rotors_set_lineedit(inedit)

    def rotors_clicked_edit(self):
        if self.rotor_cur_index == None:
            return

        self.rotors_state = 2
        self.rotors_in_edit(inedit=True)

    def rotors_clicked_save(self):
        self.rotors_state = 1
        self.rotors_in_edit(inedit=False)

        # 将信息保存到all data
        self.rotors_save_info_to_all_data()

        # 将all data写回到csv文件
        # self.rotors_write_all_data_to_csv()
        self.write_all_data_to_pkl()

        self.set_rotors_table_content()

    def rotors_save_info_to_all_data(self):
        idx = self.rotor_cur_index.row()
        tmp_ctx:Ctx = copy(self.all_data[idx]['core_data'])
        tmp_ctx.calibration_name.file_name = self.m.rotors_rn.text()

        self.rotors_cur_pipeline = tmp_ctx.pipeline  # 0,1,2
        
        # TODO:名称冲突检测.
        tmp_ctx.geometric_dimensions.diameter1 =  float(self.m.rotors_d1.text())
        if self.rotors_cur_pipeline >= 1:
            tmp_ctx.geometric_dimensions.diameter2 =  float(self.m.rotors_d2.text())
        if self.rotors_cur_pipeline >= 2:
            tmp_ctx.geometric_dimensions.diameter3 =  float(self.m.rotors_d3.text())

        tmp_ctx.balancing.correction_weight = "added" if self.m.rotors_added.isChecked() else "removed"
        tmp_ctx.norm.gmm = "1" if self.m.rotors_gmm_button.isChecked() else "0"
        tmp_ctx.norm.G = "1" if self.m.rotors_g_button.isChecked() else "0"

        if tmp_ctx.norm.gmm == '1':
            for i in range(1, 8 + 1):
                if getattr(self.m, f"rs_g{i}").isChecked():
                    tmp_ctx.norm.G_value = index2g[i]
        elif tmp_ctx.norm.G == '1':
            for i in [1,2,3]:
                value = getattr(self.m, f'rotors_ru{i}').text()
                try:
                    v = float(value)
                    setattr(tmp_ctx.norm, f'residual_unbalance_{i}', v)
                    # tmp_ctx.norm.residual_unbalance_1
                except:
                    pass


        tmp_ctx.norm.rotor_mass = float(self.m.rotors_rm.text())
        tmp_ctx.norm.nominal_rpm = float(self.m.rotors_nrpm.text())
        

    def rotors_clicked_refresh(self):
        # refresh是什么意思呢?
        ...

    def rotors_clicked_cancel(self):
        self.rotors_state = 1
        self.rotors_in_edit(inedit=False)
        self.set_rotors_table_content()

    def rotors_clicked_delete(self):
        question_box = QMessageBox(self)
        question_box.setWindowFlags(
            question_box.windowFlags() | Qt.WindowStaysOnTopHint
        )
        # question_box.setStyleSheet('background-color: rgba(255,255,255,150);')
        choice = question_box.question(
            self,
            "Confirm",
            "Do you want to delete?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        # background-color: rgba(150, 150, 150,150);
        if choice == QMessageBox.Yes:
            # data = self.model.data(self.rotor_cur_index)
            row = self.rotor_cur_index.row()
            idx = int(self.model.index(row, 0).data()) -1
            self.all_data.pop(idx)

            # self.rotors_page_index = min(max_v, self.rotors_page_index)
            self.rotors_findname(self.m.rotors_findname.text())
            self.rotors_write_all_data_to_csv()
            # self.set_rotors_table_content()
        else:
            pass

    def rotors_clicked_measure(self):
        # 跳转页面
        self.m.content_stack.setCurrentIndex(INDEX_CONTENT_RES)
        self.m.button_stack.setCurrentIndex(INDEX_BUTTON_MEASURE)

        # 加载参数
        self.rotors_load_ctx()
        self.calculate_result()
        # 进入测量页
        # self.switch_to_fake_mea()
        self.m.res_meter.setCurrentIndex(self.ctx.pipeline)

    def rotors_load_ctx(self, provided_idx: int = -2):
        # if provided_idx == -1:
        #     return

        # if provided_idx != -2:
        #     self.rotors_cur_row = provided_idx
        #     # self.load_and_set_all_labels_plots()
        # else:
        #     row = self.rotor_cur_index.row()
        #     idx = int(self.model.index(row, 0).data()) -1
    
        row = self.rotor_cur_index.row()
        idx = int(self.model.index(row, 0).data()) -1
        try:
            self.ctx:Ctx = self.all_data[idx]['core_data']
        except:
            return

        # self.ctx.calibration_name.file_name     = data[1]
        # self.ctx.calibration_name.rpm           = data[2]
        # self.ctx.norm.gmm                       = data[3]
        # self.ctx.norm.residual_unbalance_1      = data[4]
        # self.ctx.norm.residual_unbalance_2      = data[5]
        # self.ctx.norm.residual_unbalance_3      = data[6]
        # self.ctx.norm.G                         = data[7]
        # self.ctx.norm.G_value                   = data[8]
        # self.ctx.norm.rotor_mass                = data[9]
        # self.ctx.norm.nominal_rpm               = data[10]
        # self.ctx.geometric_dimensions.diameter1 = data[11]
        # self.ctx.geometric_dimensions.diameter2 = data[12]
        # self.ctx.geometric_dimensions.diameter3 = data[13]
        # self.ctx.balancing.balance_type         = data[14]
        # self.ctx.balancing.correction_weight    = data[15]
        # self.ctx.test_weight_1.weight           = data[16]
        # self.ctx.test_weight_1.angle            = data[17]
        # self.ctx.test_weight_1.diameter         = data[18]
        # self.ctx.test_weight_2.weight           = data[19]
        # self.ctx.test_weight_2.angle            = data[20]
        # self.ctx.test_weight_2.diameter         = data[21]
        # self.ctx.response_1_0.length            = data[22]
        # self.ctx.response_1_0.angle             = data[23]
        # self.ctx.response_2_0.length            = data[24]
        # self.ctx.response_2_0.angle             = data[25]
        # self.ctx.response_1_1.length            = data[26]
        # self.ctx.response_1_1.angle             = data[27]
        # self.ctx.response_2_1.length            = data[28]
        # self.ctx.response_2_1.angle             = data[29]
        # self.ctx.response_1_2.length            = data[30]
        # self.ctx.response_1_2.angle             = data[31]
        # self.ctx.response_2_2.length            = data[32]
        # self.ctx.response_2_2.angle             = data[33]
        # self.ctx.response_1_3.length            = data[34]
        # self.ctx.response_1_3.angle             = data[35]
        # self.ctx.response_2_3.length            = data[36]
        # self.ctx.response_2_3.angle             = data[37]
        # self.ctx.pipeline                       = data[38]
        # self.ctx.date_of_calibration            = data[39]
        # self.ctx.other                          = data[40]
        # self.ctx.init_finished                  = data[41]

        # self.ctx.calibration_name.file_name = data[1]
        # self.ctx.calibration_name.rpm = float(data[2])
        # self.ctx.norm.gmm = data[3]
        # self.ctx.norm.residual_unbalance_1 = float(data[4])
        # self.ctx.norm.residual_unbalance_2 = float(data[5])
        # self.ctx.norm.residual_unbalance_3 = float(data[6])
        # self.ctx.norm.G = data[7]
        # self.ctx.norm.G_value = float(data[8])
        # self.ctx.norm.rotor_mass = float(data[9])
        # self.ctx.norm.nominal_rpm = float(data[10])
        # self.ctx.geometric_dimensions.diameter1 = float(data[11])
        # self.ctx.geometric_dimensions.diameter2 = float(data[12])
        # self.ctx.geometric_dimensions.diameter3 = float(data[13])
        # self.ctx.balancing.balance_type = data[14]
        # self.ctx.balancing.correction_weight = data[15]
        # self.ctx.test_weight_1.weight = float(data[16])
        # self.ctx.test_weight_1.angle = float(data[17])
        # self.ctx.test_weight_1.diameter = float(data[18])
        # self.ctx.test_weight_2.weight = float(data[19])
        # self.ctx.test_weight_2.angle = float(data[20])
        # self.ctx.test_weight_2.diameter = float(data[21])
        # self.ctx.response_1_0.length = float(data[22])
        # self.ctx.response_1_0.angle = float(data[23])
        # self.ctx.response_2_0.length = float(data[24])
        # self.ctx.response_2_0.angle = float(data[25])
        # self.ctx.response_1_1.length = float(data[26])
        # self.ctx.response_1_1.angle = float(data[27])
        # self.ctx.response_2_1.length = float(data[28])
        # self.ctx.response_2_1.angle = float(data[29])
        # self.ctx.response_1_2.length = float(data[30])
        # self.ctx.response_1_2.angle = float(data[31])
        # self.ctx.response_2_2.length = float(data[32])
        # self.ctx.response_2_2.angle = float(data[33])
        # self.ctx.response_1_3.length = float(data[34])
        # self.ctx.response_1_3.angle = float(data[35])
        # self.ctx.response_2_3.length = float(data[36])
        # self.ctx.response_2_3.angle = float(data[37])
        # self.ctx.pipeline = int(data[38])
        # self.ctx.date_of_calibration = data[39]
        # self.ctx.other = data[40]
        # self.ctx.init_finished = True if data[41] == "True" else False
        self.last_rpm = float(self.ctx.calibration_name.rpm) * config.restart_ratio
        # set all the lables

        # set all the cals

        self.res_set_cor_weight_btn(
            self.ctx.balancing.correction_weight == "added", init_set=True
        )
        # print("pipeline", self.ctx.pipeline, int(data[38]))
        self.set_pipeline()
        self.set_cal_labels()
        self.set_cal_names()
        self.set_new_rotor_by_ctx()

    def set_new_rotor_by_ctx(self):
        self.m.nr_filename.setText(self.ctx.calibration_name.file_name)
        self.m.nr_rpm.setText(str(self.ctx.calibration_name.rpm))
        if self.ctx.norm.gmm == "1":
            self.m.new_rotor_gmm_button.setChecked(True)
            self.m.nr_ru1.setText(str(self.ctx.norm.residual_unbalance_1))
            self.m.nr_ru2.setText(str(self.ctx.norm.residual_unbalance_2))
            self.m.nr_ru3.setText(str(self.ctx.norm.residual_unbalance_3))

        if self.ctx.norm.G == "1":
            g_index = self.ctx.norm.G_value
            for i in range(1, 11 + 1):
                getattr(self.m, f"nr_g{i}").setChecked(False)
            try:
                getattr(self.m, f"nr_g{g_index}").setChecked(True)
            except:
                pass
            self.m.nr_rm.setText(str(self.ctx.norm.rotor_mass))
            self.m.nr_nrpm.setText(str(self.ctx.norm.nominal_rpm))

        self.m.nr_d1.setText(str(self.ctx.geometric_dimensions.diameter1))
        self.m.nr_d2.setText(str(self.ctx.geometric_dimensions.diameter2))
        self.m.nr_d3.setText(str(self.ctx.geometric_dimensions.diameter3))

        self.m.new_rotor_s_button.setChecked(
            self.ctx.balancing.balance_type == "static"
        )
        self.m.new_rotor_d_button.setChecked(
            self.ctx.balancing.balance_type == "dynamic"
        )
        self.m.new_rotor_ds_button.setChecked(
            self.ctx.balancing.balance_type == "dynamic static"
        )

        self.m.new_rotor_added_button.setChecked(
            self.ctx.balancing.correction_weight == "added"
        )
        self.m.new_rotor_removed_button.setChecked(
            self.ctx.balancing.correction_weight == "added"
        )

        self.m.new_rotor_s_button.setChecked(self.ctx.pipeline == 0)
        self.m.new_rotor_d_button.setChecked(self.ctx.pipeline == 1)
        self.m.new_rotor_ds_button.setChecked(self.ctx.pipeline == 2)

    def rotors_findname(self, name:str):
        # search the all data with the name as prefix
        # self.old_name = name
        self.rotors_findres.clear()
        for i in range(len(self.all_data)):
            tar_name = self.all_data[i]['core_data'].calibration_name.file_name
            if tar_name.lower().find(name.lower()) != -1:
                self.rotors_findres.append(i)
        self.rotors_clear_table()
        self.set_rotors_table_content()

    #################################################
    # 窗口移动相关函数

    def install_all_event_filter(self):
        """
        This function will allow the focus available
        """
        # self.input_lineedit = self.main_window.tw1_lineEdit_weight
        self.main_window.tw1_lineEdit_weight.installEventFilter(self)
        self.main_window.tw1_lineEdit_angle.installEventFilter(self)
        self.main_window.tw1_lineEdit_diameter.installEventFilter(self)
        self.main_window.tw2_lineEdit_weight.installEventFilter(self)
        self.main_window.tw2_lineEdit_angle.installEventFilter(self)
        self.main_window.tw2_lineEdit_diameter.installEventFilter(self)
        ...

    def mouseMoveEvent(self, e):
        """
        allow moving by pressing the window
        """
        try:
            if self._tracking:
                self._endPos = e.pos() - self._startPos
                self.move(self.pos() + self._endPos)
        except:
            pass

    def mousePressEvent(self, e):
        """
        Check pressing by left button
        """
        if e.button() == Qt.LeftButton:
            self._startPos = QPoint(e.x(), e.y())
            self._tracking = True

    def mouseReleaseEvent(self, e):
        """
        Check releasing by left button
        """
        if e.button() == Qt.LeftButton:
            self._tracking = False
            self._startPos = None
            self._endPos = None

    def close_window(self):
        self.logger.debug("close window")

        self.read_thread.set_stop(True)
        # print(self.all_data)
        # with open('./data/all_data.pkl', 'wb') as f:
        #     bytes_data = pickle.dumps(self.all_data[0]['core_data'])
        #     f.write(bytes_data)
        
        # with open('./data/all_data.pkl', 'rb') as f:
        #     tmp_data = pickle.load(f)
        # print(tmp_data)
        
        self.record_all_data()
        with open('config.pkl', 'wb') as f:
            pickle.dump(config, f)
            
        self.write_statictic_data_to_pkl()

        self.close()

    def eventFilter(self, watched, event):
        """
        allow focus.
        """
        if event.type() == QEvent.MouseButtonPress:
            if watched == self.main_window.tw1_lineEdit_weight:
                self.input_lineedit = self.main_window.tw1_lineEdit_weight
                self.logger.debug("focus on self.main_window.tw1_lineEdit_weight")
            elif watched == self.main_window.tw1_lineEdit_angle:
                self.input_lineedit = self.main_window.tw1_lineEdit_angle
                self.logger.debug("focus on self.main_window.tw1_lineEdit_angle")
            elif watched == self.main_window.tw1_lineEdit_diameter:
                self.input_lineedit = self.main_window.tw1_lineEdit_diameter
                self.logger.debug("focus on self.main_window.tw1_lineEdit_diameter")

            if watched == self.main_window.tw2_lineEdit_weight:
                self.input_lineedit = self.main_window.tw2_lineEdit_weight
                self.logger.debug("focus on self.main_window.tw2_lineEdit_weight")
            elif watched == self.main_window.tw2_lineEdit_angle:
                self.input_lineedit = self.main_window.tw2_lineEdit_angle
                self.logger.debug("focus on self.main_window.tw2_lineEdit_angle")
            elif watched == self.main_window.tw2_lineEdit_diameter:
                self.input_lineedit = self.main_window.tw2_lineEdit_diameter
                self.logger.debug("focus on self.main_window.tw2_lineEdit_diameter")
        else:
            pass
        return False

    #################################################
    #

    def prev_page(self):
        c_idx = self.m.content_stack.currentIndex()
        self.m.content_stack.setCurrentIndex(c_idx - 1)
        if c_idx == 1:
            self.m.button_stack.setCurrentIndex(0)

    def next_page(self, not_process_data=False):
        """
        1:new_rotor
        2:ir
        3:tw1
        4:fp
        5:tw2
        6:sp
        7:m
        """

        c_idx = self.m.content_stack.currentIndex() 
        if self.block_next_page_on_tw and (
            c_idx == INDEX_CONTENT_TW1 or c_idx == INDEX_CONTENT_TW2
        ):
            return

        if c_idx == INDEX_CONTENT_NEWROTOR:
            
            ok, msg = self.new_rotor_collect_all_information()
            if not ok:
                question_box = QMessageBox(self)
                question_box.setWindowFlags(
                    question_box.windowFlags() | Qt.WindowStaysOnTopHint
                )
                # question_box.setStyleSheet('background-color: rgba(255,255,255,150);')
                choice = question_box.question(
                    self,
                    "Error",
                    f"Error:{msg}",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                return
            
            self.res_set_cor_weight_btn(
                self.ctx.balancing.correction_weight == "added", init_set=True
            )
            self.set_pipeline()
            self.set_cal_labels()
            self.set_cal_names()
            self.m.content_stack.setCurrentIndex(INDEX_CONTENT_IR)

        elif c_idx == INDEX_CONTENT_IR:
            # record the state
            self.m.content_stack.setCurrentIndex(INDEX_CONTENT_TW1)
            self.input_lineedit = self.main_window.tw1_lineEdit_weight

        elif c_idx == INDEX_CONTENT_TW1:
            # record the state
            # weight_satisfy = float(self.m.)
            w, a, d = self.wad_satisfy_test(c_idx)
            test_res = w and a and d
            if test_res:
                self.m.content_stack.setCurrentIndex(INDEX_CONTENT_FP)
            else:
                message_w = "Weight must be greater than 0."
                message_a = "Angle can not be negative value."
                message_d = "Diameter can not be vegative value。"
                message = ""
                if not w:
                    message += message_w
                if not a:
                    message += message_a
                if not d:
                    message += message_d

                message_box = QMessageBox(self)
                message_box.setStyleSheet("")
                message_box.setStyle(QStyleFactory.create("Fusion"))

                message_box.setWindowTitle("Message Box")
                message_box.setText(message)
                message_box.setIcon(QMessageBox.Information)
                message_box.setWindowFlags(
                    message_box.windowFlags() | Qt.WindowStaysOnTopHint
                )
                # 添加一个按钮
                message_box.addButton(QMessageBox.Ok)

                # 显示消息框
                message_box.exec_()
            
        elif c_idx == INDEX_CONTENT_FP:
            # record the state
            if self.pipe_line == 0:
                self.m.content_stack.setCurrentIndex(INDEX_CONTENT_RES)
                self.m.button_stack.setCurrentIndex(INDEX_BUTTON_MEASURE)

                # name checking
                self.name_check_procedure()
                if not not_process_data:
                    self.calculate_result()

            else:
                self.m.content_stack.setCurrentIndex(INDEX_CONTENT_TW2)
                self.input_lineedit = self.main_window.tw2_lineEdit_weight

        elif c_idx == INDEX_CONTENT_TW2:
            w, a, d = self.wad_satisfy_test(c_idx)
            test_res = w and a and d
            if test_res:
                self.m.content_stack.setCurrentIndex(INDEX_CONTENT_SP)
            else:
                message_w = "Weight must be greater than 0."
                message_a = "Angle can not be negative value."
                message_d = "Diameter can not be vegative value。"
                message = ""
                if not w:
                    message += message_w
                if not a:
                    message += message_a
                if not d:
                    message += message_d

                message_box = QMessageBox(self)
                message_box.setStyleSheet("")
                message_box.setStyle(QStyleFactory.create("Fusion"))

                message_box.setWindowTitle("Message Box")
                message_box.setText(message)
                message_box.setIcon(QMessageBox.Information)
                message_box.setWindowFlags(
                    message_box.windowFlags() | Qt.WindowStaysOnTopHint
                )
                # 添加一个按钮
                message_box.addButton(QMessageBox.Ok)

                # 显示消息框
                message_box.exec_()
        elif c_idx == INDEX_CONTENT_SP:
            self.m.content_stack.setCurrentIndex(INDEX_CONTENT_RES)
            self.m.button_stack.setCurrentIndex(INDEX_BUTTON_MEASURE)

            self.name_check_procedure()
            if not not_process_data:
                self.calculate_result()

        elif c_idx == INDEX_CONTENT_RES:
            if self.is_current_page_res1():
                self.switch_to_fake_mea()
            elif self.is_current_page_res2():
                self.switch_from_fake_mea_to_res()

        elif c_idx == INDEX_CONTENT_MEASURE:
            self.m.content_stack.setCurrentIndex(INDEX_CONTENT_RES)

    def name_check_procedure(self):
        self.logger.debug("name_check_procedure")
        self.name_checking = True
        name_ok = self.name_confilction_check()
        self.logger.debug(f"name_confilction_check name ok:{name_ok}")

        if name_ok:
            self.auto_save()
            self.name_checking = False
            return

        question_box = QMessageBox(self)
        question_box.setWindowFlags(
            question_box.windowFlags() | Qt.WindowStaysOnTopHint
        )
        # question_box.setStyleSheet('background-color: rgba(255,255,255,150);')
        choice = question_box.question(
            self,
            "Confirm",
            "Calibration exist. Do you want to overwrite?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        # background-color: rgba(150, 150, 150,150);
        if choice == QMessageBox.Yes:
            # 覆盖

            self.auto_save(True)
            self.name_checking = False
        else:
            while True:
                name_ok = self.name_confilction_check()
                if name_ok:
                    self.name_checking = False
                    self.auto_save()
                    break

                message_box = QInputDialog(self)
                # message_box.setStyleSheet('background-color: rgba(255,255,255,150);')
                cur_name = self.m.nr_filename.text().strip()
                message_box.setWindowFlags(
                    message_box.windowFlags() | Qt.WindowStaysOnTopHint
                )
                new_name, ok = message_box.getText(
                    self,
                    "Name Conflict.",
                    f"Name {cur_name} is already used. Please input new name.",
                )
                if ok:
                    self.m.nr_filename.setText(new_name)
                    self.ctx.calibration_name.file_name = new_name
                    self.set_cal_names()

    def switch_new_name(self, name: str):
        self.ctx.calibration_name.file_name = name
        self.auto_save()

    def name_confilction_check(self):
        self.init_table()

        all_names = [record['core_data'].calibration_name.file_name for record in self.all_data]
        cur_name = self.m.nr_filename.text().strip()
        print(all_names)
        print(cur_name)
        self.logger.debug(f"name conf chk:{not (cur_name in all_names)}")
        if not (cur_name in all_names):
            return True

        return False

    def wad_satisfy_test(self, page_num):
        idx = 1 if page_num == INDEX_CONTENT_TW1 else 2
        weight = getattr(self.m, f"tw{idx}_lineEdit_weight").text()
        angle = getattr(self.m, f"tw{idx}_lineEdit_angle").text()
        diameter = getattr(self.m, f"tw{idx}_lineEdit_diameter").text()

        try:
            w = float(weight) >= 0
            a = float(angle) >= 0
            d = float(diameter) >= 0
        except ValueError as e:
            return False, False, False

        return w, a, d

    def get_pipeline_name(self) -> str:
        if self.pipe_line == PIPELINE_STATIC:
            return "s"
        elif self.pipe_line == PIPELINE_DYNAMIC:
            return "d"
        elif self.pipe_line == PIPELINE_DYNAMIC_STATIC:
            return "ds"
        else:
            raise

    def res_set_cor_weight_btn(self, state: bool, init_set: bool = False):
        # False -> added
        # True -> removed
        
        # False -> removed
        # True -> added
        self.logger.debug(f"res set cor weight {state} {init_set}")
        text = "added" if state else "removed"

        self.m.res_cor_weight_s.setChecked(state)
        self.m.res_cor_weight_d.setChecked(state)
        self.m.res_cor_weight_ds.setChecked(state)

        self.m.res_cor_weight_s.setText(text)
        self.m.res_cor_weight_d.setText(text)
        self.m.res_cor_weight_ds.setText(text)
#         if state:
#             style_sheet = """
# font: 300 10pt "微软雅黑";
# 	color: black;
# 	border: 2px solid #778899;
# 	border-radius: 3px;

# 	padding-left: 0px;
#     padding-top:15px;

# background-image: url(:/button/resources/added.png);
#             """
#         else:
#             style_sheet = """

# font: 300 10pt "微软雅黑";
# 	color: black;
# 	border: 2px solid #778899;
# 	border-radius: 3px;

# 	padding-left: 0px;
#     padding-top:15px;

# background-image: url(:/button/resources/sub.png);
#             """
#         self.m.res_cor_weight_s.setStyleSheet(style_sheet)
#         self.m.res_cor_weight_d.setStyleSheet(style_sheet)
#         self.m.res_cor_weight_ds.setStyleSheet(style_sheet)

        if self.m.content_stack.currentIndex() == INDEX_CONTENT_RES and not init_set:
            self.logger.debug("res_set_cor_weight_btn call calculate_result")
            self.calculate_result(use_last_result=True)

    def get_reverse(self):
        # TODO: not or not to not
        res = self.m.res_cor_weight_d.isChecked()
        self.logger.debug(f"get_reverse {res}")
        return res

    #################################################
    # 数据流相关函数.

    def receive_data(self):
        # 在每次read-thread读到数据时，会调用这个函数。
        # FFT receive和该函数只运行一个
        if self.fft_receive_data_on == True:
            return

        # 从队列里读取数据
        data_dict = self.read_queue.get()
        rpm = data_dict["rpm"]
        self.set_real_rpm(rpm)

        # 将rpm记入历史队列.便于后续直接判断.
        self.history_rpm_data_queue.append(rpm)
        if len(self.history_rpm_data_queue) > config.tolorance_cnt_max:
            self.history_rpm_data_queue.pop(0)

        if self.is_current_page_res1():
            # 结果页
            if self.name_checking:
                self.logger.debug("res1 namechecking")
                return
            else:
                # measure界面自动重开
                # 逻辑为，当出现越过阈值且当前转速稳定后，页面跳转开始测量

                limit = float(self.ctx.calibration_name.rpm) * config.restart_ratio
                cond1 = rpm > limit > self.last_rpm
                self.last_rpm = rpm
                self.res_restart1 = self.res_restart1 or cond1
                
                target_rpm = float(self.ctx.calibration_name.rpm)
                lb = target_rpm - config.tolorance
                ub = target_rpm + config.tolorance

                in_tolorance_cnt = sum(
                    [lb <= r <= ub for r in self.history_rpm_data_queue]
                )

                if in_tolorance_cnt >= config.tolorance_cnt_max:
                    self.res_restart2 = True
                else:
                    self.res_restart2 = False
                    
                self.logger.debug(f"{self.res_restart1=},{cond1=},{self.res_restart2=}")
                
                if self.res_restart1 and self.res_restart2:
                    self.is_collecting = True
                    self.databuffer.save(data_dict)
                    self.switch_to_fake_mea(keep_is_collecting = True)
                return

        elif self.is_current_page_ir_fp_sp_res2():
            # 测量页
            if self.is_collecting:

                collect_cnt = len(self.databuffer)

                self.databuffer.save(data_dict)

                collect_cnt += 1
                self.logger.debug(
                    f"collecting data {collect_cnt} {config.MAX_COLLECT_CNT} {config.MAX_PROGRESS_CNT}"
                )

                if collect_cnt == config.MAX_COLLECT_CNT:
                    self.process_data_wave(self.m.content_stack.currentIndex())

                self.update_progress_bar()

                if collect_cnt == config.MAX_PROGRESS_CNT:
                    self.next_page(not_process_data=True)

                    self.is_collecting = False
                    self.res_restart1 = False
                    self.res_restart2 = False
                    self.databuffer.clear()

            else:
                target_rpm = float(self.ctx.calibration_name.rpm)
                lb = target_rpm - config.tolorance
                ub = target_rpm + config.tolorance

                in_tolorance_cnt = sum(
                    [lb <= r <= ub for r in self.history_rpm_data_queue]
                )

                if in_tolorance_cnt >= config.tolorance_cnt_max:
                    self.is_collecting = True
                    self.databuffer.save(data_dict)
        else:
            # 其他页面
            return

    def is_current_page_res1(self):
        # res1 就是 结果页面
        # res2 就是 测试界面
        return (
            self.m.content_stack.currentIndex() == INDEX_CONTENT_RES
            and self.m.res_meter.currentIndex() != 3
        )

    def is_current_page_res2(self):
        return (
            self.m.content_stack.currentIndex() == INDEX_CONTENT_RES
            and self.m.res_meter.currentIndex() == 3
        )

    def is_current_page_ir_fp_sp_res2(self):
        ir = self.m.content_stack.currentIndex() == INDEX_CONTENT_IR
        fp = self.m.content_stack.currentIndex() == INDEX_CONTENT_FP
        sp = self.m.content_stack.currentIndex() == INDEX_CONTENT_SP
        res2 = self.is_current_page_res2()

        return ir or fp or sp or res2

    def update_progress_bar(self, zero: bool = False):
        content_id = self.m.content_stack.currentIndex()

        names = ["s", "d", "ds"]
        pages = {
            INDEX_CONTENT_IR: "ir",
            INDEX_CONTENT_FP: "fp",
            INDEX_CONTENT_SP: "sp",
            INDEX_CONTENT_MEASURE: "m",
            INDEX_CONTENT_RES: "res",
        }

        databuffer = self.databuffer
        max_cnt = config.MAX_PROGRESS_CNT
        
        # 得到progressbar的名字,并拿到progressbar
        if content_id == INDEX_CONTENT_FFT:
            bar_name = "fft_progressBar"
            databuffer = self.fft_databuffer
            max_cnt = config.MAX_COLLECT_CNT
        elif content_id == INDEX_CONTENT_RES:
            bar_name = "res_progressBar"
        else:
            bar_name = f"{pages[content_id]}_{names[self.ctx.pipeline]}_progressBar"
        
        bar = getattr(self.m, bar_name)

        # 计算progressbar的值.
        if zero:
            value = 0
        else:
            value = int(len(databuffer) / max_cnt * 100)

        self.logger.debug(f"{bar_name} update {value}")
        bar.setValue(value)

    def process_data_wave(self, page_num):
        """
        get data from databuffer
        calculate the theta and phi for the sensor channel
        """
        self.block_next_page_on_tw = True
        if self.is_next_page_res():
            self.processing_data_before_res = True
        self.logger.debug("process data wave")
        data = self.databuffer.read()
        one_plane = True if self.pipe_line == 0 else False

        self.t = Thread_wave()
        self.t.set(self.ctx, data, one_plane, page_num)
        self.t.finished_signal.connect(self.process_thread_result)
        self.t.start()

        return

    def process_thread_result(self, result):
        # 由负责计算的线程唤起，将结果同步到对应界面。
        res = result[0]
        page = result[1]
        self.logger.debug(f"process result:{res}")

        if page == INDEX_CONTENT_IR:
            prefix_label = "ir"
            suffix_param = 0
        elif page == INDEX_CONTENT_FP:
            prefix_label = "fp"
            suffix_param = 1
        elif page == INDEX_CONTENT_SP:
            prefix_label = "sp"
            suffix_param = 2
        elif page == INDEX_CONTENT_RES:
            prefix_label = "m"
            suffix_param = -1

        suffix_label = ["s", "d", "ds"][self.pipe_line]

        vectorized_res = [
            Vector(res[i][1], self.phase_to_angle(res[i][2])) for i in range(len(res))
        ]
        self.logger.debug(f"raw result:{res}")
        self.logger.debug(f"wave process result(amp,phase):{vectorized_res}")

        # 将结果记入Ctx
        # ir是resp_1/2_1
        # fp是resp_1/2_2
        # sp是resp_1/2_3
        # mea是resp_1/2_0

        for i in range(len(res)):
            setattr(
                self.ctx,
                f"response_{i+1}_{suffix_param+1}",
                Vector(res[i][1], self.phase_to_angle(res[i][2])),
            )

        # 将结果更新到表格
        for i in range(len(res)):
            # 幅值
            getattr(self.m, f"{prefix_label}_{suffix_label}_amp{i+1}").setText(
                self.html_text_generate(f"{res[i][1]:.{config.precision_amp}f}")
            )
            # 角度
            getattr(self.m, f"{prefix_label}_{suffix_label}_ang{i+1}").setText(
                self.html_text_generate(
                    str(f"{self.phase_to_angle(res[i][2]):.{config.precision_ang}f}[°]")
                )
            )

        if not self.is_current_page_res():
            self.new_rotor_update_polar_plot(vectorized_res, page)
        self.block_next_page_on_tw = False

        # 如果下一页是res界面或者当前是mea界面,那么计算vector结果.
        if self.is_next_page_res() or self.is_current_page_res():
            self.logger.debug("process_thread_result call calculate_result")

            self.calculate_result()

    def calculate_result(self, use_last_result: bool = False):
        # 会被 计算完成 和 点击added or removed 调用
        self.logger.debug("calculate result")

        if not use_last_result:
            self.vec_result, factors = vector_process(self.ctx)
            if len(factors) == 1:
                self.ctx.influence_factor_1_1 = factors[0]
            elif len(factors) == 4:
                self.ctx.influence_factor_1_1 = factors[0]
                self.ctx.influence_factor_2_1 = factors[1]
                self.ctx.influence_factor_1_2 = factors[2]
                self.ctx.influence_factor_2_2 = factors[3]
        self.vector_process_recall(use_last_result)

    def vector_process_recall(self, use_last_result:bool = False):
        if not hasattr(self, "vec_result"):
            return
        self.result = deepcopy(self.vec_result)
        self.logger.debug(f"vector process self.result:{self.result}")

        # 保证所有角度是正数
        for i in range(len(self.result)):
            if self.result[i].angle < 0:
                self.result[i].angle += 360
        if not use_last_result:
            # recover the weight btn state
            self.res_set_cor_weight_btn(
                self.ctx.balancing.correction_weight == "added", init_set=True
            )
        # 默认为False（去重），点击后为True（增重）。
        reverse = self.get_reverse()
        if reverse:
            for r in self.result:
                r.angle += 180 if r.angle < 180 else -180

        # weight：r.length = r.length * 试重的直径 / init的直径
        
        if self.pipe_line == 0:
            self.result[0].length = (
                self.result[0].length
                * self.ctx.test_weight_1.diameter
                / self.ctx.geometric_dimensions.diameter1
            )

        if self.pipe_line == 1:
            self.result[0].length = (
                self.result[0].length
                * self.ctx.test_weight_1.diameter
                / self.ctx.geometric_dimensions.diameter1
            )
            self.result[1].length = (
                self.result[1].length
                * self.ctx.test_weight_2.diameter
                / self.ctx.geometric_dimensions.diameter2
            )

        if self.pipe_line == 2:
            self.result[0].length = (
                self.result[0].length
                * self.ctx.test_weight_1.diameter
                / self.ctx.geometric_dimensions.diameter1
            )
            self.result[1].length = (
                self.result[1].length
                * self.ctx.test_weight_2.diameter
                / self.ctx.geometric_dimensions.diameter2
            )
            new_v1 = deepcopy(self.result[0])
            new_v2 = deepcopy(self.result[1])
            new_v1.length = new_v1.length * self.ctx.geometric_dimensions.diameter1 / self.ctx.geometric_dimensions.diameter3
            new_v2.length = new_v2.length * self.ctx.geometric_dimensions.diameter2 / self.ctx.geometric_dimensions.diameter3
            
            v3 = new_v1 + new_v2
            self.result.append(v3)
            if self.result[2].angle < 0:
                self.result[2].angle += 360
            elif self.result[2].angle > 360:
                self.result[2].angle -= 360


        # 根据结果大小计算量程与单位
        factor = self.range_select(max([r.length for r in self.result]), type_r="res")

        level = max(0, math.floor(math.log(factor, 10) / 3))
        
            
        # polar part
        # green circle
        color_range = self.ctx.get_color_range() # gmm
        
        diameters = [
            getattr(self.ctx.geometric_dimensions, f"diameter{i}")
            for i in range(1, 3 + 1)
        ]
        draw_color_range = [c / (d / 2) for c, d in zip(color_range, diameters)] # 除以校正半径，结果为g
        
        self.res_polar_plot(self.result, draw_color_range, factor)
        
        if config.res_unit == 'g':
            show_unit = 'g'
            show_weight_range = int(5 * factor)
            unit = 'g'
            show_result:list[Vector] = deepcopy(self.result)
        elif config.res_unit == 'mg':
            show_unit = 'mg'
            show_weight_range = int(5 * factor * 1000)
            unit = 'mg'
            show_result:list[Vector] = deepcopy(self.result)
            show_result = [v * 1000 for v in self.result]
            
        # label
        # 把结果打在label上
        self.res_label_set_content(show_result, unit)

        # 把label根据结果变色
        self.res_set_label_color_page(
            [a.length <= c for a, c, d in zip(show_result, draw_color_range, diameters)]
        )
        
        # range
        # 写量程
        getattr(self.m, f"res_range_{self.get_pipeline_name()}").setText(
            f"{show_weight_range}{show_unit}"
        )
        

    def range_select(
        self, res1: float = 0.0, res2: float = 0.0, type_r: str = "res"
    ) -> float:
        """
        5g     5g         5*10^0 g
        50g    50g        5*10^1 g
        500g   500g       5*10^2 g

        find the k that
        res = max(res1, res2)
        5*10^k <= res < 5*10^(k+1)
        return 10^(k+1)

        """
        try:
            max_input = max(res1, res2)
            if type_r == "res":
                max_input = max(max_input, 0.05) # 50mg for minimum
            k = math.ceil(math.log10(max_input / 5))
            self.logger.debug(f"range select res1:{res1},res2:{res2},k:{k},type-r:{type_r}")

            return 10**k
        except:
            return 1

    #################################################
    # 结果页绘制相关函数

    def res_polar_plot(
        self, result: list[Vector], color_range: list[float], factor: float
    ):
        pipe_line_name = self.get_pipeline_name()
        r: Vector
        for idx, (r, c) in enumerate(zip(result, color_range)):
            self.update_plot(
                pha=r.angle,
                amp=r.length / factor,
                name=f"res_polar_new_{pipe_line_name}_{idx+1}",
                color_range=c / factor,
            )

    def res_label_set_content(self, result: list[Vector], weight_unit: str):
        pipeline_name = self.get_pipeline_name()

        f_w = f".{config.precision_res_weight}f"
        f_a = f".{config.precision_res_angle}f"
        f_n = f".{config.precision_res_n}f"

        for idx, r in enumerate(result):
            w_label: QLabel = getattr(self.m, f"res_{pipeline_name}_w{idx+1}")
            a_label: QLabel = getattr(self.m, f"res_{pipeline_name}_a{idx+1}")
            n_label: QLabel = getattr(self.m, f"res_{pipeline_name}_n{idx+1}")
            diameter = getattr(self.ctx.geometric_dimensions, f"diameter{idx+1}")
            # weight：r.length = r.length * 试重的直径 / init的直径
            # gmm没问题。
            type2 = pipeline_name
            if type2 == "ds":
                type2 += "_s" if idx in [0, 1] else "_m"

            w_label.setText(
                self.html_text_generate(
                    f"{format(r.length, f_w)}[{weight_unit}]", type1="res", type2=type2
                )
            )
            if not config.res_angle_direction:
                angle = 360 - r.angle
            else:
                angle = r.angle
            a_label.setText(
                self.html_text_generate(
                    f"{format(angle, f_a)}[°]", type1="res", type2=type2
                )
            )
            n_label.setText(
                self.html_text_generate(
                    f"{format(r.length * diameter/2, f_n)}[gmm]",
                    type1="res",
                    type2=type2,
                )
            )

    def res_set_label_color_page(self, in_range_list: list[bool]):
        pipe_line_name = ["s", "d", "ds"][self.pipe_line]
        for idx, in_range in enumerate(in_range_list):
            self.res_set_label_color_group(pipe_line_name, idx + 1, in_range, is_bald_mid = (len(in_range_list) == 3 and idx == 1))

    def res_set_label_color_group(self, pipe_line: str, group: int, in_range: bool, is_bald_mid: bool):
        if not is_bald_mid:
            in_sheet = res_in_range_style_sheet
            out_sheet = res_out_range_style_sheet
            for t in ["a", "n", "w"]:
                label: QLabel = getattr(self.m, f"res_{pipe_line}_{t}{group}")
                sheet = in_sheet if in_range else out_sheet
                label.setStyleSheet(sheet)
        else:
            in_sheets = [
                res_in_range_style_sheet_bald_angle,
                res_in_range_style_sheet_bald_residual,
                res_in_range_style_sheet_bald_weight
                ]
            out_sheets = [
                res_out_range_style_sheet_bald_angle,
                res_out_range_style_sheet_bald_residual,
                res_out_range_style_sheet_bald_weight
                ]
            for idx, t in enumerate(["a", "n", "w"]):
                label: QLabel = getattr(self.m, f"res_{pipe_line}_{t}{group}")
                sheet = in_sheets[idx] if in_range else out_sheets[idx]
                label.setStyleSheet(sheet)

    #################################################
    # res1与res2转换相关函数

    def switch_to_fake_mea(self, keep_is_collecting=False):
        self.logger.debug("switch_to_fake_mea")
        # 把plot都清空
        pipeline_name = ["s", "d", "ds"][self.ctx.pipeline]
        for i in range(self.ctx.pipeline + 1):
            name = f"res_polar_new_{pipeline_name}_{i+1}"
            self.update_plot(0, 0, 0, name, empty=True)

        # 把采集相关数据初始化
        self.reset_collection(keep_is_collecting)

        # 把progressBar换出来
        self.m.res_meter.setCurrentIndex(3)

    def switch_from_fake_mea_to_res(self):
        self.logger.debug("switch_from_fake_mea_to_res")
        self.m.res_meter.setCurrentIndex(self.ctx.pipeline)

    def save_test_weight(self, content_id):
        if content_id - 1 == INDEX_CONTENT_TW1:
            idx = 1
        elif content_id - 1 == INDEX_CONTENT_TW2:
            idx = 2
        else:
            return

        tw: Test_weight = getattr(self.ctx, f"test_weight_{idx}")

        tw.weight = float(getattr(self.m, f"tw{idx}_lineEdit_weight").text())
        tw.angle = float(getattr(self.m, f"tw{idx}_lineEdit_angle").text())
        tw.diameter = float(getattr(self.m, f"tw{idx}_lineEdit_diameter").text())

    def write_all_data_to_pkl(self):
        list_to_write = []
        for item in self.all_data:
            tmp_ctx = item['core_data']
            data_ckpt = {
                'core_data':self.switch_ctx_to_dict(tmp_ctx),
                'other_data':item['other_data'],
            }
            list_to_write.append(data_ckpt)

        with open('./data/all_data.pkl', 'wb') as f:
            pickle.dump(list_to_write, f)
    
    def switch_ctx_to_dict(self, tmp_ctx):
        return {
            'ctx':tmp_ctx,
            'calibration_name' : tmp_ctx.calibration_name,
            'norm' : tmp_ctx.norm,
            'geometric_dimensions' : tmp_ctx.geometric_dimensions,
            'balancing' : tmp_ctx.balancing,
            'test_weight_1' : tmp_ctx.test_weight_1,
            'test_weight_2' : tmp_ctx.test_weight_2,
        }
        
    def switch_dict_to_ctx(self, dict_item):
        tmp_ctx = dict_item['core_data']['ctx']
            
        # data below can not be save directly by ctx......
        tmp_ctx.calibration_name = dict_item['core_data']['calibration_name']
        tmp_ctx.norm = dict_item['core_data']['norm']
        tmp_ctx.geometric_dimensions = dict_item['core_data']['geometric_dimensions']
        tmp_ctx.balancing = dict_item['core_data']['balancing']
        tmp_ctx.test_weight_1 = dict_item['core_data']['test_weight_1']
        tmp_ctx.test_weight_2 = dict_item['core_data']['test_weight_2']
        
        return tmp_ctx
    
    def load_all_data_from_pkl(self):
        self.all_data = []
        if os.path.exists('./data/all_data.pkl'):
            with open('./data/all_data.pkl', 'rb') as f:
                all_data = pickle.load(f)
        else:
            all_data = []
        for item in all_data:
            tmp_ctx = self.switch_dict_to_ctx(item)
            data_ckpt = {
                'core_data':tmp_ctx,
                'other_data':item['other_data'],
            }
            self.all_data.append(data_ckpt)
        
    def auto_save(self, overwrite: bool = False):
        self.logger.debug(f"auto save overwrite:{overwrite}")
        data_ckpt = {
                'core_data':self.ctx,
                'other_data':self.pack_other_data(),
            }
        if not overwrite:
            self.all_data.append(data_ckpt)
        else:
            for i in range(len(self.all_data)):
                tmp_ctx:Ctx = self.all_data[i]['core_data']
                if tmp_ctx.calibration_name.file_name == self.ctx.calibration_name.file_name:
                    target_i = i
                    break
            self.all_data[target_i] = data_ckpt
    
        
        self.write_all_data_to_pkl()
        
        return
        content_list = [
            # number
            self.ctx.calibration_name.file_name,
            int(self.ctx.calibration_name.rpm),
            self.ctx.norm.gmm,
            self.ctx.norm.residual_unbalance_1,
            self.ctx.norm.residual_unbalance_2,
            self.ctx.norm.residual_unbalance_3,
            self.ctx.norm.G,
            self.ctx.norm.G_value,
            self.ctx.norm.rotor_mass,
            self.ctx.norm.nominal_rpm,
            self.ctx.geometric_dimensions.diameter1,
            self.ctx.geometric_dimensions.diameter2,
            self.ctx.geometric_dimensions.diameter3,
            self.ctx.balancing.balance_type,
            self.ctx.balancing.correction_weight,
            self.ctx.test_weight_1.weight,
            self.ctx.test_weight_1.angle,
            self.ctx.test_weight_1.diameter,
            self.ctx.test_weight_2.weight,
            self.ctx.test_weight_2.angle,
            self.ctx.test_weight_2.diameter,
            self.ctx.response_1_0.length,
            self.ctx.response_1_0.angle,
            self.ctx.response_2_0.length,
            self.ctx.response_2_0.angle,
            self.ctx.response_1_1.length,
            self.ctx.response_1_1.angle,
            self.ctx.response_2_1.length,
            self.ctx.response_2_1.angle,
            self.ctx.response_1_2.length,
            self.ctx.response_1_2.angle,
            self.ctx.response_2_2.length,
            self.ctx.response_2_2.angle,
            self.ctx.response_1_3.length,
            self.ctx.response_1_3.angle,
            self.ctx.response_2_3.length,
            self.ctx.response_2_3.angle,
            self.ctx.pipeline,
            self.ctx.date_of_calibration,
            self.ctx.other,
            self.ctx.init_finished,
        ]

        with open(self.data_root, "r") as f:
            content = f.readlines()

        number = len(content) - 1
        content_list.insert(0, number)

        content_list = [str(obj) for obj in content_list]
        str_to_be_written = ",".join([str(obj) for obj in content_list]) + "\n"

        if not overwrite:
            with open(self.data_root, "a") as f:
                f.write(str_to_be_written)
        else:
            header = content[0]
            content = content[1:]
            for i in range(len(content)):
                if content[i].startswith(self.ctx.calibration_name.file_name + ","):
                    content.remove(i)
                    break
            content.append(str_to_be_written)
            with open(self.data_root, "w") as f:
                f.writelines([header] + content)

    def new_rotor_collect_all_information(self):
        if self.m.new_rotor_s_button.isChecked():
            self.ctx.balancing.balance_type = "static"
            self.ctx.pipeline = 0
        elif self.m.new_rotor_d_button.isChecked():
            self.ctx.balancing.balance_type = "dynamic"
            self.ctx.pipeline = 1
        elif self.m.new_rotor_ds_button.isChecked():
            self.ctx.balancing.balance_type = "dynamic static"
            self.ctx.pipeline = 2
            
        if self.ctx.pipeline == 0:
            if float(self.m.nr_d1.text()) == 0.0:
                return False, 'Diameter cannot be zero'
        else:
            if float(self.m.nr_d1.text()) == 0.0 or float(self.m.nr_d2.text()) == 0.0 or float(self.m.nr_d3.text()) == 0.0:
                return False, 'Diameter cannot be zero'
        
        self.ctx.calibration_name.file_name = self.m.nr_filename.text()
        self.ctx.calibration_name.rpm = float(self.m.nr_rpm.text())

        self.ctx.date_of_calibration = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(time.time())
        )

        self.ctx.norm.gmm = "1" if self.m.new_rotor_gmm_button.isChecked() else "0"
        self.ctx.norm.residual_unbalance_1 = float(self.m.nr_ru1.text())
        self.ctx.norm.residual_unbalance_2 = float(self.m.nr_ru2.text())
        self.ctx.norm.residual_unbalance_3 = float(self.m.nr_ru3.text())

        self.ctx.norm.G = "1" if self.m.new_rotor_g_button.isChecked() else "0"
        g_index = 0
        for i in range(1, 11 + 1):
            if getattr(self.m, f"nr_g{i}").isChecked():
                g_index = i
                break

        self.ctx.norm.G_value = float(index2g[g_index])
        self.ctx.norm.rotor_mass = float(self.m.nr_rm.text())
        self.ctx.norm.nominal_rpm = float(self.m.nr_nrpm.text())

        self.ctx.geometric_dimensions.diameter1 = float(self.m.nr_d1.text())
        self.ctx.geometric_dimensions.diameter2 = float(self.m.nr_d2.text())
        self.ctx.geometric_dimensions.diameter3 = float(self.m.nr_d3.text())
        


        if self.m.new_rotor_added_button.isChecked():
            self.ctx.balancing.correction_weight = "added"
        elif self.m.new_rotor_removed_button.isChecked():
            self.ctx.balancing.correction_weight = "removed"


        self.ctx.init_finished = False

        self.pipe_line = self.ctx.pipeline
        self.last_rpm = float(self.ctx.calibration_name.rpm) * config.restart_ratio
        
        return True, ''

    def set_cal_labels(self):
        page_names = ["ir", "fp", "sp", "m", "res"]
        modes = ["s", "d", "ds"]
        prefix = r'<html><head/><body><p align="center"><span style=" font-size:16pt; color:#00ac53;">'
        suffix = r"</span></p></body></html>"
        for p, m in product(page_names, modes):
            label_name = f"{p}_{m}_cal_label"
            getattr(self.m, label_name).setText(
                prefix + f"{self.ctx.calibration_name.rpm:.0f}" + suffix
            )

    def set_cal_names(self):
        page_names = ["res"]
        modes = ["s", "d", "ds"]

        for p, m in product(page_names, modes):
            label_name = f"{p}_{m}_calname_label"

            getattr(self.m, label_name).setText(
                str(self.ctx.calibration_name.file_name)
            )
        ...

    def shift_input_lineedit(self, page_name: str):
        if page_name == "test_weight_1":
            if self.input_lineedit == self.main_window.tw1_lineEdit_weight:
                self.input_lineedit = self.main_window.tw1_lineEdit_angle
            elif self.input_lineedit == self.main_window.tw1_lineEdit_angle:
                self.input_lineedit = self.main_window.tw1_lineEdit_diameter
        elif page_name == "test_weight_2":
            if self.input_lineedit == self.main_window.tw2_lineEdit_weight:
                self.input_lineedit = self.main_window.tw2_lineEdit_angle
            elif self.input_lineedit == self.main_window.tw2_lineEdit_angle:
                self.input_lineedit = self.main_window.tw2_lineEdit_diameter
        self.input_lineedit.setFocus()

    def edit_input_lineedit(self, char=None, delete_one_char=False, delete_all=False):
        if delete_all:
            self.input_lineedit.setText("")
            return
        if delete_one_char:
            cur_text = self.input_lineedit.text()
            self.input_lineedit.setText(cur_text[:-1] if cur_text != "" else "")
            return
        self.input_lineedit.setText(self.input_lineedit.text() + char)

    def reset_collection_on_condition(self, page_num):
        if self.is_current_page_ir_fp_sp_res2():
            self.reset_collection()

    def reset_collection(self,keep_is_collecting=False):
        if not keep_is_collecting:
            self.is_collecting = False
        self.name_checking = False
        self.databuffer.clear()
        self.update_progress_bar(zero=True)

        # self.collecting = False
        # self.measure_ready_collect = False
        # self.collect_cnt = 0
        # self.in_tolorance_cnt = 0
        # self.databuffer.clear()

    def is_next_page_res(self):
        page_num = self.m.content_stack.currentIndex()
        pipe_line = self.pipe_line

        if page_num == INDEX_CONTENT_FP and pipe_line == 0:
            return True

        if page_num == INDEX_CONTENT_SP:
            return True

        if page_num == INDEX_CONTENT_MEASURE:
            return True

        return False

    def is_current_page_res(self):
        # 判断当前页是否为res idx
        return self.m.content_stack.currentIndex() == INDEX_CONTENT_RES

    def set_real_rpm(self, rpm):
        page_names = ["ir", "fp", "sp", "m", "res"]
        modes = ["s", "d", "ds"]
        rpm_str = f"{rpm:.0f}"
        for p, m in product(page_names, modes):
            label_name = f"{p}_{m}_real_label"
            getattr(self.m, label_name).setText(rpm_str)
        self.m.fft_rpm.setText(rpm_str)
        self.m.new_rotor_auto_rpm_button.setText(rpm_str)

        self.m.tw1_auto_rpm_button.setText(rpm_str)
        self.m.tw2_auto_rpm_button.setText(rpm_str)

    def new_rotor_update_polar_plot(self, vectorized_res: list[Vector], page_number):
        # find the polar to be updated.
        # page
        # page_number = self.m.content_stack.currentIndex()

        page_name = {
            INDEX_CONTENT_IR: "ir",
            INDEX_CONTENT_FP: "fp",
            INDEX_CONTENT_SP: "sp",
            INDEX_CONTENT_RES: "res",
            INDEX_CONTENT_MEASURE: "mea",
        }[page_number]

        pipeline_name = {
            0: "s",
            1: "d",
            2: "ds",
        }[self.pipe_line]

        if len(vectorized_res) == 1:
            factor = self.range_select(vectorized_res[0].length, type_r="mid")
        else:
            factor = self.range_select(
                vectorized_res[0].length, vectorized_res[1].length, type_r="mid"
            )

        for i in range(len(vectorized_res)):
            vectorized_res[i].length /= factor

        if pipeline_name == "s":
            self.update_plot(
                amp=vectorized_res[0].length,
                pha=vectorized_res[0].angle,
                name=f"{page_name}_polar_new_s_1",
            )

        elif pipeline_name in ["d", "ds"]:
            for i in range(2):
                self.update_plot(
                    amp=vectorized_res[i].length,
                    pha=vectorized_res[i].angle,
                    name=f"{page_name}_polar_new_{pipeline_name}_{i+1}",
                )

        if page_name == "res" and pipeline_name == "ds":
            composed_vector: Vector = vectorized_res[0] + vectorized_res[1]

            # self.draw_qcustom_plot(
            #     phi=composed_vector.angle,
            #     A=composed_vector.length,
            #     polarPlot_temp=getattr(self.m, f"{page_name}_polar_d3"),
            # )
            self.update_plot(
                amp=composed_vector.length,
                pha=composed_vector.angle,
                name=f"{page_name}_polar_new_{pipeline_name}_{3}",
            )

    def phase_to_angle(self, phase):
        if phase < 0:
            phase += 2 * np.pi

        return phase / np.pi * 180

    def set_new_rotor_disable(self):
        """ """
        self.logger.debug("set new rotor disable")
        if self.m.new_rotor_one_plane_button.isChecked():
            # self.m.nr_d2.setEnabled(False)
            # self.m.nr_ru2.setEnabled(False)

            self.m.new_rotor_s_button.setEnabled(True)
            self.m.new_rotor_d_button.setEnabled(False)
            self.m.new_rotor_ds_button.setEnabled(False)

            self.m.new_rotor_s_button.setChecked(True)

        else:
            # self.m.nr_d2.setEnabled(True)
            # self.m.nr_ru2.setEnabled(True)

            self.m.new_rotor_s_button.setEnabled(False)
            self.m.new_rotor_d_button.setEnabled(True)
            self.m.new_rotor_ds_button.setEnabled(True)

            self.m.new_rotor_d_button.setChecked(True)

    def set_level_packed(self, enable: bool):

        if not enable:
            return

        self.level_enable()

    def level_enable(self):
        level = (
            int(self.m.new_rotor_s_button.isChecked())
            + 2 * int(self.m.new_rotor_d_button.isChecked())
            + 3 * int(self.m.new_rotor_ds_button.isChecked())
        )

        for i in range(1, 3 + 1):
            self.level_set(level=i, enable=(i <= level))

    def level_set(self, level: int, enable: bool):
        getattr(self.m, f"nr_ru{level}").setEnabled(enable)
        getattr(self.m, f"nr_d{level}").setEnabled(enable)

    def html_text_generate(self, s, type1: str = "mid", type2: str = "s"):
        # <html><head/><body><p align="center"><span style=" font-size:20pt; font-weight:600;">0</span></p></body></html>
        if type1 == "mid":
            return f'<html><head/><body><p align="center"><span style=" font-size:20pt; font-weight:600;">{s}</span></p></body></html>'
        elif type1 == "res":
            if type2 == "s" or type2 == "d":
                return f'<html><head/><body><p align="center"><span style=" font-size:18pt; font-weight:600;">{s}</span></p></body></html>'
            elif type2 == "ds_s":
                return f'<html><head/><body><p align="center"><span style=" font-size:15pt; font-weight:600;">{s}</span></p></body></html>'
            elif type2 == "ds_m":
                return f'<html><head/><body><p align="center"><span style=" font-size:16pt; font-weight:600;">{s}</span></p></body></html>'

    def init_all_polar_plot_new(self):
        self.logger.debug("init all polar plot new")
        names = ["ir", "fp", "sp", "mea", "res"]
        pips = ["s", "d", "ds"]
        idx = 0

        self.fills = []
        self.canvases = []
        self.points = []
        self.axes = []
        self.polar_xyfill = []
        self.name2plot_idx = {}
        
        for n, p in product(names, pips):

            if p == "s":
                n_plots = 1
            elif p == "d" or (p == "ds" and n != "res"):
                n_plots = 2
            elif p == "ds" and n == "res":
                n_plots = 3

            for i in range(1, n_plots + 1):
                name = f"{n}_polar_new_{p}_{i}"  # ir_polar_new_s_1
                fig = plt.figure()
                fig.patch.set_alpha(0.0)

                fig_config = (
                    config.plot_args_ds_res[i - 1]
                    if n_plots == 3
                    else config.plot_args_other
                )
                fig.subplots_adjust(*fig_config)

                canvas = FigureCanvas(fig)
                canvas.setStyleSheet(
                    "background-color:transparent;"
                )  # 设置 canvas 的样式为透明
                canvas.setAttribute(Qt.WA_TranslucentBackground)  # 确保 canvas 背景透明

                layout = getattr(self.m, f"{n}_polar_{p}_{i}")
                layout.addWidget(canvas)

                ax = canvas.figure.add_subplot(111, polar=True)

                # 设置背景色
                ax.set_facecolor("#a5bdff")

                # 设置y轴范围
                ax.set_ylim(0, 5)
                ax.set_yticks([1, 2, 3, 4, 5])
                ax.set_yticklabels(["", "", "", "", ""])

                ax.set_xticklabels([])
                ax.set_xticks([0, np.pi * 0.5, np.pi, np.pi * 1.5])

                # 设置坐标轴和网格线颜色
                ax.xaxis.label.set_color("black")
                ax.yaxis.label.set_color("black")
                ax.tick_params(axis="x", colors="black")  # 改变x轴刻度颜色
                ax.tick_params(axis="y", colors="black")  # 改变y轴刻度颜色
                ax.grid(color="black")

                self.color_range_x = np.linspace(0, 2 * np.pi, 36)
                y = np.array([0] * 36)
                fill_between = ax.fill(self.color_range_x, y, "#00ff00")
                (point,) = ax.plot(
                    [], [], "ro", markersize=config.point_size, markeredgecolor="black"
                )  # 初始化点，但不设置数据

                self.fills.append(fill_between)
                self.canvases.append(canvas)
                self.points.append(point)
                self.axes.append(ax)
                self.polar_xyfill.append((0,0,0))
                self.name2plot_idx[name] = idx
                idx += 1

                self.update_plot(0, 0, 0, name)
                ...

    def update_plot(
        self, amp=0, pha=0, color_range=0, name: str = "", empty: bool = False
    ):
        # return
        self.logger.debug(
            f"plotname:{name},amp:{amp},pha:{pha},color_range:{color_range},empty:{empty}"
        )
        idx = self.name2plot_idx[name]

        fill = self.fills[idx]
        canvas = self.canvases[idx]
        point = self.points[idx]
        ax = self.axes[idx]
        self.polar_xyfill[idx] = (amp, pha, color_range)
        
        pha += 90
        if pha > 360:
            pha -= 360

        # 更换fill区域
        y = np.array([color_range] * 36)
        fill[0].remove()
        self.fills[idx] = ax.fill(self.color_range_x, y, "#00ff00")

        if not empty:
            # 画点，设置点的颜色为红色，并加黑色边框
            point.set_data([pha / 180 * np.pi], [amp])
        else:
            point.set_data([], [])

        canvas.draw_idle()

    def pack_other_data(self):
        other_data = {}
        # FP、SP、TW1、TW2、Res页的数据：图、文本框
        # FP
        other_data['fp_s_amp1'] = self.m.fp_s_amp1.text()
        other_data['fp_s_ang1'] = self.m.fp_s_ang1.text()
        
        other_data['fp_d_amp1'] = self.m.fp_d_amp1.text()
        other_data['fp_d_ang1'] = self.m.fp_d_ang1.text()
        other_data['fp_d_amp2'] = self.m.fp_d_amp2.text()
        other_data['fp_d_ang2'] = self.m.fp_d_ang2.text()
        
        other_data['fp_ds_amp1'] = self.m.fp_ds_amp1.text()
        other_data['fp_ds_ang1'] = self.m.fp_ds_ang1.text()
        other_data['fp_ds_amp2'] = self.m.fp_ds_amp2.text()
        other_data['fp_ds_ang2'] = self.m.fp_ds_ang2.text()
        
        
        # SP
        other_data['sp_s_amp1'] = self.m.sp_s_amp1.text()
        other_data['sp_s_ang1'] = self.m.sp_s_ang1.text()
        
        other_data['sp_d_amp1'] = self.m.sp_d_amp1.text()
        other_data['sp_d_ang1'] = self.m.sp_d_ang1.text()
        other_data['sp_d_amp2'] = self.m.sp_d_amp2.text()
        other_data['sp_d_ang2'] = self.m.sp_d_ang2.text()
        
        other_data['sp_ds_amp1'] = self.m.sp_ds_amp1.text()
        other_data['sp_ds_ang1'] = self.m.sp_ds_ang1.text()
        other_data['sp_ds_amp2'] = self.m.sp_ds_amp2.text()
        other_data['sp_ds_ang2'] = self.m.sp_ds_ang2.text()
        
        # TW1
        other_data['tw1_lineEdit_weight'] = self.m.tw1_lineEdit_weight.text()
        other_data['tw1_lineEdit_angle'] = self.m.tw1_lineEdit_angle.text()
        other_data['tw1_lineEdit_diameter'] = self.m.tw1_lineEdit_diameter.text()
        
        # TW2
        other_data['tw2_lineEdit_weight'] = self.m.tw2_lineEdit_weight.text()
        other_data['tw2_lineEdit_angle'] = self.m.tw2_lineEdit_angle.text()
        other_data['tw2_lineEdit_diameter'] = self.m.tw2_lineEdit_diameter.text()
        
        # Res
        other_data['res_s_a1'] = self.m.res_s_a1.text()
        other_data['res_s_n1'] = self.m.res_s_n1.text()
        other_data['res_s_w1'] = self.m.res_s_w1.text()
        
        other_data['res_d_a1'] = self.m.res_d_a1.text()
        other_data['res_d_n1'] = self.m.res_d_n1.text()
        other_data['res_d_w1'] = self.m.res_d_w1.text()
        other_data['res_d_a2'] = self.m.res_d_a2.text()
        other_data['res_d_n2'] = self.m.res_d_n2.text()
        other_data['res_d_w2'] = self.m.res_d_w2.text()
        
        other_data['res_ds_a1'] = self.m.res_ds_a1.text()
        other_data['res_ds_n1'] = self.m.res_ds_n1.text()
        other_data['res_ds_w1'] = self.m.res_ds_w1.text()
        other_data['res_ds_a2'] = self.m.res_ds_a2.text()
        other_data['res_ds_n2'] = self.m.res_ds_n2.text()
        other_data['res_ds_w2'] = self.m.res_ds_w2.text()
        
        # New Rotor页的数据：文本框、按钮
        other_data['nr_filename'] = self.m.nr_filename.text()
        other_data['nr_rpm'] = self.m.nr_rpm.text()
        other_data['new_rotor_auto_rpm_button'] = self.m.new_rotor_auto_rpm_button.text()
        
        other_data['new_rotor_gmm_button'] = self.m.new_rotor_gmm_button.isChecked()
        other_data['new_rotor_g_button'] = self.m.new_rotor_g_button.isChecked()
        
        other_data['nr_ru1'] = self.m.nr_ru1.text()
        other_data['nr_ru2'] = self.m.nr_ru2.text()
        other_data['nr_ru3'] = self.m.nr_ru3.text()
        
        other_data['nr_g1'] = self.m.nr_g1.isChecked()
        other_data['nr_g2'] = self.m.nr_g2.isChecked()
        other_data['nr_g3'] = self.m.nr_g3.isChecked()
        other_data['nr_g4'] = self.m.nr_g4.isChecked()
        other_data['nr_g5'] = self.m.nr_g5.isChecked()
        other_data['nr_g6'] = self.m.nr_g6.isChecked()
        other_data['nr_g7'] = self.m.nr_g7.isChecked()
        other_data['nr_g8'] = self.m.nr_g8.isChecked()
        other_data['nr_g9'] = self.m.nr_g9.isChecked()
        other_data['nr_g10'] = self.m.nr_g10.isChecked()
        other_data['nr_g11'] = self.m.nr_g11.isChecked()
        
        other_data['nr_rm'] = self.m.nr_rm.text()
        other_data['nr_nrpm'] = self.m.nr_nrpm.text()
        
        other_data['nr_d1'] = self.m.nr_d1.text()
        other_data['nr_d2'] = self.m.nr_d2.text()
        other_data['nr_d3'] = self.m.nr_d3.text()
        
        other_data['new_rotor_one_plane_button'] = self.m.new_rotor_one_plane_button.isChecked()
        other_data['new_rotor_two_plane_button'] = self.m.new_rotor_two_plane_button.isChecked()
        
        other_data['new_rotor_s_button'] = self.m.new_rotor_s_button.isChecked()
        other_data['new_rotor_d_button'] = self.m.new_rotor_d_button.isChecked()
        other_data['new_rotor_ds_button'] = self.m.new_rotor_ds_button.isChecked()
        
        other_data['new_rotor_added_button'] = self.m.new_rotor_added_button.isChecked()
        other_data['new_rotor_removed_button'] = self.m.new_rotor_removed_button.isChecked()
        
        # all polars
        other_data['polar'] = self.polar_xyfill
        
        # other
        other_data['pipeline'] = self.pipe_line
        
        return other_data
    
    def record_all_data(self):
        other_data = self.pack_other_data()
        data_ckpt = {
            'core_data':self.switch_ctx_to_dict(self.ctx),
            'other_data':other_data,
        }

        with open('./last_ctx.pkl', 'wb') as f:
            pickle.dump(data_ckpt, f)

    def restore_all_data(self):
        self.logger.info('restore_all_data')
        try:
            if os.path.exists('./last_ctx.pkl'):
                with open('./last_ctx.pkl', 'rb') as f:
                    data_ckpt = pickle.load(f)
                    self.ctx = self.switch_dict_to_ctx(data_ckpt)
                    other_data = data_ckpt['other_data']
            else:
                return
        except Exception as e:
            if os.path.exists('./last_ctx.pkl'):
                os.remove('./last_ctx.pkl')
            print(str(e))
            return
        
        self.logger.info('restore fp data')
        self.m.fp_s_amp1.setText(other_data['fp_s_amp1'])
        self.m.fp_s_ang1.setText(other_data['fp_s_ang1'])
        self.m.fp_d_amp1.setText(other_data['fp_d_amp1'])
        self.m.fp_d_ang1.setText(other_data['fp_d_ang1'])
        self.m.fp_d_amp2.setText(other_data['fp_d_amp2'])
        self.m.fp_d_ang2.setText(other_data['fp_d_ang2'])
        self.m.fp_ds_amp1.setText(other_data['fp_ds_amp1'])
        self.m.fp_ds_ang1.setText(other_data['fp_ds_ang1'])
        self.m.fp_ds_amp2.setText(other_data['fp_ds_amp2'])
        self.m.fp_ds_ang2.setText(other_data['fp_ds_ang2'])
        
        self.logger.info('restore sp data')
        self.m.sp_s_amp1.setText(other_data['sp_s_amp1'])
        self.m.sp_s_ang1.setText(other_data['sp_s_ang1'])
        self.m.sp_d_amp1.setText(other_data['sp_d_amp1'])
        self.m.sp_d_ang1.setText(other_data['sp_d_ang1'])
        self.m.sp_d_amp2.setText(other_data['sp_d_amp2'])
        self.m.sp_d_ang2.setText(other_data['sp_d_ang2'])
        self.m.sp_ds_amp1.setText(other_data['sp_ds_amp1'])
        self.m.sp_ds_ang1.setText(other_data['sp_ds_ang1'])
        self.m.sp_ds_amp2.setText(other_data['sp_ds_amp2'])
        self.m.sp_ds_ang2.setText(other_data['sp_ds_ang2'])
        
        # TW1
        self.logger.info('restore tw1 data')
        self.m.tw1_lineEdit_weight.setText(other_data['tw1_lineEdit_weight'])
        self.m.tw1_lineEdit_angle.setText(other_data['tw1_lineEdit_angle'])
        self.m.tw1_lineEdit_diameter.setText(other_data['tw1_lineEdit_diameter'])
        
        # TW2
        self.logger.info('restore tw2 data')
        self.m.tw2_lineEdit_weight.setText(other_data['tw2_lineEdit_weight'])
        self.m.tw2_lineEdit_angle.setText(other_data['tw2_lineEdit_angle'])
        self.m.tw2_lineEdit_diameter.setText(other_data['tw2_lineEdit_diameter'])
        
        # Res
        self.logger.info('restore res data')
        self.m.res_s_a1.setText(other_data['res_s_a1'])
        self.m.res_s_n1.setText(other_data['res_s_n1'])
        self.m.res_s_w1.setText(other_data['res_s_w1'])
        
        self.m.res_d_a1.setText(other_data['res_d_a1'])
        self.m.res_d_n1.setText(other_data['res_d_n1'])
        self.m.res_d_w1.setText(other_data['res_d_w1'])
        self.m.res_d_a2.setText(other_data['res_d_a2'])
        self.m.res_d_n2.setText(other_data['res_d_n2'])
        self.m.res_d_w2.setText(other_data['res_d_w2'])
        
        self.m.res_ds_a1.setText(other_data['res_ds_a1'])
        self.m.res_ds_n1.setText(other_data['res_ds_n1'])
        self.m.res_ds_w1.setText(other_data['res_ds_w1'])
        self.m.res_ds_a2.setText(other_data['res_ds_a2'])
        self.m.res_ds_n2.setText(other_data['res_ds_n2'])
        self.m.res_ds_w2.setText(other_data['res_ds_w2'])
        
        # New Rotor页的数据：文本框、按钮
        self.logger.info('restore new rotor data')
        self.m.nr_filename.setText(other_data['nr_filename'])
        self.m.nr_rpm.setText(other_data['nr_rpm'])
        self.m.new_rotor_auto_rpm_button.setText(other_data['new_rotor_auto_rpm_button'])
        
        self.m.new_rotor_gmm_button.setChecked(other_data['new_rotor_gmm_button'])
        self.m.new_rotor_g_button.setChecked(other_data['new_rotor_g_button'])
        
        self.m.nr_ru1.setText(other_data['nr_ru1'])
        self.m.nr_ru2.setText(other_data['nr_ru2'])
        self.m.nr_ru3.setText(other_data['nr_ru3'])
        
        
        self.m.nr_g1.setChecked(other_data['nr_g1'])
        self.m.nr_g2.setChecked(other_data['nr_g2'])
        self.m.nr_g3.setChecked(other_data['nr_g3'])
        self.m.nr_g4.setChecked(other_data['nr_g4'])
        self.m.nr_g5.setChecked(other_data['nr_g5'])
        self.m.nr_g6.setChecked(other_data['nr_g6'])
        self.m.nr_g7.setChecked(other_data['nr_g7'])
        self.m.nr_g8.setChecked(other_data['nr_g8'])
        self.m.nr_g9.setChecked(other_data['nr_g9'])
        self.m.nr_g10.setChecked(other_data['nr_g10'])
        self.m.nr_g11.setChecked(other_data['nr_g11'])
        
        self.m.nr_rm.setText(other_data['nr_rm'])
        self.m.nr_nrpm.setText(other_data['nr_nrpm'])
        
        self.m.nr_d1.setText(other_data['nr_d1'])
        self.m.nr_d2.setText(other_data['nr_d2'])
        self.m.nr_d3.setText(other_data['nr_d3'])
        
        self.m.new_rotor_one_plane_button.setChecked(other_data['new_rotor_one_plane_button'])
        self.m.new_rotor_two_plane_button.setChecked(other_data['new_rotor_two_plane_button'])
        
        self.m.new_rotor_s_button.setChecked(other_data['new_rotor_s_button'])
        self.m.new_rotor_d_button.setChecked(other_data['new_rotor_d_button'])
        self.m.new_rotor_ds_button.setChecked(other_data['new_rotor_ds_button'])
        
        self.m.new_rotor_added_button.setChecked(other_data['new_rotor_added_button'])
        self.m.new_rotor_removed_button.setChecked(other_data['new_rotor_removed_button'])
        
        self.set_new_rotor_disable()
        self.level_enable()
        # all polars
        self.logger.info('restore polar data')
        polar_xyfill = other_data['polar']
        
        self.logger.debug("init all polar plot new")
        names = ["ir", "fp", "sp", "mea", "res"]
        pips = ["s", "d", "ds"]
        idx = 0
        for n, p in product(names, pips):
            if p == "s":
                n_plots = 1
            elif p == "d" or (p == "ds" and n != "res"):
                n_plots = 2
            elif p == "ds" and n == "res":
                n_plots = 3

            for i in range(1, n_plots + 1):
                name = f"{n}_polar_new_{p}_{i}"  # ir_polar_new_s_1
                self.update_plot(*polar_xyfill[idx], name)
                idx += 1
        
        # other
        self.set_pipeline()
        
    #################################
    # settings related
    def settings_save_clicked(self):
        # 弹框
        question_box = QMessageBox(self)
        question_box.setWindowFlags(
            question_box.windowFlags() | Qt.WindowStaysOnTopHint
        )
        # question_box.setStyleSheet('background-color: rgba(255,255,255,150);')
        choice = question_box.question(
            self,
            "Confirm",
            "Do you want to save configs?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        # background-color: rgba(150, 150, 150,150);
        if choice == QMessageBox.Yes:
            self.update_configs_from_window()
    
    def switch_str_to_precision(self, s:str):
        return max(len(s) - 2, 0)
    
    def switch_precision_to_index(self, precision:int):
        return precision
        
    def update_configs_from_window(self):
        self.logger.debug('update_configs_from_window')
        config.duration = float(self.m.duration.text())
        config.tolorance = int(float(self.m.tolorance.text()))
        config.tolorance_cnt_max = int(float(self.m.tolorance_cnt_max.text()))
        config.rpm_threshold = float(self.m.rpm_threshold.text())
        
        config.unit_mass = self.m.unit_mass.currentText()
        config.unit_speed = self.m.unit_speed.currentText()
        config.unit_norm = self.m.unit_norm.currentText()
        config.unit_vibration = self.m.unit_vibration.currentText()
        
        config.precision_mass = self.switch_str_to_precision(self.m.precision_mass.currentText())
        config.precision_speed = self.switch_str_to_precision(self.m.precision_speed.currentText())
        config.precision_norm = self.switch_str_to_precision(self.m.precision_norm.currentText())
        config.precision_vibration = self.switch_str_to_precision(self.m.precision_vibration.currentText())
        
        config.other_vibration = self.m.other_vibration.currentText()
        
        config.rate = int(float(self.m.rate.text()))
        config.amplification_factor = float(self.m.amplification_factor.text())
        config.avg_add_window = self.m.window_function.currentText() == 'Yes'
        config.smooth_d = int(float(self.m.smooth_d.text()))
        config.rpm_cal_duration = float(self.m.rpm_cal_duration.text())
        config.progress_bar_extand_time = float(self.m.progress_bar_extand_time.text())
        config.export = self.m.export_data.currentText() == 'Yes'
        config.restart_ratio = float(self.m.restart_ratio.text())
        config.rotate_smooth = self.m.rotate_smooth.currentText() == 'True'
        
        config.show_rfr = self.m.show_rfr.isChecked()
        config.show_hsb = self.m.show_hsb.isChecked()
        config.show_dst = self.m.show_dst.isChecked()
        config.show_rfr = self.m.show_rfr.isChecked()
        
        config.order = int(float(self.m.order.text()))
        config.gap = float(self.m.gap.text())
        config.avg_period = int(float(self.m.avg_period.text()))
        config.avg_cut_lb = int(float(self.m.avg_cut_lb.text()))
        config.avg_cut_rb = int(float(self.m.avg_cut_rb.text()))
        config.avg_stride = int(float(self.m.avg_stride.text()))
        
        config.mid_filter = self.m.mid_filter.currentText() == 'True'
        
        config.mid_filter_d = int(float(self.m.mid_filter_d.text()))
        config.angle_mean_mid_filter_d = int(float(self.m.angle_mean_mid_filter_d.text()))
        
        config.MAX_COLLECT_CNT = int(config.duration * config.rate / config.chunk)
        config.MAX_PROGRESS_CNT = config.MAX_COLLECT_CNT + math.ceil(
            config.progress_bar_extand_time / 0.2
        )

    def update_configs_to_window(self):
        self.logger.debug('update_configs_to_window')
        self.m.duration.setText(str(config.duration))
        self.m.tolorance.setText(str(config.tolorance))
        self.m.tolorance_cnt_max.setText(str(config.tolorance_cnt_max))
        self.m.rpm_threshold.setText(str(config.rpm_threshold))
        
        self.m.unit_mass.setCurrentIndex({'g':0,'mg':1}[config.unit_mass])
        self.m.unit_speed.setCurrentIndex({'RPM':0}[config.unit_speed])
        self.m.unit_norm.setCurrentIndex({'gmm':0,'gcm':1}[config.unit_norm])
        self.m.unit_vibration.setCurrentIndex({'mm/s':0,'G':1,'mm/s2':2,'mm':3,'um':4}[config.unit_vibration])
        
        self.m.precision_mass.setCurrentIndex(self.switch_precision_to_index(config.precision_mass))
        self.m.precision_speed.setCurrentIndex(self.switch_precision_to_index(config.precision_speed))
        self.m.precision_norm.setCurrentIndex(self.switch_precision_to_index(config.precision_norm))
        self.m.precision_vibration.setCurrentIndex(self.switch_precision_to_index(config.precision_vibration))
        
        
        self.m.other_vibration.setCurrentIndex(
            {"RMS":0,"O-P":1,"P-P":2}[config.other_vibration]
        )
        
        self.m.rate.setText(str(config.rate))
        self.m.amplification_factor.setText(str(config.amplification_factor))
        self.m.smooth_d.setText(str(config.smooth_d))
        self.m.rpm_cal_duration.setText(str(config.rpm_cal_duration))
        self.m.progress_bar_extand_time.setText(str(config.progress_bar_extand_time))
        self.m.restart_ratio.setText(str(config.restart_ratio))

        self.m.window_function.setCurrentIndex({False:0,True:1}[config.avg_add_window])
        self.m.export_data.setCurrentIndex({False:0,True:1}[config.export])
        self.m.rotate_smooth.setCurrentIndex({False:0,True:1}[config.rotate_smooth])
        
        self.m.show_rfr.setChecked(config.show_rfr)
        self.m.show_hsb.setChecked(config.show_hsb)
        self.m.show_dst.setChecked(config.show_dst)
        self.m.show_rfr.setChecked(config.show_rfr)
        
        self.m.order.setText(str(config.order))
        self.m.gap.setText(str(config.gap))
        self.m.avg_period.setText(str(config.avg_period))
        self.m.avg_cut_lb.setText(str(config.avg_cut_lb))
        self.m.avg_cut_rb.setText(str(config.avg_cut_rb))
        self.m.avg_stride.setText(str(config.avg_stride))
        
        self.m.mid_filter.setCurrentIndex({False:0,True:1}[config.mid_filter])
        
        self.m.mid_filter_d.setText(str(config.mid_filter_d))
        self.m.angle_mean_mid_filter_d.setText(str(config.angle_mean_mid_filter_d))
        
        
    def init_statistics_table(self):
        self.statistic_use_find_data = False
        self.show_items_statistic = [
            "No.",
            "Time",
            "P1 Mass[g]",
            "P1 Angle[°]",
            "P2 Mass[g]",
            "P2 Angle[°]",
            "Cal Name",
        ]
        if self.model_stastic == None:
            self.model_stastic = QStandardItemModel(
                len(self.show_items_statistic), len(self.show_items_statistic), self
            )
            self.m.statistics_table.setModel(self.model_stastic)
            self.m.statistics_table.setSelectionMode(QAbstractItemView.SingleSelection)

            # 点击单元格时选中整行
            self.m.statistics_table.setSelectionBehavior(QAbstractItemView.SelectRows)

            # self.m.tableView.setItemDelegate(NoEditDelegate())
            # 设置表头文字
            for i, text in enumerate(self.show_items_statistic):
                self.model_stastic.setHeaderData(i, Qt.Horizontal, text)

            # 设置表头字体
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)
            self.m.statistics_table.horizontalHeader().setFont(font)

            # 设置表头对齐方式
            self.m.statistics_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)

            # 设置表头背景颜色
            self.m.statistics_table.horizontalHeader().setStyleSheet(
                "background-color: lightgray;"
            )
            self.m.statistics_table.verticalHeader().setVisible(False)
            # self.m.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.m.statistics_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch
            )
            self.m.statistics_table.horizontalHeader().setStretchLastSection(True)
            self.m.statistics_table.horizontalHeader().setMinimumSectionSize(int(1000 / 7))
        
        self.set_statistic_table_data()

    def load_statistic_data_from_pkl(self):
        self.statistic_data = []
        
        if os.path.exists('./data/statistic_data.pkl'):
            with open('./data/statistic_data.pkl','rb')as f:
                self.statistic_data = pickle.load(f)

    def write_statictic_data_to_pkl(self):
        with open('./data/statistic_data.pkl','wb')as f:
            pickle.dump(self.statistic_data, f)
            
    def set_statistic_table_data(self):
        self.statistic_clear_table()
        if self.statistic_use_find_data:
            show_list = self.statistic_data_show
        else:
            show_list = self.statistic_data
            
        for index, entry in enumerate(show_list):
            entry:list[str]
            show_entry = [f'{index+1}', *entry]
            for j, s in enumerate(show_entry):
                item = QStandardItem(s)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | ~Qt.ItemIsEditable)
                self.model_stastic.setItem(index, j, item)
        
        self.m.statistics_number_label.setText(f'{len(show_list)} in total.')

    def statistic_clear_table(self):
        while self.model_stastic.rowCount() > 0:
            self.model_stastic.removeRow(0)
            
    def add_item_to_statistic_data(self):
        self.logger.debug("add_item_to_statistic_data")
        entry:list[str] = [
            time.strftime('%Y-%m-%d', time.localtime()),
            str(self.result[0].length),
            str(self.result[0].angle),
            '' if len(self.result) == 1 else str(self.result[1].length),
            '' if len(self.result) == 1 else str(self.result[1].angle),
            self.ctx.calibration_name.file_name   
        ]
        self.logger.debug(f"{entry=}")
        
        self.statistic_data.append(entry)
        
    def statistic_find_button_clicked(self):
        start_time = int(self.m.statistics_start_time.time().toString('yyyyMMdd'))
        end_time = int(self.m.statistics_end_time.time().toString('yyyyMMdd'))
        
        self.statistic_data_show = []
        
        for item in self.statistic_data:
            item_time = int(item[0].replace('-',''))
            if start_time <= item_time <= end_time:
                self.statistic_data_show.append(item)
        self.statistic_use_find_data = True
        self.set_statistic_table_data()
        
    
    def statistic_export_button_clicked(self):
        os.makedirs('./data', exist_ok=True)
        time_stamp = time.strftime('%Y-%m-%d %H-%M-%S', time.localtime()),
        with open(f'./data/statistic_data {time_stamp}.csv','w')as f:
            if self.statistic_use_find_data:
                data_list = self.statistic_data_show
            else:
                data_list = self.statistic_data
                
            for item in data_list:
                item:list[str]
                f.write(','.join(item) + '\n')
    
    def report_pdf_generate(self):
        pass

    def settings_enable_developer_options_press(self):
        message_box = QInputDialog(self)
        
        # cur_name = self.m.nr_filename.text().strip()
        message_box.setWindowFlags(
            message_box.windowFlags() | Qt.WindowStaysOnTopHint
        )
        input_code, ok = message_box.getText(
            self,
            "Developer options.",
            f"Please input developer code.",
        )
        
        if ok:
            self.developer_options = input_code == self.password
            self.m.measure_tab.setTabVisible(1, self.developer_options)
            
            question_box = QMessageBox(self)
            question_box.setWindowFlags(
                question_box.windowFlags() | Qt.WindowStaysOnTopHint
            )
            # question_box.setStyleSheet('background-color: rgba(255,255,255,150);')
            if input_code == self.password:            
                choice = question_box.question(
                    self,
                    "Successful",
                    "Successfully enter developer mode.",
                    QMessageBox.Yes,
                    QMessageBox.Yes,
                )
            else:
                choice = question_box.question(
                    self,
                    "Error",
                    "Password error!",
                    QMessageBox.Yes,
                    QMessageBox.Yes,
                )

'''
TODO 
- rotors里面的GMM那些框没有连上 DONE
- 生成PDF连起来，调一下格式
- 生成PDF时候，弹出框，要order
- settings里面时间有问题 DONE
- FFT里面有问题，process会报错，好像是形状的问题
''' 
    