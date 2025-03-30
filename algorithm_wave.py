import numpy as np
import matplotlib.pyplot as plt
from scipy import signal as sig
import os
from Config import Ctx, config
import time
from random import shuffle
from utils import time_cal
# import butter as butter

def filterate_signal(
    signal: np.ndarray[np.float32],
    sample_rate: int,
    filter: str,
    order: int,
    fpass: list[int],
):
    fs = sample_rate  # 采样频率
    nyquist = 0.5 * fs
    low = fpass[0] / nyquist
    high = fpass[1] / nyquist

    b, a = sig.butter(order, [low, high], btype="band")

    # 应用滤波器
    filtered_signal = sig.filtfilt(b, a, signal)
    return filtered_signal


def window_signal(
    signal: np.ndarray[np.float32],
    window_type: str,
):
    window = sig.hamming(len(signal))
    windowed_signal = signal * window * 2 / np.sum(window)

    return windowed_signal


def apply_fft(signal: np.ndarray[np.float32], sample_rate: int):
    fft = np.fft.fft(signal)
    freqs = np.fft.fftfreq(signal.size, 1 / sample_rate)
    # print('1/fs:',1/sample_rate)
    return fft, freqs


def signal_process(
    signal: np.ndarray[np.float32],
    sample_rate: int,
    window_type: str,
    filter: str,
    order: int,
    fpass: list[int],
    lb1:float,
    rb1:float,
    lb2:float,
    rb2:float,
    fft_mode: bool = False,
):
    signal = signal[lb1:rb1]
    # filter
    filtered_signal = filterate_signal(
        signal=signal,
        sample_rate=sample_rate,
        filter=filter,
        order=order,
        fpass=fpass,
    )
    filtered_signal = filtered_signal[lb2:rb2]

    # window
    # filterate_signal = window_signal(
    #     signal=filtered_signal,
    #     window_type=window_type,
    # )


    fft, freqs = apply_fft(signal=filtered_signal, sample_rate=sample_rate)

    ffts = np.abs(fft)[freqs >= 0]
    freqs = freqs[freqs >= 0]

    # 找到频谱中具有最大幅度的频率
    max_magnitude_index = np.argmax(ffts)
    max_magnitude_freq = freqs[max_magnitude_index]
    phase = np.angle(fft[max_magnitude_index])
    magnitude = ffts[max_magnitude_index] * 2 / len(filtered_signal)

    # if fft_mode:
    #     return (
    #         filtered_signal,
    #         windowed_signal,
    #         freqs,
    #     )
    # else:
    #     return max_magnitude_freq, magnitude, phase
    return max_magnitude_freq, magnitude, phase

