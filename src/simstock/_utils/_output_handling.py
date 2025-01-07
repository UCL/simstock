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


def _build_summary_database(out_dir: str, building_dict: dict, efficiency_dict=None) -> pd.Series:
    """
    Builds a summary SQLite database with indoor temperature, heating energy, cooling energy,
    equipment energy, and total energy data collated from simulation results.

    Adds total or mean columns for each building, depending on the table.

    Args:
        out_dir (str): The directory where the database file will be created.
        building_dict (dict): A dictionary mapping building IDs to their respective directories.
        efficiency_dict (dict): A dictionary mapping building IDs to their efficiencies.
                                Defaults to 5.4 for heating and cooling if not provided.

    Returns:
        pd.Series: A timeseries of total energy consumption.
    """
    # Ensure the output directory exists
    if not os.path.isdir(out_dir):
        raise ValueError(f"The directory {out_dir} does not exist.")

    # Define the database file path
    db_path = os.path.join(out_dir, "summary_database.db")

    # Default efficiencies
    default_efficiency = 5.4
    efficiency_dict = efficiency_dict or {building_id: default_efficiency for building_id in building_dict.keys()}

    # Connect to the database
    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # Create tables if they don't exist
        for table in ["indoor_temperature", "heating_energy", "cooling_energy", "equipment_energy", "totals"]:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    timestamp TEXT PRIMARY KEY
                );
            """)

        # Add columns for totals in the `totals` table
        cursor.execute("""
            ALTER TABLE totals ADD COLUMN total_cooling_energy REAL;
        """)
        cursor.execute("""
            ALTER TABLE totals ADD COLUMN total_heating_energy REAL;
        """)
        cursor.execute("""
            ALTER TABLE totals ADD COLUMN total_equipment_energy REAL;
        """)
        cursor.execute("""
            ALTER TABLE totals ADD COLUMN total_energy REAL;
        """)

        # Get the current year for timestamp processing
        current_year = datetime.now().year

        # Store total values across all buildings as pandas Series
        total_cooling = pd.Series(dtype=float)
        total_heating = pd.Series(dtype=float)
        total_equipment = pd.Series(dtype=float)

        # Maintain a sorted list of columns for each table
        table_columns = {table: [] for table in ["indoor_temperature", "heating_energy", "cooling_energy", "equipment_energy"]}

        # Iterate through each building in the dictionary
        for building_id, dir_index in building_dict.items():
            # Construct the file path to the relevant CSV
            csv_path = os.path.join(out_dir, f"built_island_{dir_index}_ep_outputs", "eplusout.csv")

            if not os.path.isfile(csv_path):
                print(f"Warning: File {csv_path} not found. Skipping building {building_id}.")
                continue

            # Read the CSV file
            df = pd.read_csv(csv_path, index_col="Date/Time")

            # Preprocess the index to handle 24:00:00 and set the current year
            df.index = df.index.to_series().apply(lambda dt: _process_timestamp(dt, current_year))

            # Define column filters for different data types
            column_filters = {
                "indoor_temperature": f"{building_id}_FLOOR_.*:Zone Operative Temperature \\[C\\]",
                "heating_energy": f"{building_id}_FLOOR_.*_HVAC:Zone Ideal Loads Zone Total Heating Energy \\[J\\]",
                "cooling_energy": f"{building_id}_FLOOR_.*_HVAC:Zone Ideal Loads Zone Total Cooling Energy \\[J\\]",
                "equipment_energy": f"Electricity:Zone:{building_id}_FLOOR_.* \\[J\\]"
            }

            # Process each data type
            for table, pattern in column_filters.items():
                relevant_columns = [
                    col for col in df.columns if pd.Series(col).str.contains(pattern).any()
                ]

                if not relevant_columns:
                    print(f"Warning: No relevant columns found for {table} in building {building_id}.")
                    continue

                # Extract floor-specific columns
                floor_columns = {}
                for col in relevant_columns:
                    match = pd.Series(col).str.extract(f"{building_id}_(FLOOR_\\d+)")
                    floor_id = match.iloc[0, 0] if not match.empty else None
                    if floor_id:
                        floor_columns[floor_id] = col

                # Sort floor columns by floor number
                sorted_floor_columns = dict(sorted(floor_columns.items(), key=lambda x: int(x[0].split('_')[1])))

                # Add columns for each floor dynamically
                for floor_id in sorted_floor_columns:
                    column_name = f"{building_id}_{floor_id}"
                    if column_name not in table_columns[table]:
                        table_columns[table].append(column_name)
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} REAL;")

                # Compute building total column
                total_column_name = building_id
                if total_column_name not in table_columns[table]:
                    table_columns[table].append(total_column_name)
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {total_column_name} REAL;")

                # Insert data for each floor and compute total/mean
                for timestamp, row in df.iterrows():
                    if pd.isna(timestamp):
                        continue

                    values = [timestamp.strftime("%Y-%m-%d %H:%M:%S")]
                    floor_values = []

                    for floor_id, col in sorted_floor_columns.items():
                        floor_value = row.get(col, None)
                        floor_values.append(floor_value)
                        values.append(floor_value)

                    # Compute total (sum for most tables, mean for indoor_temperature)
                    if table == "indoor_temperature":
                        total_value = pd.Series(floor_values).mean(skipna=True)
                    else:
                        total_value = pd.Series(floor_values).sum(skipna=True)

                    values.append(total_value)  # Append the total/mean value for the building

                    placeholders = ", ".join(["?"] * (1 + len(sorted_floor_columns) + 1))  # Include timestamp + total
                    floor_columns_sql = ", ".join([f"{building_id}_{floor_id}" for floor_id in sorted_floor_columns])
                    floor_columns_sql += f", {total_column_name}"

                    cursor.execute(f"""
                        INSERT INTO {table} (timestamp, {floor_columns_sql})
                        VALUES ({placeholders})
                        ON CONFLICT(timestamp) DO UPDATE SET
                            {', '.join([f'{building_id}_{floor_id} = excluded.{building_id}_{floor_id}' for floor_id in sorted_floor_columns])},
                            {total_column_name} = excluded.{total_column_name};
                    """, values)

                # Compute totals for the `totals` table
                if table == "cooling_energy":
                    cooling_total = df[relevant_columns].sum(axis=1, skipna=True) * efficiency_dict[building_id]
                    total_cooling = total_cooling.add(cooling_total, fill_value=0)
                elif table == "heating_energy":
                    heating_total = df[relevant_columns].sum(axis=1, skipna=True) * efficiency_dict[building_id]
                    total_heating = total_heating.add(heating_total, fill_value=0)
                elif table == "equipment_energy":
                    equipment_total = df[relevant_columns].sum(axis=1, skipna=True)
                    total_equipment = total_equipment.add(equipment_total, fill_value=0)

        # Compute total energy (sum of cooling, heating, and equipment)
        total_energy = total_cooling.add(total_heating, fill_value=0).add(total_equipment, fill_value=0)

        # Insert totals into the totals table
        for timestamp in total_cooling.index.union(total_heating.index).union(total_equipment.index):
            cursor.execute("""
                INSERT INTO totals (timestamp, total_cooling_energy, total_heating_energy, total_equipment_energy, total_energy)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(timestamp) DO UPDATE SET
                    total_cooling_energy = excluded.total_cooling_energy,
                    total_heating_energy = excluded.total_heating_energy,
                    total_equipment_energy = excluded.total_equipment_energy,
                    total_energy = excluded.total_energy;
            """, (
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                total_cooling.get(timestamp, 0),
                total_heating.get(timestamp, 0),
                total_equipment.get(timestamp, 0),
                total_energy.get(timestamp, 0),
            ))

        # Commit changes
        conn.commit()

        # Return the total_energy timeseries
        return total_energy

    finally:
        # Close the connection
        conn.close()


def _add_building_totals(out_dir: str, df: pd.DataFrame, efficiency_dict=None) -> pd.DataFrame:
    """
    Adds total_cooling, total_heating, total_equipment, total, max_total_energy,
    max_temperature, and min_temperature columns to the input DataFrame.

    Args:
        out_dir (str): The directory where the database file is located.
        df (pd.DataFrame): A DataFrame containing a column 'osgb' with building IDs.
        efficiency_dict (dict, optional): A dictionary mapping building IDs to their efficiencies.
                                          Defaults to 5.4 for heating and cooling if not provided.

    Returns:
        pd.DataFrame: The updated DataFrame with added total and max/min fields.
    """
    # Ensure the output directory exists
    if not os.path.isdir(out_dir):
        raise ValueError(f"The directory {out_dir} does not exist.")

    # Define the database file path
    db_path = os.path.join(out_dir, "summary_database.db")

    # Default efficiencies
    default_efficiency = 5.4
    efficiency_dict = efficiency_dict or {}

    # Conversion factor from Joules to kWh
    joules_to_kwh = 1 / 3600000

    # Connect to the database
    conn = sqlite3.connect(db_path)

    try:
        # Iterate over each building ID in the DataFrame
        for index, row in df.iterrows():
            building_id = row["osgb"]

            # Fetch energy timeseries for this building
            try:
                cooling_timeseries = pd.read_sql_query(
                    f"SELECT timestamp, {building_id} AS value FROM cooling_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)

                heating_timeseries = pd.read_sql_query(
                    f"SELECT timestamp, {building_id} AS value FROM heating_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)

                equipment_timeseries = pd.read_sql_query(
                    f"SELECT timestamp, {building_id} AS value FROM equipment_energy;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
            except Exception as e:
                print(f"Warning: Failed to retrieve energy data for building {building_id}. Error: {e}")
                cooling_timeseries, heating_timeseries, equipment_timeseries = pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)

            # Adjust timeseries for efficiency and convert to kWh
            efficiency = efficiency_dict.get(building_id, default_efficiency)
            cooling_timeseries = cooling_timeseries * efficiency * joules_to_kwh
            heating_timeseries = heating_timeseries * efficiency * joules_to_kwh
            equipment_timeseries = equipment_timeseries * joules_to_kwh

            # Compute total energy timeseries
            total_energy_timeseries = cooling_timeseries + heating_timeseries + equipment_timeseries

            # Calculate total energy values
            total_cooling = cooling_timeseries.sum()
            total_heating = heating_timeseries.sum()
            total_equipment = equipment_timeseries.sum()
            max_total_energy = total_energy_timeseries.max()

            # Fetch temperature data for this building
            try:
                temperature_timeseries = pd.read_sql_query(
                    f"SELECT timestamp, {building_id} AS value FROM indoor_temperature;",
                    conn,
                    index_col="timestamp"
                )["value"].fillna(0)
            except Exception as e:
                print(f"Warning: Failed to retrieve temperature data for building {building_id}. Error: {e}")
                temperature_timeseries = pd.Series(dtype=float)

            # Compute max and min temperatures
            max_temperature = temperature_timeseries.max()
            min_temperature = temperature_timeseries.min()

            # Add totals and max/min values to the DataFrame
            df.loc[index, "total_cooling"] = total_cooling
            df.loc[index, "total_heating"] = total_heating
            df.loc[index, "total_equipment"] = total_equipment
            df.loc[index, "total"] = total_cooling + total_heating + total_equipment
            df.loc[index, "max_total_energy"] = max_total_energy
            df.loc[index, "max_temperature"] = max_temperature
            df.loc[index, "min_temperature"] = min_temperature

    finally:
        # Close the database connection
        conn.close()

    return df
