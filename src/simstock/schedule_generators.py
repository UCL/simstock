import pandas as pd
import numpy as np

class UnifiedScheduleManager:
    """
    A schedule manager that, for each day in a (user-specified) date range,
    uses one daily occupancy block if it's a weekday (Mon-Fri),
    and another daily occupancy block if it's weekend (Sat/Sun).
    Lighting/equipment are scaled from occupancy. Heating/cooling remain constant.

    The daily pattern is repeated for each day in the range,
    but the weekday pattern is chosen randomly once, and
    the weekend pattern is chosen randomly once (in __init__).
    """

    def __init__(self, random_seed=None, freq="10T", days=14):
        """
        :param random_seed: for reproducible randomness
        :param freq: e.g. "10T" for 10-minute intervals
        :param days: how many total days you want to generate 
                     starting from 2025-01-01
        """
        self.random_seed = random_seed
        if random_seed is not None:
            np.random.seed(random_seed)
        self.freq = freq
        self.days = days

        # Pre-generate the occupant "template" for weekdays vs. weekends:
        #   self.weekday_block = (start_hour, end_hour, amplitude)
        #   self.weekend_block = (start_hour, end_hour, amplitude)
        self.weekday_block = self._random_daily_block_params("weekday")
        self.weekend_block = self._random_daily_block_params("weekend")

    def get_schedules_for_zone(self, usage_type: str, zone_name: str):
        """
        Return a dictionary of time series:
          { "occupancy", "lighting", "equipment",
            "heating", "cooling" }
        each with freq resolution over 'days' days.

        Occ. = 1 daily block for weekday vs. 1 daily block for weekend.
        Lighting/equipment scale from occupancy.
        Heating/cooling are constant.
        """
        # 1) build the date/time index
        self.weekday_block = self._random_daily_block_params("weekday")
        self.weekend_block = self._random_daily_block_params("weekend")
        index = self._build_index()

        # 2) occupant fraction
        occ_series = self._gen_occupancy(usage_type, index)

        # 3) other schedules
        light_series = self._gen_lighting(usage_type, index, occ_series)
        equip_series = self._gen_equipment(usage_type, index, occ_series)
        heat_series = self._gen_heating(usage_type, index)
        cool_series = self._gen_cooling(usage_type, index)

        return {
            "occupancy": occ_series,
            "lighting": light_series,
            "equipment": equip_series,
            "heating": heat_series,
            "cooling": cool_series
        }

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _build_index(self):
        """Build a date range from 2025-01-01 up to N days, at given freq."""
        steps_per_day = (24 * 60) // self._freq_to_minutes()
        total_steps = steps_per_day * self.days
        return pd.date_range("2025-01-01", periods=total_steps, freq=self.freq)

    def _freq_to_minutes(self):
        return int(self.freq.replace("T", ""))

    def _random_daily_block_params(self, usage_type="weekday"):
        """
        Returns (start_hour, end_hour, amplitude).

        If usage_type == 'weekday', we do one random block 
        (e.g. 7..9 start, 16..20 end, amplitude 0.4..0.8).
        If usage_type == 'weekend', do a different range.
        """
        if usage_type == "weekday":
            start_hour = np.random.randint(7, 10)     # e.g. 7..9
            end_hour   = np.random.randint(16, 21)   # e.g. 16..20
            amp = np.random.uniform(0.4, 0.8)
        else:
            # weekend
            start_hour = np.random.randint(9, 12)    # e.g. 9..11
            end_hour   = np.random.randint(14, 20)   # e.g. 14..19
            amp = np.random.uniform(0.2, 0.6)

        if end_hour <= start_hour:
            end_hour = start_hour + 4
        return (start_hour, end_hour, amp)

    def _gen_occupancy(self, usage_type, index):
        """
        For each day in index:
          If day_of_week < 5 => weekday, use self.weekday_block
          else => weekend_block

        Fill occupant fraction start_hour..end_hour = amplitude, else 0.
        """
        values = np.zeros(len(index))

        for day in sorted(set(index.date)):
            # Monday=0, Sunday=6 => day_of_week
            day_of_week = pd.Timestamp(day).dayofweek
            if day_of_week < 5:
                # weekday
                (start_hour, end_hour, amp) = self.weekday_block
            else:
                # weekend
                (start_hour, end_hour, amp) = self.weekend_block

            # fill occupant fraction for that day
            mask = (
                (index.date == day)
                & (index.hour >= start_hour)
                & (index.hour < end_hour)
            )
            values[mask] = amp

        return pd.Series(values, index=index)

    def _gen_lighting(self, usage_type, index, occupancy_series):
        """
        e.g. lighting fraction = 0.1 + factor * occupancy
        for dwell => factor=0.8, otherwise factor=0.9
        """
        base = 0.1
        factor = 0.8 if usage_type.lower() == "dwell" else 0.9
        arr = base + factor * occupancy_series.values
        return pd.Series(np.clip(arr, 0.0, 1.0), index=index)

    def _gen_equipment(self, usage_type, index, occupancy_series):
        """eq fraction = 0.05 + 0.5 * occupant"""
        base = 0.05
        factor = 0.5
        arr = base + factor * occupancy_series.values
        return pd.Series(np.clip(arr, 0.0, 1.0), index=index)

    def _gen_heating(self, usage_type, index):
        """constant setpoint by usage_type"""
        if usage_type.lower() == "dwell":
            return pd.Series(20.0, index=index)
        elif usage_type.lower() == "commercial":
            return pd.Series(19.0, index=index)
        else:
            return pd.Series(19.5, index=index)

    def _gen_cooling(self, usage_type, index):
        """constant setpoint by usage_type"""
        if usage_type.lower() == "dwell":
            return pd.Series(26.0, index=index)
        elif usage_type.lower() == "commercial":
            return pd.Series(25.0, index=index)
        else:
            return pd.Series(25.5, index=index)
