"""
    There are two kinds of algorithms:
        1) the FFT and related wave analysis algorithms
        2) the influence factor and calibration algorithms
"""

import cmath
from typing import Tuple
from Config import Ctx, Vector
import time
from utils import time_cal


def angle2radian(angle):
    """
    The unit of angle should be degree
    """
    # 角度转弧度
    return angle / 180 * cmath.pi


def scalar2vector(amplitude: float, angle: float) -> complex:
    return amplitude * cmath.exp(1j * angle2radian(angle))



def complex2magnitude_phase(v: complex):
    # 将复数v的相位（角度）从弧度转换为角度
    phase = cmath.phase(v) / cmath.pi * 180
    if phase < 0:
        phase += 360

    return abs(v), phase


def calculate_influence_factor_one_plane(a10, s10, u11, s1, a11, s11):
    # 原始情况
    v10 = scalar2vector(a10, s10)
    # 加上试重后
    v11 = scalar2vector(a11, s11)
    # 试重
    u11 = scalar2vector(u11, s1)
    try:
        factor = (v11 - v10) / u11
    except Exception as e:
        # print(f"ERROR:{e}")
        # print(v10,v11,u11)
        pass

    return factor


def oneplane(a10, s10, u11, s1, a11, s11, a1x, s1x):
    """
    param:
        a10: amplitude of sensor 1 before adding test weight
        s10: phase of sensor 1 before adding test weight
        u11: test weight
        s1:  phase of test weight
        a11: amplitude of sensor 1 after adding test weight
        s11: phase of sensor 1 before adding test weight
        ax:  amplitude of sensor 1 on calibration object
        sx:  phase of sensor on calibration object
    return:
        um:  magnitude of unbalance,g
        ua:  phase of unbalance,degree
    """
    try:
        factor = calculate_influence_factor_one_plane(a10, s10, u11, s1, a11, s11)
        v0 = scalar2vector(a1x, s1x)

        u1 = v0 / factor
        # u1 = u1 / 
        km, ka = complex2magnitude_phase(factor)
        v_factor = Vector(km, ka)
        # print(factor)
        # print(f'magnitude:{km} phase:{ka}')

        # print(u1)
        # print(f'magnitude:{um} phase:{ua}')

        # print(complex2magnitude_phase(u1))
    except Exception as e:
        # print(str(e))
        return [Vector(0, 0)], [Vector(0, 0)]

    return [Vector(*complex2magnitude_phase(u1))], [v_factor]


def calculate_influence_factor_two_plane(
        a10, s10, a20, s20, a11, s11, a21, s21, tw1, s1, a12, s12, a22, s22, tw2, s2
):
    v10 = scalar2vector(a10, s10)
    v20 = scalar2vector(a20, s20)
    v11 = scalar2vector(a11, s11)
    v21 = scalar2vector(a21, s21)
    v12 = scalar2vector(a12, s12)
    v22 = scalar2vector(a22, s22)
    u11 = scalar2vector(tw1, s1)
    u21 = scalar2vector(tw2, s2)

    k11 = (v11 - v10) / u11
    k21 = (v21 - v20) / u11
    k12 = (v12 - v10) / u21
    k22 = (v22 - v20) / u21

    return k11, k21, k12, k22


def twoplane(
        a10,
        s10,
        a20,
        s20,
        u11,
        s1,
        a11,
        s11,
        a21,
        s21,
        u21,
        s2,
        a12,
        s12,
        a22,
        s22,
        a1x,
        s1x,
        a2x,
        s2x,
):
    try:
        k11, k21, k12, k22 = calculate_influence_factor_two_plane(
            a10, s10, a20, s20, a11, s11, a21, s21, u11, s1, a12, s12, a22, s22, u21, s2
        )

        v0 = scalar2vector(a1x, s1x)
        v1 = scalar2vector(a2x, s2x)

        delta = k11 * k22 - k12 * k21

        u1 = k22 / delta * v0 - k12 / delta * v1
        u2 = k11 / delta * v1 - k21 / delta * v0

        v_factor = [Vector(*complex2magnitude_phase(f)) for f in [k11, k21, k12, k22]]
        # print(complex2magnitude_phase(u1))
        # print(complex2magnitude_phase(u2))
    except Exception as e:
        return [Vector(0, 0) for _ in range(2)], [Vector(0, 0) for _ in range(4)]
    return [Vector(*complex2magnitude_phase(u1)), Vector(*complex2magnitude_phase(u2))], v_factor


