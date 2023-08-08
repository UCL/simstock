import os
import shutil
from eppy.modeleditor import IDF
import pandas as pd


def _copy_directory_contents(
        source_dir: str,
        destination_dir: str
        ) -> None:
    
    try:
        # Get the list of items in the source directory
        items = os.listdir(source_dir)

        for item in items:
            if not item.endswith((".idf", ".epw")):

                source_item_path = os.path.join(source_dir, item)
                destination_item_path = os.path.join(destination_dir, item)

                if os.path.isdir(source_item_path):
                    # If the item is a directory, recursively copy its contents
                    _copy_directory_contents(source_item_path, destination_item_path)
                else:
                    # If the item is a file, copy it to the destination directory
                    shutil.copy2(source_item_path, destination_dir)

    except Exception as e:
        print(f"Error while copying: {e}")



def _delete_directory_contents(directory_path: str) -> None:

    try:
        # Remove all the contents of the directory
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                # If the item is a subdirectory, recursively delete its contents
                _delete_directory_contents(item_path)
            else:
                # If the item is a file, remove it
                os.remove(item_path)

    except Exception as e:
        print(f"Error while deleting: {e}")



def _extract_class_name(file_name: str) -> str:
    """
    Function to extract the IDF file class name
    from the csv file name in the settings directory.
    """
    # Split the file name by "-"
    parts = file_name.split("-")
    
    # Take the last part of the split as the relevant field name
    relevant_part = parts[-1]
    
    # Replace underscores with colons
    return relevant_part.replace("_", ":")



def _add_or_modify_idfobject(
        classname: str,
        row: pd.Series,
        idf: IDF
        ) -> None:
    
    # Turn row into a nice dictionary
    d = {}
    for key, val in row.items():
        if not pd.isna(val) and val != ",":
            d[key] = val

    # Check if this thing already exists 
    # in the idf object
    duplicate_count = 0
    for ind, item in enumerate(idf.idfobjects[classname]):
        if item.Name == d["Name"]:
            duplicate_count += 1
    if duplicate_count > 0:
        for _ in range(duplicate_count):
            for ind, item in enumerate(idf.idfobjects[classname]):
                if item.Name == d["Name"]:
                    idf.popidfobject(classname, ind)
                    break

    idf.newidfobject(classname, **d)



def _compile_csvs_to_idf(idf: IDF, path: str) -> None:
    
    for csv_file in os.listdir(path):
        if csv_file.endswith(".csv"):

            # Get idf class name
            idf_class = _extract_class_name(csv_file[:-4])
            if idf_class != "OnOff":

                # load as pandas dataframe
                try:
                    na_values = ["", "N/A", "NA", "NaN", "NULL", "None"]
                    df = pd.read_csv(
                        os.path.join(path, csv_file), na_values=na_values
                        )
                except FileNotFoundError:
                    print(f"File '{csv_file}' not found.")
                except pd.errors.EmptyDataError:
                    print(f"File '{csv_file}' is empty.")
                except pd.errors.ParserError as pe:
                    print(f"Error parsing '{csv_file}': {pe}")
                except Exception as e:
                    print(f"An error occurred while loading '{csv_file}': {e}")

                # Iterate over rows of df
                for _, row in df.iterrows():

                    # Add each entry as a new idf object
                    _add_or_modify_idfobject(idf_class, row, idf)

    # Then handle the on/off thing
    df = pd.read_csv(os.path.join(path, "DB-HeatingCooling-OnOff.csv"))
    heatcool = df["Heating_Cooling"].iloc[0]
    if not heatcool:
        thermostats = idf.idfobjects["ThermostatSetpoint:DualSetpoint"]
        for thermostat in thermostats:
            # Swap the names
            thermostat.Heating_Setpoint_Temperature_Schedule_Name = "Dwell_Heat_Off"
            thermostat.Cooling_Setpoint_Temperature_Schedule_Name = "Dwell_Cool_Off"


