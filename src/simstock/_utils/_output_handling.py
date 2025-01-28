import os
import sqlite3
import subprocess
import pandas as pd
from difflib import get_close_matches
from datetime import datetime


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


def _get_building_file_dict(file_path: str) -> dict:
    """
    Function to return a dictionary mapping built island numbers
    to output file numbers.

    Returns
    -------
    bi_to_file: dict
        A dictionary whose keys are built island numbers
        and values are file numbers.
    """
    # Check if the provided path exists
    if not os.path.exists(file_path):
        raise NotADirectoryError(f"{file_path} not found.")
    
    # Compile a dictionary whose keys are the building name and 
    # vars are the file number
    bi_to_file_dict = {}
    
    # Iterate over the directories in the provided path
    # and find any starting with "built_island"
    for root, dirs, _ in os.walk(file_path):
        for directory in dirs:
            if directory.startswith("built_island"):

                # Get the built island number
                bi_num = int(directory.split("_")[2])

                # Read the eso file
                esopath = os.path.join(root, directory, "eplusout.eso")
                with open(esopath, 'r') as file:
                    eso_content = file.read()

                # Split the content into lines
                lines = eso_content.split('\n')

                # Iterate over the lines sequentially
                scu_list = []
                for l in lines:
                    line = l.split(",")

                    # Check if we have come to the end of the file's data dictionary
                    if line[0].strip() == "End of Data Dictionary":
                        break
                    
                    # Take the third thing in the line and split it and 
                    # see if it contains the word FLOOR
                    if "FLOOR" in line[2]:
                        tag_phrases = line[2].split(":")
                        for phrase in tag_phrases:
                            if "FLOOR" in phrase:
                                scu_list.append(phrase.split("_")[0])

                # Get just the unique scus in this file and add them to the dict
                for building in list(set(scu_list)):
                    bi_to_file_dict[building] = bi_num

    return bi_to_file_dict


def _make_output_csvs(file_path: str, readvarseso_path: str) -> None:

    # Check if the provided path exists
    if not os.path.exists(file_path):
        raise NotADirectoryError(f"Output file path {file_path} not found.")
    
    # Iterate over the directories in the provided path
    # and find any starting with "built_island"
    for root, dirs, _ in os.walk(file_path):
        for directory in dirs:
            if directory.startswith("built_island"):

                # Get the path to this built island
                island_path = os.path.join(root, directory)
                
                # Generate an rvi file within this directory
                _generate_rvi(island_path)

                # Run ReadVarESO within this directory
                _run_readvarseso(readvarseso_path, island_path)


def _generate_rvi(file_path: str) -> None:
    with open (os.path.join(file_path, "results-rvi.rvi"), "w") as f:
        f.write("eplusout.eso\neplusout.csv\n0")
        
        
def _run_readvarseso(readvarseso_path: str, file_path: str) -> None:
    try:
        subprocess.run([readvarseso_path , "results-rvi.rvi", "unlimited"], cwd=file_path)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"The readVarsESO executable could not be found at {readvarseso_path}") from e


def _process_timestamp(dt: str, year: int) -> pd.Timestamp:
    """
    Process a datetime string, handling '24:00:00' and setting the current year.

    Args:
        dt (str): The datetime string to process.
        year (int): The year to set in the datetime.

    Returns:
        pd.Timestamp: A processed timestamp.
    """
    try:
        # Replace 24:00:00 with 00:00:00 and add one day
        if "24:00:00" in dt:
            dt = dt.replace("24:00:00", "00:00:00")
            ts = pd.to_datetime(f"{year} {dt}", format="%Y %m/%d %H:%M:%S") + pd.Timedelta(days=1)
        else:
            ts = pd.to_datetime(f"{year} {dt}", format="%Y %m/%d %H:%M:%S")
        return ts
    except Exception as e:
        print(f"Error processing datetime: {dt}. Error: {e}")
        return pd.NaT


