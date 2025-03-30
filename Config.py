import pyaudio
from dataclasses import dataclass, field
import math
import logging
import pickle  # dxb
import os


@dataclass
class Config:
    online_reader: bool = False

    chunk: int = int(48000 * 0.2)
    FORMAT: int = pyaudio.paFloat32
    read_channels: int = 4
    send_channels: int = 1
    rate: int = 48000
    duration: float = 4
    input_device_index = None

    high_amplitude: float = 1.0
    high_duration: float = 0.1
    tolorance: int = 15
    rpm_threshold: float = 0.5  # 转速阈值
    alpha: float = 0.9
    tolorance_cnt_max: int = 5  # 转速需要有多少次在范围内。

    precision_amp: int = 5  #
    precision_ang: int = 1  #

    precision_res_weight: int = 3  # 质量的小数点
    precision_res_angle: int = 1  # 角度的小数点
    precision_res_n: int = 3  # gmm的小数点

    order: int = 2

    cut_threshold_1: float = 300
    cut_time_1: float = 0.5  # second
    cut_period_1: int = 5  # period

    cut_threshold_2: float = 300
    cut_time_2: float = 0.5  # second
    cut_period_2: int = 5  # period

    gap: float = 0.1

    window_type: str = "hanning"
    filter: str = "butterworth"

    amplification_factor: float = 100.0  # the raw signal will multiply this factor except the rotation signal.
    avg_period: int = 8
    avg_cut_lb: int = 5  # 滤波后，前截断avg_cut_lb个周期
    avg_cut_rb: int = 5  # 滤波后，后截断avg_cut_rb个周期
    avg_stride: int = 8  # 每次处理范围的移动距离。假设avg_period是8，当avg_stride是1时，每次处理的周期是1~8,2~9,3~10等等，当avg_stride是2时，每次处理的周期是1~8,3~10,5~13.
    export: bool = False  # True：导出；False：不导出。

    avg_add_window: bool = False  # True:在截断后加hanning窗，False：在截断后不加hanning窗

    mid_filter: bool = True  # 是否使用中值滤波,幅值。
    mid_filter_d: int = 15  # 必须为奇数，且小于递推周期结果的总个数

    angle_mean: bool = False  # 是否使用角度平均

    activate_new_filter: bool = False  # 是否使用新的滤波器
    new_filter_Q: float = 10  # 新滤波器的Q值
    activate_conducted_filter: bool = False

    rotate_smooth: bool = False  # 转速平滑
    smooth_d: int = 5  # 平滑因子

    angle_mean_mid_filter: bool = True  # 角度的向量+中值求平均。如果“angle_mean”和“angle_mean_mid_filter”均为True，则使用后者。
    angle_mean_mid_filter_d: int = 5  # 角度的向量+中值平均过程中，中值窗口大小
    phase_mean_mid_shuffle: bool = False  # 在计算中值滤波前，是否打乱角度的顺序

    rpm_cal_duration: float = 1.0  # 计算RPM所用信号时间长度。可以不是0.2的整数倍

    example_img_root: str = r"./resources/Rotor.png"  # init界面图片的路径
    res_angle_direction: bool = True  # True:顺时针；False：逆时针
    restart_ratio: float = 0.5

    rpm_queue_lenght: int = 2
    # left,bottom,right,top,wspace,hspace
    plot_args_ds_res = [
        [0, 0.08, 1, 0.92, 0, 0],
        [0, 0.08, 1, 0.92, 0, 0],
        [0, 0.08, 1, 0.92, 0, 0],
    ]
    plot_args_other = [0, 0.1, 1, 0.95, 0, 0]
    point_size: int = 12  # 坐标图里，点的大小

    logging_level = (
        logging.DEBUG
    )  # 调试时，使用logging.DEBUG, 正常运行时，使用logging.INFO
    logging_file: str = "logs/log-file.txt"  # 只在debug模式调用.

    progress_bar_extand_time: float = 0.6  # 运行时,取不小于该值的0.2的整数倍

    res_unit: str = 'g'
    unit_mass: str = 'g'  # g or mg
    unit_speed: str = 'RPM'  # RPM or hz
    unit_norm: str = 'gmm'  # gmm or gcm
    unit_vibration: str = 'mm/s'

    precision_mass: int = 3  #
    precision_speed: int = 0
    precision_norm: int = 3
    precision_vibration: int = 3

    other_vibration: str = 'RMS'

    show_fft: bool = True
    show_hsb: bool = True
    show_dst: bool = True
    show_rfr: bool = True

    # def __init__(self):
    #     self.MAX_COLLECT_CNT: int = int(self.duration * self.rate / self.chunk)
    #     self.MAX_PROGRESS_CNT: int = self.MAX_COLLECT_CNT + math.ceil(
    #         self.progress_bar_extand_time / 0.2
    #     )
    def __post_init__(self):
        self.MAX_COLLECT_CNT: int = int(self.duration * self.rate / self.chunk)
        self.MAX_PROGRESS_CNT: int = self.MAX_COLLECT_CNT + math.ceil(self.progress_bar_extand_time / 0.2)