def oneplane_test():
    a10 = 2
    s10 = 83
    a11 = 8.6
    s11 = 1.1
    u11 = 83
    s1 = 0
    a1x = 6.4 + 2
    s1x = 78.7 + 110
    result = oneplane(a10, s10, u11, s1, a11, s11, a1x, s1x)
    print(result)


def twoplane_test():
    a10 = 2
    s10 = 83
    a20 = 1.7
    s20 = 240
    a11 = 8.6
    s11 = 1.1
    a21 = 2.2
    s21 = 305
    u11 = 83
    s1 = 0
    a12 = 2.2
    s12 = 77.9
    a22 = 6.6
    s22 = 182.9
    u21 = 83
    s2 = 0
    a1x = 6.4 + 2
    s1x = 78.7 + 10
    a2x = 0.79
    s2x = 214.4
    result = twoplane(
        a10,
        s10,
        a20,
        s20,
        u11,
        s1,
        a11,
        s11,
        a21,
        s21,
        u21,
        s2,
        a12,
        s12,
        a22,
        s22,
        a1x,
        s1x,
        a2x,
        s2x,
    )
    print(result)


def speed_test():
    import time

    N = 100000

    s_one = time.time()
    for _ in range(N):
        oneplane_test()
    e_one = time.time()

    s_two = time.time()
    for _ in range(N):
        twoplane_test()
    e_two = time.time()

    print(f"one plane:{e_one - s_one:.3f} two plane:{e_two - s_two:.3f}")


# @time_cal
def process_v(ctx: Ctx) -> Tuple[list[Vector], list[Vector]]:
    # time.sleep(0.5)

    pipeline = ctx.pipeline
    measure_page = ctx.init_finished
    if pipeline == 0:
        # 解未装试重的值 if not ... else 解measure得到的值.
        args = {
            'a10': ctx.response_1_1.length,
            's10': ctx.response_1_1.angle,
            'u11': ctx.test_weight_1.weight,
            's1': ctx.test_weight_1.angle,
            'a11': ctx.response_1_2.length,
            's11': ctx.response_1_2.angle,
            'a1x': ctx.response_1_1.length if not measure_page else ctx.response_1_0.length,
            's1x': ctx.response_1_1.angle if not measure_page else ctx.response_1_0.angle,
        }
        res = oneplane(**args)
    else:
        args = {
            'a10': ctx.response_1_1.length,
            's10': ctx.response_1_1.angle,
            'a20': ctx.response_2_1.length,
            's20': ctx.response_2_1.angle,
            'u11': ctx.test_weight_1.weight,
            's1': ctx.test_weight_1.angle,
            'a11': ctx.response_1_2.length,
            's11': ctx.response_1_2.angle,
            'a21': ctx.response_2_2.length,
            's21': ctx.response_2_2.angle,
            'u21': ctx.test_weight_2.weight,
            's2': ctx.test_weight_2.angle,
            'a12': ctx.response_1_3.length,
            's12': ctx.response_1_3.angle,
            'a22': ctx.response_2_3.length,
            's22': ctx.response_2_3.angle,
            'a1x': ctx.response_1_1.length if not measure_page else ctx.response_1_0.length,
            's1x': ctx.response_1_1.angle if not measure_page else ctx.response_1_0.angle,
            'a2x': ctx.response_2_1.length if not measure_page else ctx.response_2_0.length,
            's2x': ctx.response_2_1.angle if not measure_page else ctx.response_2_0.angle,
        }
        res = twoplane(**args)
    # print(f'pipeline :{pipeline},measure page {measure_page}')
    # ctx.init_finished = True
    return res


if __name__ == "__main__":
    oneplane_test()
    twoplane_test()
    # speed_test()
