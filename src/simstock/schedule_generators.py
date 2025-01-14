import numpy as np
import pandas as pd
from abc import ABC, abstractmethod


class UnifiedScheduleManager:
    """
    A lumps-based schedule manager that, for each day-of-week 
    (Mon..Sun), generates one occupant/lighting/equipment block 
    and a single all-day heating/cooling setpoint.

    It returns lines that look like valid SCHEDULE:COMPACT lines, for example:

      Through: 12/31,
      For: Monday,
         Until: 06:00, 0.0,
         Until: 12:00, 0.6,
         Until: 24:00, 0.0,
      For: Tuesday,
         ...
      For: Sunday,
         Until: 24:00, 0.0;

    Notice each day is ended with a trailing comma, except Sunday 
    ends with a semicolon.
    """

    def __init__(self, random_seed=None):
        """
        :param random_seed: optional integer to fix the random generator 
                            for reproducible runs.
        """
        if random_seed is not None:
            np.random.seed(random_seed)

    def get_schedules_for_zone(self, usage_type: str, zone_name: str):
        """
        Return a dict of lumps-based lines, suitable for direct injection 
        into SCHEDULE:COMPACT objects in EnergyPlus:

          {
             "occupancy": [...],
             "lighting":  [...],
             "equipment": [...],
             "heating":   [...],
             "cooling":   [...]
          }

        Each value is a list of lines for lumps-based schedules. 
        """

        # occupant lumps
        occ_lines    = self._build_weekly_lumps_fraction(usage_type)
        # lighting lumps (base=0.1, scale depends on usage_type)
        if usage_type.lower() == "dwell":
            light_lines  = self._build_weekly_lumps_fraction(usage_type, base_val=0.1, scale=0.8)
        else:
            light_lines  = self._build_weekly_lumps_fraction(usage_type, base_val=0.1, scale=0.9)
        # equipment lumps (base=0.05, scale=0.5)
        equip_lines  = self._build_weekly_lumps_fraction(usage_type, base_val=0.05, scale=0.5)
        # heating lumps
        heat_lines   = self._build_weekly_lumps_setpoint(usage_type, is_cooling=False)
        # cooling lumps
        cool_lines   = self._build_weekly_lumps_setpoint(usage_type, is_cooling=True)

        return {
            "occupancy": occ_lines,
            "lighting":  light_lines,
            "equipment": equip_lines,
            "heating":   heat_lines,
            "cooling":   cool_lines
        }


    def _build_weekly_lumps_fraction(self, usage_type, base_val=0.0, scale=0.6):
        """
        Build lumps for occupant/lighting/equipment fraction:
        One random block each day-of-week. 
        Produces lines that are valid for SCHEDULE:COMPACT, for instance:

        [
          "Through: 12/31,",
          "For: Monday,",
          "   Until: 06:00, 0.0,",
          "   Until: 12:00, 0.5,",
          "   Until: 24:00, 0.0,",
          "For: Tuesday,",
          ...
          "For: Sunday,",
          "   Until: 24:00, 0.0;"
        ]

        We select a random start_hour..end_hour block per day 
        (Monday..Friday one style, Saturday/Sunday another), 
        and an amplitude = base_val + scale*(random in [0.3..0.7]).
        """
        lines = []
        # The top line
        lines.append("Through: 12/31")

        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

        for i, day_name in enumerate(day_names):
            # For Monday..Friday => e.g. start ~ 6..9, for weekend => ~ 8..12
            if i < 5:
                # weekday
                start_hour = np.random.randint(6, 10)
            else:
                # weekend
                start_hour = np.random.randint(8, 12)

            # random duration 4..6 hours
            duration   = np.random.randint(4, 7)
            end_hour   = start_hour + duration
            if end_hour > 24:
                end_hour = 24

            # random amplitude in ~ [0.3..1.0], scaled by base_val
            rand_amp   = np.random.uniform(0.3, 0.7)
            block_amp  = base_val + scale * rand_amp

            # "For: Monday," line
            lines.append(f"For: {day_name}")

            # from 00:00..start => base_val
            if start_hour > 0:
                lines.append(f"   Until: {start_hour:02d}:00, {base_val}")
            # from start..end => block_amp
            lines.append(f"   Until: {end_hour:02d}:00, {block_amp}")
            # from end..24 => base_val
            if i == len(day_names) - 1:
                # last day => semicolon
                lines.append(f"   Until: 24:00, {base_val}")
            else:
                lines.append(f"   Until: 24:00, {base_val}")

        return lines


    def _build_weekly_lumps_setpoint(self, usage_type, is_cooling=False):
        """
        Build lumps for a single setpoint all day for each day-of-week.

        E.g. for dwell usage => 20C heating, 26C cooling, 
             for commercial => 19C heating, 25C cooling, etc.
        """
        # pick setpoints by usage
        if usage_type.lower() == "dwell":
            heat_sp = 20.0
            cool_sp = 26.0
        elif usage_type.lower() == "commercial":
            heat_sp = 19.0
            cool_sp = 25.0
        else:
            heat_sp = 19.5
            cool_sp = 25.5

        sp_val = cool_sp if is_cooling else heat_sp

        lines = []
        lines.append("Through: 12/31")

        day_names = ["Monday","Tuesday","Wednesday","Thursday",
                     "Friday","Saturday","Sunday"]

        for i, day_name in enumerate(day_names):
            lines.append(f"For: {day_name}")
            # same setpoint the entire day
            if i == len(day_names) - 1:
                # final line => semicolon
                lines.append(f"   Until: 24:00, {sp_val}")
            else:
                lines.append(f"   Until: 24:00, {sp_val}")
        return lines