@dataclass
class Test_weight:
    weight: float = 0.0
    angle: float = 0.0
    diameter: float = 0.0

    def __init__(self):
        self.weight = 0.0
        self.angle = 0.0
        self.diameter = 0.0
        pass


@dataclass
class Vector:
    length: float = 0.0
    angle: float = 0.0

    def __add__(self, other):
        x1 = self.length * math.cos(math.radians(self.angle))
        y1 = self.length * math.sin(math.radians(self.angle))
        x2 = other.length * math.cos(math.radians(other.angle))
        y2 = other.length * math.sin(math.radians(other.angle))

        # 计算新向量的分量
        x_sum = x1 + x2
        y_sum = y1 + y2

        # 计算新向量的长度和角度
        length_sum = math.sqrt(x_sum ** 2 + y_sum ** 2)
        angle_sum = math.degrees(math.atan2(y_sum, x_sum))

        return Vector(length_sum, angle_sum)

    def __mul__(self, other):
        if isinstance(other, (float, int)):
            x = self.length * other
            y = self.angle
            return Vector(x, y)


@dataclass
class Calibration_name:
    file_name: str = ""
    rpm: float = 0.0

    def __init__(self):
        pass


# dxb
@dataclass
class Plane_type:
    one_plane: bool = True
    two_plane: bool = False


@dataclass
class Norm:
    gmm: str = ""
    residual_unbalance_1: float = 0.0
    residual_unbalance_2: float = 0.0
    residual_unbalance_3: float = 0.0

    G: str = ""
    G_value: float = 0.0
    rotor_mass: float = 0.0
    nominal_rpm: float = 0.0

    def __init__(self):
        pass


@dataclass
class Geometric_dimensions:
    diameter1: float = 0.0
    diameter2: float = 0.0
    diameter3: float = 0.0

    def __init__(self):
        pass


@dataclass
class Balancing:
    balance_type: str = ""
    correction_weight: str = ""

    def __init__(self):
        pass


# bug: calibration_name, norm, geometric_dimensions, balancing, test_weight_1 can not be saved correctly
@dataclass
class Ctx:
    # calibration_name: Calibration_name = Calibration_name()
    # norm: Norm = Norm()
    # geometric_dimensions: Geometric_dimensions = Geometric_dimensions()
    # balancing: Balancing = Balancing()
    #
    # test_weight_1: Test_weight = Test_weight()
    # test_weight_2: Test_weight = Test_weight()
    #
    # # response_i_j is the response of the i-th plane on the j-th test.
    # # 0th test refers to that this is the measure response.
    # response_1_0: Vector = Vector()
    # response_2_0: Vector = Vector()
    # response_1_1: Vector = Vector()
    # response_2_1: Vector = Vector()
    # response_1_2: Vector = Vector()
    # response_2_2: Vector = Vector()
    # response_1_3: Vector = Vector()
    # response_2_3: Vector = Vector()
    #
    # influence_factor_1_1: Vector = Vector()
    # influence_factor_1_2: Vector = Vector()
    # influence_factor_2_1: Vector = Vector()
    # influence_factor_2_2: Vector = Vector()

    calibration_name: Calibration_name = field(default_factory=Calibration_name)
    norm: Norm = field(default_factory=Norm)
    geometric_dimensions: Geometric_dimensions = field(default_factory=Geometric_dimensions)
    balancing: Balancing = field(default_factory=Balancing)
    test_weight_1: Test_weight = field(default_factory=Test_weight)
    test_weight_2: Test_weight = field(default_factory=Test_weight)

    # response_i_j represents the response of the i-th plane on the j-th test.
    # 0th test indicates the measurement response.
    response_1_0: Vector = field(default_factory=Vector)
    response_2_0: Vector = field(default_factory=Vector)
    response_1_1: Vector = field(default_factory=Vector)
    response_2_1: Vector = field(default_factory=Vector)
    response_1_2: Vector = field(default_factory=Vector)
    response_2_2: Vector = field(default_factory=Vector)
    response_1_3: Vector = field(default_factory=Vector)
    response_2_3: Vector = field(default_factory=Vector)

    influence_factor_1_1: Vector = field(default_factory=Vector)
    influence_factor_1_2: Vector = field(default_factory=Vector)
    influence_factor_2_1: Vector = field(default_factory=Vector)
    # dxb
    influence_factor_2_2: Vector = field(default_factory=Vector)
    plane_type: Plane_type = field(default_factory=Plane_type)

    # 每个图的结果
    result_1: str = field(default_factory=str)
    result_2: str = field(default_factory=str)
    result_3: str = field(default_factory=str)
    # 总结果
    result: str = field(default_factory=str)

    pipeline: int = field(default_factory=int)
    date_of_calibration: str = field(default_factory=str)
    init_finished: bool = field(default_factory=bool)
    other: str = field(default_factory=str)

    # is_in_range: list[bool] = field(default_factory=list)
    # factor_1_1 = 0 + 0j
    # factor_1_2 = 0 + 0j
    # factor_2_1 = 0 + 0j
    # factor_2_2 = 0 + 0j

    # pipeline: int = 0
    # date_of_calibration: str = ""
    # other: str = ""
    # init_finished: bool = False

    # def __init__(self):
    #     pass

    def get_color_range(self) -> list[float]:
        if self.norm.gmm == "1":
            if self.balancing.balance_type == "static":
                return [self.norm.residual_unbalance_1]
            elif self.balancing.balance_type == "dynamic":
                return [self.norm.residual_unbalance_1, self.norm.residual_unbalance_2]
            elif self.balancing.balance_type == "dynamic static":
                return [
                    self.norm.residual_unbalance_1,
                    self.norm.residual_unbalance_2,
                    self.norm.residual_unbalance_3,
                ]
            else:
                raise

        elif self.norm.G == "1":
            k = {"static": 1, "dynamic": 2, "dynamic static": 3}[
                self.balancing.balance_type
            ]

            return self.G_calculate(k)

    def G_calculate(self, k: int):
        pre_value = (
                self.norm.rotor_mass
                * self.norm.G_value
                * 60
                * 10 ** 3
                / (2 * math.pi * self.norm.nominal_rpm)
        )
        if k in [2, 3]:  # 若是双面动平衡，则每个面的允许不平衡质量m=mper/2，
            pre_value /= 2
        res = [pre_value for _ in range(k)]

        # res = []
        # if k == 1:
        #     res.append(pre_value / self.geometric_dimensions.diameter1)
        # if k == 2:
        #     res.append(pre_value / self.geometric_dimensions.diameter1)
        #     res.append(pre_value / self.geometric_dimensions.diameter2)

        # for i in range(1, k + 1):
        #     res.append(pre_value / getattr(self.geometric_dimensions, f"diameter{i}"))

        return res


