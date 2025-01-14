import numpy as np

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

    # ----------------------------------------------------------------
    # Example lumps-based methods
    # ----------------------------------------------------------------

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
