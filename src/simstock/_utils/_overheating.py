import os
import sqlite3
import pandas as pd
import numpy as np


def _compute_criterion1(series, threshold, percentage_threshold):
    """
    Computes whether the percentage of time a temperature series exceeds a threshold
    is greater than a given percentage threshold.

    Args:
        series (pd.Series): Timeseries of temperature data.
        threshold (float): Temperature threshold above which a value is considered "overheated."
        percentage_threshold (float): Percentage of time above the threshold required to meet this criterion.

    Returns:
        bool: True if the percentage of time above the threshold exceeds the percentage threshold, False otherwise.
    """
    # Identify values in the series that exceed the threshold
    over_threshold = series[series > threshold]

    # Calculate the percentage of time the series exceeds the threshold
    percentage_over_threshold = (len(over_threshold) / len(series)) * 100

    # Return True if the percentage exceeds the threshold, False otherwise
    return percentage_over_threshold > percentage_threshold


def _compute_criterion2(series, threshold, integral_threshold):
    """
    Computes whether the daily integral of excess temperature above a threshold exceeds
    a specified threshold on any day.

    Args:
        series (pd.Series): Timeseries of temperature data.
        threshold (float): Temperature threshold above which a value contributes to the integral.
        integral_threshold (float): Threshold for the daily integral to meet this criterion.

    Returns:
        bool: True if the integral threshold is exceeded on any day, False otherwise.
    """
    # Calculate excess temperatures above the threshold
    excess_temperatures = series - threshold

    # Set any negative values (below the threshold) to 0
    excess_temperatures[excess_temperatures < 0] = 0

    # Resample to daily frequency and calculate the daily integral of excess temperatures
    daily_integrals = excess_temperatures.resample("D").sum()

    # Check if any day's integral exceeds the threshold
    return (daily_integrals > integral_threshold).any()


def _compute_trm(daily_max_ts):
    """
    Computes the running mean temperature (Trm) based on daily maximum outdoor temperatures
    over the past 7 days, using a weighted formula.

    Args:
        daily_max_ts (pd.Series): Timeseries of daily maximum outdoor temperatures.

    Returns:
        pd.Series: Timeseries of running mean temperatures (Trm).
    """
    # Create a DataFrame to hold the shifted values of the daily maximum temperatures
    df = pd.DataFrame()

    # Shift the timeseries to create columns for the past 7 days
    for i in range(1, 8):
        df[f"Tod_{i}"] = daily_max_ts.shift(i, fill_value=0)

    # Calculate the weighted running mean temperature
    trm = (df["Tod_1"] + 0.8 * df["Tod_2"] + 0.6 * df["Tod_3"] +
           0.5 * df["Tod_4"] + 0.4 * df["Tod_5"] + 0.3 * df["Tod_6"] +
           0.2 * df["Tod_7"]) / 3.8

    return trm


def _compute_criterion3(outdoor_temp, indoor_temp, offset):
    """
    Computes whether the maximum daily indoor temperature exceeds the adaptive comfort threshold
    on any day. The adaptive comfort threshold is based on the running mean outdoor temperature (Trm).

    Args:
        outdoor_temp (pd.Series): Timeseries of outdoor temperatures.
        indoor_temp (pd.Series): Timeseries of indoor temperatures.
        offset (float): Offset added to the adaptive comfort threshold.

    Returns:
        bool: True if the maximum daily indoor temperature exceeds the threshold on any day, False otherwise.
    """
    # Calculate the daily maximum outdoor temperatures
    daily_max_outdoor = outdoor_temp.resample("D").max()

    # Compute the running mean temperature (Trm) based on the outdoor temperatures
    trm = _compute_trm(daily_max_outdoor)

    # Calculate the adaptive comfort threshold (Tmax) using Trm
    tmax = 0.33 * trm + 18.8 + offset

    # Calculate the daily maximum indoor temperatures
    daily_max_indoor = indoor_temp.resample("D").max()

    # Align the Tmax index with the indoor temperature index
    tmax = tmax.reindex(daily_max_indoor.index, method="ffill")

    # Check if the indoor temperature exceeds the threshold on any day
    return (daily_max_indoor >= tmax).any()



def _add_overheating_flags(
        out_dir: str,
        df: pd.DataFrame,
        threshold: float,
        percentage_threshold: float,
        integral_threshold: float,
        offset: float,
    ) -> pd.DataFrame:
    """
    Adds overheating flags for each floor of each building in the DataFrame.

    Args:
        out_dir (str): Directory where the SQLite database is located.
        df (pd.DataFrame): DataFrame containing a column 'osgb' for building IDs.
        threshold (float): Temperature threshold for overheating criteria.
        percentage_threshold (float): Percentage of time above the threshold for criterion 1.
        integral_threshold (float): Daily integral threshold for criterion 2.
        offset (float): Offset for criterion 3 (adaptive comfort model).

    Returns:
        pd.DataFrame: The input DataFrame with overheating flags for each floor.
    """

    # Connect to the SQLite database
    db_path = os.path.join(out_dir, "summary_database.db")
    conn = sqlite3.connect(db_path)

    try:
        for index, row in df.iterrows():
            building_id = row["osgb"]
            overheating_flags = []

            # Dynamically determine the floors for the building
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(indoor_temperature);")
            all_columns = [col[1] for col in cursor.fetchall()]
            floor_columns = [col for col in all_columns if col.startswith(f"{building_id.upper()}_FLOOR_")]

            if not floor_columns:
                print(f"Warning: No floors found for building {building_id}. Skipping.")
                continue

            # Iterate over the floors
            for floor_col in floor_columns:
                overheating_criteria = []

                try:
                    # Fetch the temperature timeseries for the floor
                    temp_series = pd.read_sql_query(
                        f"SELECT timestamp, {floor_col} AS value FROM indoor_temperature;",
                        conn,
                        index_col="timestamp"
                    )["value"]

                    # Ensure the index is a DatetimeIndex
                    temp_series.index = pd.to_datetime(temp_series.index)

                    # Apply Criterion 1
                    c1 = _compute_criterion1(temp_series, threshold, percentage_threshold)
                    overheating_criteria.append(c1)

                    # Apply Criterion 2
                    c2 = _compute_criterion2(temp_series, threshold, integral_threshold)
                    overheating_criteria.append(c2)

                    # Criterion 3 (adaptive comfort model) not applicable due to lack of outdoor temperature.
                    # Assuming Criterion 3 is skipped.
                    c3 = False  # Replace this if outdoor data becomes available.
                    overheating_criteria.append(c3)

                    # Overheated if at least 2 criteria are met
                    is_overheated = sum(overheating_criteria) >= 1
                    overheating_flags.append(is_overheated)

                except Exception as e:
                    print(f"Warning: Failed to process data for {building_id}, {floor_col}. Error: {e}")
                    overheating_flags.append(False)

            # Add overheating flags for the building's floors to the DataFrame
            for floor_index, is_overheated in enumerate(overheating_flags, start=1):
                column_name = f"FLOOR_{floor_index}_overheated"
                df.loc[index, column_name] = is_overheated

    finally:
        conn.close()

    return df