def avg_method(
    signal,
    rotate_sig,
    time_stamp,
    idx,
):
    '''
        raw signal(30s)-->cut-->real signal-->filter-->window-->FFT-->amp, phase
    '''
    sample_rate = config.rate
    # 得到转速target_freq与各周期分界线indexes
    rotation_a = np.where(rotate_sig<config.rpm_threshold, 1, 0)[:-1]
    rotation_b = np.where(rotate_sig>config.rpm_threshold, 1, 0)[1:]

    descending_edge_data = np.logical_and(rotation_a, rotation_b)
    indexes = np.argwhere(descending_edge_data==1).reshape(-1)

    diff_indexes = indexes[1:] - indexes[:-1]
    target_freq = sample_rate / np.mean(diff_indexes)

    # 进行滤波
    if config.activate_conducted_filter:
        print('New filter')

        filtered_signal = butter.filter(config.order, config.rate, target_freq * 60, config.gap, list(signal))
        filtered_signal = np.asarray(filtered_signal)
    else:
        print('Old filter')
        lowcut = target_freq * (1 - config.gap)
        highcut = target_freq * (1 + config.gap)
        b, a = sig.butter(N=config.order/2, Wn=[lowcut/(0.5*sample_rate), highcut/(0.5*sample_rate)], btype='band')
        filtered_signal = sig.filtfilt(b, a, signal)

    if config.export:
        np.savetxt(f'./out-data/{time_stamp} filtered channel-{idx}.txt', filtered_signal)

    # print(indexes)
    # plt.subplot(2,1,1)
    # plt.plot(np.arange(len(rotate_sig)), rotate_sig)
    # plt.subplot(2,1,2)
    # plt.plot(np.arange(len(filtered_signal)), filtered_signal)
    # plt.savefig('./tmp.png')

    # filtered_signal = filtered_signal[lb:rb]
    # indexes = indexes[config.avg_cut_lb:-config.avg_cut_rb]

    if config.export:
        lb, rb = indexes[config.avg_cut_lb], indexes[-config.avg_cut_rb]
        np.savetxt(f'./out-data/{time_stamp} cutted filtered channel-{idx}.txt', filtered_signal[lb:rb])

    amps = []
    phases = []

    # print(len(filtered_signal))
    # print(indexes[-1])
    for lb in range(config.avg_cut_lb, len(indexes)-config.avg_cut_rb-config.avg_period,config.avg_stride):

    # for lb,rb in zip(range(0,len(indexes),config.avg_stride), range(period-1,len(indexes),config.avg_stride)):
        rb = lb + config.avg_period
        real_lb, real_rb = indexes[lb], indexes[rb]
        cutted_sig = filtered_signal[real_lb:real_rb]
        # if cutted_len == 0:
        #     cutted_len = len(cutted_sig)
        # if abs(len(cutted_sig)-cutted_len)>1000:
        #     break
        # print(len(cutted_sig))
        if config.avg_add_window:
            hann_window = np.hanning(len(cutted_sig))
            cutted_sig = cutted_sig * hann_window
        # print(len(cutted_sig))
        fft_result = np.fft.fft(cutted_sig)
        freqs = np.fft.fftfreq(len(fft_result), 1/sample_rate)
        fft_amplitude = np.abs(fft_result)
        fft_phase = np.angle(fft_result)

        if config.avg_add_window:
            correction_factor = 2 / np.sum(hann_window)
            fft_amplitude = fft_amplitude * correction_factor
        else:
            fft_amplitude = fft_amplitude * 2 / len(cutted_sig)

        target_idx = 0
        while True:
            if abs(freqs[target_idx] - target_freq) > abs(freqs[target_idx+1] - target_freq):
                target_idx += 1
            else:
                break

        peak_freq_index = target_idx

        # peak_freq_index = np.argmax(fft_amplitude[:len(fft_result)//2])
        peak_freq = freqs[peak_freq_index]
        peak_amplitude = fft_amplitude[peak_freq_index]
        peak_phase = fft_phase[peak_freq_index]

        amps.append(peak_amplitude)
        phases.append(peak_phase)

    # print(len(indexes)/config.avg_stride)
    # print(len(amps))

    if config.mid_filter:
        amp = np.mean(my_mid_filter(amps, config.mid_filter_d))
    else:
        amp = np.mean(amps)

    if config.angle_mean_mid_filter:
        phase = phase_mean_mid(phases)
    elif config.angle_mean:
        phase = phase_mean(phases)
    else:
        phase = np.mean(phases)

    return peak_freq, amp, phase

def process_old(
    data: list[np.ndarray],
    threshold: float,
    sample_rate: int,
    window_type: str,
    filter: str,
    order: int,
    fpass: list[int],
    one_plane: bool,
    ctx: Ctx,
    fft_mode: bool = True,
    avg_version:bool = True
):
    """
    This function first cut the signal by the period according to the rotation signal
    then use the signal process to get the amp and phi of the signal.
    """
    ts = time.strftime('%m-%d %H-%M-%S', time.localtime())

    if config.export:
        os.makedirs('./out-data/',exist_ok=True)
        for i in range(len(data)):
            np.savetxt(f'./out-data/{ts} channel-{i}.txt', data[i])

        rotate_sig = data[3]
        rotation_a = np.where(rotate_sig<config.rpm_threshold, 1, 0)[:-1]
        rotation_b = np.where(rotate_sig>config.rpm_threshold, 1, 0)[1:]

        descending_edge_data = np.logical_and(rotation_a, rotation_b)

        np.savetxt(f'./out-data/{ts} processed rotate sig.txt', descending_edge_data)


    if not avg_version:
        rotation = data[3]
        lb1, rb1, lb2, rb2 = get_cut_index(rotation, ctx, threshold)
        # print(lb1, rb1)
        # print(lb2, rb2)

        def vib_process(vib_data):
            # vib_data = vib_data[lb:rb]  # the cut operation
            freq, magnitude, phase = signal_process(
                signal=vib_data,
                sample_rate=sample_rate,
                window_type=window_type,
                filter=filter,
                order=order,
                fpass=fpass,
                lb1 = lb1,
                rb1 = rb1,
                lb2 = lb2-lb1,
                rb2 = rb2-lb1,
            )
            return freq, magnitude, phase

        buf = [data[i] for i in range(1 if one_plane else 2)]

        res = []
        for vib_data in buf:
            res.append(vib_process(vib_data))

        return res
    else:
        rotate_sig = data[3]
        lowcut, highcut = fpass[0], fpass[1]
        order = config.order
        period = config.avg_period
        buf = [data[i] for i in range(1 if one_plane else 2)]

        res = []
        for idx, signal_data in enumerate(buf):
            result = avg_method(
                signal=signal_data,
                lowcut=lowcut,
                highcut=highcut,
                sample_rate=config.rate,
                rotate_sig=rotate_sig,
                order=order,
                period=period,
                ts = ts,
                idx=idx
            )

            res.append(result)

        return res

