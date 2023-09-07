__author__ = "Simon Nilsson"

import time
from typing import List, Tuple

import numpy as np
from numba import jit, njit, prange, typed

from simba.utils.data import fast_mean_rank


class CircularStatisticsMixin(object):

    """
    Mixin for circular statistics. Support for multiple animals and base
    radial directions derived from two or three body-parts.

    Methods are adopted from the referenced packages below which are **far** more reliable. However,
    runtime is prioritized and typically multiple orders of magnitude faster than referenced libraries.

    .. note::
        Many method has numba typed `signatures < https://numba.pydata.org/numba-doc/latest/reference/types.html>`_ to decrease
        compilation time. Make sure to pass the correct dtypes as indicated by signature decorators.

    .. important::
        See references below for  mature packages computing extensive circular measurements.

    .. image:: _static/img/circular_statistics.png
       :width: 800
       :align: center

    References
    ----------
    .. [1] `pycircstat <https://github.com/circstat/pycircstat>`_.
    .. [2] `circstat <https://www.mathworks.com/matlabcentral/fileexchange/10676-circular-statistics-toolbox-directional-statistics>`_.
    .. [3] `pingouin.circular <https://github.com/raphaelvallat/pingouin/blob/master/pingouin/circular.py>`_.
    .. [4] `pycircular <https://github.com/albahnsen/pycircular>`_.
    .. [5] `scipy.stats.directional_stats <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.directional_stats.html>`_.
    .. [6] `astropy.stats.circstats <https://docs.astropy.org/en/stable/_modules/astropy/stats/circstats.html>`_.
    """

    def __init__(self):
        pass

    @staticmethod
    @njit("(float32[:],)")
    def mean_resultant_vector_length(data: np.ndarray) -> float:
        """
        Jitted compute of the mean resultant vector length of a single sample. Captures the overall "pull" or "tendency" of the
        data points towards a central direction on the circle with a range between 0 and 1.

        :parameter np.ndarray data: 1D array of size len(frames) representing angles in degrees.
        :returns float: The mean resultant vector of the angles. 1 represents tendency towards a single point. 0 represents no central point.

        :example:
        >>> data = np.array([50, 90, 70, 60, 20, 90]).astype(np.float32)
        >>> CircularStatisticsMixin().mean_resultant_vector_length(data=data_1)
        >>> 0.9132277170817057
        """

        data = np.deg2rad(data)
        mean_angles = np.arctan2(np.mean(np.sin(data)), np.mean(np.cos(data)))
        return np.sqrt(
            np.sum(np.cos(data - mean_angles)) ** 2
            + np.sum(np.sin(data - mean_angles)) ** 2
        ) / len(data)

    @staticmethod
    @njit("(float32[:], float64, float64[:])")
    def sliding_mean_resultant_vector_length(
        data: np.ndarray, fps: int, time_windows: np.ndarray
    ) -> np.ndarray:
        """
        Jitted compute of the mean resultant vector within sliding time window. Captures the overall "pull" or "tendency" of the
        data points towards a central direction on the circle with a range between 0 and 1.

        .. attention::
           The returned values represents resultant vector length in the time-window ``[(current_frame-time_window)->current_frame]``.
           `-1` is returned where ``current_frame-time_window`` is less than 0.


        .. image:: _static/img/sliding_mean_resultant_length.png
           :width: 600
           :align: center

        :parameter np.ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Rolling time-window as float in seconds.
        :parameter int fps: fps of the recorded video
        :returns np.ndarray: Size len(data) x len(time_windows) representing resultant vector length in the prior ``time_window``.

        :example:
        >>> data_1, data_2 = np.random.normal(loc=45, scale=1, size=100), np.random.normal(loc=90, scale=45, size=100)
        >>> data = np.hstack([data_1, data_2])
        >>> CircularStatisticsMixin().sliding_mean_resultant_vector_length(data=data.astype(np.float32),time_windows=np.array([1.0]), fps=10)

        """
        data = np.deg2rad(data)
        results = np.full((data.shape[0], time_windows.shape[0]), -1.0)
        for time_window_cnt in prange(time_windows.shape[0]):
            window_size = int(time_windows[time_window_cnt] * fps)
            for window_end in prange(window_size, data.shape[0] + 1, 1):
                window_data = data[window_end - window_size : window_end]
                print(window_data)
                mean_angles = np.arctan2(
                    np.mean(np.sin(window_data)), np.mean(np.cos(window_data))
                )
                r = np.sqrt(
                    np.sum(np.cos(window_data - mean_angles)) ** 2
                    + np.sum(np.sin(window_data - mean_angles)) ** 2
                ) / len(window_data)
                results[window_end - 1] = r
        return results

    @staticmethod
    @njit("(float32[:],)")
    def circular_mean(data: np.ndarray) -> float:
        """
        Jitted compute of the circular mean of single sample.

        :parameter np.ndarray data: 1D array of size len(frames) representing angles in degrees.
        :returns float: The circular mean of the angles in degrees.

        :example:
        >>> data = np.array([50, 90, 70, 60, 20, 90]).astype(np.float32)
        >>> CircularStatisticsMixin().circular_mean(data=data)
        >>> 63.737892150878906
        """

        return np.rad2deg(
            np.arctan2(
                np.mean(np.sin(np.deg2rad(data))), np.mean(np.cos(np.deg2rad(data)))
            )
        )

    @staticmethod
    @njit("(float32[:], float64[:], float64)")
    def sliding_circular_mean(
        data: np.ndarray, time_windows: np.ndarray, fps: int
    ) -> np.ndarray:
        """
        Compute the circular mean in degrees within sliding temporal windows.

        :parameter np.ndarray data: 1d array with feature values in degrees.
        :parameter np.ndarray time_windows: Rolling time-windows as floats in seconds. E.g., [0.2, 0.4, 0.6]
        :parameter int fps: fps of the recorded video
        :returns np.ndarray: Size data.shape[0] x time_windows.shape[0] array

        .. image:: _static/img/mean_rolling_timeseries_angle.png
           :width: 600
           :align: center

        .. attention::
           The returned values represents the angular mean dispersion in the time-window ``[current_frame-time_window->current_frame]``.
           `-1` is returned when ``current_frame-time_window`` is less than 0.

        :example:
        >>> data = np.random.normal(loc=45, scale=1, size=20).astype(np.float32)
        >>> CircularStatisticsMixin().sliding_circular_mean(data=data,time_windows=np.array([0.5, 1.0]), fps=10)
        """

        data = np.deg2rad(data)
        results = np.full((data.shape[0], time_windows.shape[0]), -1.0)
        for time_window in prange(time_windows.shape[0]):
            window_size = int(time_windows[time_window] * fps)
            for current_frm in prange(window_size, results.shape[0]):
                data_window = np.deg2rad(data[current_frm - window_size : current_frm])
                results[current_frm, time_window] = np.rad2deg(
                    np.arctan2(
                        np.mean(np.sin(data_window)), np.mean(np.cos(data_window))
                    )
                )
        return results

    @staticmethod
    @njit("(float32[:],)")
    def circular_std(data: np.ndarray) -> float:
        """
        Jitted compute of the circular standard deviation of a single distribution of angles in degrees

        :parameter ndarray data: 1D array of size len(frames) with angles in degrees
        :returns float: The standard deviation of the data sample in degrees

        :example:
        >>> data = np.array([180, 221, 32, 42, 212, 101, 139, 41, 69, 171, 149, 200]).astype(np.float32)
        >>> CircularStatisticsMixin().circular_std(data=data)
        >>> 75.03725024504664
        """

        data = np.deg2rad(data)
        return np.rad2deg(np.sqrt(-2 * np.log(np.abs(np.mean(np.exp(1j * data))))))

    @staticmethod
    @njit("(float32[:], int64, float64[:])")
    def sliding_circular_std(
        data: np.ndarray, fps: int, time_windows: np.ndarray
    ) -> np.ndarray:
        """
        Compute standard deviation of angular data in sliding time windows.

        .. image:: _static/img/angle_stdev.png
           :width: 600
           :align: center

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Sliding time-window as float in seconds.
        :parameter int fps: fps of the recorded video
        :returns np.ndarray: Size data.shape[0] x time_windows.shape[0] with angular standard deviations in rolling time windows in degrees.

        :example:
        >>> data = np.array([180, 221, 32, 42, 212, 101, 139, 41, 69, 171, 149, 200]).astype(np.float32)
        >>> CircularStatisticsMixin().sliding_circular_std(data=data.astype(np.float32), time_windows=np.array([0.5]), fps=10)
        """

        data = np.deg2rad(data)
        results = np.full((data.shape[0], time_windows.shape[0]), 0.0)
        for time_window_cnt in prange(time_windows.shape[0]):
            window_size = int(time_windows[time_window_cnt] * fps)
            for window_end in prange(window_size, data.shape[0] + 1, 1):
                window_data = data[window_end - window_size : window_end]
                results[window_end - 1][time_window_cnt] = np.rad2deg(
                    np.sqrt(-2 * np.log(np.abs(np.mean(np.exp(1j * window_data)))))
                )
        return results

    @staticmethod
    @njit("(float32[:], int64)")
    def instantaneous_angular_velocity(data: np.ndarray, bin_size: int):
        """
        Jitted compute of absolute angular change in the smallest possible time bin.

        .. note::
            If the smallest possible frame-to-frame time-bin in Video 1 is 33ms (recorded at 30fps), and the
            smallest possible frame-to-frame time-bin in Video 2 is 66ms (recorded at 15fps) we have to correct for
            this across recordings using the ``bin_size`` argument. E.g., when passing angular data from Video 1
            we would set bin_size to ``2``, and when passing angular data for Video 2 we would set bin_size to ``1`` to
            allow comparisons of instantaneous angular velocity between Video 1 and Video 2.

            When current frame minus bin_size results in a negative index, 1 is returned.

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter int bin_size: The number of frames prior to compare the current angular velocity against.

        :example:
        >>> data = np.array([350, 360, 365, 360]).astype(np.float32)
        >>> CircularStatisticsMixin().instantaneous_angular_velocity(data=data, bin_size=1.0)
        >>> [-1., 10.00002532, 4.999999, 4.999999]
        >>> CircularStatisticsMixin().instantaneous_angular_velocity(data=data, bin_size=2)
        >>> [-1., -1., 15.00002432, 0.]
        """
        data = np.deg2rad(data)
        results = np.full((data.shape[0]), -1.0)
        left_idx, right_idx = 0, bin_size
        for end_idx in prange(right_idx, data.shape[0] + 1, 1):
            results[end_idx] = np.rad2deg(
                np.pi - np.abs(np.pi - np.abs(data[left_idx] - data[end_idx]))
            )
            left_idx += 1
        return results

    @staticmethod
    @njit("(float32[:],)")
    def degrees_to_cardinal(degree_angles: np.ndarray) -> List[str]:
        """
        Convert degree angles to cardinal direction bucket e.g., 0 -> "N", 180 -> "S"

        .. note::
           To convert cardinal literals to integers, map using ``simba.utils.enums.lookups.cardinality_to_integer_lookup``.
           To convert integers to cardinal literals, map using ``simba.utils.enums.lookups.integer_to_cardinality_lookup``.

        .. image:: _static/img/degrees_to_cardinal.png
           :width: 600
           :align: center

        :parameter np.ndarray degree_angles: 1d array of degrees. Note: return by ``self.head_direction``.
        :return List[str]: List of strings representing frame-wise cardinality.

        :example:
        >>> data = np.array(list(range(0, 405, 45))).astype(np.float32)
        >>> CircularStatisticsMixin().degrees_to_cardinal(degree_angles=data)
        >>> ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
        """

        DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        results = typed.List(["str"])
        for i in prange(degree_angles.shape[0]):
            ix = round(degree_angles[i] / (360.0 / len(DIRECTIONS)))
            direction = DIRECTIONS[ix % len(DIRECTIONS)]
            results.append(direction)
        return results[1:]

    @staticmethod
    @njit("(float32[:,:], float32[:, :], float32[:, :])")
    def direction_three_bps(
        nose_loc: np.ndarray, left_ear_loc: np.ndarray, right_ear_loc: np.ndarray
    ) -> np.ndarray:
        """
        Jitted helper to compute the degree angle from three body-parts. Computes the angle in degrees left_ear <-> nose
        and right_ear_nose and returns the midpoint.

        .. image:: _static/img/angle_from_3_bps.png
          :width: 600
          :align: center

        :parameter ndarray nose_loc: 2D array of size len(frames)x2 representing nose coordinates
        :parameter ndarray left_ear_loc: 2D array of size len(frames)x2 representing left ear coordinates
        :parameter ndarray right_ear_loc: 2D array of size len(frames)x2 representing right ear coordinates
        :return np.ndarray: Array of size nose_loc.shape[0] with direction in degrees.

        :example:
        >>> nose_loc = np.random.randint(low=0, high=500, size=(50, 2)).astype(np.float32)
        >>> left_ear_loc = np.random.randint(low=0, high=500, size=(50, 2)).astype(np.float32)
        >>> right_ear_loc = np.random.randint(low=0, high=500, size=(50, 2)).astype(np.float32)
        >>> results = CircularStatisticsMixin().direction_three_bps(nose_loc=nose_loc, left_ear_loc=left_ear_loc, right_ear_loc=right_ear_loc)
        """

        results = np.full((nose_loc.shape[0]), np.nan)
        for i in prange(nose_loc.shape[0]):
            left_ear_to_nose = np.degrees(
                np.arctan2(
                    left_ear_loc[i][0] - nose_loc[i][1],
                    left_ear_loc[i][1] - nose_loc[i][0],
                )
            )
            right_ear_nose = np.degrees(
                np.arctan2(
                    right_ear_loc[i][0] - nose_loc[i][1],
                    right_ear_loc[i][1] - nose_loc[i][0],
                )
            )
            results[i] = ((left_ear_to_nose + right_ear_nose) % 360) / 2
        return results

    @staticmethod
    @njit("(float32[:, :], float32[:, :])")
    def direction_two_bps(
        swim_bladder_loc: np.ndarray, tail_loc: np.ndarray
    ) -> np.ndarray:
        """
        Jitted method computing degree directionality from two body-parts. E.g., ``nape`` and ``nose``,
        or ``swim_bladder`` and ``tail``.

        .. image:: _static/img/angle_from_2_bps.png
           :width: 1200
           :align: center

        :parameter np.ndarray bp_x: Size len(frames) x 2 representing x and y coordinates for first body-part.
        :parameter np.ndarray bp_y: Size len(frames) x 2 representing x and y coordinates for second body-part.
        :return np.ndarray: Frame-wise directionality in degrees.

        :example:
        >>> swim_bladder_loc = np.random.randint(low=0, high=500, size=(50, 2)).astype(np.float32)
        >>> tail_loc = np.random.randint(low=0, high=500, size=(50, 2)).astype(np.float32)
        >>> CircularStatisticsMixin().direction_two_bps(swim_bladder_loc=swim_bladder_loc, tail_loc=tail_loc)
        """

        results = np.full((swim_bladder_loc.shape[0]), np.nan)
        for i in prange(swim_bladder_loc.shape[0]):
            angle_degrees = np.degrees(
                np.arctan2(
                    swim_bladder_loc[i][0] - tail_loc[i][0],
                    tail_loc[i][1] - swim_bladder_loc[i][1],
                )
            )
            angle_degrees = angle_degrees + 360 if angle_degrees < 0 else angle_degrees
            results[i] = angle_degrees
        return results

    @staticmethod
    @njit("(float32[:],)")
    def rayleigh(data: np.ndarray) -> Tuple[float, float]:
        """
        Jitted compute of Rayleigh Z (test of non-uniformity) of single sample of circular data in degrees.

        .. note:
           Adapted from ``pingouin.circular.circ_rayleigh`` and ``pycircstat.tests.rayleigh``.

        >>> data = np.array([350, 360, 365, 360, 100, 109, 232, 123, 42, 3,4, 145]).astype(np.float32)
        >>> CircularStatisticsMixin().rayleigh(data=data)
        >>> (2.3845645695246467, 0.9842236169985417)
        """

        data = np.deg2rad(data)
        R = np.sqrt(np.sum(np.cos(data)) ** 2 + np.sum(np.sin(data)) ** 2) / len(data)
        p = np.exp(
            np.sqrt(1 + 4 * len(data) + 4 * (len(data) ** 2 - R**2))
            - (1 + 2 * len(data))
        )
        return len(data) * R**2, p

    @staticmethod
    @njit("(float32[:], float64[:], float64)")
    def rolling_rayleigh_z(
        data: np.ndarray, time_windows: np.ndarray, fps: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Jitted compute of Rayleigh Z (test of non-uniformity) of circular data within sliding time-window.

        .. note:
           Adapted from ``pingouin.circular.circ_rayleigh`` and ``pycircstat.tests.rayleigh``.

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Rolling time-window as float in seconds. Two windows of 0.5s and 1s would be represented as np.array([0.5, 1.0])
        :parameter int fps: fps of the recorded video
        :returns Tuple[np.ndarray, np.ndarray]: Two 2d arrays with the first representing Rayleigh Z scores and second representing associated p values.

        :example:
        >>> data = np.random.randint(low=0, high=360, size=(100,)).astype(np.float32)
        >>> CircularStatisticsMixin().rolling_rayleigh_z(data=data, time_windows=np.array([0.5, 1.0]), fps=10)
        """

        data = np.deg2rad(data)
        Z_results, P_results = np.full(
            (data.shape[0], time_windows.shape[0]), 0.0
        ), np.full((data.shape[0], time_windows.shape[0]), 0.0)
        for i in prange(time_windows.shape[0]):
            win_size = int(time_windows[i] * fps)
            for j in prange(win_size, len(data) + 1):
                data_win = data[j - win_size : j]
                R = np.sqrt(
                    np.sum(np.cos(data_win)) ** 2 + np.sum(np.sin(data_win)) ** 2
                ) / len(data_win)
                Z_results[j - 1][i] = len(data_win) * R**2
                P_results[j - 1][i] = np.exp(
                    np.sqrt(1 + 4 * len(data_win) + 4 * (len(data_win) ** 2 - R**2))
                    - (1 + 2 * len(data_win))
                )
        return Z_results, P_results

    @staticmethod
    @njit("(float32[:], float32[:],)")
    def circular_correlation(sample_1: np.ndarray, sample_2: np.ndarray) -> float:
        """
        Jitted compute of circular correlation coefficient of two samples.

        .. note::
           Adapted from ``astropy.stats.circstats.circcorrcoef``.

        :parameter np.ndarray sample_1: Angular data for e.g., Animal 1
        :parameter np.ndarray sample_1: Angular data for e.g., Animal 2
        :parameter float circular_correlation: The correlation between the two distributions.

        :example:
        >>> sample_1 = np.array([50, 90, 20, 60, 20, 90]).astype(np.float32)
        >>> sample_2 = np.array([50, 90, 70, 60, 20, 90]).astype(np.float32)
        >>> CircularStatisticsMixin().circular_correlation(sample_1=sample_1, sample_2=sample_2)
        """

        sample_1, sample_2 = np.deg2rad(sample_1), np.deg2rad(sample_2)
        m1 = np.arctan2(np.mean(np.sin(sample_1)), np.mean(np.cos(sample_1)))
        m2 = np.arctan2(np.mean(np.sin(sample_2)), np.mean(np.cos(sample_2)))
        sin_1, sin_2 = np.sin(sample_1 - m1), np.sin(sample_2 - m2)
        return np.sum(sin_1 * sin_2) / np.sqrt(
            np.sum(sin_1 * sin_1) * np.sum(sin_2 * sin_2)
        )

    @staticmethod
    @njit("(float32[:], float32[:], float64[:], int64)")
    def sliding_circular_correlation(
        sample_1: np.ndarray, sample_2: np.ndarray, time_windows: np.ndarray, fps: float
    ) -> np.ndarray:
        """
        Jitted compute of correlations between two angular distributions in sliding time-windows.

        .. image:: _static/img/cicle_correlation.png
           :width: 800
           :align: center

        :parameter np.ndarray sample_1: Angular data for e.g., Animal 1
        :parameter np.ndarray sample_1: Angular data for e.g., Animal 2
        :parameter float time_windows: Size of sliding time window in seconds. E.g., two windows of 0.5s and 1s would be represented as np.array([0.5, 1.0])
        :parameter int fps: Frame-rate of recorded video.
        :return np.ndarray: Array of size len(sample_1) x len(time_window) with correlation coefficients.


        :example:
        >>> sample_1 = np.random.randint(0, 360, (200,)).astype(np.float32)
        >>> sample_2 = np.random.randint(0, 360, (200,)).astype(np.float32)
        >>> CircularStatisticsMixin().sliding_circular_correlation(sample_1=sample_1, sample_2=sample_2, time_windows=np.array([0.5, 1.0]), fps=10.0)
        """

        sample_1, sample_2 = np.deg2rad(sample_1), np.deg2rad(sample_2)
        results = np.full((sample_1.shape[0], time_windows.shape[0]), np.nan)
        for i in prange(time_windows.shape[0]):
            win_size = int(time_windows[i] * fps)
            for j in prange(win_size, sample_1.shape[0] + 1):
                data_1_window = sample_1[j - win_size : j]
                data_2_window = sample_2[j - win_size : j]
                m1 = np.arctan2(
                    np.mean(np.sin(data_1_window)), np.mean(np.cos(data_1_window))
                )
                m2 = np.arctan2(
                    np.mean(np.sin(data_2_window)), np.mean(np.cos(data_2_window))
                )
                sin_1, sin_2 = np.sin(data_1_window - m1), np.sin(data_2_window - m2)
                c = np.sum(sin_1 * sin_2) / np.sqrt(
                    np.sum(sin_1 * sin_1) * np.sum(sin_2 * sin_2)
                )
                print(c)
                results[j][i] = c

        return results

    @staticmethod
    @njit("(float32[:], float64[:], int64)")
    def sliding_angular_diff(
        data: np.ndarray, time_windows: np.ndarray, fps: float
    ) -> np.ndarray:
        """
        Computes the angular difference in the current frame versus N seconds previously.
        For example, if the current angle is 45 degrees, and the angle N seconds previously was 350 degrees, then the difference
        is 55 degrees.

        .. note::
           Frames where current frame - N seconds prior equal a negative value is populated with 0.

        .. image:: _static/img/sliding_angular_difference.png
           :width: 600
           :align: center

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Rolling time-window as float in seconds.
        :parameter int fps: fps of the recorded video

        :example:
        >>> data = np.array([350, 350, 1, 1]).astype(np.float32)
        >>> CircularStatisticsMixin().sliding_angular_diff(data=data, fps=1.0, time_windows=np.array([1.0]))
        >>> [[ 0.], [ 0.], [11.00000964], [ 0.]]
        """

        data_rad = np.deg2rad(data)
        results = np.full((data_rad.shape[0], time_windows.shape[0]), 0.0)
        for time_window_cnt in prange(time_windows.shape[0]):
            window_size = int(time_windows[time_window_cnt] * fps)
            for left, right in zip(
                prange(0, (data_rad.shape[0] - window_size) + 1),
                prange(window_size - 1, data_rad.shape[0] + 1),
            ):
                distance = np.pi - np.abs(
                    np.pi - np.abs(data_rad[left] - data_rad[right])
                )
                results[right][time_window_cnt] = np.rad2deg(distance)

        return results

    @staticmethod
    @njit("(float32[:], float64[:], int64)")
    def agg_angular_diff_timebins(
        data: np.ndarray, time_windows: np.ndarray, fps: int
    ) -> np.ndarray:
        """
        Compute the difference between the median angle in the current time-window versus the previous time window.
        For example, computes the difference between the mean angle in the first 1s of the video versus
        the second 1s of the video, the second 1s of the video versus the third 1s of the video, ... etc.

        .. note::
           The first time-bin of the video can't be compared against the prior time-bin of the video and the results
           for this first time-bin is populated with `0`.

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Rolling time-window as float in seconds.
        :parameter int fps: fps of the recorded video

        :example:
        >>> data = np.random.normal(loc=45, scale=3, size=20).astype(np.float32)
        >>> CircularStatisticsMixin().agg_angular_diff_timebins(data=data,time_windows=np.array([1.0]), fps=5.0))
        """

        data = np.deg2rad(data)
        results = np.full((data.shape[0], time_windows.shape[0]), 0.0)
        for time_window_cnt in prange(time_windows.shape[0]):
            window_size = int(time_windows[time_window_cnt] * fps)
            prior_window = [0, window_size]
            for win_cnt, window_end in enumerate(
                prange(int(window_size * 2), data.shape[0] + 1, window_size)
            ):
                window_start = (window_end - window_size) - 1
                current_data = data[window_start:window_end]
                prior_data = data[prior_window[0] : prior_window[1]]
                prior_median = np.arctan2(
                    np.sum(np.sin(prior_data)), np.sum(np.cos(prior_data))
                )
                if prior_median < 0:
                    prior_median += 2 * np.pi
                current_median = np.arctan2(
                    np.sum(np.sin(current_data)), np.sum(np.cos(current_data))
                )
                if current_median < 0:
                    current_median += 2 * np.pi
                distance = np.pi - np.abs(np.pi - np.abs(prior_median - current_median))
                results[window_start:window_end, win_cnt] = np.rad2deg(distance)
                prior_window = [window_start, window_end]

        return results

    @staticmethod
    @njit("(float32[:], float64[:], int64)")
    def sliding_rao_spacing(
        data: np.ndarray, time_windows: np.ndarray, fps: int
    ) -> np.ndarray:
        """
        Jitted compute of the uniformity of a circular dataset in sliding windows.

        :parameter ndarray data: 1D array of size len(frames) representing degrees.
        :parameter np.ndarray time_window: Rolling time-window as float in seconds.
        :parameter int fps: fps of the recorded video
        :return np.ndarray: representing rao-spacing U in every sliding windows [-window:n]

        .. image:: _static/img/raospacing.png
           :width: 800
           :align: center

        :references:
        .. [1] `UCSB <https://jammalam.faculty.pstat.ucsb.edu/html/favorite/test.htm>`__.

        :example:
        >>> data = np.random.randint(low=0, high=360, size=(500,)).astype(np.float32)
        >>> result = CircularStatisticsMixin().sliding_rao_spacing(data=data, time_windows=np.array([0.5, 1.0]), fps=10)
        """

        results = np.full((data.shape[0], time_windows.shape[0]), -1.0)
        for win_cnt in prange(time_windows.shape[0]):
            window_size = int(time_windows[win_cnt] * fps)
            for i in range(window_size, data.shape[0]):
                w_data = np.sort(data[i - window_size : i])
                Ti, TiL = np.full((w_data.shape[0]), np.nan), np.full(
                    (w_data.shape[0]), np.nan
                )
                l = np.int8(360 / len(w_data))
                Ti[-1] = np.rad2deg(
                    np.pi
                    - np.abs(
                        np.pi - np.abs(np.deg2rad(w_data[0]) - np.deg2rad(w_data[-1]))
                    )
                )
                for j in prange(w_data.shape[0] - 1, -1, -1):
                    Ti[j] = np.rad2deg(
                        np.pi
                        - np.abs(
                            np.pi
                            - np.abs(np.deg2rad(w_data[j]) - np.deg2rad(w_data[j - 1]))
                        )
                    )
                for k in prange(Ti.shape[0]):
                    TiL[int(k)] = max((l, Ti[k])) - min((l, Ti[k]))
                S = np.sum(TiL)
                U = int(S / 2)
                results[i][win_cnt] = U
        return results

    @staticmethod
    @njit("(float32[:], float32[:])")
    def kuipers_two_sample_test(sample_1: np.ndarray, sample_2: np.ndarray) -> float:
        """
        .. note::
           Adapted from `Kuiper <https://github.com/aarchiba/kuiper/tree/master>`__ by `Anne Archibald <https://github.com/aarchiba>`_.

        :example:
        >>> sample_1, sample_2 = np.random.normal(loc=45, scale=1, size=100).astype(np.float32), np.random.normal(loc=180, scale=20, size=100).astype(np.float32)
        >>> CircularStatisticsMixin().kuipers_two_sample_test(sample_1=sample_1, sample_2=sample_2)
        """

        sample_1, sample_2 = np.deg2rad(np.sort(sample_1)), np.deg2rad(
            np.sort(sample_2)
        )
        cdfv1 = np.searchsorted(sample_2, sample_1) / float(len(sample_2))
        cdfv2 = np.searchsorted(sample_1, sample_2) / float(len(sample_1))
        return np.amax(
            cdfv1 - np.arange(len(sample_1)) / float(len(sample_1))
        ) + np.amax(cdfv2 - np.arange(len(sample_2)) / float(len(sample_2)))

    @staticmethod
    @njit("(float32[:], float32[:], float64[:], int64)")
    def sliding_kuipers_two_sample_test(
        sample_1: np.ndarray, sample_2: np.ndarray, time_windows: np.ndarray, fps: int
    ) -> np.ndarray:
        """
        Jitted compute of Kuipers two-sample test comparing two distributions with sliding time window.

        :examples:
        >>> data = np.random.randint(low=0, high=360, size=(100,)).astype(np.float64)
        >>> D = CircularStatisticsMixin().sliding_kuipers_two_sample_test(data=data, time_windows=np.array([0.5, 5]), fps=2)
        """
        sample_1, sample_2 = np.deg2rad(sample_1), np.deg2rad(sample_2)
        results = np.full((sample_1.shape[0], time_windows.shape[0]), -1.0)
        for time_window_cnt in prange(time_windows.shape[0]):
            win_size = int(time_windows[time_window_cnt] * fps)
            for i in range(win_size, sample_1.shape[0]):
                sample_1_win, sample_2_win = (
                    sample_1[i - win_size : i],
                    sample_2[i - win_size : i],
                )
                cdfv1 = np.searchsorted(sample_2, sample_1_win) / float(
                    len(sample_2_win)
                )
                cdfv2 = np.searchsorted(sample_1_win, sample_2_win) / float(
                    len(sample_1_win)
                )
                D = np.amax(
                    cdfv1 - np.arange(len(sample_1_win)) / float(len(sample_1_win))
                ) + np.amax(
                    cdfv2 - np.arange(len(sample_2_win)) / float(len(sample_2_win))
                )
                results[i][time_window_cnt] = D

        return results

    @staticmethod
    def sliding_hodges_ajne(
        data: np.ndarray, time_window: float, fps: int
    ) -> np.ndarray:
        data = np.deg2rad(data)
        results, window_size = np.full((data.shape[0]), -1.0), int(time_window * fps)
        for i in range(window_size, data.shape[0]):
            w_data = data[i - window_size : i]
            v = 1 - np.abs(np.mean(np.exp(1j * w_data)))
            n = len(w_data)
            H = n * (1 - v)
            results[i] = H
        return results

    @staticmethod
    def hodges_ajne(sample: np.ndarray):
        v = 1 - np.abs(np.mean(np.exp(1j * sample)))
        n = len(sample)
        H = n * (1 - v)
        return H

    @staticmethod
    @jit(nopython=True)
    def watson_williams_test(sample_1: np.ndarray, sample_2: np.ndarray):
        variance1 = 1 - np.abs(np.mean(np.exp(1j * sample_1)))
        variance2 = 1 - np.abs(np.mean(np.exp(1j * sample_2)))
        numerator = (variance1 + variance2) / 2
        denominator = (variance1**2 / len(sample_1)) + (
            variance2**2 / len(sample_2)
        )
        F = numerator / denominator
        return F

    @staticmethod
    def watsons_u(data: np.ndarray):
        data = np.deg2rad(data)
        mean_vector = np.exp(1j * data).mean()
        n = len(data)
        return n * (1 - np.abs(mean_vector))


data = np.array([350, 100, 110, 105, 1, 45, 301, 206, 180, 45]).astype(np.float32)
CircularStatisticsMixin().sliding_angular_diff(
    data=data, time_windows=np.array([0.5]), fps=10
)

# CircularStatisticsMixin().sliding_mean_resultant_vector_length(data=data.astype(np.float32),time_windows=np.array([0.5]), fps=10)


# sample_1 = np.deg2rad([10, 40, 90, 100, 90])
# sample_2 = np.deg2rad([10, 40, 90, 100, 1])
#
#
# # sample_2 = np.random.randint(low=0, high=360, size=(100,)).astype(np.float32)
# # D = CircularStatisticsMixin().sliding_kuipers_two_sample_test(sample_1=sample_1, sample_2=sample_2, time_windows=np.array([0.5, 5]), fps=2)
#
# D = CircularStatisticsMixin().watson_williams_test(sample_1=sample_1, sample_2=sample_2)
# print(D)