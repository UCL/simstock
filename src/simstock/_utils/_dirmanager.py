"""
Module containing internal functions for modifying and copying files.
Mostly used to allow users to create and modify csv files for settings
"""

import os
import shutil
from eppy.modeleditor import IDF
import pandas as pd


def _copy_directory_contents(
        source_dir: str,
        destination_dir: str
        ) -> None:
    """
    Makes a copy of source_dir in destination_dir
    """
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
    """
    Recursively removes contents of directory_path
    """
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
    """
    Function used to take a row of a csv (pandas Dataframe), 
    and create an IDF object out of it
    """

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
    
    
def _create_schedule_compact_obj(
    idf, 
    schedule_name, 
    schedule_type_limits_name,
    lines
    ):
    """
    Creates a 'SCHEDULE:COMPACT' object in the IDF 
    by assigning lines to Field_1, Field_2, etc.
    """
    sch = idf.newidfobject("SCHEDULE:COMPACT")
    sch.Name = schedule_name
    sch.Schedule_Type_Limits_Name = schedule_type_limits_name

    for i, line in enumerate(lines, start=1):
        setattr(sch, f"Field_{i}", line)
    return sch


def _compile_csvs_to_idf(idf: IDF, path: str) -> None:
    """
    Function that looks for csv files within path, and looks add their
    contents. It uses to rows of the csv files to create IDF objects
    that are then added to idf
    """
    
    for csv_file in os.listdir(path):
        if csv_file.endswith(".csv"):

            # Get idf class name
            idf_class = _extract_class_name(csv_file[:-4])
            if idf_class != "OnOff" and idf_class.casefold() != "schedule:compact":

                # load as pandas dataframe
                try:
                    na_values = ["", "N/A", "NA", "NaN", "NULL", "None"]
                    df = pd.read_csv(
                        os.path.join(path, csv_file),
                        na_values=na_values,
                        on_bad_lines='skip'
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
                    try:
                        _add_or_modify_idfobject(idf_class, row, idf)
                    except Exception as e:
                        print(e)
                        print(f"Cause: class {idf_class}")
                        # for item in row.items():
                        #     print(item)
                        raise Exception from e

    # Then handle the on/off thing
    df = pd.read_csv(os.path.join(path, "DB-HeatingCooling-OnOff.csv"))
    heatcool = df["Heating_Cooling"].iloc[0]
    if not heatcool:
        thermostats = idf.idfobjects["ThermostatSetpoint:DualSetpoint"]
        for thermostat in thermostats:
            # Swap the names
            thermostat.Heating_Setpoint_Temperature_Schedule_Name = "Dwell_Heat_Off"
            thermostat.Cooling_Setpoint_Temperature_Schedule_Name = "Dwell_Cool_Off"


def _replicate_archetype_objects_for_zones(
    idf, 
    classes_to_duplicate=None, 
    remove_original=True,
    infiltration_schedule="On 24/7", 
    ventilation_schedule="Dwell_Occ",
    infiltration_ach=0.5,
    ventilation_ach=0.3
    ):
    """
    1) For each class in classes_to_duplicate (e.g. ["PEOPLE","LIGHTS","ELECTRICEQUIPMENT"]),
       find any object referencing a ZONELIST in 'Zone_or_ZoneList_Name'.
       Replicate that object for each zone in that zonelist.
         - If a schedule field references e.g. "Some_Occ", we check if "Some_Occ_zone"
           exists. If it does, we rename to it. Otherwise if "Some_Occ" itself
           doesn't exist, we skip that zone.

    2) Then forcibly create infiltration & ventilation objects for every zone
       with exactly the infiltration_schedule and ventilation_schedule arguments.
       If these schedules do not exist, we create a simple always-on schedule
       so EnergyPlus won't complain about them missing.

    :param idf: Eppy IDF object
    :param classes_to_duplicate: e.g. ["PEOPLE","LIGHTS","ELECTRICEQUIPMENT"]
    :param remove_original: remove the original "archetype" object after replication
    :param infiltration_schedule: universal infiltration schedule name
    :param ventilation_schedule: universal ventilation schedule name
    :param infiltration_ach: infiltration air changes per hour
    :param ventilation_ach: ventilation air changes per hour

    NOTE:
      - This code *ignores* any usage-based infiltration/vent references that might
        exist. All infiltration objects use infiltration_schedule, all ventilation
        objects use ventilation_schedule, no matter if the zone usage is "Commercial",
        "Dwell", etc.
      - If you see an error about 'Commercial_Occ' not found, that means *somewhere else*
        you have a ZoneVentilation:DesignFlowRate referencing 'Commercial_Occ' 
        that was not created by this function.
    """
    # default classes
    if classes_to_duplicate is None:
        classes_to_duplicate = ["PEOPLE", "LIGHTS", "ELECTRICEQUIPMENT"]

    # 1) replicate archetype loads (PEOPLE, LIGHTS, etc.) that use a ZONELIST
    objects_to_remove = []
    for c in classes_to_duplicate:
        c_up = c.upper()
        if c_up not in idf.idfobjects:
            continue

        archetype_objs = list(idf.idfobjects[c_up])
        for obj in archetype_objs:
            zone_or_list = obj.Zone_or_ZoneList_Name.strip()
            if not zone_or_list:
                continue

            # check if zone_or_list matches a ZONELIST
            zlists = [
                zl for zl in idf.idfobjects["ZONELIST"]
                if zl.Name.strip().lower() == zone_or_list.lower()
            ]
            if zlists:
                # replicate
                zlist_obj = zlists[0]
                zone_names = extract_zones_from_zonelist(zlist_obj)
                replicate_object_for_zones(idf, obj, c_up, zone_names)
                if remove_original:
                    objects_to_remove.append((c_up, obj))

    # remove original archetype objects if desired
    for (classname, archetype_obj) in objects_to_remove:
        try:
            idf.removeidfobject(archetype_obj)
        except ValueError:
            pass

    # 2) ensure infiltration_schedule & ventilation_schedule exist
    if not schedule_compact_exists(idf, infiltration_schedule):
        # create an always-on schedule with value=1
        _create_always_on_schedule(idf, infiltration_schedule, 1.0)

    if not schedule_compact_exists(idf, ventilation_schedule):
        _create_always_on_schedule(idf, ventilation_schedule, 1.0)

    # 3) forcibly create infiltration & ventilation for each zone
    for zone_obj in idf.idfobjects["ZONE"]:
        zone_name = zone_obj.Name.strip()

        # infiltration
        infil_name = f"{zone_name}_Infiltration"
        idf.newidfobject(
            "ZONEINFILTRATION:DESIGNFLOWRATE",
            Name=infil_name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name=infiltration_schedule,
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Air_Changes_per_Hour=infiltration_ach,
            Constant_Term_Coefficient=1.0,
            Temperature_Term_Coefficient=0.0,
            Velocity_Term_Coefficient=0.0,
            Velocity_Squared_Term_Coefficient=0.0
        )

        # ventilation
        vent_name = f"{zone_name}_Ventilation"
        idf.newidfobject(
            "ZONEVENTILATION:DESIGNFLOWRATE",
            Name=vent_name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name=ventilation_schedule,
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Air_Changes_per_Hour=ventilation_ach,
            Ventilation_Type="Natural",
            Fan_Pressure_Rise=0.0,
            Fan_Total_Efficiency=1.0,
            Constant_Term_Coefficient=1.0,
            Temperature_Term_Coefficient=0.0,
            Velocity_Term_Coefficient=0.0,
            Velocity_Squared_Term_Coefficient=0.0,
            Minimum_Indoor_Temperature=18.0,
            Maximum_Indoor_Temperature=100.0,
            Minimum_Outdoor_Temperature=-100.0,
            Maximum_Outdoor_Temperature=100.0,
            Maximum_Wind_Speed=40.0
        )

    # done creating infiltration/vent for each zone


def replicate_object_for_zones(idf, source_obj, class_name, zone_names):
    """
    For a source E+ object (PEOPLE, LIGHTS, or ELECTRICEQUIPMENT) referencing
    a ZONELIST, replicate per zone. We handle schedules as follows:
      - PEOPLE => "Number_of_People_Schedule_Name"
      - LIGHTS => "Schedule_Name"
      - ELECTRICEQUIPMENT => "Schedule_Name"
      If a field references e.g. "Some_Occ", we check if "Some_Occ_zone"
      exists. If yes, we rename to that. If neither the base nor zone-specific
      schedule exists, we skip that zone object entirely.
    """
    flds = source_obj.fieldnames
    vals = source_obj.fieldvalues
    source_dict = dict(zip(flds, vals))

    old_name = source_dict.get("Name", "")
    # figure out which field references a schedule
    schedule_fields = []
    if class_name == "PEOPLE":
        schedule_fields = ["Number_of_People_Schedule_Name"]
    elif class_name in ("LIGHTS", "ELECTRICEQUIPMENT"):
        schedule_fields = ["Schedule_Name"]

    for zname in zone_names:
        new_dict = dict(source_dict)
        new_dict["Name"] = f"{old_name}_{zname}"
        new_dict["Zone_or_ZoneList_Name"] = zname

        skip_this_zone = False
        for sf in schedule_fields:
            base_sched = new_dict.get(sf, "").strip()
            if not base_sched:
                continue

            # check zone-specific
            zsched = f"{base_sched}_{zname}"
            if schedule_compact_exists(idf, zsched):
                new_dict[sf] = zsched
            else:
                # fallback to base_sched
                if not schedule_compact_exists(idf, base_sched):
                    print(
                        f"Skipping object '{old_name}' for zone '{zname}' "
                        f"because schedule '{base_sched}' or '{zsched}' not found."
                    )
                    skip_this_zone = True
                    break

        if skip_this_zone:
            continue

        new_dict.pop("key", None)  # remove eppy's internal key if present
        idf.newidfobject(class_name, **new_dict)


def extract_zones_from_zonelist(zone_list_obj):
    """Return zone names from a ZONELIST object (fields like Zone_1_Name, etc.)."""
    result = []
    for i in range(1, 500):
        fname = f"Zone_{i}_Name"
        if not hasattr(zone_list_obj, fname):
            break
        val = getattr(zone_list_obj, fname)
        if val and val.strip():
            result.append(val.strip())
    return result


def schedule_compact_exists(idf, sched_name):
    """Check if SCHEDULE:COMPACT named sched_name exists."""
    if "SCHEDULE:COMPACT" not in idf.idfobjects:
        return False
    target = sched_name.strip().lower()
    for sc in idf.idfobjects["SCHEDULE:COMPACT"]:
        if sc.Name.strip().lower() == target:
            return True
    return False


def _cleanup_infiltration_and_ventilation(
    idf,
    remove_if_invalid_schedule=True,
    fallback_schedule_name="Always_ON_1",
    fallback_schedule_value=1.0
):
    """
    Post-processing to ensure each zone has exactly one infiltration object
    and one ventilation object, removing duplicates and/or fixing schedule references.

    Steps:
      1) Possibly create a fallback schedule if not present (Always_ON_1 => 1.0).
      2) Gather all infiltration & vent objects.
      3) Group them by zone:
         - If a zone has multiple infiltration objects, keep exactly one
           (the first) & remove the rest.
         - Similarly for ventilation objects.
      4) For each infiltration/vent object, check the .Schedule_Name:
         - If it doesn't exist in SCHEDULE:COMPACT and remove_if_invalid_schedule=True,
           then remove the object.
         - Else if it doesn't exist and remove_if_invalid_schedule=False,
           re-assign to fallback_schedule_name.

    :param idf: an eppy IDF object
    :param remove_if_invalid_schedule: if True, we remove infiltration/vent objects
           that reference a missing schedule. If False, we fix them by using fallback.
    :param fallback_schedule_name: name of a schedule to use if you want to
           reassign missing schedules. (Used only if remove_if_invalid_schedule=False)
    :param fallback_schedule_value: value of that fallback schedule if we need to create it
    """

    # 1) Ensure fallback schedule exists
    if not remove_if_invalid_schedule:
        # We'll create or confirm an always-on schedule for fallback
        if not schedule_compact_exists(idf, fallback_schedule_name):
            _create_always_on_schedule(idf, fallback_schedule_name, fallback_schedule_value)

    # 2) Gather infiltration & ventilation objects
    infiltration_objs = idf.idfobjects.get("ZONEINFILTRATION:DESIGNFLOWRATE", [])
    ventilation_objs  = idf.idfobjects.get("ZONEVENTILATION:DESIGNFLOWRATE", [])

    # We'll create a dictionary: zone_name -> list of infiltration objects
    from collections import defaultdict
    zone_infil = defaultdict(list)
    zone_vent  = defaultdict(list)

    # fill them
    for infil in infiltration_objs:
        z = infil.Zone_or_ZoneList_Name.strip()
        if z:
            zone_infil[z].append(infil)
    for vent in ventilation_objs:
        z = vent.Zone_or_ZoneList_Name.strip()
        if z:
            zone_vent[z].append(vent)

    # 3) For each zone, keep at most one infiltration, one ventilation
    for zname, infil_list in zone_infil.items():
        # if there's more than one infiltration, keep the first, remove others
        if len(infil_list) > 1:
            # e.g. keep infiltration_objs[0], remove infiltration_objs[1..]
            # or define custom logic if you prefer (like by object Name)
            to_keep = infil_list[0]
            for extra in infil_list[1:]:
                idf.removeidfobject(extra)

    for zname, vent_list in zone_vent.items():
        if len(vent_list) > 1:
            to_keep = vent_list[0]
            for extra in vent_list[1:]:
                idf.removeidfobject(extra)

    # 4) Check each infiltration/vent for schedule validity
    #    Possibly remove or fix them
    infiltration_objs = idf.idfobjects.get("ZONEINFILTRATION:DESIGNFLOWRATE", [])
    ventilation_objs  = idf.idfobjects.get("ZONEVENTILATION:DESIGNFLOWRATE", [])

    for infil in infiltration_objs:
        sched = infil.Schedule_Name.strip()
        if not sched:
            # if it's truly empty, maybe remove it or set fallback
            if remove_if_invalid_schedule:
                idf.removeidfobject(infil)
            else:
                infil.Schedule_Name = fallback_schedule_name
            continue

        if not schedule_compact_exists(idf, sched):
            if remove_if_invalid_schedule:
                print(f"Removing infiltration '{infil.Name}' referencing missing schedule '{sched}'.")
                idf.removeidfobject(infil)
            else:
                print(f"Fix infiltration '{infil.Name}' referencing missing sched '{sched}' => fallback '{fallback_schedule_name}'.")
                infil.Schedule_Name = fallback_schedule_name

    for vent in ventilation_objs:
        sched = vent.Schedule_Name.strip()
        if not sched:
            if remove_if_invalid_schedule:
                idf.removeidfobject(vent)
            else:
                vent.Schedule_Name = fallback_schedule_name
            continue

        if not schedule_compact_exists(idf, sched):
            if remove_if_invalid_schedule:
                print(f"Removing ventilation '{vent.Name}' referencing missing schedule '{sched}'.")
                idf.removeidfobject(vent)
            else:
                print(f"Fix ventilation '{vent.Name}' referencing missing sched '{sched}' => fallback '{fallback_schedule_name}'.")
                vent.Schedule_Name = fallback_schedule_name

def _fix_infiltration_vent_schedules(
    idf,
    remove_if_missing_schedule=True,
    fallback_schedule="Always_ON_1",
    fallback_value=1.0
):
    """
    Post-processing step that fixes infiltration/vent schedules and removes duplicates.
    """

    # 1) Possibly ensure fallback schedule
    if not remove_if_missing_schedule:
        if not schedule_compact_exists(idf, fallback_schedule):
            _create_always_on_schedule(idf, fallback_schedule, fallback_value)

    # 2) Gather infiltration & ventilation (Idf_MSequence objects)
    infiltration_objs = idf.idfobjects.get("ZONEINFILTRATION:DESIGNFLOWRATE", [])
    ventilation_objs  = idf.idfobjects.get("ZONEVENTILATION:DESIGNFLOWRATE", [])

    # Convert each to plain list
    infiltration_list = list(infiltration_objs)
    ventilation_list  = list(ventilation_objs)

    # 3) Group by zone, remove duplicates
    from collections import defaultdict
    zone_infil = defaultdict(list)
    zone_vent  = defaultdict(list)

    for infil in infiltration_list:
        z = infil.Zone_or_ZoneList_Name.strip()
        if z:
            zone_infil[z].append(infil)

    for vent in ventilation_list:
        z = vent.Zone_or_ZoneList_Name.strip()
        if z:
            zone_vent[z].append(vent)

    for z, infil_list in zone_infil.items():
        if len(infil_list) > 1:
            keep = infil_list[0]
            for extra in infil_list[1:]:
                idf.removeidfobject(extra)

    for z, vent_list in zone_vent.items():
        if len(vent_list) > 1:
            keep = vent_list[0]
            for extra in vent_list[1:]:
                idf.removeidfobject(extra)

    # 4) Now re-fetch infiltration & vent (in case we removed some)
    infiltration_list = list(idf.idfobjects.get("ZONEINFILTRATION:DESIGNFLOWRATE", []))
    ventilation_list  = list(idf.idfobjects.get("ZONEVENTILATION:DESIGNFLOWRATE", []))

    all_infil_vent = infiltration_list + ventilation_list

    # 5) Fix or remove infiltration/vent schedules
    for obj in all_infil_vent:
        zone_name = obj.Zone_or_ZoneList_Name.strip()
        sched = obj.Schedule_Name.strip()

        if not sched:
            # If infiltration/vent has a blank schedule => remove or fallback
            if remove_if_missing_schedule:
                idf.removeidfobject(obj)
            else:
                obj.Schedule_Name = fallback_schedule
            continue

        # Attempt to rename e.g. "Commercial_Occ" => "Commercial_Occ_<zone>"
        zone_specific = f"{sched}_{zone_name}"
        if schedule_compact_exists(idf, zone_specific):
            obj.Schedule_Name = zone_specific
        else:
            # If the base schedule doesn't exist, remove or fallback
            if not schedule_compact_exists(idf, sched):
                if remove_if_missing_schedule:
                    print(f"[fix_infiltration_vent] Removing '{obj.Name}' because "
                          f"schedule '{sched}' nor '{zone_specific}' found.")
                    idf.removeidfobject(obj)
                else:
                    print(f"[fix_infiltration_vent] Assigning fallback '{fallback_schedule}' to "
                          f"'{obj.Name}' missing schedule '{sched}'/'{zone_specific}'.")
                    obj.Schedule_Name = fallback_schedule
            else:
                # base_sched is valid => keep it as is
                pass




def schedule_compact_exists(idf, sched_name):
    """Returns True if there's a SCHEDULE:COMPACT with Name == sched_name."""
    if "SCHEDULE:COMPACT" not in idf.idfobjects:
        return False
    target = sched_name.strip().lower()
    for sc in idf.idfobjects["SCHEDULE:COMPACT"]:
        if sc.Name.strip().lower() == target:
            return True
    return False

def _create_always_on_schedule(idf, sched_name, value=1.0):
    """
    Creates a minimal SCHEDULE:COMPACT that stays at 'value' for all hours of the year.
    """
    idf.newidfobject(
        "SCHEDULE:COMPACT",
        Name=sched_name,
        Schedule_Type_Limits_Name="Fraction",
        Field_1="Through: 12/31",
        Field_2="For: AllDays",
        Field_3="Until: 24:00",
        Field_4=str(value)
    )