def _build_summary_database(
    out_dir: str,
    building_dict: dict,
    efficiency_dict=None,
    report_cooling_summary: bool = False,
    report_heating_summary: bool = False
    ) -> pd.Series:
    """
    Builds a summary SQLite database with:
      - indoor temperature
      - outdoor temperature
      - heating energy (kWh)
      - cooling energy (kWh)
      - equipment energy (kWh)
      - totals

    Key points:
      - We read raw Joules from CSV for heating/cooling/equipment.
      - We convert per-floor to kWh in the DB itself, *not* storing Joules.
      - For heating/cooling, we also divide by the building's efficiency
        (default=3.0). So each floor's numeric value in the DB is electric usage (kWh).
      - The 'indoor_temperature' and 'outdoor_temperature' remain as °C.
      - We also accumulate total_cooling, total_heating, total_equipment, and total_energy
        in the 'totals' table. The returned pd.Series is total_energy (kWh) indexed by timestamp.

    Returns:
        pd.Series: A time series of total (kWh) at each timestamp.
    """
    if not os.path.isdir(out_dir):
        raise ValueError(f"The directory {out_dir} does not exist.")

    db_path = os.path.join(out_dir, "summary_database.db")

    # Default efficiency = 3.0
    default_efficiency = 3.0
    if efficiency_dict is None:
        efficiency_dict = {}
    # If user didn't provide some building's efficiency, fallback
    # (We fill all building_ids with 3.0 if missing.)
    for b_id in building_dict:
        if b_id not in efficiency_dict:
            efficiency_dict[b_id] = default_efficiency

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Create tables if they don't exist
        tables_to_create = [
            "indoor_temperature",
            "outdoor_temperature",
            "heating_energy",
            "cooling_energy",
            "equipment_energy",
            "totals"
        ]
        for table in tables_to_create:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    timestamp TEXT PRIMARY KEY
                );
            """)

        # Add columns for totals in the `totals` table if not present
        try:
            cursor.execute("ALTER TABLE totals ADD COLUMN total_cooling_energy REAL;")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE totals ADD COLUMN total_heating_energy REAL;")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE totals ADD COLUMN total_equipment_energy REAL;")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE totals ADD COLUMN total_energy REAL;")
        except:
            pass

        # We'll accumulate time-series for total usage across all buildings
        total_cooling   = pd.Series(dtype=float)
        total_heating   = pd.Series(dtype=float)
        total_equipment = pd.Series(dtype=float)

        # Keep track of columns we've already created in each table
        table_columns = {table: set() for table in tables_to_create}

        # Current year for timestamp parsing
        current_year = datetime.now().year

        # For each building
        for building_id, dir_index in building_dict.items():
            # CSV path
            csv_path = os.path.join(
                out_dir, f"built_island_{dir_index}_ep_outputs", "eplusout.csv"
            )
            if not os.path.isfile(csv_path):
                print(f"Warning: File {csv_path} not found. Skipping building {building_id}.")
                continue

            # Read CSV
            df = pd.read_csv(csv_path, index_col="Date/Time")
            # Convert the timestamps
            df.index = df.index.to_series().apply(lambda dt: _process_timestamp(dt, current_year))

            # Column regex patterns
            column_filters = {
                "indoor_temperature":  f"{building_id}_FLOOR_.*:Zone Operative Temperature \\[C\\]",
                "outdoor_temperature": f"{building_id}_FLOOR_.*:Zone Outdoor Air Drybulb Temperature \\[C\\]",
                "heating_energy":      f"{building_id}_FLOOR_.*_HVAC:Zone Ideal Loads Zone Total Heating Energy \\[J\\]",
                "cooling_energy":      f"{building_id}_FLOOR_.*_HVAC:Zone Ideal Loads Zone Total Cooling Energy \\[J\\]",
                "equipment_energy":    f"Electricity:Zone:{building_id}_FLOOR_.* \\[J\\]"
            }

            # We'll do floor-by-floor inserts
            for table, pattern in column_filters.items():
                # Find all columns matching the pattern
                relevant_columns = [
                    col for col in df.columns if pd.Series(col).str.contains(pattern).any()
                ]
                if not relevant_columns:
                    print(f"Warning: No relevant columns found for {table} in building {building_id}.")
                    continue

                # Extract floor IDs from the column name
                floor_columns = {}
                for col in relevant_columns:
                    match = pd.Series(col).str.extract(f"{building_id}_(FLOOR_\\d+)")
                    floor_id = match.iloc[0,0] if not match.empty else None
                    if floor_id:
                        floor_columns[floor_id] = col

                # Sort floors by floor number
                sorted_floor_cols = dict(
                    sorted(floor_columns.items(), key=lambda x: int(x[0].split('_')[1]))
                )

                # Add columns to this table
                for floor_id in sorted_floor_cols:
                    col_name = f"{building_id}_{floor_id}"
                    if col_name not in table_columns[table]:
                        # record that we've used this col
                        table_columns[table].add(col_name)
                        try:
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} REAL;")
                        except:
                            pass  # Already exists

                # Also add a building-level "total" column
                building_col_name = building_id
                if building_col_name not in table_columns[table]:
                    table_columns[table].add(building_col_name)
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {building_col_name} REAL;")
                    except:
                        pass

                # Efficiency for this building
                eff = efficiency_dict[building_id]
                # Insert row by row
                for timestamp, rowdata in df.iterrows():
                    if pd.isna(timestamp):
                        continue

                    # We'll store floor_kwh in a list
                    floor_kwh_list = []
                    # We'll build a param list for the SQL
                    param_list = [timestamp.strftime("%Y-%m-%d %H:%M:%S")]

                    for floor_id, col in sorted_floor_cols.items():
                        raw_joules = rowdata.get(col, 0.0)
                        if pd.isna(raw_joules):
                            raw_joules = 0.0

                        # If it's heating/cooling => convert to electric kWh => / eff
                        # If it's equipment => just J->kWh
                        # If it's temperature => no conversion
                        if table == "heating_energy":
                            val_kwh = (raw_joules / 3.6e6) / eff
                        elif table == "cooling_energy":
                            val_kwh = (raw_joules / 3.6e6) / eff
                        elif table == "equipment_energy":
                            val_kwh = (raw_joules / 3.6e6)
                        elif table in ["indoor_temperature", "outdoor_temperature"]:
                            # These are in Celsius, just store as-is
                            val_kwh = raw_joules
                        else:
                            val_kwh = raw_joules

                        floor_kwh_list.append(val_kwh)
                        param_list.append(val_kwh)

                    # Now compute the building-level "total" for this row
                    if table in ["indoor_temperature", "outdoor_temperature"]:
                        row_total = pd.Series(floor_kwh_list).mean(skipna=True)
                    else:
                        row_total = pd.Series(floor_kwh_list).sum(skipna=True)

                    param_list.append(row_total)

                    # Now build placeholders
                    placeholders = ", ".join(["?"] * (1 + len(sorted_floor_cols) + 1))
                    # col_name for each floor
                    floor_cols_sql = ", ".join([f"{building_id}_{fid}" for fid in sorted_floor_cols])
                    floor_cols_sql += f", {building_col_name}"

                    # Upsert
                    update_stmts = []
                    for fid in sorted_floor_cols:
                        update_stmts.append(f"{building_id}_{fid} = excluded.{building_id}_{fid}")
                    update_stmts.append(f"{building_col_name} = excluded.{building_col_name}")
                    update_sql = ", ".join(update_stmts)

                    cursor.execute(f"""
                        INSERT INTO {table} (timestamp, {floor_cols_sql})
                        VALUES ({placeholders})
                        ON CONFLICT(timestamp) DO UPDATE SET
                            {update_sql};
                    """, param_list)

                # Also accumulate into total_cooling/heating/equipment if relevant
                if table == "cooling_energy":
                    # sum over time steps => raw_joules => now we have them in kWh
                    # but let's do a sum across floors from the DataFrame perspective
                    # we can just do the same logic we do below by reading the columns
                    # but simpler is to do it after the loop
                    # We'll do it in a single pass below:
                    raw_joules_per_ts = df[relevant_columns].sum(axis=1, skipna=True)
                    building_eff = efficiency_dict[building_id]
                    building_kwh = (raw_joules_per_ts / 3.6e6) / building_eff
                    total_cooling = total_cooling.add(building_kwh, fill_value=0)

                elif table == "heating_energy":
                    raw_joules_per_ts = df[relevant_columns].sum(axis=1, skipna=True)
                    building_eff = efficiency_dict[building_id]
                    building_kwh = (raw_joules_per_ts / 3.6e6) / building_eff
                    total_heating = total_heating.add(building_kwh, fill_value=0)

                elif table == "equipment_energy":
                    raw_joules_per_ts = df[relevant_columns].sum(axis=1, skipna=True)
                    building_kwh = (raw_joules_per_ts / 3.6e6)
                    total_equipment = total_equipment.add(building_kwh, fill_value=0)

        # Now total_energy across all time steps
        total_energy = total_cooling.add(total_heating, fill_value=0).add(total_equipment, fill_value=0)

        # Insert time-based totals into 'totals'
        all_ts = total_cooling.index.union(total_heating.index).union(total_equipment.index)
        for ts in all_ts:
            cursor.execute("""
                INSERT INTO totals (
                    timestamp,
                    total_cooling_energy,
                    total_heating_energy,
                    total_equipment_energy,
                    total_energy
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(timestamp) DO UPDATE SET
                    total_cooling_energy   = excluded.total_cooling_energy,
                    total_heating_energy   = excluded.total_heating_energy,
                    total_equipment_energy = excluded.total_equipment_energy,
                    total_energy           = excluded.total_energy;
            """, (
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                total_cooling.get(ts, 0.0),
                total_heating.get(ts, 0.0),
                total_equipment.get(ts, 0.0),
                total_energy.get(ts, 0.0)
            ))

        conn.commit()

        # Return the aggregated total energy time-series
        out_dict = {
            "total_energy": total_energy,
            "total_cooling": total_cooling if report_cooling_summary else None,
            "total_heating": total_heating if report_heating_summary else None,
        }
        return out_dict

    finally:
        conn.close()


def _add_building_totals(
    out_dir: str,
    df: pd.DataFrame,
    include_heating: bool = True,
    include_cooling: bool = True
    ) -> pd.DataFrame:
    """
    Reads per-building energy/temperature from 'summary_database.db' 
    (which already stores usage in kWh), then populates columns in `df`:

      - total_cooling   (kWh)
      - total_heating   (kWh)
      - total_equipment (kWh)
      - total           (kWh) = sum of the above
      - max_total_energy (kWh) = maximum hourly total usage
      - max_temperature (°C) = maximum indoor temperature
      - min_temperature (°C) = minimum indoor temperature

    Args:
        out_dir (str):
          Directory where 'summary_database.db' is located.
        df (pd.DataFrame):
          Must have column 'osgb' with building IDs.
        include_heating (bool):
          If False, we set building's heating usage = 0 for the final sums.
        include_cooling (bool):
          If False, we set building's cooling usage = 0 for the final sums.

    Returns:
        pd.DataFrame: The same `df`, augmented with total columns.
    """
    # Path to the database file
    db_path = os.path.join(out_dir, "summary_database.db")
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Could not find database at {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        # For each building in df
        for i, row in df.iterrows():
            bldg_id = row.get("osgb")
            if not bldg_id:
                continue

            # Attempt reading kWh timeseries from the DB
            try:
                cooling_ts = pd.read_sql_query(
                    f"SELECT timestamp, {bldg_id} as value FROM cooling_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
            except Exception as e:
                print(f"Warning: No cooling_energy data for building {bldg_id}. ({e})")
                cooling_ts = pd.Series(dtype=float)

            try:
                heating_ts = pd.read_sql_query(
                    f"SELECT timestamp, {bldg_id} as value FROM heating_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
            except Exception as e:
                print(f"Warning: No heating_energy data for building {bldg_id}. ({e})")
                heating_ts = pd.Series(dtype=float)

            try:
                equipment_ts = pd.read_sql_query(
                    f"SELECT timestamp, {bldg_id} as value FROM equipment_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
            except Exception as e:
                print(f"Warning: No equipment_energy data for building {bldg_id}. ({e})")
                equipment_ts = pd.Series(dtype=float)

            # These values are already in kWh. If user wants to exclude heating/cooling:
            if not include_cooling:
                cooling_ts[:] = 0.0
            if not include_heating:
                heating_ts[:] = 0.0

            # Sum up the time-series
            total_ts = cooling_ts + heating_ts + equipment_ts

            # Aggregate
            total_cooling   = cooling_ts.sum()
            total_heating   = heating_ts.sum()
            total_equipment = equipment_ts.sum()
            max_total_usage = total_ts.max() if not total_ts.empty else 0.0

            # Retrieve indoor temperature timeseries
            try:
                temp_ts = pd.read_sql_query(
                    f"SELECT timestamp, {bldg_id} as value FROM indoor_temperature;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
                max_temp = temp_ts.max() if not temp_ts.empty else None
                min_temp = temp_ts.min() if not temp_ts.empty else None
            except Exception as e:
                print(f"Warning: No indoor_temperature data for building {bldg_id}. ({e})")
                max_temp = None
                min_temp = None

            # Insert aggregated results into df
            df.loc[i, "total_cooling"]    = total_cooling
            df.loc[i, "total_heating"]    = total_heating
            df.loc[i, "total_equipment"]  = total_equipment
            df.loc[i, "total"]            = total_cooling + total_heating + total_equipment
            df.loc[i, "max_total_energy"] = max_total_usage
            df.loc[i, "max_temperature"]  = max_temp
            df.loc[i, "min_temperature"]  = min_temp

    finally:
        conn.close()

    return df