# 这是对于每一个测试物品所需要保存的所有内容
config_all_items = [
    "Number",
    "file_name",
    "rpm",
    "gmm",
    "residual_unbalance_1",
    "residual_unbalance_2",
    "residual_unbalance_3",
    "G",
    "G_value",
    "rotor_mass",
    "nominal_rpm",
    "diameter1",
    "diameter2",
    "diameter3",
    "balance_type",
    "correction_weight",
    "test_weight_1_weight",
    "test_weight_1_angle",
    "test_weight_1_diameter",
    "test_weight_2_weight",
    "test_weight_2_angle",
    "test_weight_2_diameter",
    "response_1_0_length",
    "response_1_0_angle",
    "response_2_0_length",
    "response_2_0_angle",
    "response_1_1_length",
    "response_1_1_angle",
    "response_2_1_length",
    "response_2_1_angle",
    "response_1_2_length",
    "response_1_2_angle",
    "response_2_2_length",
    "response_2_2_angle",
    "response_1_3_length",
    "response_1_3_angle",
    "response_2_3_length",
    "response_2_3_angle",
    "pipeline",
    "date_of_calibration",
    "other",
    "init_finished",
]
config_all_items_idx = {
    "Number": 0,
    "file_name": 1,
    "rpm": 2,
    "gmm": 3,
    "residual_unbalance_1": 4,
    "residual_unbalance_2": 5,
    "residual_unbalance_3": 6,
    "G": 7,
    "G_value": 8,
    "rotor_mass": 9,
    "nominal_rpm": 10,
    "diameter1": 11,
    "diameter2": 12,
    "diameter3": 13,
    "balance_type": 14,
    "correction_weight": 15,
    "test_weight_1_weight": 16,
    "test_weight_1_angle": 17,
    "test_weight_1_diameter": 18,
    "test_weight_2_weight": 19,
    "test_weight_2_angle": 20,
    "test_weight_2_diameter": 21,
    "response_1_0_length": 22,
    "response_1_0_angle": 23,
    "response_2_0_length": 24,
    "response_2_0_angle": 25,
    "response_1_1_length": 26,
    "response_1_1_angle": 27,
    "response_2_1_length": 28,
    "response_2_1_angle": 29,
    "response_1_2_length": 30,
    "response_1_2_angle": 31,
    "response_2_2_length": 32,
    "response_2_2_angle": 33,
    "response_1_3_length": 34,
    "response_1_3_angle": 35,
    "response_2_3_length": 36,
    "response_2_3_angle": 37,
    "pipeline": 38,
    "date_of_calibration": 39,
    "other": 40,
    "init_finished": 41,
}

