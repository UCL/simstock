import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional
from simstock._utils._timeseries_methods import _timeseries_day_to_lumps


class TimeseriesUsageRule(ABC):
    """
    Each usage type (Dwell, Commercial, etc.) can subclass this.
    The user code only produces numeric time series with
    a DatetimeIndex *for a single day* (possibly multi-day),
    but we handle day-of-week logic by calling 
    occupant_series_for_day(zone_name, day_of_week).

    Note: We now pass 'zone_name' so that each zone can
    have a unique schedule (e.g., a different random seed).
    """
    @abstractmethod
    def occupant_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return occupant fraction [0..1] for zone_name, day_of_week (0=Mon..6=Sun)."""

    @abstractmethod
    def activity_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return occupant activity (Watts/person) for zone_name, day_of_week."""

    @abstractmethod
    def lighting_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return lighting fraction [0..1] for zone_name, day_of_week."""

    @abstractmethod
    def equipment_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return equipment fraction [0..1] for zone_name, day_of_week."""

    @abstractmethod
    def heating_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return heating setpoint (degC) for zone_name, day_of_week."""

    @abstractmethod 
    def cooling_series_for_day(self, zone_name: str, day_of_week: int) -> pd.Series:
        """Return cooling setpoint (degC) for zone_name, day_of_week."""
     
    # Optional cooling capacity per unit floor area (W/m2). 
    # Return None if not implemented.  
    def nominal_cooling_capacity_w_m2(self) -> Optional[float]:
        return None
    
    # Optional cooling capacity for the whole zone (W). 
    # Return None if not implemented.  
    def nominal_cooling_capacity_w(self) -> Optional[float]:
        return None
        
    # Optional infiltration schedule
    def infiltration_series_for_day(self, zone_name: str, day_of_week: int) -> Optional[pd.Series]:
        return None

    # Optional infiltration ACH single number
    def infiltration_ach(self) -> Optional[float]:
        return None

    # Optional ventilation schedule
    def ventilation_series_for_day(self, zone_name: str, day_of_week: int) -> Optional[pd.Series]:
        return None

    # Optional ventilation ACH single number
    def ventilation_ach(self) -> Optional[float]:
        return None
    
    def is_fractional_schedule(self, schedule_type: str) -> bool:
        """
        Default: occupant, lighting, equipment => fractional [0..1].
        Heating/cooling => not fractional. Subclasses override as needed.
        """
        if schedule_type in ["occupant", "lighting", "equipment"]:
            return True
        return False


class ScheduleManager:
    """
    A manager that holds usage rules (one per usage type).
    Each rule implements day-of-week occupant/lights/equipment/heating/cooling
    for each zone. The manager lumps those daily time-series into
    SCHEDULE:COMPACT lines for EnergyPlus.
    """
    def __init__(self):
        self._rules = {}

    def add_rule(self, usage_type: str, rule_obj):
        """
        Add or override a usage rule for e.g. "dwell", "commercial", etc.

        rule_obj must implement occupant_series_for_day(zone_name, dow), etc.
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
        Each item is a list of strings suitable for SCHEDULE:COMPACT in EnergyPlus.
        
        This version calls `rule_obj.is_fractional_schedule(schedule_type)`
        to decide whether we clamp values to [0..1] or preserve them as-is.
        """
        # lookup the rule object
        key = usage_type.lower()
        if key not in self._rules:
            raise KeyError(f"No rule defined for usage type '{usage_type}'")
        rule_obj = self._rules[key]

        # 1) occupant fraction
        occ_clamp = rule_obj.is_fractional_schedule("occupant")
        occ_lines = self._build_weekly_lumps(rule_obj, "occupant", zone_name, clamp_fraction=occ_clamp)

        # 2) occupant activity (W/person or absolute W)
        #    If the rule doesn't implement "activity_series_for_day", fallback is a constant 100
        try:
            act_clamp = rule_obj.is_fractional_schedule("activity")
            act_lines = self._build_weekly_lumps(rule_obj, "activity", zone_name, clamp_fraction=act_clamp)
        except AttributeError:
            act_lines = self._constant_all_day(100.0)

        # 3) lighting
        light_clamp = rule_obj.is_fractional_schedule("lighting")
        light_lines = self._build_weekly_lumps(rule_obj, "lighting", zone_name, clamp_fraction=light_clamp)

        # 4) equipment
        equip_clamp = rule_obj.is_fractional_schedule("equipment")
        equip_lines = self._build_weekly_lumps(rule_obj, "equipment", zone_name, clamp_fraction=equip_clamp)

        # 5) heating (°C => typically no clamp)
        heat_clamp = rule_obj.is_fractional_schedule("heating")
        heat_lines = self._build_weekly_lumps(rule_obj, "heating", zone_name, clamp_fraction=heat_clamp)

        # 6) cooling (°C => typically no clamp)
        cool_clamp = rule_obj.is_fractional_schedule("cooling")
        cool_lines = self._build_weekly_lumps(rule_obj, "cooling", zone_name, clamp_fraction=cool_clamp)

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
        rule_obj,
        what: str,
        zone_name: str,
        clamp_fraction: bool = False
        ) -> list[str]:
        """
        For day_of_week in [0..6], call e.g. rule_obj.occupant_series_for_day(zone_name, day_of_week)
        => lumps => produce lines for SCHEDULE:COMPACT.
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
            # Now call the zone-based method
            day_series = get_series_for_day(zone_name, i)
            lumps = _timeseries_day_to_lumps(day_series, clamp_0_1=clamp_fraction)

            lines.append(f"For: {day_name}")

            # If it's Sunday, remove trailing comma from final lumps line
            if i == len(day_names) - 1 and lumps:
                lumps[-1] = lumps[-1].rstrip(",")
            lines.extend(lumps)

        return lines

    def _constant_all_day(self, value: float) -> list[str]:
        """
        Return lumps that set 'value' all day, for Monday..Sunday,
        "Through: 12/31". E.g. occupant activity that is always 100 W/p.
        """
        lines = []
        lines.append("Through: 12/31")
        day_names = [
            "Monday","Tuesday","Wednesday","Thursday",
            "Friday","Saturday","Sunday"
        ]
        for i, day in enumerate(day_names):
            lines.append(f"For: {day}")
            # We produce a single lumps line 
            if i < 6:
                lines.append(f"   Until: 24:00, {value}")
            else:
                # final day => no trailing comma
                lines.append(f"   Until: 24:00, {value}")
        return lines
