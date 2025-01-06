import os
import sqlite3
import subprocess
import pandas as pd
from datetime import datetime


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


def _build_summary_database(out_dir: str, building_dict: dict, efficiency_dict=None) -> None:
    """
    Builds a summary SQLite database with indoor temperature, heating energy, cooling energy,
    equipment energy, and total energy data collated from simulation results.

    Adds average temperature columns and total energy columns for each building,
    and computes overall totals adjusted for efficiencies.

    Args:
        out_dir (str): The directory where the database file will be created.
        building_dict (dict): A dictionary mapping building IDs to their respective directories.
        efficiency_dict (dict): A dictionary mapping building IDs to their efficiencies.
                                Defaults to 5.4 for heating and cooling if not provided.

    Raises:
        ValueError: If the provided directory does not exist.
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

        # Get the current year for timestamp processing
        current_year = datetime.now().year

        # Store total values across all buildings as pandas Series
        total_cooling = pd.Series(dtype=float)
        total_heating = pd.Series(dtype=float)
        total_equipment = pd.Series(dtype=float)

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

                # Aggregate the data into lists per timestamp for the original table
                df[building_id] = df[relevant_columns].apply(lambda row: row.dropna().tolist(), axis=1)

                # Add a column to the table for this building if it doesn't exist
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {building_id} TEXT;")

                # Insert the data into the original table
                for timestamp, values in df[building_id].items():
                    if pd.isna(timestamp):  # Check if the timestamp is NaT after processing
                        print(f"Warning: Skipping row with NaT timestamp for building {building_id}")
                        continue
                    cursor.execute(f"""
                        INSERT INTO {table} (timestamp, {building_id})
                        VALUES (?, ?)
                        ON CONFLICT(timestamp) DO UPDATE SET {building_id} = excluded.{building_id};
                    """, (timestamp.strftime("%Y-%m-%d %H:%M:%S"), str(values)))

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

        # Insert totals into the totals table
        for timestamp in total_cooling.index.union(total_heating.index).union(total_equipment.index):
            cursor.execute("""
                INSERT INTO totals (timestamp, total_cooling_energy, total_heating_energy, total_equipment_energy)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(timestamp) DO UPDATE SET
                    total_cooling_energy = excluded.total_cooling_energy,
                    total_heating_energy = excluded.total_heating_energy,
                    total_equipment_energy = excluded.total_equipment_energy;
            """, (
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                total_cooling.get(timestamp, 0),
                total_heating.get(timestamp, 0),
                total_equipment.get(timestamp, 0),
            ))

        # Commit changes
        conn.commit()

    finally:
        # Close the connection
        conn.close()
