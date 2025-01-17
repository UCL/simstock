import numpy as np
import pandas as pd
from difflib import get_close_matches


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


def _timeseries_to_schedule_compact(name, schedule_series, schedule_type_limits_name='Fraction'):
    """
    Converts a pandas Series into a Schedule:Compact string.
    """
    schedule_compact_str = f"Schedule:Compact,\n    {name},       !- Name\n    {schedule_type_limits_name},  !- Schedule Type Limits Name\n"

    current_month = None
    previous_value = None
    for timestamp, value in schedule_series.iteritems():
        month_day = f"{timestamp.month}/{timestamp.day}"
        if timestamp.hour == 0 and timestamp.minute == 0:
            # Start of a new day
            if current_month != month_day:
                if previous_value is not None:
                    schedule_compact_str += f"    Until: 24:00, {previous_value};\n"
                schedule_compact_str += f"    Through: {month_day},\n    For: AllDays,\n"
                current_month = month_day
            schedule_compact_str += f"    Until: {timestamp.hour + 1}:00, {value},\n"
        else:
            schedule_compact_str += f"    Until: {timestamp.hour + 1}:00, {value},\n"
        previous_value = value

    schedule_compact_str += f"    Until: 24:00, {previous_value};\n"
    return schedule_compact_str


def _timeseries_to_schedule_fields_lumped_daily_repeat(
    schedule_series: pd.Series,
    schedule_type_limits: str = "Fraction",
    repeat_days: int = 365
    ) -> list[str]:
    """
    Convert a *short* time-indexed schedule (e.g. 7 days) into a repeated 
    pattern up to `repeat_days` total, and then produce daily lumps in 
    SCHEDULE:COMPACT format.

    For example, if schedule_series covers 7 distinct calendar days 
    (e.g. 2025-01-01 through 2025-01-07), we replicate that daily pattern 
    ~52 times so that we end up with ~365 days of lumps from 
    2025-01-01 through (2025-01-01 + repeat_days - 1).

    :param schedule_series: 
        A short multi-day time-indexed schedule (like 7 or 14 days).
    :param schedule_type_limits: 
        "Fraction" (default) => clamp 0..1, 
        otherwise "Temperature" etc.
    :param repeat_days:
        How many total days you want in the final schedule.
    :return:
        A list of lines suitable for building SCHEDULE:COMPACT. 
        For example:
          [
            "Through: 1/1",
            "For: AllDays",
            "Until: 07:00, 0.0",
            "Until: 19:00, 0.4",
            ...
            "Through: 12/31",
            "For: AllDays",
            "Until: 24:00, 0.0"
          ]
    """

    # 1) clamp if fraction
    if schedule_type_limits.lower() == "fraction":
        schedule_series = schedule_series.clip(0.0, 1.0)

    # 2) ensure ascending chronological order
    schedule_series = schedule_series.sort_index()

    # 3) figure out how many distinct days are in the original short schedule
    unique_days = sorted(set(schedule_series.index.normalize()))
    if len(unique_days) == 0:
        # no data => just return empty
        return []

    # The start date we'll call day0
    start_day = unique_days[0]  # e.g. 2025-01-01
    # We'll define an end_day for the short schedule:
    end_day = unique_days[-1]   # e.g. 2025-01-07
    short_n_days = (end_day - start_day).days + 1

    # If the user already generated e.g. 14 days but wants 365 repeated, 
    # we will replicate the entire chunk as many times as needed.
    # We'll build a new "long_series" that repeats the short pattern
    # enough times to fill `repeat_days`.

    # 4) Build repeated index
    # The short schedule has short_n_days. We want repeat_days total.
    # We'll replicate the numeric data. 
    short_vals = schedule_series.values
    short_len = len(short_vals)  # total number of points

    # figure out how many times we replicate
    reps_needed = (repeat_days // short_n_days) + 1  # a bit of over-shoot
    # e.g. if short_n_days=7 and repeat_days=365 => reps_needed=53

    import numpy as np
    import pandas as pd

    # replicate the entire array
    repeated_vals = np.tile(short_vals, reps_needed)  
    # e.g. if short_vals had length=1008 (7days@10min steps), 
    # repeated_vals might have 1008*53 = 53424

    # We'll build a new DatetimeIndex that starts exactly at 
    # "start_day 00:00" and extends for repeat_days, 
    # in the same freq as the original schedule_series. 
    # We'll deduce freq from the original index if possible:
    freq_str = schedule_series.index.inferred_freq
    if freq_str is None:
        # fallback => guess 10T or let user pass freq
        freq_str = "10T"

    repeated_len = len(repeated_vals)
    # define a new index from start_day for repeated_len steps
    # We interpret start_day as midnight of that calendar day:
    start_dt = pd.Timestamp(start_day.year, start_day.month, start_day.day, 0, 0)
    new_index = pd.date_range(
        start=start_dt, 
        periods=repeated_len, 
        freq=freq_str
    )

    # Now we only want the first `repeat_days` worth of calendar days 
    # from that new_index. Let's figure out the cutoff date:
    final_day = start_day + pd.Timedelta(days=repeat_days - 1)
    # We'll keep data up to final_day + 23:59
    final_dt = pd.Timestamp(final_day.year, final_day.month, final_day.day, 23, 59)

    # Build the repeated series, then slice
    long_series = pd.Series(repeated_vals, index=new_index)
    # slice to final_dt
    long_series = long_series[long_series.index <= final_dt]

    # Now `long_series` covers from day0 to day0+(repeat_days-1), 
    # with lumps repeated from the short pattern.

    # 5) Lump day-by-day into lines
    return _build_daily_lumped_lines(long_series, schedule_type_limits)


def _build_daily_lumped_lines(
    full_series: pd.Series, 
    schedule_type_limits="Fraction"
    ) -> list[str]:
    """
    Like original "timeseries_to_schedule_fields_lumped_daily" 
    but without repeating logic. Just lumps day by day.
    """
    # ensure ascending
    full_series = full_series.sort_index()

    lines = []
    unique_dates = sorted(set(full_series.index.normalize()))

    for day in unique_dates:
        day_slice = full_series[full_series.index.normalize() == day]
        if day_slice.empty:
            continue

        # "Through: M/D"
        m = day.month
        d = day.day
        lines.append(f"Through: {m}/{d}")
        # "For: AllDays"
        lines.append("For: AllDays")

        # day_00, day_24
        day_00 = pd.Timestamp(day.year, day.month, day.day, 0, 0)
        day_24 = day_00 + pd.Timedelta(hours=24)

        # if first record is after day_00 => add a point at day_00
        if day_slice.index[0] > day_00:
            first_val = day_slice.iloc[0]
            day_slice = pd.concat([
                pd.Series([first_val], index=[day_00]),
                day_slice
            ])

        # if last record is < day_24 => add a point at day_24
        if day_slice.index[-1] < day_24:
            last_val = day_slice.iloc[-1]
            day_slice = pd.concat([
                day_slice,
                pd.Series([last_val], index=[day_24])
            ])

        # lump the intervals
        current_val = day_slice.iloc[0]
        current_start = day_slice.index[0]

        for i in range(1, len(day_slice)):
            t = day_slice.index[i]
            v = day_slice.iloc[i]
            if not np.isclose(v, current_val, atol=1e-9):
                # close out [current_start, t)
                line = _build_until_line(current_start, t, current_val)
                lines.append(line)
                current_val = v
                current_start = t

        # final close
        final_t = day_slice.index[-1]
        line = _build_until_line(current_start, final_t, current_val, last_segment=True)
        lines.append(line)

    return lines


def _build_until_line(start_ts, end_ts, val, last_segment=False) -> str:
    """
    Return a string like "Until: HH:MM, value".
    We'll decide commas vs semicolons later.
    """
    hh = end_ts.hour
    mm = end_ts.minute
    # If end_ts is exactly next day 00:00 => interpret as 24:00
    if hh == 0 and mm == 0 and (end_ts.normalize() > start_ts.normalize()):
        hh = 24
        mm = 0

    return f"Until: {hh:02d}:{mm:02d}, {val}"


def _build_until_field(start_ts, end_ts, val, last=False) -> str:
    """
    Return something like "Until: HH:MM, VAL"
    *without* the trailing comma or semicolon appended here.

    We'll let the top-level code decide how to place commas vs semicolons.

    If you want to interpret 'end_ts' = next day 00:00 as 24:00,
    do so in the hour extraction.

    If 'last=True', the caller might interpret that as
    "this is the last line in this daily block".
    """
    # figure out hour:minute for end_ts
    # if hour=0 and minute=0 and the date is next day -> treat as 24:00
    # A simpler approach:
    hh = end_ts.hour
    mm = end_ts.minute
    # If we do see exactly 00:00 and it's the next day, call that 24:00
    if hh == 0 and mm == 0:
        # check if end_ts.date() > start_ts.date()
        if end_ts.normalize() > pd.Timestamp(start_ts.date()):
            hh = 24
            mm = 0

    time_str = f"{hh:02d}:{mm:02d}"
    return f"Until: {time_str}, {val}"


def finalise_schedule_compact_block(
    schedule_name: str,
    schedule_type: str,
    fields: list[str]
    ) -> list[str]:
    """
    Given a schedule name, schedule type, and the raw fields
    (like "Through: 1/1", "For: AllDays", "Until: 07:00, 0.6", ...),
    build a canonical IDF SCHEDULE:COMPACT block with commas/semicolons
    in standard format:

    [
       "SCHEDULE:COMPACT,",
       "    MyScheduleName,",
       "    Fraction,",
       "    Through: 1/1,",
       "    For: AllDays,",
       "    Until: 07:00, 0.0,",
       "    Until: 17:00, 0.65;",
    ]

    The caller can then do '\n'.join(...) on that if desired.
    """
    result = []
    # The object header
    result.append("SCHEDULE:COMPACT,")
    # field 1: the schedule name
    # field 2: schedule type
    # afterwards: all the lines from 'fields'
    # but we need to carefully put commas vs. semicolons
    all_fields = [schedule_name, schedule_type] + fields

    for i, fval in enumerate(all_fields):
        # If not last => comma, if last => semicolon
        if i < len(all_fields) - 1:
            result.append(f"    {fval},")
        else:
            result.append(f"    {fval};")
    return result


def _create_until_line(start_time, end_time, val, last_segment=False):
    """
    Build something like "Until: HH:MM, val," 
    or final line with a semicolon. 
    We approximate the 'Until' time as the end_time 
    in HH:MM format.

    If you want daily breaks, you'd add logic to 
    handle day boundaries, etc.
    """
    # We'll do "Until: HH:MM, val," 
    # if not last_segment, else we end with ";"

    time_str = _timestamp_to_hhmm(end_time)
    line = f"Until: {time_str}, {val}"
    if last_segment:
        line += ";"
    else:
        line += ","
    return line

def _timestamp_to_hhmm(ts):
    """
    Convert a timestamp or partial timestamp to HH:MM string.
    If you want to consider multi-day, you'll need more advanced logic:
    e.g., "Through: 1/31, For: AllDays".
    """
    if hasattr(ts, "hour"):
        hh = ts.hour
        mm = ts.minute
        return f"{hh:02d}:{mm:02d}"
    # fallback if numeric
    return f"{int(ts):02d}:00"


def _time_to_str(timestamp):
    """
    Convert a timestamp to "HH:MM" for the IDF line. 
    If you want to handle multi-day properly, you'd 
    need a more robust approach (like 'Through: 1/30, For: AllDays, ...').
    """
    if hasattr(timestamp, "hour"):
        hh = timestamp.hour
        mm = timestamp.minute
        return f"{hh:02d}:{mm:02d}"
    else:
        # fallback if numeric
        return f"{timestamp}:00"
