"""
Module containing the base simstock objects:
- :class:`SimstockDataframe`
- :class:`IDFcreator`
"""

import os
import shutil
import json
import inspect
import copy
import glob
import numpy as np
from typing import Any, Union
import platform
import itertools
import pandas as pd
from pandas.core.frame import DataFrame
import shapely as shp
from shapely.geometry import (
    Polygon,
    LineString, 
    MultiLineString
)
from shapely.ops import unary_union, linemerge
from eppy.modeleditor import IDF
from eppy.bunch_subclass import EpBunch
from simstock._utils._serialisation import (
    _series_serialiser,
    _assert_bool,
    _generate_unique_string
)
from simstock._utils._exceptions import SimstockException
import simstock._algs._polygon_algs as algs
import simstock._algs._simplification as smpl
import simstock._algs._idf_algs as ialgs
from simstock._utils._dirmanager import (
    _copy_directory_contents,
    _delete_directory_contents,
    _compile_csvs_to_idf
)


class SimstockDataframe:
    """
    A :class:`SimstockDataframe` is an object used by Simstock to store all input data and perform the necessary geometric simplification steps to make it a compatable with EnergyPlus. It behaves the in the same way as a Pandas :class:`DataFrame`, but with some key additional methods to perform geometric-based pre-processing.

    The :class:`SimstockDataframe` object also stores EnergyPlus settings, such as constructions, materials, and schedules. The class provides an interface for viewing and editing these settings. The settings can be viewed via the :class:`SimstockDataframe`'s properties; e.g. ``.constructions`` to view constructions, or ``.schedules`` to view schedules. These settings are stored in the form of `Eppy EpBunch <https://pythonhosted.org/eppy/dev_docs/epbunch.html>`_ objects which can be edited directly (see examples below). Settings can also be set by using ``csv`` files (see example below and :py:meth:`override_settings_with_csv`). By default the :class:`SimstockDataframe` will contain some standard settings. If you wish to start from a blank slate with no settings so that you can specify all of them yourself, then specifiy ``use_base_idf=True`` when constructing the :class:`SimstockDataframe`.

    Once the settings and data have been set, the :py:meth:`preprocessing` method can be used to ensure all geometries are compatable with E+, such as adjacent coordinates being a suitable tolerance away from each other (see example below). An EnergyPlus simulation can then be run using the :class:`IDFmanager` class.
    
    :param inputobject: The geometric data, containing polygons, a unique
        identifier, shading etc.
    :type inputobject: dict, :class:`DataFrame`, :class:`SimstockDataframe`
    :param polygon_coloumn_name: *Optional*. The name of the column or   
        field containing the geometric data (which should either
        be shapely objects or wkb or wkt strings). This is only required if the column is named something other that ``polygon``
    :type polygon_coloumn_name: str
    :param uid_column_name: *Optional*. The name of the column containing
        the unique IDs. This is only required if the ID column name is something other than ``osgb``
    :type uid_column_name: str
    :param epw_file: *Optional*. The file name, including the path, to your
        epw weather file. If none is specified, Simstock will default to using the St. James's park epw data
    :type epw_file: str
    :param tol: *Optional*. The minimum distance in metres that two 
        coordinates are allowed to be after geometric simplification. EnergyPlus requires this to be at least 0.1m.
    :type tol: float
    :param use_base_idf: *Optional* Whether or not to start with a blank slate
        settings object, so that you can populate the settings from scratch. Defaults to False
    :type use_base_idf: bool
    :param idd_file: *Optional* The file name, including the path, to your
        EnergyPlus .idd file. If none is specified, Simstock will look in common locations, such as ``C:\\EnergyPlus*\\`` if you are running Windows or ``/usr/local/EnergyPlus*`` or ``/Applications/EnergyPlus*`` if you are running Unix (note * will be the version number)
    :type idd_file: str

    :raises SystemError: If your operating systemm is of unknown type
    :raises FileNotFoundError: If an EnergyPlus .idd file could not be found
    :raises TypeError: If the input data is not a dict, :class:`DataFrame`, 
        or :class:`SimstockDataframe`, or if your polygon data is not comprised of shapely objects or wkb or wkt strings
    :raises KeyError: If a valid unique ID column could not be found. Hint: if
        your ID column is named something other than ``osgb``, then specifiy its name using the uid_column_name parameter

    **See also**: :class:`IDFmanager`

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # Create a SimstockDataframe from an already existing dict d
        sdf = sim.SimstockDataframe(d) 

    If your EnergyPlus installation, and therfore your .idd file is stored in a non-standard place, then use the `idd_file` parameter:

    .. code-block:: python

        sdf = sim.SimstockDataframe(
            d,
            idd_file="pathto/myenergyplusinstallation/my_idd_file.idd"
            )

    To view settings, e.g. the materials:

    .. code-block:: python

        mats = sdf.materials
        print(mats)

    Each setting is an `Eppy EpBunch <https://pythonhosted.org/eppy/dev_docs/epbunch.html>`_ object; e.g.,

    .. code-block:: python

        # This is a list of EpBunch objects, 
        # one for each material
        mats = sdf.materials

        # print the first material in the list
        print(mats[0])

    returns:

    .. code-block:: text

        MATERIAL,
            10mm_carpet,              !- Name
            Rough,                    !- Roughness
            0.01,                     !- Thickness
            0.058,                    !- Conductivity
            20,                       !- Density
            1000,                     !- Specific Heat
            0.9,                      !- Thermal Absorptance
            0.5,                      !- Solar Absorptance
            0.5;                      !- Visible Absorptance

    To edit any field in each bunch, you can do ``bunchobject.Fieldname`. For example, to edit the `Name` field of the material above:

    .. code-block:: python

        # Change the name
        mats[0].Name = "new_name" 

        # Now print to see the new name
        print(mats[0])

    returns: 

    .. code-block:: text

        MATERIAL,
            10mm_carpet,              !- new_name
            Rough,                    !- Roughness
            0.01,                     !- Thickness
            0.058,                    !- Conductivity
            20,                       !- Density
            1000,                     !- Specific Heat
            0.9,                      !- Thermal Absorptance
            0.5,                      !- Solar Absorptance
            0.5;                      !- Visible Absorptance

    As another example, let's adjust the heat balance algorithm: 

    .. code-block:: python

        # Print the heat balance algorithm EpBunch
        print(sdf.heat_balance_algorithm)

    returns:

    .. code-block:: text 

        HEAT_BALANCE_ALGORITHM,
            ConductionTransferFunction,       !- Algorithm
            200;                              !- Surface Temperature Upper Limit

    Now edit the surface temperature upper limit field and print the result:

    .. code-block:: python

        sdf.heat_balance_algorithm.Surface_Temperature_Upper_Limit = 210
        print(heat_balance_algorithm)

    gives:

    .. code-block:: text 

        HEAT_BALANCE_ALGORITHM,
            ConductionTransferFunction,       !- Algorithm
            210;                              !- Surface Temperature Upper Limit

    Settings can be edited in this programmatic fashion, or, alternatively, settings can be read in as csv files (see :py:meth:`override_settings_with_csv` and :py:meth:`create_csv_folder`). To do this, it is recommended to start from a blank settings template by doing:

    .. code-block:: python

        # Use the use_base_idf option to start from a blank settings template
        sdf = sim.SimstockDataframe(d, use_base_idf=True)

    Once you are satisfied with the settings, you can run the :py:meth:`preprocessing` function, to get the data ready for an EnergyPlus simulation:

    .. code-block:: python

        # Perform all necessary geometric simplification steps
        sdf.preprocessing()

    .. note:: \ \ 

        The :class:`SimstockDataframe` constructor creates a :class:`SimstockDataframe` from an object such as dict or Pandas :class:`DataFrame` that has been already instantiated and is in memory. To create a :class:`SimstockDataframe` from a file, see the functions :py:func:`read_csv`, :py:func:`read_json`, :py:func:`read_parquet`, and :py:func:`read_geopackage_layer`.
    
    Class properties:
    ~~~~~~~~~~~~~~~~~
    """

    # Common locations for E+ idd files
    _common_windows_paths = ["C:\\EnergyPlus*\\Energy+.idd"]
    _common_posix_paths = [
        "/usr/local/EnergyPlus*/Energy+.idd",
        "/Applications/EnergyPlus*/Energy+.idd"
    ]

    # Necessary data
    _required_cols = [
        "shading", "height", "wwr", "nofloors", "construction"
        ]

    def __init__(
            self,
            inputobject: Any,
            polygon_column_name: str = None,
            uid_column_name: str = None,
            epw_file: str = None,
            tol: float = 0.1,
            use_base_idf: str = False,
            idd_file: str = None,
            **kwargs
            ) -> None:
        """
        Constructor method
        """
        self.__dict__.update(kwargs) 

        #: The minumum allowable distance between adjacent coordinates in a polygon
        #:
        #: Example
        #: ~~~~~~~
        #:
        #: .. code-block:: python
        #:      
        #:      # Create a SimstockDaframe with tolerance 20cm
        #:      sdf = sim.SimstockDataframe(d, tol=0.2)
        #:
        #:      # View the tolerance
        #:      print(sdf.tol)
        #:
        #:      # Change the tolerance to 10cm
        #:      sdf.tol = 0.1
        #:
        self.tol: float = tol 

        #: idd file name and full path
        if idd_file is not None:
            self._idd_file: str = idd_file
        elif os.environ.get('IDD_FILE'):
            self._idd_file = os.environ.get('IDD_FILE')
        elif idd_file is None:
            # Determine OS
            opsys = platform.system().casefold()
            if opsys not in ["windows", "darwin", "linux"]:
                msg = f"OS: {opsys} not recognised."
                raise SystemError(msg)
            self._find_idd(opsys)

        # Get simstock directory
        current_file_path = inspect.getframeinfo(inspect.currentframe()).filename
        absolute_file_path = os.path.abspath(current_file_path)
        self.simstock_directory = os.path.dirname(absolute_file_path)

        # Set default settings
        IDF.setiddname(self._idd_file)
        if use_base_idf:
            self.settings = IDF(
            os.path.join(self.simstock_directory, "settings", "base.idf")
        )
        else:
            self.settings = IDF(
                os.path.join(self.simstock_directory, "settings", "settings.idf")
            )
        self.settings_csv_path = None
        
        # If it is already a valid simstock dataframe
        # then nothing further needs to be done
        if isinstance(inputobject, SimstockDataframe):
            self._df = inputobject._df.copy()
            return
            
        # If it is not already a pandas dataframe, then
        # try and turn it into one.
        # Input data that does not meet the specs 
        # will fail to be serialised here and 
        # will throw an Exception
        if not isinstance(inputobject, pd.DataFrame):
            try:
                self._df = pd.DataFrame(inputobject)
            except Exception as exc:
                errmsg = "Unable to create data frame from input data."
                raise TypeError(errmsg) from exc
        else:
            self._df = inputobject.copy()

        # Rename polygon and osgb columns if user has specified
        if uid_column_name:
            self._df.rename(columns={uid_column_name: "osgb"}, inplace=True)
        if polygon_column_name:
            self._df.rename(columns={polygon_column_name: "polygon"}, inplace=True)
        
        # Check that an osgb column exists
        self._validate_osgb_column()

        # Check that the polygon column exists
        self._validate_polygon_column() 

        # Check for any multipolygons with length > 1
        self._check_for_multipolygons()

        # Add any missing columns
        self._add_missing_cols()

        # Has pre-processing occured?
        self.processed = False

        # Set weather file
        if epw_file:
            self.epw = epw_file
        else:
            self.epw = os.path.join(self.simstock_directory, "settings", "GBR_ENG_London.Wea.Ctr-St.James.Park.037700_TMYx.2007-2021.epw")

    def __getattr__(self, attr: str) -> Any:
        """
        Required function to allow user to interface
        with underlying dataframe.
        """
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self._df, attr)

    def __getitem__(self, item: Any) -> Any:
        """
        Required function to allow user to interface
        with underlying dataframe.
        """
        return self._df[item]

    def __setitem__(self, item: Any, data: Any) -> None:
        """
        Required function to allow user to interface
        with underlying dataframe.
        """
        self._df[item] = data

    def __str__(self) -> str:
        """
        Points string method to the underlying dataframe.
        """
        return self._df.__str__()

    # Replace this with a modified call down to pandas __repr__. 
    def __repr__(self) -> str:
        """
        Prints concise info about this object.
        """
        return "SimstockDataframe()"
    
    def _find_idd(self, system: str) -> None:
        if system == "windows":
            paths = self._common_windows_paths
        else:
            paths = self._common_posix_paths
        for path in paths:
            # Use glob to handle pattern matching for version number
            matches = glob.glob(path)
            if matches:
                self._idd_file = matches[0]
                break
        if self._idd_file == None:
            raise FileNotFoundError("Could not find EnergyPlus IDD file")
            
    @property
    def is_exterior_ccw(self) -> list[bool]:
        """
        True if polygon exteriors are counter-clockwise
        """
        return self._df['polygon'].map(algs._is_exterior_ccw)
    
    @property
    def is_valid(self) -> list[bool]:
        """
        True if the polygon column's objects are valid shapely geometries
        """
        return shp.is_valid(self._df['polygon'])
    
    @property
    def length(self) -> int:
        """
        Number of data entries in this SimstockDataframe 
        """
        return self._df.__len__()
    
    @property
    def built_islands(self) -> int:
        """
        The number of built islands
        """
        try:
            return len(self._df["bi"].unique())
        except KeyError:
            return 0
    
    @property
    def materials(self) -> list:
        """
        The list of materials (in :class:`eppy.bunch_subclass.EpBunch` format)

        Example
        ~~~~~~~
        .. code-block:: python

            # Print each material's EpBunch 
            for mat in sdf.materials:
                print(mat)

            # Change the name of the first material in the list
            sdf.materials[0].Name = "some_new_name"
        
        """
        return self.settings.idfobjects["MATERIAL"]
    
    @property
    def material_nomass(self) -> list:
        """
        The list of no-mass materials (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["MATERIAL:NOMASS"]
    
    @property
    def window_material_glazing(self) -> list:
        """
        The list of window glazing materials (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["WINDOWMATERIAL:GLAZING"]
    
    @property
    def window_material_gas(self) -> list:
        """
        The list of window gas layer materials (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["WINDOWMATERIAL:GAS"]
    
    @property
    def constructions(self) -> list:
        """
        The list of constructions (in :class:`eppy.bunch_subclass.EpBunch` format)

        Example
        ~~~~~~~
        .. code-block:: python

            # Print each constructions's EpBunch 
            for cons in sdf.sonstructions:
                print(cons)

            # Change the name of the first construction in the list
            sdf.constructions[0].Name = "some_new_name"
        
        """
        return self.settings.idfobjects["CONSTRUCTION"]
    
    @property
    def schedules(self) -> list:
        """
        The list of schedules (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["SCHEDULE:COMPACT"]
    
    @property
    def simulation_control(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the simulation control options:
         
        - "Do Zone Sizing Calculation", defaults to No
        - "Do System Sizing Calculation", defaults to No
        - "Do Plant Sizing Calculation", defaults to No
        - "Run Simulation for Sizing Periods", defaults to No
        - "Run Simulation for Weather File Run Periods", defaults to Yes
        """
        return self.settings.idfobjects["SIMULATIONCONTROL"][0]
    
    @simulation_control.setter
    def simulation_control(self, new_controls: EpBunch) -> None:
        self.settings.idfobjects["SIMULATIONCONTROL"][0] = new_controls
    
    @property
    def building(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the building simulation options:

        - "Name", defaults to "building"
        - "North Axis", defaults to 0
        - "Terrain", defaults to "City"
        - "Loads Convergence Tolerance Value", defaults to 0.04
        - "Temperature Convergence Tolerance Value", defaults to 0.4
        - "Solar Distribution", defaults to "FullExerior"
        - "Maximum Number of Warmup Days", defaults to 25
        - "Minimum Number of Warmup Days", defaults to 6
        """
        return self.settings.idfobjects["BUILDING"][0]
    
    @building.setter
    def simulation_control(self, new_building: EpBunch) -> None:
        self.settings.idfobjects["BUILDING"][0] = new_building
    
    @property
    def shadow_calculation(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the shadow calculation options:

        - "Calculation Method", defaults to "AverageOverDaysInFrequency"
        - "Calculation Frequency", defaults to 20
        - "Maximum Figure in Shadow Overlap Calculations", defaults to 15000
        - "Polygon Clipping Algorithm", defaults to "SutherlandHodgman"
        - "Sky Diffuse Mofeling Algorithm", defaults to "SimpleSkyDiffuseModeling"
        """
        return self.settings.idfobjects["SHADOWCALCULATION"][0]
    
    @shadow_calculation.setter
    def shadow_calculation(self, new_shadow_cals: EpBunch) -> None:
        self.settings.idfobjects["SHADOWCALCULATION"][0] = new_shadow_cals
    
    @property
    def inside_convection_algorithm(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the inside surface convection algorithm, defaults to "TARP"
        """
        return self.settings.idfobjects["SURFACECONVECTIONALGORITHM:INSIDE"][0]
    
    @inside_convection_algorithm.setter
    def inside_convection_algorithm(
        self, new_inside_convection_alg: EpBunch
        ) -> None:
        self.settings.idfobjects["SURFACECONVECTIONALGORITHM:INSIDE"][0] = new_inside_convection_alg
    
    @property
    def outside_convection_algorithm(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the outside surface convection algorithm, defaults to "TARP"
        """
        return self.settings.idfobjects["SURFACECONVECTIONALGORITHM:OUTSIDE"][0]
    
    @outside_convection_algorithm.setter
    def outside_convection_algorithm(
        self, new_outside_convection_alg: EpBunch
        ) -> None:
        self.settings.idfobjects["SURFACECONVECTIONALGORITHM:OUTSIDE"][0] = new_outside_convection_alg
    
    @property
    def heat_balance_algorithm(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the heat balance algorithm options: 

        - "Algorithm", defaults to "ConductionTransferFunction
        - "Surface Temperature Upper Limit", defaults to 200
        """
        return self.settings.idfobjects["HEATBALANCEALGORITHM"][0]
    
    @heat_balance_algorithm.setter
    def heat_balance_algorithm(self, new_heat_alg: EpBunch) -> None:
        self.settings.idfobjects["HEATBALANCEALGORITHM"][0] = new_heat_alg
    
    @property
    def timestep(self) -> int:
        """
        The number of timesteps per hour, defaults to 4
        """
        return self.settings.idfobjects["TIMESTEP"][0].Number_of_Timesteps_per_Hour
    
    @timestep.setter
    def timestep(self, new_timestep: int) -> None:
        self.settings.idfobjects["TIMESTEP"][0].Number_of_Timesteps_per_Hour = new_timestep
    
    @property
    def run_period(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing the run period options: 

        - "Name", defaults to NA
        - "Begin Month", defaults to 1
        - "Begin Day of Month", defaults to 1
        - "End Month", defaults to 12
        - "End Day of Month", defaults to 31
        - "Day of Week for Start Day", defaults to "Monday"
        - "Use Weather File Holidays and Special Days", defaults to "Yes"
        - "Use Weather File Daylight Saving Period", defaults to "Yes"
        - "Apply Weekend Holiday Rule", "defaults to "No"
        - "Use Weather File Rain Indicators", defaults to "Yes"
        - "Use Weather File Snow Indicators", defaults to "Yes"
        - "Number of Times Runperiod to be Repeated", defaults to 1
        """
        return self.settings.idfobjects["RUNPERIOD"][0]
    
    @run_period.setter
    def run_period(self, new_run_period: EpBunch) -> None:
        self.settings.idfobjects["RUNPERIOD"][0] = new_run_period
    
    @property
    def schedule_type_limits(self) -> list:
        """
        List of :class:`eppy.bunch_subclass.EpBunch` objects containing schedule type limits
        """
        return self.settings.idfobjects["SCHEDULETYPELIMITS"]
    
    @property
    def schedule_constant(self) -> EpBunch:
        """
        :class:`eppy.bunch_subclass.EpBunch` object containing constant schedule options:

        - "Name", defaults to "Always 4"
        - "Schedule Type Limits Name", defaults to "Control Type"
        - "Hourly Value", defauts to 4 
        """
        return self.settings.idfobjects["SCHEDULE:CONSTANT"][0]
    
    @schedule_constant.setter
    def schedule_constant(self, new_schedule_constant: EpBunch) -> None:
        self.settings.idfobjects["SCHEDULE:CONSTANT"][0] = new_schedule_constant
    
    @property
    def people(self) -> list:
        """
        The list of people types (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["PEOPLE"]
    
    @property
    def lights(self) -> list:
        """
        The lighting list (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["LIGHTS"]
    
    @property
    def electric_equipment(self) -> list:
        """
        The list of electrical equipment (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["ELECTRICEQUIPMENT"]
        
    @property
    def thermostat(self) -> list:
        """
        The list of thermostats (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["ZONECONTROL:THERMOSTAT"]
    
    @property
    def thermostat_dual_setpoint(self) -> list:
        """
        The list of thermostat dual set points (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["THERMOSTATSETPOINT:DUALSETPOINT"]
    
    @property
    def output_variable_dictionary(self) -> EpBunch:
        """
        The output variable dictionary (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["OUTPUT:VARIABLEDICTIONARY"][0]
    
    @output_variable_dictionary.setter
    def output_variable_dictionary(self, new_out_dict: EpBunch) -> None:
        self.settings.idfobjects["OUTPUT:VARIABLEDICTIONARY"][0] = new_out_dict
    
    @property
    def output_variable(self) -> list:
        """
        The list of desired EnergyPlus simulation output variables (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["OUTPUT:VARIABLE"]
    
    @property
    def output_diagnostics(self) -> EpBunch:
        """
        The EnergyPlus simulation output diagnostics (in :class:`eppy.bunch_subclass.EpBunch` format)
        """
        return self.settings.idfobjects["OUTPUT:DIAGNOSTICS"][0]
    
    @output_diagnostics.setter
    def output_diagnostics(self, new_out_diags: EpBunch) -> None:
        self.settings.idfobjects["OUTPUT:DIAGNOSTICS"][0] = new_out_diags
    
    def print_settings(self) -> None:
        """
        Function to print the entire settings in a readable format. Interally, the SimstockDataframe stores settings as an :class:`IDF` object. This function essentially displays this object. 

        Example
        ~~~~~~~
        .. code-block:: python

            # Given a simstockdataframe sdf
            sdf.print_settings()

        Idividual settings, such as ``constructions`` can be viewed and edited using the invidual settings properties, such as :py:meth:`constructions`
        """
        self.settings.printidf()

    def create_csv_folder(
            self,
            settings_csv_path: str = "simulation_settings"
            ) -> None:
        """
        Function to create an empty directory full of csv files, into which you can add your settings. The directory will have the following structure: 

        | simulation_settings/
        | ├── DB-Fabric-CONSTRUCTION.csv
        | ├── DB-Fabric-MATERIAL_NOMASS.csv
        | ├── DB-Fabric-MATERIAL.csv
        | ├── DB-Fabric-WINDOWMATERIAL_GAS.csv
        | ├── DB-Fabric-WINDOWMATERIAL_GLAZING.csv
        | ├── DB-HeatingCooling-OnOff.csv
        | ├── DB-Loads-ELECTRICEQUIPMENT.csv
        | ├── DB-Loads-LIGHTS.csv
        | ├── DB-Loads-PEOPLE.csv
        | ├── DB-Schedules-SCHEDULE_COMPACT.csv
        | ├── infiltration_dict.json
        | └── ventilation_dict.json

        The :py:meth:`override_settings_with_csv` method can then be used to set the SimstockDataframe's internal settings using these csv files.

        :param settings_csv_path: *Optional*. The name of the directory (including the full path from your current working directory) into which to 
            place the csv files. Defaults to ``simulation_settings/``, which we be placed in your working directory
        :type dirname: str

        .. warning:: \ \ 

            If the directory `settings_csv_path` (default: "simulation_settings/") already exists, then it will be overwritten.
        """
        # Check if the directory already exists and delete
        # its contents if it does, otherwise make it
        self.settings_csv_path = settings_csv_path
        if os.path.exists(self.settings_csv_path):
            _delete_directory_contents(self.settings_csv_path)
        else:
            os.makedirs(self.settings_csv_path)

        # Copy defaults from internal database into new settings directory
        _copy_directory_contents(
            os.path.join(self.simstock_directory, "settings"),
            os.path.join(self.settings_csv_path)
        )


    def override_settings_with_csv(self, **kwargs) -> None:
        """
        Function that reads in the settings stored in the csv files in the directory ``settings_csv_path`` (default `` simulation_settings``) and uses them to set the internal SimstockDataframe settings, such as materials etc. 

        An ``FileNotFoundError`` will be raised if the ``settings_csv_path`` directory cannot be found. In this case, either call the :py:meth:`create_csv_folder` method to create it, or specify the path to one that already exists using the SimstockDataframe's ``settings_csv_path`` property. Equivalently, you could specify this as a key word argument when calling the :py:meth:`override_settings_with_csv`.

        :param \**kwargs:
            Optional keyword parameters, such as `settings_csv_path` or any of
            the other SimstockDataframe properties
        
        :raises FileNotFoundError:
            If the `settings_csv_path` does not exist or has not been specified.
        :raises KeyError:
            If the input csv data contains unrecognised fields. Try running :py:meth:`create_csv_folder` to generate correctly formated files.

        **See also**: :py:meth:`create_csv_folder`

        Example
        ~~~~~~~
        .. code-block:: python 

            # If you already have settings csv files saved in a directory 
            # called my_directory within your working directory, you could call:
            sdf.override_settings_with_csv(settings_csv_path="my_directory")
        """
        self.__dict__.update(kwargs)
        if self.settings_csv_path == None:
            msg = "No csv folder found. Call create_csv_folder() first."
            raise FileNotFoundError(msg)
        _compile_csvs_to_idf(self.settings, self.settings_csv_path)

    
    def _validate_osgb_column(self) -> None:
        """
        Function to check the existance of a column named ``osgb``.
        If none is found, then a KeyError is raised. The function 
        also puts column name into lower case if not already.
        """
        cols = [e for e in self._df.columns if e.casefold() == "osgb"]
        if len(cols) == 0:
            raise KeyError("No \"osgb\" column dectected!")
        self._df = self._df.rename(columns={cols[0] : "osgb"})

    def _validate_polygon_column(self) -> None:
        """
        Function to check varify the ``polygon`` column. First, the 
        function checks there is a column named ``polygon`` and puts
        that name into lower case if not already. A KeyError is 
        thrown if no such column exists. The function then attempts
        to serialise the contents of the column into shapely 
        geometry objects. If the column does not already contain shapely
        objects or ``wkt`` or ``wkb`` objects, then this will fail and 
        throw a TypeError to indicate that the column contains
        no valid geometric data.
        """
        cols = [e for e in self._df.columns if e.casefold() == "polygon"]
        if len(cols) == 0:
            raise KeyError("No \"polygon\" column dectected!")
        try:
            self._df[cols[0]] = _series_serialiser(self._df[cols[0]])
            self._df = self._df.rename(columns={cols[0] : "polygon"})
            return 
        except TypeError as exc:
            errmsg = "Unable to find valid shapely data in \"polygon\""
            raise TypeError(errmsg) from exc

    def _add_missing_cols(self) -> None:
        missing = []
        for col in self._required_cols:
            if col not in self._df.columns:
                missing.append(col)
                print(f"Adding missing {col} column.")
                self._df[col] = float('nan')
        if len(missing) > 0:
            print(f"Please populate the following columsn with data:")
            print(missing)
    
    def _add_interiors_column(self) -> None:
        self._df['interiors'] = self._df['polygon'].map(algs._has_interior)
    
    
    def orientate_polygons(self, **kwargs) -> None:
        """
        Function to ensure that polygon exteriors are orientated anticlockwise
        annd interiors clockwise. This is to ensure internal consistency.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties
        """
        self.__dict__.update(kwargs)
        self._add_interiors_column()
        self._df['polygon'] = self._df['polygon'].map(algs._orientate)


    def _check_for_multipolygons(self) -> None:
        """
        Hand-drawn polygons can be multipolygons with len 1, i.e. a nested
        polygon within a multipolygon wrapper. This aims to extract them,
        and catch cases where there are true multipolygons that have length
        of more than 1. 
        """

        # Convert any multipolygons of length 1 into regular polygons
        # if this cant be done, then it must be a non-trivial
        # multipolygon that needs fixing. A new flag column
        # keeps track of which things are true multi-polygons
        # (will equal True if so)
        self._df[["flag", "polygon"]] = self._df["polygon"].apply(
            algs._check_for_multi
            ).apply(pd.Series)
        
        # If there are no non-trivial multipolygons, then we are
        # done here and just drop the flag column
        if not self._df["flag"].any():
            self._df.drop("flag", axis=1, inplace=True)
            return

        # Extract "osgb" values for entries with multiple polygons
        multipoly_osgb = self._df[self._df["flag"]]["osgb"].tolist()
        print("Error: The following entries are MultiPolygons:")
        for poly in multipoly_osgb:
            print(poly)
        raise TypeError(f"There are {len(multipoly_osgb)} MultiPolygons.")


    def remove_duplicate_coords(self, **kwargs) -> None:
        """
        Function to remove duplicated coordinates from polygons, while ensuring the polygons remain valid shapely objects.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        Example
        ~~~~~~~
        .. code-block:: python

            import simstock as sim
            sdf = sim.read_csv("path/to/file.csv")
            sdf.remove_duplicate_coords()
        """
        self.__dict__.update(kwargs)
        self._df['polygon'] = self._df['polygon'].map(
            algs._remove_duplicate_coords
            )

    def polygon_topology(self, **kwargs) -> None:
        """
        Function that checks whether polygons are touching or interecting each other. If any intersections are detected, an error is thrown. 

        This function adds an additonal column to the SimstockDataframe called ``touching``. The i\ :sup:`th` entry in ``touching`` lists the ``osbg`` values of all polygons touching the polygon in row i.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        :Raises: **ValueError**
            - If any polygons are touching.

        Example
        ~~~~~~~
        .. code-block:: python

            import simstock as sim
            sdf = sim.read_csv("path/to/file.csv")
            sdf.polygon_topology()
        """
        self.__dict__.update(kwargs)

        # Create column named ``touching``. Each element
        # is an empty list
        length_range = range(self._df.__len__())
        self._df['touching'] = pd.Series([] for _ in length_range)

        # Iterate over all possible pairs of polygons in the data
        for i, j in itertools.combinations(length_range, 2):
            poly_i = self._df['polygon'][i]
            poly_j = self._df['polygon'][j]
            osgb_i = self._df['osgb'][i]
            osgb_j = self._df['osgb'][j]
            try:
                # If polygon i touches polygon j, 
                # then add j's osgb value to i's
                # ``touching`` column. By symmetry, 
                # also add i's osbg to j's 
                # ``touching`` column
                if algs._is_touching(poly_i, poly_j):
                    self._df['touching'][i].append(osgb_j)
                    self._df['touching'][j].append(osgb_i)
            
            # If polygon i intersects polygon j, then the
            # _is_touching function will throw a ValueError.
            # Catch this error and pass it on with context.
            except ValueError as exc:
                errmsg = f"Warning: OSGB {osgb_i} intersects {osgb_j}"
                raise ValueError(errmsg) from exc

    def polygon_tolerance(self, **kwargs) -> None:
        """
        A function to assess which polygons need simplifying, based on a user-specifed tolerance. This can be set via the `tol` property, 
        or also via the key word arguments of this function.

        Simplification here means removing intermediate coordinates in 
        a shape while preserving the shapes topology. Coordinates that
        are closer together than some tolerance are candidates for removal.

        This function adds a boolean column named ``simplify`` which specifies whether each polygon needs simplifying or not, based on the tolerance. A value in this column will be True if the corresponding geometry contains coordinate that are closer together than tol (in metres). This is important bacause EnergyPlus requires that no two coordinates are closer together than 0.1m.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        example
        ~~~~~~~
        .. code-block:: python

            # To check if any polygons have coordinates closer than 
            # 0.2m together, first call
            sdf.polygon_tolerance(tol=0.2)

            # This will add a new column called simplify, which 
            # can now be viewed:
            print(sdf["simplify"])
        """
        self.__dict__.update(kwargs)
        f = lambda x: algs._poly_tol(x, self.tol)
        self._df['simplify'] = self._df['polygon'].map(f)

    def _polygon_within_hole(self) -> None:
        """
        Function to find if any polygons are contained
        within the interiors of another.
        """

        # Create column named ``poly_within_hole``. Each element
        # is an empty list
        length_range = range(self._df.__len__())
        self._df['poly_within_hole'] = pd.Series([] for _ in length_range)

        # Iterate over the cartesian product of polygons
        for i, j in itertools.product(length_range, length_range):
            if i != j and self._df['interiors'][i]:

                # If polygon i has interiors, then check if polygon j
                # touches polygon i
                touches = self._df['osgb'][j] in self._df['touching'][i]

                # Now iterate over the interiors of polygon i
                for item in self._df['polygon'][i].interiors:
                    item_poly = Polygon(item.coords[::-1])

                    # If the interior both touchs and contains j, then we know
                    # j exists within a hole inside i
                    # We make a note of this in the `poly_within_hole` column
                    if item_poly.contains(self._df['polygon'][j]) and touches:
                        self._df['poly_within_hole'][i].append(
                            self._df['osgb'][j]
                            )
                       
    def _polygon_buffer(self) -> None:
        for i, polygon in enumerate(self._df['polygon']):
            if not polygon.is_valid:
                # If any polygons are not valid, 
                # then we set the buffer to 0
                new_polygon = polygon.buffer(0)
                new_coords, removed_coords = [], []

                # If this invalid polygon is touching anything, 
                # then we find which coordinates have been removed
                # and added when we set the buffer to 0
                if self._df['touching'][i]:
                    new_coords = list(
                        set(list(new_polygon.exterior.coords)) - set(list(polygon.exterior.coords)))
                    removed_coords = list(
                        set(list(polygon.exterior.coords)) - set(list(new_polygon.exterior.coords)))
                    
                # If any new coordinates were found, then we iterate
                # over all polygons that this polygon touches, 
                # and replace them with buffered polygons
                if new_coords:
                    for osgb_touching in self._df['touching'][i]:
                        t_poly = self._df.loc[
                                self._df['osbg'] == osgb_touching, 'polygon'
                                ].values[0]
                        self._df.loc[
                            self._df['osgb'] == osgb_touching, 'polygon'
                            ] = algs._buffered_polygon(t_poly, new_coords, removed_coords)

    # This function seems redundant                   
    def _touching_poly(self,
                       osgb: str,
                       polygon: Polygon, 
                       osgb_list : list[str], 
                       osgb_touching : list[str]
                       ) -> list[str]:
        for t in osgb_list:
            if t != osgb:
                # Not sure this if is necessary
                t_polygon = self._df.loc[self._df['osgb'] == t, 'polygon'].values[0]
                if t_polygon:
                    if polygon.touches(t_polygon):
                        osgb_touching.append(t)
        return osgb_touching
                        
    def _polygon_simplify(self) -> None:
        """
        Internal function to apply simplification to 
        those polygons that have been flagged
        as needing simplification.
        """
        # Iterate over unique polygons and see if they 
        # the need simplifying
        osgb_list = self._df['osgb'].unique().tolist()
        for osgb in osgb_list:
            if self._df.loc[self._df['osgb'] == osgb, 'simplify'].values[0]:
                osgb_touching = list()
                polygon = self._df.loc[
                    self._df['osgb'] == osgb, 'polygon'
                    ].values[0]
                if polygon:
                    # This could be done better: 
                    # no need to be passing around the osgb list
                    osgb_touching = self._touching_poly(
                        osgb, polygon, osgb_list, osgb_touching
                        )
                    # OSGB touching could be stored as a class variable,
                    # it is also in the dataframe already. The variable
                    # osgb in this function should therefore be deprecated.
                    self._df = smpl._polygon_simplifying(
                        polygon, self._df, osgb, osgb_touching
                        )
                        
    def polygon_simplification(self, **kwargs) -> None:
        """
        Function that simplifies polygons, by e.g. exploiting transitivity of points and merging points within tolerances, such that no polygons contain coordinates closer together than ``tol``. 

        Only functions that have been marked for simplification by the 
        :py:meth:`polygon_tolerance` function will be simplified. Therefore, 
        :py:meth:`polygon_tolerance` must be called first.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        :Raises: **KeyError**
            - If no ``simplify`` column can be found, meaning that
            :py:meth:`polygon_tolerance` has not yet been called.

        **See also**: :py:meth:`polygon_tolerance`
        """
        self.__dict__.update(kwargs)
        while self._df['simplify'].sum() > 0:
            self._polygon_within_hole()
            self._polygon_simplify()
            self._df = self._df.loc[
                ~self._df['polygon'].isin([False])
                ].reset_index(drop=True)
            self._polygon_buffer()
            self.polygon_tolerance()
        try:
            self._df = self._df.drop(['simplify', 'poly_within_hole'], axis=1)
        except KeyError:
            pass

    # This could be refactored as a map
    def collinear_exterior(self, **kwargs) -> None:
        """
        Function that removes collinear points from polygons and determines exterior surfaces.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties
        """
        self.__dict__.update(kwargs)

        # Iterate over each polygon and then over each
        # polygon that it touches
        for row in self._df.itertuples():
            osgb_touching = row.touching
            polygon = row.polygon
            osgb = row.osgb
            if osgb_touching:
                for t in osgb_touching:

                    # Remove collinear points from the intersection
                    t_polygon = self._df.loc[
                        self._df['osgb'] == t, 'polygon'
                        ].values[0]
                    partition = polygon.intersection(t_polygon)
                    if partition.geom_type == 'MultiLineString':
                        partition = linemerge(partition)
                    partition_collinear_points = algs._collinear_points_list(
                        partition)
                    if partition_collinear_points:
                        polygon = algs._update_polygon(
                            polygon, partition_collinear_points)
                        t_polygon = algs._update_polygon(
                            t_polygon, partition_collinear_points)
                        self._df.loc[
                            self._df['osgb'] == t, 'polygon'
                            ] = t_polygon
                        self._df.loc[
                            self._df['osgb'] == osgb, 'polygon'
                            ] = polygon
        
        # Now iterate again over all of the polygons
        # If any of them touch anything, then carve
        # it up into inner and outer components
        for row in self._df.itertuples():
            osgb_touching = row.touching
            polygon = row.polygon
            osgb = row.osgb
            if osgb_touching:
                outer_ring = LineString(polygon.exterior)
                inner_ring = MultiLineString(polygon.interiors)
                exposed = unary_union((outer_ring, inner_ring))

                # Then subtract any of the intersecting points from 
                # the exposed areas and then remove collinear points
                for t in osgb_touching:
                    t_polygon = self._df.loc[
                        self._df['osgb'] == t, 'polygon'
                        ].values[0]
                    exposed -= polygon.intersection(t_polygon)
                exposed_collinear_points = algs._collinear_points_list(exposed)
                if exposed_collinear_points:
                    exposed = algs._update_exposed(exposed, exposed_collinear_points)
                    polygon = algs._update_polygon(polygon, exposed_collinear_points)
                horizontal = algs._remove_collinear_points_horizontal(polygon)
            else:
                # If the polygon doesn't touch anything, then 
                # remove the collinear points
                polygon = algs._remove_collinear_points_horizontal(polygon)
                horizontal = polygon
                outer_ring = LineString(polygon.exterior)
                inner_ring = MultiLineString(polygon.interiors)
                exposed = unary_union((outer_ring, inner_ring))

            # For each polygon store the coordinates of the 
            # exposed walls, the updated polygon and the 
            # horizontal polygon
            self._df.loc[
                self._df['osgb'] == osgb, 'polygon_exposed_wall'
                ] = exposed
            self._df.loc[
                self._df['osgb'] == osgb, 'polygon'
                ] = polygon
            self._df.loc[
                self._df['osgb'] == osgb, 'polygon_horizontal'
                ] = horizontal
        self.processed = True

    def bi_adj(self, **kwargs) -> None:
        """
        Function to group buildings into built islands (BIs). E.g. 
        two semi-detatched houses in BIs. This adds a new column 
        to the SimstockDataframe called BI, which contains unique
        building island IDs.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        :Raises: **ValueError**
            - If building islands are unable to be resolved.
        """
        self.__dict__.update(kwargs)
        polygon_union = unary_union(self._df.polygon)
        if polygon_union.geom_type == "MultiPolygon":
            for bi in polygon_union.geoms:
                # Get a unique name for the BI which is based on a point
                # within the BI so that it doesn't change if new areas are lassoed
                rep_point = bi.representative_point()
                bi_name = "bi_" + str(round(rep_point.x, 2)) + "_" + str(round(rep_point.y, 2))
                bi_name = bi_name.replace(".", "-") #replace dots with dashes for filename compatibility
                for row in self._df.itertuples():
                    if row.polygon.within(bi):
                        self._df.at[row.Index, 'bi'] = bi_name
        else:
            # If there is only one BI
            rep_point = polygon_union.representative_point()
            bi_name = "bi_" + str(round(rep_point.x, 2)) + "_" + str(round(rep_point.y, 2))
            bi_name = bi_name.replace(".", "-")
            for row in self._df.itertuples():
                self._df.at[row.Index, 'bi'] = bi_name
        
        if len(self._df["bi"]) != len(self._df["bi"].dropna()):
            raise ValueError("Simstock was unable to resolve all built islands."
                            "It is likely that intersections are present.")

        try:
            non_shading_gdf = self._df[self._df["shading"] == False]["bi"]
            modal_bi = non_shading_gdf.mode().values
            modal_bi_num = sum(non_shading_gdf.isin([modal_bi[0]]).values)
            print("The BI(s) with the most buildings: %s with %s thermally simulated buildings" % (modal_bi, modal_bi_num))
        except:
            pass

            
    def preprocessing(self, **kwargs) -> None:
        """
        Function to perform default all the necessary geometric simplification and processing on the SimstockDataframe to make it EnergyPlus compatable. Specifically this function takes ensures all the necessary conditions ar met, such as no adjacent coordinates ina polygon being closer than 0.1m together. 

        This function calls the following functions in order: 

            1. :py:meth:`orientate_polygons`
            2. :py:meth:`remove_duplicate_coords`
            3. :py:meth:`polygon_topology`
            4. :py:meth:`polygon_tolerance`
            5. :py:meth:`polygon_simplification`
            6. :py:meth:`polygon_topology`
            7. :py:meth:`collinear_exterior`
            8. :py:meth:`polygon_topology`
            9. :py:meth:`bi_adj`

        In essence, this function first checks that all polygons are correctly orientated. It then proceeds to remove duplicate coordinates and simplify polygons while ensuring that polygons do not intersect each other.

        :param \**kwargs:
            Optional keyword parameters: any of the  
            SimstockDataframe properties

        .. hint:: \ \ 

            You can instead call functions 1. to 9. above manually for finer grained control.

        """
        self.__dict__.update(kwargs)
        # Perform all of the steps,
        # one after the other
        self.orientate_polygons()
        self.remove_duplicate_coords()
        self.polygon_topology()
        self.polygon_tolerance()
        self.polygon_simplification()
        self.polygon_topology()
        self.collinear_exterior()
        self.polygon_topology()
        self.bi_adj()


class IDFmanager:
    """
    An ``IDFmanager`` is a container object used to create elements
    for an EnergyPlus simulation. The object contains functions to
    take geometric and contextual data in the form of a 
    SimstockDataframe, and create an IDF file or Eppy IDF
    object for an E+ run.

    :param data:
        The input data containing polygon information, and optionally built-island data.
    :type data: 
        :class:`simstock.SimstockDataframe`
    :param min_avail_width_for_window: 
        *Optional*. Do not place window if the wall width is less than this number
    :type min_avail_width_for_window:
        float, int
    :param min_avail_height: 
        *Optional*. Do not place window if partially exposed external wall is less than this number % of zone height
    :type min_avail_height: 
        float, int
    :param out_dir:
        *Optional*. The directory (including full file path) into which to place the EnergyPlus output files, defaults to ``outs/``
    :type out_dir: 
        str
    :param bi_mode:
        *Optional*. Whether or not to group buildings into built islands (BIs)
    :type bi_mode: 
        bool
    :param data_fname: 
        *Optional*. Unique name for this simuation project. Only necessary if you want to save the building count, in which case that information will be saved to a file called data_fname within the out_dir directory
    :type data_fname:
        str
    :param save_building_count:
        *Optional*. Whether or not to save the number of buildings being simulated to a file called data_fname within out_dir. If not data_fname is supplied, then a unique string will be generated for the file name instead
    :type save_building_count:
        bool
    :param epw:
        *Optional*. Path and file name of an epw weather file to use for the weather settings. If none is specified, the St. James's park weather data will be used instead
    :type epw:
        str
    :param buffer_radius:
        *Optional*. The distance in metres of building buffers
    :type buffer_radius:
        float, int
    :param ventilation_dict:
        *Optional*. Dictioary containing ventilation settings. If none is specified, then default settings will be used
    :type ventilation_dict:
        dict
    :param infiltration_dict:
        *Optional*. Dictionary containing infiltration settings. If none is specified, then default settings will be used
    :type infiltration_dict:
        dict

    :raises TypeError:
        If the input data is not of type *str*, :class:`simstock.SimstockDataframe`, or :class:`DataFrame`
    :raises FileNotFoundError: 
        If the input data is a file name and path, but that file cannot be found
    :raises IOError: 
        If the input data is a file name and path, but that file cannot be read
    :raises SimstockException:
        If the input data does not contain the necessary fields. (See data specification above)

    Example
    ~~~~~~~
    .. code-block:: python

        # Basic usage example
        # given a SimstockDataframe sdf
        simulation = sim.IDFmanager(sdf)

        # Now compute model IDFs for each built island
        simulation.create_model_idf(bi_mode=True)

        # Run E+ simulation, this will put outputs into outs/ folder by default
        simulation.run()
    
    

    **See also**: :py:class:`SimstockDataframe`
    """

    # Required column names
    _col_names = [
        'polygon', 'osgb', 'shading', 'height', 'wwr', 'nofloors','construction', 'interiors', 'touching', 'polygon_exposed_wall',
        'polygon_horizontal'
    ]

    def __init__(self,
                 data: SimstockDataframe,
                 min_avail_width_for_window: Union[float, int] = 1,
                 min_avail_height: Union[float, int] = 80,
                 out_dir: str = "outs",
                 bi_mode: bool = True,
                 data_fname: str = None,
                 save_building_count: bool = False,
                 epw: str = None,
                 buffer_radius: Union[float, int] = 50,
                 ventilation_dict: dict = None, 
                 infiltration_dict: dict = None
                 ) -> None:
        """
        Constructor method
        """

        self.min_avail_width_for_window = min_avail_width_for_window
        self.min_avail_height = min_avail_height
        self.buffer_radius = buffer_radius
        self.out_dir = out_dir
        self.bi_mode = bi_mode
        self.data_fname = data_fname
        self.save_building_count = save_building_count

        # Try and load data from simstockdataframe
        try:
            self._get_df(data)
        except TypeError as exc:
            msg = f"Type: {type(data)} cannot be loaded."
            raise TypeError(msg) from exc
        except FileNotFoundError as exc:
            msg = f"File {data} not found."
            raise FileNotFoundError(msg) from exc
        except IOError as exc:
            msg = f"Data in {data} cannot be read."
            raise IOError(msg) from exc
        
        # Validate the df
        if not self.is_valid:
            msg = (
                "Error: the following columns are missing from the data: \n"
                f"{self.missing_columns} \n"
                "Please pre-process the data accordingly using the SimstockDataframe and its methods."
            )
            raise SimstockException(msg)

        # Set the settings IDF to be the one specified 
        # in the SimstockDataframe
        self.idf = data.settings.copyidf()

        # Set the weather file to be the one specified in the 
        # SimstockDataframe, unless user has specified it 
        # as a keyword argument at initialisation
        if epw == None:
            self.epw = data.epw

        # Get simstock directory
        current_file_path = inspect.getframeinfo(inspect.currentframe()).filename
        absolute_file_path = os.path.abspath(current_file_path)
        self.simstock_directory = os.path.dirname(absolute_file_path)

        # Load in the ventilation and infiltration
        # dictionaries, if now provided by user
        if ventilation_dict == None:
            json_fname = os.path.join(
                self.simstock_directory, "settings", "ventilation_dict.json"
                )
            with open(json_fname, 'r') as json_file:
                self.ventilation_dict = json.load(json_file)
        else:
            self.ventilation_dict = ventilation_dict
        if infiltration_dict == None:
            json_fname = os.path.join(
                self.simstock_directory, "settings", "infiltration_dict.json"
                )
            with open(json_fname, 'r') as json_file:
                self.infiltration_dict = json.load(json_file)
        else:
            self.infiltration_dict = infiltration_dict


    def __str__(self) -> str:
        msg = (
            "This is an IDFmanager, it's function is to create and handle IDF files."
        )
        return msg

    def __repr__(self) -> str:
        return "IDFobject()"

    def _get_df(self,
                data: Union[SimstockDataframe, DataFrame, str]
                ) -> None:
        """
        Function to extract the simstock or pandas
        data frame from `data` and store it in 
        the IDFcreator object.

        :param data:
            The data that should contain somehow a dataframe.
            This data can either already be a simstock or 
            pandas data frame, or it can be a filename 
            (including path) containing such.
        :type data: 
            :class:`simstock.SimstockDataframe`, :class:`DataFrame`, str

        :Raises TypeError:
            If the data is an invalid format.
        """

        # Extract the data frame using the appropriate
        # method based on type
        if type(data) == SimstockDataframe:
            self._sdf_to_df(data)
        elif type(data) == DataFrame:
            self._df_to_df(data)
        elif type(data) == str:
            self._str_to_df(data)
        else:
            raise TypeError  
    
    def _sdf_to_df(self, data: SimstockDataframe) -> None:
        self.df = data._df.copy()

    def _df_to_df(self, data: DataFrame) -> None:
        self.df = data.copy()

    def _str_to_df(self, data: str) -> None:
        if not os.path.exists(data):
            raise FileNotFoundError
        try:
            if data["-3:"] == "csv":
                self.df = pd.read_csv(data)
            elif data["-7:"] == "parquet":
                self.df = pd.read_parquet(data)
            elif data["-4:"] == "json":
                self.df = pd.read_json(data)
            else:
                raise IOError
        except IOError as exc:
            raise IOError from exc
        
    @property
    def is_valid(self) -> bool:
        """
        Are all of the necessary column names present
        """
        return all(col in self.df.columns for col in self._col_names)
    
    @property
    def missing_columns(self) -> list:
        """
        Necessary column names that are missing from the data
        """
        return list(set(self._col_names).difference(set(self.df.columns)))
    

    def _get_osgb_value(
            self,
            val_name: str,
            zones_df: DataFrame,
            zone: str
            ) -> float:
        """Gets the value of a specified attribute for the zone"""
        try:
            osgb_from_zone = "_".join(zone.split("_")[:-2])
            value = zones_df[zones_df["osgb"]==osgb_from_zone][val_name]
            return value.to_numpy()[0]
        except KeyError:
            return 0.0
    

    def create_model_idf(self, **kwargs) -> None:
        """
        Function to create IDF objects for each built island (if bi_mode=True), or else a single IDF for the entire model. 

        Creates a new attibute called bi_idf_list containing all the created IDF objects. Each of these can be used to run a simulation.

        Example
        ~~~~~~~

        .. code-block:: python

            # Assuming we have a correctly processed SimstockDataframe sdf,
            # instantiate a IDFmanager object
            simulation = sim.IDFmanager(sdf)

            # Now compute IDFs for each built island
            simulation.create_model_idf(bi_mode=True)

            # This will create a list constaining the IDFs for each BI
            # This can be accessed via
            idf_list = simulation.bi_idf_list
            print(idf_list)

            # Alternatively, we can create a single IDF for the whole 
            # model using the command
            simulation.create_model_idf(bi_mode=False)

            # This will create a list of length 1 called bi_idf_list
            # which will contain the single IDF for the model
            # This can be accessed via
            model_idf = simulation.bi_idf_list[0]

        :param \**kwargs:
            Optional keyword parameters, such as `bi_mode` or any of
            the other IDFmanager properties

        **See also**: :py:meth:`save_idfs` -- Used to save the IDF objects
        """

        self.__dict__.update(kwargs)

        # Ensure unique data file name
        if not self.data_fname:
            self.data_fname = _generate_unique_string()

        if os.path.exists(self.out_dir):
                shutil.rmtree(self.out_dir)
        else:
            os.makedirs(self.out_dir)
            
        # If the dataframe contains a built island column
        if self.bi_mode:

            # Calculate how many thermally simulated buildings are in each BI and output info as csv
            bi_bldg_count = self.df[self.df["shading"]!=True]["bi"].value_counts()
            if self.save_building_count:
                bi_bldg_count.to_csv(
                    os.path.join(self.out_dir, f"{self.data_fname}_bi_bldg_count.csv")
                    )

            # Iterate over unique building islands
            self.bi_idf_list = []
            for bi in self.df['bi'].unique().tolist():

                # Revert idf to settings idf
                temp_idf = self.idf.copyidf()
            
                # Change the name field of the building object
                building_object = temp_idf.idfobjects['BUILDING'][0]
                building_object.Name = bi
                
                # Get the data for the BI
                bi_df = self.df[self.df['bi'] == bi]

                # Get the data for other BIs to use as shading
                rest  = self.df[self.df['bi'] != bi]

                # Include other polygons which fall under the specified shading buffer radius
                bi_df = pd.concat(
                        [
                        bi_df, 
                        algs._shading_buffer(self.buffer_radius, bi_df, rest)
                        ]
                    )
                
                # Only create idf if the BI is 
                # not entirely composed of shading blocks
                shading_vals_temp = bi_df['shading'].to_numpy()
                shading_vals = [_assert_bool(v) for v in shading_vals_temp]
                if not np.asarray(shading_vals).all():
                    self._createidfs(temp_idf, bi_df)
                else:
                    continue
                
                # Store the idf object for this built island
                self.bi_idf_list.append(temp_idf)
                

        else: # Not built island mode

            # Revert idf to settings idf
            temp_idf = self.idf.copyidf()

            # Change the name field of the building object
            building_object = temp_idf.idfobjects['BUILDING'][0]
            building_object.Name = self.data_fname

             # Get non-shading data
            df1 = self.df[self.df['shading'] == False]
            bi_list = df1["bi"].unique()
            
            # Get the data for other BIs to use as shading
            rest = self.df[self.df['shading'] == True]

            # Include other polygons which fall under the specified shading buffer radius
            shading_dfs = []
            for bi in bi_list:
                # Get the data for the BI
                bi_df = self.df[self.df['bi'] == bi]

                # Buffer each BI to specified radius and include shading which falls within this
                shading_dfs.append(algs._shading_buffer(self.buffer_radius, bi_df, rest))

            # Combine these separate shading DataFrames and drop duplicate rows
            shading_df = pd.concat(shading_dfs)
            shading_df = shading_df.drop_duplicates()

            # Append the shading to the main DataFrame
            if self.buffer_radius != 0:
                df1 = pd.concat([df1, shading_df]).drop_duplicates(subset="osgb", keep="first")

            # If shading radius is zero, i.e. no shading is to be included
            elif self.buffer_radius == 0:
                # Overwrite touching column with empty data to avoid errors
                df1.loc[:, "touching"] = ["[]"] * len(df1)

            # Only create idf if it is not entirely composed of shading blocks
            shading_vals_temp = df1['shading'].to_numpy()
            shading_vals = [_assert_bool(v) for v in shading_vals_temp]
            if not np.asarray(shading_vals).all():

                # If requested, output csv which excludes any buildings not within the shading buffer
                df1.to_csv(os.path.join(self.out_dir, f"{self.data_fname}_final.csv"))

                # Generate the idf file
                self._createidfs(temp_idf, df1)

            else:
                raise Exception("There are no thermal zones to create! All zones are shading.")
            
            self.bi_idf_list.append(temp_idf)


    def _createidfs(
            self,
            temp_idf: IDF,
            bi_df: DataFrame
            ) -> None:
        """
        Internal function to create IDF objects for each built island, or for the entire model
        """
    
        # Move all objects towards origins
        origin = bi_df['polygon'].iloc[0]
        origin = list(origin.exterior.coords[0])
        origin.append(0)

        bi_df['shading'] = bi_df['shading'].apply(_assert_bool)
        
        # Shading volumes converted to shading objects
        shading_df = bi_df.loc[bi_df['shading'] == True]
        shading_df.apply(ialgs._shading_volumes, args=(self.df, temp_idf, origin,), axis=1)

        # Polygons with zones converted to thermal zones based on floor number
        zones_df = bi_df.loc[bi_df['shading'] == False]
        zone_use_dict = {} 
        zones_df.apply(ialgs._thermal_zones, args=(bi_df, temp_idf, origin, self.min_avail_width_for_window, self.min_avail_height, zone_use_dict,), axis=1)

        # Extract names of thermal zones:
        zones = temp_idf.idfobjects['ZONE']
        zone_names = list()
        for zone in zones:
            zone_names.append(zone.Name)

        # Plugin feature: mixed-use
        ialgs._mixed_use(temp_idf, zone_use_dict)

        # Ideal loads system
        for zone in zone_names:
            system_name = f"{zone}_HVAC"
            eq_name = f"{zone}_Eq"
            supp_air_node = f"{zone}_supply"
            air_node = f"{zone}_air_node"
            ret_air_node = f"{zone}_return"

            temp_idf.newidfobject('ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Name=system_name,
                                Zone_Supply_Air_Node_Name=supp_air_node,
                                Dehumidification_Control_Type='None')

            temp_idf.newidfobject('ZONEHVAC:EQUIPMENTLIST',
                                Name=eq_name,
                                Zone_Equipment_1_Object_Type='ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Zone_Equipment_1_Name=system_name,
                                Zone_Equipment_1_Cooling_Sequence=1,
                                Zone_Equipment_1_Heating_or_NoLoad_Sequence=1)

            temp_idf.newidfobject('ZONEHVAC:EQUIPMENTCONNECTIONS',
                                Zone_Name=zone,
                                Zone_Conditioning_Equipment_List_Name=eq_name,
                                Zone_Air_Inlet_Node_or_NodeList_Name=supp_air_node,
                                Zone_Air_Node_Name=air_node,
                                Zone_Return_Air_Node_or_NodeList_Name=ret_air_node)
        
            # Get specified inputs for zone
            ventilation_rate = self._get_osgb_value("ventilation_rate", zones_df, zone)
            infiltration_rate = self._get_osgb_value("infiltration_rate", zones_df, zone)

            # Get the rest of the default obj values from dict
            zone_ventilation_dict = copy.deepcopy(self.ventilation_dict)
            zone_infiltration_dict = copy.deepcopy(self.infiltration_dict)

            # Set the name, zone name and ventilation rate
            zone_ventilation_dict["Name"] = zone + "_ventilation"
            zone_ventilation_dict["Zone_or_ZoneList_Name"] = zone
            zone_ventilation_dict["Air_Changes_per_Hour"] = ventilation_rate
            zone_ventilation_dict["Schedule_Name"] = zone_use_dict[zone] + "_Occ"

            # Same for infiltration
            zone_infiltration_dict["Name"] = zone + "_infiltration"
            zone_infiltration_dict["Zone_or_ZoneList_Name"] = zone
            zone_infiltration_dict["Air_Changes_per_Hour"] = infiltration_rate

            # Add the ventilation idf object
            temp_idf.newidfobject(**zone_ventilation_dict)
            temp_idf.newidfobject(**zone_infiltration_dict)


    def save_idfs(self, **kwargs) -> None:
        """
        Function to save the IDF objects in a directory. By default, this directory will be called "outs/" and be located in the working directory. A different directory can be specified by the parameter or keyword argument "out_dir".

        Each IDF object is saved in its own file within the directory, and will be named "built_island_i.idf", where "i" will be the index of each built island. If built island mode is not being used (bi_mode=False), then only a single IDF is saved. 

        :param \**kwargs:
            Optional keyword parameters, such as `out_dir` or any of
            the other IDFmanager properties
        
        :raises SimstockException:
            If no IDF objects yet exist. This is likely because 
            :py:meth:`create_model_idf` has not yet been called


        Example
        ~~~~~~~
        .. code-block:: python

            # Output the idf objects to some folder of your choice
            simulation.save_idfs(out_dir="path/to/some_folder")
        """

        self.__dict__.update(kwargs)

        if len(self.bi_idf_list) == 0:
            msg = (
                """
                No model IDFs have been created yet.
                Please call create_model_idf() first.
                """
            )
            raise SimstockException()

        # Iterate over the list of idfs that have been created
        # and save each in a seperate file in out_dir
        for j, idf in enumerate(self.bi_idf_list):
            fname = os.path.join(self.out_dir, f"built_island_{j}.idf")
            idf.saveas(fname)
    

    def run(self, **kwargs) -> None:
        """
        Function to run an EnergyPlus simulation on each of the model
        IDF objects created by :py:meth:`create_model_idf`. The settings
        used for the simulation will be those specified within the :class:`SimstockDataframe`.

        The EnergyPlus output files resulting from the simulations will be saved into a directory. By default, this directory will be called "outs/" and be located in the working directory. A different directory can be specified by the parameter or keyword argument "out_dir". Within this directory, a further subdirectory will be made for each simulation (one per built island) containind all E+ files. Each subdirectory will be called "built_island_i_ep_outputs" where "i" will be the index of the built island. If built island mode is not being used (bi_mode=False), then only a single such subdirectory will be created. 

        :param \**kwargs:
            Optional keyword parameters, such as `out_dir` or any of
            the other IDFmanager properties

        .. code-block:: python

            # Assuming creat_model_idf() has already been called to 
            # create the model IDFs. We can check how many IDFs, 
            # corresponding to the number of built islands there
            # are by doing
            no_bi = len(simulation.bi_idf_list)

            # If bi_mode=False, then no_bi will equal 1. Now when we call
            # run(), it will create no_bi subdirectories inside  out_dir 
            # directory. E.g.
            simulation.run() 

            # This will have created, by default a directory called outs/
            # containing at least one subdirectory containing E+ outputs
        """


        self.__dict__.update(kwargs)

        # Iterate over the list of idfs that have been created
        # and run them, putting the results of each into 
        # a new subdirectory
        for j, idf in enumerate(self.bi_idf_list):

            # Create a new subdirectory for this build island
            # idf within the out_dir directory.
            # If the directory already exists, then 
            # clear its contents
            new_dir_path = os.path.join(
                self.out_dir, f"built_island_{j}_ep_outputs"
                )
            if os.path.exists(new_dir_path):
                shutil.rmtree(new_dir_path)
            else:
                os.makedirs(new_dir_path)

            # Run energy plus
            idf.epw = self.epw
            idf.run(output_directory=new_dir_path)