config = Config()
config.rpm_threshold = config.rpm_threshold * config.amplification_factor
ctx = Ctx()

# print(config)
# print(ctx)


# index2g = {
#     0: "0",
#     1: "0.4",
#     2: "1.0",
#     3: "2.5",
#     4: "6.3",
#     5: "10",
#     6: "40",
#     7: "100",
#     8: "250",
#     9: "630",
#     10: "1600",
#     11: "4000",
# }
# g2index = {
#     "0": 0,
#     "0.4": 1,
#     "1.0": 2,
#     "2.5": 3,
#     "6.3": 4,
#     "10.0": 5,
#     "40.0": 6,
#     "100.0": 7,
#     "250.0": 8,
#     "630.0": 9,
#     "1600.0": 10,
#     "4000.0": 11,
# }
index2g = {
    0: 0.0,
    1: 0.4,
    2: 1.0,
    3: 2.5,
    4: 6.3,
    5: 10.0,
    6: 40.0,
    7: 100.0,
    8: 250.0,
    9: 630.0,
    10: 1600.0,
    11: 4000.0,
}
g2index = {
    0.0: 0,
    0.4: 1,
    1.0: 2,
    2.5: 3,
    6.3: 4,
    10.0: 5,
    40.0: 6,
    100.0: 7,
    250.0: 8,
    630.0: 9,
    1600.0: 10,
    4000.0: 11,
}

res_in_range_style_sheet = """
background-color: rgb(161, 255, 149);
border: 2px groove black;"""

res_out_range_style_sheet = """
background-color: rgb(252, 213, 114);
border: 2px groove black;"""

res_in_range_style_sheet_bald_weight = """
background-color: rgb(161, 255, 149);
border: 2px groove black;
border-left: 3.5px groove black;
border-top: 3.5px groove black;"""

res_in_range_style_sheet_bald_angle = """
background-color: rgb(161, 255, 149);
border: 2px groove black;
border-right: 3.5px groove black;
border-top: 3.5px groove black;"""

res_in_range_style_sheet_bald_residual = """
background-color: rgb(161, 255, 149);
border: 2px groove black;
border-left: 3.5px groove black;
border-right: 3.5px groove black;
border-bottom: 3.5px groove black;"""

res_out_range_style_sheet_bald_weight = """
background-color: rgb(252, 213, 114);
border: 2px groove black;
border-left: 3.5px groove black;
border-top: 3.5px groove black;"""

res_out_range_style_sheet_bald_angle = """
background-color: rgb(252, 213, 114);
border: 2px groove black;
border-right: 3.5px groove black;
border-top: 3.5px groove black;"""

res_out_range_style_sheet_bald_residual = """
background-color: rgb(252, 213, 114);
border: 2px groove black;
border-left: 3.5px groove black;
border-right: 3.5px groove black;
border-bottom: 3.5px groove black;"""

'''
background-color: rgb(161, 255, 149);
border: 2px groove black;'''

INDEX_CONTENT_HOME = 0
INDEX_CONTENT_NEWROTOR = 1
INDEX_CONTENT_IR = 2
INDEX_CONTENT_TW1 = 3
INDEX_CONTENT_FP = 4
INDEX_CONTENT_TW2 = 5
INDEX_CONTENT_SP = 6
INDEX_CONTENT_RES = 7
INDEX_CONTENT_MEASURE = 8
INDEX_CONTENT_ROTORS = 9
INDEX_CONTENT_FFT = 10
INDEX_CONTENT_SETTINGS = 11

INDEX_BUTTON_HOME = 0
INDEX_BUTTON_NEWROTOR = 1
INDEX_BUTTON_ROTORS = 2
INDEX_BUTTON_MEASURE = 3
INDEX_BUTTON_FFT = 4
INDEX_BUTTON_SETTINGS = 5

PIPELINE_STATIC = 0
PIPELINE_DYNAMIC = 1
PIPELINE_DYNAMIC_STATIC = 2

# res_cor_weight_stylesheet_sub = '''

# font: 300 10pt "微软雅黑";
# 	color: black;
# 	border: 2px solid #778899;
# 	border-radius: 3px;

# 	padding-left: 0px;
#     padding-top:-2px;

# '''
# res_cor_weight_stylesheet_added = '''

# font: 300 10pt "微软雅黑";
# 	color: black;
# 	border: 2px solid #778899;
# 	border-radius: 3px;

# 	padding-left: 0px;
#     padding-top:-2px;

# '''


# 将对象保存为 pkl 文件
# with open('config_dxb.pkl', 'wb') as file:
#     pickle.dump(Config(), file)
#     print("配置类已保存为 pkl 文件")
#
# with open('config_dxb.pkl', 'rb') as file:
#     config = pickle.load(file)
#     print(config)