class TimeseriesUsageRule(ABC):
    """
    Each usage type (Dwell, Commercial, etc.) can subclass this.
    The user code only produces numeric time series with
    a DatetimeIndex *for a single day* (or possibly multi-day, 
    but we typically handle day-of-week logic by calling 
    occupant_series_for_day(now)).
    """
    @abstractmethod
    def occupant_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return occupant fraction [0..1] for the given day_of_week (0=Mon..6=Sun)."""

    @abstractmethod
    def lighting_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return lighting fraction [0..1] for day_of_week."""

    @abstractmethod
    def equipment_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return equipment fraction [0..1] for day_of_week."""

    @abstractmethod
    def heating_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return heating setpoint (e.g. degrees C) for day_of_week."""

    @abstractmethod
    def cooling_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return cooling setpoint (e.g. degrees C) for day_of_week."""


class ScheduleManager:
    """
    A manager that holds usage rules (one per usage type).
    Each rule implements day-of-week occupant/lights/equip/heating/cooling.
    The manager lumps those daily time-series into SCHEDULE:COMPACT lines 
    for EnergyPlus.
    """

    def __init__(self):
        self._rules = {} 

    def add_rule(self, usage_type: str, rule_obj):
        """
        Add or override a usage rule for e.g. "dwell", "commercial", etc.

        rule_obj must implement occupant_series_for_day(dow), etc.
        """
        key = usage_type.lower().strip()
        self._rules[key] = rule_obj

    def get_schedules_for_zone(
        self,
        usage_type: str,
        zone_name: str,
        **kwargs
        ) -> dict[str, list[str]]:
        """
        Return a dict of lumps lines, e.g.:
          {
            "occupancy": [... lines ...],
            "lighting":  [... lines ...],
            "equipment": [... lines ...],
            "heating":   [... lines ...],
            "cooling":   [... lines ...]
          }
        Each item is a list of strings for SCHEDULE:COMPACT lines.
        """
        key = usage_type.lower()
        if key not in self._rules:
            raise KeyError(f"No rule defined for usage type '{usage_type}'")

        rule_obj = self._rules[key]

        # occupant fraction (clamp 0..1)
        occ_lines = self._build_weekly_lumps(rule_obj, "occupant", clamp_fraction=True)
        # lighting fraction
        light_lines = self._build_weekly_lumps(rule_obj, "lighting", clamp_fraction=True)
        # equipment fraction
        equip_lines = self._build_weekly_lumps(rule_obj, "equipment", clamp_fraction=True)
        # heating setpoint
        heat_lines = self._build_weekly_lumps(rule_obj, "heating", clamp_fraction=False)
        # cooling setpoint
        cool_lines = self._build_weekly_lumps(rule_obj, "cooling", clamp_fraction=False)

        return {
            "occupancy": occ_lines,
            "lighting":  light_lines,
            "equipment": equip_lines,
            "heating":   heat_lines,
            "cooling":   cool_lines
        }


    def _build_weekly_lumps(self, rule_obj, what: str, clamp_fraction=False):
        """
        For day_of_week in [0..6], call the rule's occupant/lights/etc. 
        method => get a single-day time series => lumps => produce 
        lines for SCHEDULE:COMPACT.

        We produce lines like:
          [
            "Through: 12/31",
            "For: Monday",
            "   Until: 07:00, 0.0,",
            "   Until: 16:30, 0.6,",
            "   Until: 24:00, 0.0,",
            "For: Tuesday",
            ...
            "For: Sunday",
            "   Until: 24:00, 0.0"
          ]
        """
        lines = []
        lines.append("Through: 12/31")

        # pick the appropriate method
        if what == "occupant":
            get_series_for_day = rule_obj.occupant_series_for_day
        elif what == "lighting":
            get_series_for_day = rule_obj.lighting_series_for_day
        elif what == "equipment":
            get_series_for_day = rule_obj.equipment_series_for_day
        elif what == "heating":
            get_series_for_day = rule_obj.heating_series_for_day
        elif what == "cooling":
            get_series_for_day = rule_obj.cooling_series_for_day
        else:
            raise ValueError(f"Unknown schedule type '{what}'.")

        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

        for i, day_name in enumerate(day_names):
            # get the single-day series
            day_series = get_series_for_day(i)  # day_of_week i
            # compress lumps
            lumps = _timeseries_day_to_lumps(day_series, clamp_0_1=clamp_fraction)

            # "For: Monday" line
            lines.append(f"For: {day_name}")

            # lumps might end with trailing commas. 
            # If it's Sunday, let's make the final line have a semicolon
            if i == 6 and lumps:
                # Sunday => convert the final lumps line 
                # from e.g. "   Until: 24:00, 0.0," => "... 0.0;"
                lumps[-1] = lumps[-1].rstrip(",") + ""

            lines.extend(lumps)

        return lines


def _timeseries_day_to_lumps(day_series: pd.Series, clamp_0_1: bool=False) -> list[str]:
    """
    Convert a single-day Pandas Series with a DatetimeIndex 
    (covering e.g. 2025-01-06 00:00..23:59) into lumps lines:
       [
         "   Until: 06:00, 0.0,",
         "   Until: 12:30, 0.5,",
         "   Until: 24:00, 0.0,"
       ]

    We assume all times lie within the same calendar day. 
    If clamp_0_1=True, clip values to [0,1].
    """
    # 1) sort, clamp if fraction
    s = day_series.sort_index()
    if clamp_0_1:
        s = s.clip(0,1)

    # 2) ensure coverage up to day+24:00
    day_date = s.index[0].normalize()  # e.g. 2025-01-06 00:00
    day_24   = day_date + pd.Timedelta(hours=24)

    # if not ending at 24:00, append final value
    if s.index[-1] < day_24:
        s.loc[day_24] = s.iloc[-1]

    s = s.sort_index()

    # 3) lumps
    lumps = []
    current_val   = s.iloc[0]

    # step through
    for i in range(1, len(s)):
        t = s.index[i]
        v = s.iloc[i]
        if not np.isclose(v, current_val, atol=1e-12):
            # close out from current_start..t
            lumps.append(f"   Until: {_fmt_time(t, day_date)}, {current_val}")
            current_val   = v

    # close final from current_start..24:00
    # note we guaranteed there's a 24:00 point
    lumps.append(f"   Until: 24:00, {current_val}")
    return lumps


def _fmt_time(ts: pd.Timestamp, day_start: pd.Timestamp) -> str:
    """
    Return "HH:MM" or "24:00" if it’s exactly midnight next day.
    """
    hh = ts.hour
    mm = ts.minute
    # if dt is day_start+24 => 24:00
    if hh == 0 and mm == 0 and ts > day_start:
        return "24:00"
    return f"{hh:02d}:{mm:02d}"
