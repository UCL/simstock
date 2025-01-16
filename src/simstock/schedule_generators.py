import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional
from simstock._utils._timeseries_methods import _timeseries_day_to_lumps


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
    def activity_series_for_day(self, day_of_week: int) -> pd.Series:
        """Return occupant activity (Watts/person) for day_of_week."""

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
        
    # Optional infiltration series (daily lumps). Return None if not implemented.
    def infiltration_series_for_day(self, day_of_week: int) -> Optional[pd.Series]:
        return None

    # Optional infiltration ACH single number. Return None if not implemented.
    def infiltration_ach(self) -> Optional[float]:
        return None

    # Optional ventilation series. Return None if not implemented.
    def ventilation_series_for_day(self, day_of_week: int) -> Optional[pd.Series]:
        return None

    # Optional ventilation ACH single number. Return None if not implemented.
    def ventilation_ach(self) -> Optional[float]:
        return None



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
        

    def get_rule_obj(self, usage_type: str):
        key = usage_type.lower().strip()
        if key not in self._rules:
            raise KeyError(f"No rule defined for usage type '{usage_type}'")
        return self._rules[key]


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
            "activity":  [... lines ...],
            "lighting":  [... lines ...],
            "equipment": [... lines ...],
            "heating":   [... lines ...],
            "cooling":   [... lines ...]
          }
        Each item is a list of strings suitable for 
        SCHEDULE:COMPACT in EnergyPlus.
        """
        key = usage_type.lower()
        if key not in self._rules:
            raise KeyError(f"No rule defined for usage type '{usage_type}'")

        rule_obj = self._rules[key]

        # occupant fraction (clamp 0..1)
        occ_lines = self._build_weekly_lumps(rule_obj, "occupant", clamp_fraction=True)

        # occupant activity schedule (W/person) if rule_obj implements it;
        # else fallback to all-constant 100 W/person
        try:
            act_lines = self._build_weekly_lumps(rule_obj, "activity", clamp_fraction=False)
        except AttributeError:
            # the user might not have 'activity_series_for_day(...)'
            # so we produce a single all-day constant
            act_lines = self._constant_all_day(100.0)

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
            "activity":  act_lines,
            "lighting":  light_lines,
            "equipment": equip_lines,
            "heating":   heat_lines,
            "cooling":   cool_lines
        }


    def _build_weekly_lumps(
        self,
        rule_obj: TimeseriesUsageRule,
        what: str,
        clamp_fraction=False
        ) -> list[str]:
        """
        For day_of_week in [0..6], call the rule's occupant/lights/equipment/
        heating/cooling or activity method => get a single-day time series 
        => lumps => produce lines for SCHEDULE:COMPACT.

        Example output lines for occupant fraction:
          [
            "Through: 12/31",
            "For: Monday",
            "   Until: 07:00, 0.0,",
            "   Until: 16:30, 0.6,",
            "   Until: 24:00, 0.0,",
            "For: Tuesday",
            ...
            "For: Sunday",
            "   Until: 24:00, 0.0;"
          ]
        """
        lines = []
        lines.append("Through: 12/31")

        # pick the appropriate method
        if what == "occupant":
            get_series_for_day = rule_obj.occupant_series_for_day
        elif what == "activity":
            get_series_for_day = rule_obj.activity_series_for_day
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

        day_names = [
            "Monday","Tuesday","Wednesday","Thursday",
            "Friday","Saturday","Sunday"
        ]

        for i, day_name in enumerate(day_names):
            day_series = get_series_for_day(i)  # single-day pd.Series
            lumps = _timeseries_day_to_lumps(day_series, clamp_0_1=clamp_fraction)

            # "For: Monday" line
            lines.append(f"For: {day_name}")

            # lumps might end with trailing commas. If it's Sunday, 
            # convert the final lumps line from e.g. "   Until: 24:00, 0.0," => "   Until: 24:00, 0.0;"
            if i == len(day_names) - 1 and lumps:
                lumps[-1] = lumps[-1].rstrip(",") + ""
            lines.extend(lumps)

        return lines


    def _constant_all_day(self, value: float) -> list[str]:
        """
        Return a lumps schedule that simply sets the value all day, 
        for Monday..Sunday, through 12/31. For example, 
        an occupant activity schedule that is always 100 W/person.
        """
        lines = []
        lines.append("Through: 12/31")
        day_names = [
            "Monday","Tuesday","Wednesday","Thursday",
            "Friday","Saturday","Sunday"
        ]
        for i, day in enumerate(day_names):
            lines.append(f"For: {day}")
            if i < 6:
                # not the last day
                lines.append(f"   Until: 24:00, {value}")
            else:
                # last day
                lines.append(f"   Until: 24:00, {value}")
        return lines
