import pandas as pd
import numpy as np
from simstock import SimstockDataframe
from simstock._utils._output_handling import _get_building_file_dict
from simstock._utils._timeseries_methods import _extract_timeseries


def add_overheating_columns(sdf: SimstockDataframe) -> None:

    d = _get_building_file_dict("outs")

    # Add some columns
    totfloors = 0
    for column_name in sdf.columns:
        if str(column_name).startswith("FLOOR_"):
            totfloors += 1
    for i in range(totfloors):
        sdf[f"FLOOR_{i+1}: max_temp"] = None
        sdf[f"FLOOR_{i+1}: perc_above_26"] = None
        sdf[f"FLOOR_{i+1}: criterion1"] = None
        sdf[f"FLOOR_{i+1}: criterion2"] = None
        sdf[f"FLOOR_{i+1}: criterion3"] = None
        sdf[f"FLOOR_{i+1}: overheated"] = None
        sdf[f"SCU_overheated"] = None
     
    # Iterate over the SCUs
    for j, scu in enumerate(sdf.osgb):
        print(f"\r{j+1} of {len(sdf.osgb)}", flush=True, end="")

        # Find how many floors the scu has
        row = sdf[sdf["osgb"]==scu]
        num_floors = count_floor_columns_without_nan(row)

        # Iterate over the floors and for each one extract a timeseries of 
        # the operative temperature
        is_scu_overheated = False
        for i in range(num_floors):
            attribute = f"{scu}_FLOOR_{i+1}:Zone Operative Temperature [C](Hourly)"
            op_temp_ts = _extract_timeseries("outs", scu, attribute, d)

            # Calculate the max value
            max_val = op_temp_ts.max()
            sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: max_temp"] = max_val

            # Calculate criterion 1: percentage of time that Top>26, is it more than 3%
            percent_over_thresh = criterion1(op_temp_ts, 30.0, 5, 9)
            sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: perc_above_26"] = percent_over_thresh
            if percent_over_thresh > 3.0:
                crit1 = True
            else:
                crit1 = False
            sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: criterion1"] = crit1

            # Calculate criterion 2: the integral measure
            crit2 = criterion2(op_temp_ts, 30.0, 5, 9, 6.0)
            sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: criterion2"] = crit2

            # Calculate criterion 3: the moving window thing
            crit3 = criterion3(scu, i+1, d)
            sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: criterion3"] = crit3

            # See if the criteria for overheating are met
            if (crit1 + crit2 + crit3) >= 2:
                sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: overheated"] = True
                is_scu_overheated = True
            else:
                sdf.loc[sdf["osgb"] == scu, f"FLOOR_{i+1}: overheated"] = False
        
        # Determing if the building contains any overheating
        sdf.loc[sdf["osgb"] == scu, "SCU_overheated"] = is_scu_overheated


def criterion1(series, threshold, start_month, end_month):

    # Filter the Series to include only data within the specified months
    summer_series = series[(series.index.month >= start_month) & (series.index.month <= end_month)]

    # Filter the Series to include only values greater than the threshold
    over_threshold = summer_series[summer_series > threshold]

    # Calculate the percentage of entries over the threshold
    percentage_over_threshold = (len(over_threshold) / len(series)) * 100

    return percentage_over_threshold


def criterion2(series, threshold, start_month, end_month, threshold_integral):

    integral_exceeds_threshold = False

    # Filter the Series to include only data within the specified months
    summer_series = series[(series.index.month >= start_month) & (series.index.month <= end_month)]

    # Calculate the excess temperatures above the threshold for each time interval
    excess_temperatures = summer_series - threshold
    excess_temperatures[excess_temperatures < 0] = 0  # Set negative values to 0    

    # Iterate over each day in the specified date range
    unique_days = summer_series.index.floor('D').unique()
    for day in unique_days:

        # Convert the day to an integer index
        day_index = np.where(series.index == day)[0][0]

        # Select the excess temperatures and time intervals for the current day
        day_excess_temperatures = excess_temperatures[day_index: day_index + 24]
        daily_integral = sum(day_excess_temperatures)

        # Check if the integral for the current day exceeds the threshold
        if daily_integral > threshold_integral:
            integral_exceeds_threshold = True
            break  # No need to check other days if one day exceeds the threshold

    return integral_exceeds_threshold


def compute_trm(daily_max_ts):
    # Create a DataFrame with columns representing the daily maximum temperatures for preceding days
    df = pd.DataFrame()
    for i in range(1, 8):
        df[f'Tod_{i}'] = daily_max_ts.shift(i, fill_value=0)

    # Compute the value of Trm using the specified formula
    trm = (df['Tod_1'] + 0.8 * df['Tod_2'] + 0.6 * df['Tod_3'] + 
           0.5 * df['Tod_4'] + 0.4 * df['Tod_5'] + 0.3 * df['Tod_6'] + 
           0.2 * df['Tod_7']) / 3.8

    return trm


def criterion3(scu, floornum, d):

    # Get the outdoor air temp timseries
    attribute = f"{scu}_FLOOR_{floornum}:Zone Outdoor Air Drybulb Temperature [C](Hourly)"
    od_temp_ts = _extract_timeseries("outs", scu, attribute, d)

    # Resample it to get max daily values
    daily_max = od_temp_ts.resample('D').max()

    # Make another time series that performs the moving window thing
    trm_ts = compute_trm(daily_max)
    
    # Make another time series that computes the max for each day via the formula
    tmax = 0.33*trm_ts + 21.8 + 6.0

    # Get the op temp timeseries and limit it to just may to september
    attribute = f"{scu}_FLOOR_{floornum}:Zone Operative Temperature [C](Hourly)"
    op_temp_ts = _extract_timeseries("outs", scu, attribute, d)
    # summer_series = od_temp_ts[(od_temp_ts.index.month >= 5) & (od_temp_ts.index.month <= 9)]

    # Check if any values are over the computed max
    # Align the timestamps of od_temp_ts and trm to the same daily frequency
    op_temp_ts_daily = op_temp_ts.resample('D').max()
    tmax = tmax.reindex(op_temp_ts_daily.index, method='ffill')

    # Check if any od_temp_ts values exceed the corresponding trm values
    exceeds_trm = op_temp_ts_daily >= tmax
    return exceeds_trm.any()
