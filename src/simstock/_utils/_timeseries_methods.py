import os
import pandas as pd
from difflib import get_close_matches
from typing import Union
from _utils._output_handling import (
    _preprocess_datetime_column,
    _get_building_file_dict
)
from simstock import SimstockDataframe

domestic_keywords = {
    "dwell",
    "dwelling",
    "domestic",
    "domecile",
    "house",
    "home",
    "residence", 
    "apartment",
    "flat",
    "bungalow",
    "residential"
    }


def _is_domestic(input_string):
    input_string = input_string.lower().strip()
    closest_match = get_close_matches(input_string, domestic_keywords, n=1, cutoff=0.7)
    return True if closest_match else False


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



def _extract_timeseries(
        file_path: str,
        scu: Union[str, int],
        attribute: str,
        scu_to_bi: dict
        ) -> pd.Series:
    
    try:
        bi_num = scu_to_bi[str(scu)]
    except KeyError as e:
        raise KeyError(f"SCU {scu} not found in results.")
    
    res_path = os.path.join(file_path,
                            f"built_island_{bi_num}_ep_outputs",
                            "eplusout.csv"
                            )
    try:
        df = pd.read_csv(res_path)
    except Exception as e:
        raise FileNotFoundError(f"Could not open {res_path}.") from e
    
    # Preprocess "Date/Time" column
    df["Date/Time"] = df["Date/Time"].apply(_preprocess_datetime_column)

    # Convert "Date/Time" column to datetime format
    df["Date/Time"] = pd.to_datetime(df["Date/Time"], format="%m/%d  %H:%M:%S")

    # Set the index to the "Date/Time" column
    df.set_index("Date/Time", inplace=True)

    # Return just the attibute of interest
    try:
        ts = df[attribute]
    except KeyError as e:
        raise KeyError(f"Column {attribute} not found in results.")
    return ts


def extract_cooling_loads(sdf: SimstockDataframe, file_path: str):

    # Make the dictionary
    d = _get_building_file_dict(file_path)

    # Iteratare over SCUs
    domiter = 0
    nondomiter = 0
    for _, row in sdf.iterrows():
        
        # Get the BI
        scu = row["osgb"]
        try:
            bi_num = d[str(scu)]
        except KeyError as e:
            raise KeyError(f"SCU {scu} not found in results.")

        # Get the file path of the results for this scu
        res_path = os.path.join(file_path,
                                f"built_island_{bi_num}_ep_outputs",
                                "eplusout.csv"
                                )
        
        # Open the results file
        try:
            df = pd.read_csv(res_path)
        except Exception as e:
            raise FileNotFoundError(f"Could not open {res_path}.") from e
        
        # Preprocess "Date/Time" column
        df["Date/Time"] = df["Date/Time"].apply(_preprocess_datetime_column)

        # Convert "Date/Time" column to datetime format
        df["Date/Time"] = pd.to_datetime(df["Date/Time"], format="%m/%d  %H:%M:%S")

        # Set the index to the "Date/Time" column
        df.set_index("Date/Time", inplace=True)

        # Iterate over the floors
        for i in range(1,7):

            # Get the floor usage type
            floor_use = row[f"FLOOR_{i}: use"]
            if not pd.isna(floor_use):

                # If its domestic then add it to the running domestic sum
                if _is_domestic(floor_use):
                    if domiter == 0:
                        running_domsum = df[f"{scu}_FLOOR_{i}_HVAC:Zone Ideal Loads Zone Total Cooling Energy [J](Hourly)"]/(5.4*3600*10**6)
                    else:
                        running_domsum = running_domsum + df[f"{scu}_FLOOR_{i}_HVAC:Zone Ideal Loads Zone Total Cooling Energy [J](Hourly)"]/(5.4*3600*10**6)
                    domiter += 1
                else:
                    if nondomiter == 0:
                        running_nondomsum = df[f"{scu}_FLOOR_{i}_HVAC:Zone Ideal Loads Zone Total Cooling Energy [J](Hourly)"]/(5.4*3600*10**6)
                    else:
                        running_nondomsum = running_nondomsum + df[f"{scu}_FLOOR_{i}_HVAC:Zone Ideal Loads Zone Total Cooling Energy [J](Hourly)"]/(5.4*3600*10**6)
                    nondomiter += 1

    return running_domsum, running_nondomsum