@time_cal
def process_w(
    data: list[np.ndarray],
    one_plane: bool,
):
    """
    This function first cut the signal by the period according to the rotation signal
    then use the signal process to get the amp and phi of the signal.
    """
    # time.sleep(0.5)
    ts = time.strftime('%m-%d %H-%M-%S', time.localtime())

    if config.export:
        print('export data')
        os.makedirs('./out-data/',exist_ok=True)
        for i in range(len(data)):
            np.savetxt(f'./out-data/{ts} channel-{i}.txt', data[i])

        rotate_sig = data[3]
        rotation_a = np.where(rotate_sig<config.rpm_threshold, 1, 0)[:-1]
        rotation_b = np.where(rotate_sig>config.rpm_threshold, 1, 0)[1:]

        descending_edge_data = np.logical_and(rotation_a, rotation_b)

        np.savetxt(f'./out-data/{ts} processed rotate sig.txt', descending_edge_data)


    rotate_sig = data[3]
    buf = [data[i] for i in range(1 if one_plane else 2)]

    res = []
    for idx, signal_data in enumerate(buf):
        result = avg_method(
            signal=signal_data,
            rotate_sig=rotate_sig,
            time_stamp = ts,
            idx=idx
        )

        res.append(result)

    return res

def get_cut_index(rotation: np.ndarray, ctx: Ctx, threshold: float, type:bool=True):
    # Type为true是阶段一.
    rotation_a = np.where(rotation < threshold, 1, 0)[:-1]
    rotation_b = np.where(rotation > threshold, 1, 0)[1:]

    descending_edge_data = np.logical_and(rotation_a, rotation_b)
    indexes = np.argwhere(descending_edge_data == 1).reshape(-1)
    index_of_lb = 0
    # lb, rb = indexes[::len(indexes)-1]
    if ctx.calibration_name.rpm > config.cut_threshold_1:
        # cut by time
        # use time to calculate the target index of data
        # find the first descending edge such that it is greater than the calculated result
        target_index = config.cut_time_1 * config.rate
        for index_of_lb in range(len(indexes)):
            if indexes[index_of_lb] >= target_index:
                break
    else:
        # cut by period
        # directly take the target index in descending edge
        index_of_lb = config.cut_period_1
    index_of_rb = -index_of_lb

    lb1 = indexes[index_of_lb]
    rb1 = indexes[index_of_rb]

    index_of_lb = 0
    # lb, rb = indexes[::len(indexes)-1]
    if ctx.calibration_name.rpm > config.cut_threshold_2:
        # cut by time
        # use time to calculate the target index of data
        # find the first descending edge such that it is greater than the calculated result
        target_index = (config.cut_time_1+config.cut_time_2) * config.rate
        for index_of_lb in range(len(indexes)):
            if indexes[index_of_lb] >= target_index:
                break
    else:
        # cut by period
        # directly take the target index in descending edge
        index_of_lb = (config.cut_period_1+config.cut_period_2)
    index_of_rb = -index_of_lb

    lb2 = indexes[index_of_lb]
    rb2 = indexes[index_of_rb]
    return lb1, rb1, lb2, rb2


def vis_test():
    ...

def my_mid_filter(arr, d):
    # d must be odd
    new_arr = arr[-d // 2 + 1 :] + arr + arr[:d//2]
    result_arr = [sorted(new_arr[i:i+d])[d//2] for i in range(len(arr))]
    return result_arr

def phase_mean(phases):
    phases_cos = [np.cos(phase) for phase in phases]
    phases_sin = [np.sin(phase) for phase in phases]

    phase_cos = np.mean(phases_cos)
    phase_sin = np.mean(phases_sin)

    phase = np.angle(phase_cos + 1j * phase_sin, deg=False)

    return phase


def phase_mean_mid(phases):
    if config.phase_mean_mid_shuffle:
        shuffle(phases)
    # 计算向量平均
    phases_cos = [np.cos(phase) for phase in phases]
    phases_sin = [np.sin(phase) for phase in phases]

    phase_cos = np.mean(phases_cos)
    phase_sin = np.mean(phases_sin)

    norm_phase = np.angle(phase_cos + 1j * phase_sin, deg=False)
    # print(f"norm pha:{norm_phase}")
    # 角度归一化
    phases = phases - norm_phase
    # print(phases)
    small_idx = np.argwhere(phases<-np.pi).reshape(-1)
    great_idx = np.argwhere(phases>np.pi).reshape(-1)

    phases[small_idx] = phases[small_idx] + 2*np.pi
    phases[great_idx] -= 2*np.pi

    # print(f"normed phas:{phases}")
    def my_mid_filter(arr, d):
        # d must be odd
        arr = list(arr)
        new_arr = arr[-d // 2 + 1 :] + arr + arr[:d//2]
        result_arr = [sorted(new_arr[i:i+d])[d//2] for i in range(len(arr))]
        return result_arr

    phases = my_mid_filter(phases, 3)
    # print(f"mid phas:{phases}")

    return np.mean(phases) + norm_phase

if __name__ == "__main__":
    vis_test()
