"""
Module containing the base simstock objects:
- :class:`SimstockDataframe`
- :class:`IDFcreator`
"""
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
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
    _compile_csvs_to_idf,
    _add_or_modify_idfobject,
    _create_schedule_compact_obj,
    _cleanup_infiltration_and_ventilation,
    _fix_infiltration_vent_schedules,
    _extract_class_name
)
from simstock._utils._output_handling import (
    _make_output_csvs,
    _get_building_file_dict,
    _build_summary_database,
    _add_building_totals
)
from simstock._utils._overheating import _add_overheating_flags


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
            schedule_manager: Any = None,
            csv_directory: str = None,
            uid_column_name: str = None,
            epw_file: str = None,
            tol: float = 0.1,
            use_base_idf: str = False,
            idd_file: str = None,
            out_dir: str = "outs",
            buffer_radius: Union[float, int] = 50,
            min_avail_width_for_window: Union[float, int] = 1,
            min_avail_height: Union[float, int] = 80,
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
        
        # Directory for saving outputs
        self.out_dir = out_dir
        
        # The buffer radius for built island creation
        self.buffer_radius = buffer_radius
        
        # Window options
        self.min_avail_width_for_window = min_avail_width_for_window
        self.min_avail_height = min_avail_height

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
        
        # Also set the rvi program path
        s = self._idd_file[:-12]
        self._readVarsESO_path = os.path.join(s, "PostProcess", "ReadVarsESO")
        
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
        
        # Add area column if it does not exist
        if "area" not in self._df.columns:
            self._df["area"] = self._df["polygon"].map(lambda x: x.area)

        # Add any missing columns
        self._add_missing_cols()

        # Has pre-processing occured?
        self.processed = False

        # Set weather file
        if epw_file:
            self.epw = epw_file
        else:
            self.epw = os.path.join(
                self.simstock_directory,
                "settings",
                "GBR_ENG_London.Wea.Ctr-St.James.Park.037700_TMYx.2007-2021.epw"
                )
        
        # Set schedule manager
        self.settings_csv_path = csv_directory
        self.schedule_manager = schedule_manager
        
        # Load in the ventilation and infiltration
        json_fname = os.path.join(
            self.simstock_directory, "settings", "ventilation_dict.json"
            )
        with open(json_fname, 'r') as json_file:
            self.ventilation_dict = json.load(json_file)
        json_fname = os.path.join(
            self.simstock_directory, "settings", "infiltration_dict.json"
            )
        with open(json_fname, 'r') as json_file:
            self.infiltration_dict = json.load(json_file)
        
        # Set internal state regarding whether diversity is to be used
        if self.schedule_manager:
            self._diversity = True
        else:
            self._diversity = False

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


    def read_materials_and_constructions_from_csv(self) -> None:
        """
        Reads all standard IDF objects from CSV (people, materials, etc.) 
        but SKIPS 'Schedule:Compact' objects.
        """
        if not self.settings_csv_path:
            raise FileNotFoundError("Settings CSV path not specified.")
        # This loads in the materials and constructions.
        _compile_csvs_to_idf(self.settings, self.settings_csv_path)


    def read_schedules_and_settings_from_csv(
        self,
        filename: str ="DB-Schedules-SCHEDULE_COMPACT.csv",
        ) -> None:
        """
        Explicitly read 'Schedule:Compact' definitions from a CSV 
        and add them to self.settings. 
        This is for the user who wants a single schedule for all 'dwell' usage, etc.
        """
        fullpath = os.path.join(self.settings_csv_path, filename)
        if not os.path.exists(fullpath):
            raise FileNotFoundError(f"Schedule file {filename} not found in {self.settings_csv_path}")

        # Read in the compact schedule
        df = pd.read_csv(
            fullpath,
            na_values=["", "N/A", "NA", "NaN", "NULL", "None"],
            on_bad_lines='skip'
            )
        for _, row in df.iterrows():
            _add_or_modify_idfobject("SCHEDULE:COMPACT", row, self.settings)
            
        # Now read in the lights, people, and equipment
        for csv_file in os.listdir(self.settings_csv_path):
            
            # Get the idf class name
            idf_class = _extract_class_name(csv_file[:-4])
            if idf_class.casefold() in ["lights", "people", "electricequipment"]:
                
                # load as pandas dataframe
                try:
                    na_values = ["", "N/A", "NA", "NaN", "NULL", "None"]
                    df = pd.read_csv(
                        os.path.join(self.settings_csv_path, csv_file),
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
                        _add_or_modify_idfobject(idf_class, row, self.settings)
                    except Exception as e:
                        raise Exception(f"Cause: class {idf_class}") from e

        # Ensure state reflects that schedules have been read
        self._diversity = False
        self._read_schedules = True


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
            print(f"The BI(s) with the most buildings: {modal_bi} with {modal_bi_num} thermally simulated buildings.")
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

        In essence, this function first checks that all polygons are correctly orientated. 
        It then proceeds to remove duplicate coordinates and simplify polygons while 
        ensuring that polygons do not intersect each other.

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


    def create_model_idf(self, **kwargs) -> None:
        """
        Function to create IDF objects for each built island (if bi_mode=True), or
        else a single IDF for the entire model. 
        Creates a new attribute called bi_idf_list containing all the created 
        IDF objects. Each of these can be used to run a simulation.
        """
        # Update any kwargs into self
        self.__dict__.update(kwargs)

        # Ensure unique data file name
        self.data_fname = _generate_unique_string()

        # Clean out existing output directory (if it exists), else create
        if os.path.exists(self.out_dir):
            shutil.rmtree(self.out_dir)
        else:
            os.makedirs(self.out_dir)
                
        # Create the list that will hold each island's IDF
        self.bi_idf_list = []

        # Iterate over unique building islands
        for bi in self._df['bi'].unique().tolist():

            # Revert idf to settings idf
            temp_idf = self.settings.copyidf()
            
            # Change the name field of the building object
            building_object = temp_idf.idfobjects['BUILDING'][0]
            building_object.Name = bi
                
            # Get the data for this BI
            bi_df = self._df[self._df['bi'] == bi]
            # Also get the rest for shading buffer
            rest  = self._df[self._df['bi'] != bi]

            # Include additional shading blocks within buffer radius
            bi_df = pd.concat(
                [
                    bi_df,
                    algs._shading_buffer(self.buffer_radius, bi_df, rest)
                ]
            )

            # If it's all shading, skip
            shading_vals_temp = bi_df['shading'].to_numpy()
            shading_vals = [_assert_bool(v) for v in shading_vals_temp]
            if not np.asarray(shading_vals).all():
                # Create geometry etc.
                self._createidfs(temp_idf, bi_df)
            else:
                continue

            # Check if we are NOT in diversity mode, we must have read schedules from CSV
            if not self._diversity and not self._read_schedules:
                raise ValueError("Schedules must be read from file before creating IDFs.")
                
            # If we are in diversity mode, use the schedule manager
            if self._diversity:
                # Iterate over the non-shading buildings in this BI
                for _, row in bi_df[bi_df["shading"] == False].iterrows():
                    
                    building_id = row.get("osgb")
                    nofloors = int(row.get("nofloors", 0))
                        
                    # For each floor
                    for floor_idx in range(1, nofloors + 1):
                            
                        usage_type = row.get(f"FLOOR_{floor_idx}: use")
                        if usage_type:
                            
                            # Zone name, e.g. "osgb1234_floor_2"
                            zone_name = f"{building_id}_floor_{floor_idx}"

                            # Get the schedule dict and usage rule
                            schedules_dict = self.schedule_manager.get_schedules_for_zone(
                                usage_type, zone_name
                            )
                            rule_obj = self.schedule_manager.get_rule_obj(usage_type)

                            # occupant fraction lumps (0..1)
                            occ_sched_name = f"{usage_type}_Occ_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf,
                                occ_sched_name,
                                "Fraction",
                                schedules_dict["occupancy"]
                            )
                            # occupant activity lumps (Any Number)
                            activity_sched_name = f"{usage_type}_Activity_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf,
                                activity_sched_name,
                                "Any Number",
                                schedules_dict["activity"]
                            )

                            # lighting lumps (Fraction or Any Number)
                            light_sched_name = f"{usage_type}_Light_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf, 
                                light_sched_name, 
                                "Fraction",  # or "Any Number," up to your design
                                schedules_dict["lighting"]
                            )

                            # equipment lumps (Fraction or Any Number)
                            equip_sched_name = f"{usage_type}_Equip_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf, 
                                equip_sched_name, 
                                "Any Number",
                                schedules_dict["equipment"]
                            )

                            # Distinguish non-domestic vs. domestic usage by occupant_density
                            # If occupant_density is not None => non-domestic approach
                            if hasattr(rule_obj, "occupant_density") and rule_obj.occupant_density is not None:
                                # -- Non-Domestic: PEOPLE object with People/Area
                                temp_idf.newidfobject(
                                    "PEOPLE",
                                    Name=f"People_{usage_type}_{zone_name}",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Number_of_People_Schedule_Name=occ_sched_name,
                                    Number_of_People_Calculation_Method="People/Area",
                                    People_per_Zone_Floor_Area=rule_obj.occupant_density,
                                    Fraction_Radiant=0.3,
                                    Sensible_Heat_Fraction="AutoCalculate",
                                    Activity_Level_Schedule_Name=activity_sched_name
                                )

                                # LIGHTS object if lighting_power is set
                                if hasattr(rule_obj, "lighting_power") and rule_obj.lighting_power is not None:
                                    temp_idf.newidfobject(
                                        "LIGHTS",
                                        Name=f"Lights_{usage_type}_{zone_name}",
                                        Zone_or_ZoneList_Name=zone_name,
                                        Schedule_Name=light_sched_name,
                                        Design_Level_Calculation_Method="Watts/Area",
                                        Watts_per_Zone_Floor_Area=rule_obj.lighting_power,
                                        Return_Air_Fraction=0.0,
                                        Fraction_Radiant=0.42,
                                        Fraction_Visible=0.18,
                                        Fraction_Replaceable=1.0,
                                        EndUse_Subcategory="General"
                                    )

                                # ELECTRICEQUIPMENT if equipment_power is set
                                if hasattr(rule_obj, "equipment_power") and rule_obj.equipment_power is not None:
                                    temp_idf.newidfobject(
                                        "ELECTRICEQUIPMENT",
                                        Name=f"Equip_{usage_type}_{zone_name}",
                                        Zone_or_ZoneList_Name=zone_name,
                                        Schedule_Name=equip_sched_name,
                                        Design_Level_Calculation_Method="Watts/Area",
                                        Watts_per_Zone_Floor_Area=rule_obj.equipment_power,
                                        Fraction_Latent=0.0,
                                        Fraction_Radiant=0.2,
                                        Fraction_Lost=0.0
                                    )

                            else:
                                # -- Domestic approach: occupant load in absolute W => use PEOPLE object in "DesignLevel"
                                #    occupant_count=1, occupant fraction schedule=occ_sched_name or "Always 1",
                                #    occupant activity = lumps in W
                                # If you want occupant fraction (0..1) from 'occupancy' lumps => you can apply a second approach.
                                # For simplicity, let's just do occupant fraction= "Always 1", occupant lumps => activity schedule
                                # So occupant load = 1 occupant * occupant fraction=1 * activity schedule (W) => lumps W
                                always_one_sched = "AlwaysOne"
                                if not temp_idf.getobject("SCHEDULE:CONSTANT", "AlwaysOne"):
                                    # create a constant schedule
                                    temp_idf.newidfobject(
                                        "SCHEDULE:CONSTANT",
                                        Name="AlwaysOne",
                                        Schedule_Type_Limits_Name="Fraction",
                                        Hourly_Value=1.0
                                    )

                                temp_idf.newidfobject(
                                    "PEOPLE",
                                    Name=f"People_{usage_type}_{zone_name}",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Number_of_People_Calculation_Method="People",
                                    Number_of_People=1.0,
                                    Number_of_People_Schedule_Name=always_one_sched,
                                    Fraction_Radiant=0.3,
                                    Sensible_Heat_Fraction="AutoCalculate",
                                    Activity_Level_Schedule_Name=activity_sched_name
                                )

                                # LIGHTS in "LightingLevel=1.0" if you want lumps in W or skip if you prefer
                                # For example, if your 'lighting' lumps are (0..someW), do:
                                temp_idf.newidfobject(
                                    "LIGHTS",
                                    Name=f"Lights_{usage_type}_{zone_name}",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Schedule_Name=light_sched_name,  # lumps => if you store W or fraction
                                    Design_Level_Calculation_Method="LightingLevel",
                                    Lighting_Level=1.0,  # We'll multiply by lumps if lumps are W
                                    Fraction_Radiant=0.42,
                                    Fraction_Visible=0.18,
                                    Fraction_Replaceable=1.0,
                                    EndUse_Subcategory="DomesticLights"
                                )

                                # E+ might expect lumps to be fraction or W. If lumps are absolute W, 
                                # you'd do a "SCHEDULE:COMPACT" with e.g. 85, 450, etc. 
                                # That multiplies 1.0 => 85..450 W. If lumps are 0..1 fraction, you'd get 0..1 W.  

                                # Equipment in "EquipmentLevel=1.0"
                                temp_idf.newidfobject(
                                    "ELECTRICEQUIPMENT",
                                    Name=f"Equip_{usage_type}_{zone_name}",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Schedule_Name=equip_sched_name,   # lumps in W
                                    Design_Level_Calculation_Method="EquipmentLevel",
                                    Design_Level=1.0,
                                    Fraction_Latent=0.0,
                                    Fraction_Radiant=0.2,
                                    Fraction_Lost=0.0,
                                    EndUse_Subcategory="DomesticEquip"
                                )

                            # 5) Heating lumps
                            heat_sched_name = f"{usage_type}_Heat_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf, 
                                heat_sched_name, 
                                "Temperature", 
                                schedules_dict["heating"]
                            )

                            # 6) Cooling lumps
                            cool_sched_name = f"{usage_type}_Cool_{zone_name}"
                            _create_schedule_compact_obj(
                                temp_idf, 
                                cool_sched_name, 
                                "Temperature", 
                                schedules_dict["cooling"]
                            )
                                
                            # Thermostat setpoints
                            thermostat_name = f"{zone_name}_Thermostat"
                            temp_idf.newidfobject(
                                "THERMOSTATSETPOINT:DUALSETPOINT",
                                Name=thermostat_name,
                                Heating_Setpoint_Temperature_Schedule_Name=heat_sched_name,
                                Cooling_Setpoint_Temperature_Schedule_Name=cool_sched_name
                            )
                            temp_idf.newidfobject(
                                "ZONECONTROL:THERMOSTAT",
                                Name=f"{thermostat_name}_Controller",
                                Zone_or_ZoneList_Name=zone_name,
                                Control_Type_Schedule_Name="Always 4", 
                                Control_1_Object_Type="ThermostatSetpoint:DualSetpoint",
                                Control_1_Name=thermostat_name
                            )

                            # COOLING CAPACITY from rule
                            system_name = f"{zone_name}_HVAC"   # must match what's created in _createidfs
                            ideal_sys = temp_idf.getobject("ZONEHVAC:IDEALLOADSAIRSYSTEM", system_name)
                            if ideal_sys:
                                capacity_w_m2 = rule_obj.nominal_cooling_capacity_w_m2()
                                capacity_w    = rule_obj.nominal_cooling_capacity_w()

                                if capacity_w_m2 is not None:
                                    floor_area = row.get("area", 0.0)
                                    max_cooling = floor_area * capacity_w_m2
                                    ideal_sys.Cooling_Limit = "LimitCapacity"
                                    ideal_sys.Maximum_Total_Cooling_Capacity = max_cooling
                                elif capacity_w is not None:
                                    max_cooling = capacity_w
                                    ideal_sys.Cooling_Limit = "LimitCapacity"
                                    ideal_sys.Maximum_Total_Cooling_Capacity = max_cooling
                                # else => NoLimit

                            # infiltration & ventilation
                            user_infil_series = rule_obj.infiltration_series_for_day(zone_name, 0)
                            user_infil_ach = rule_obj.infiltration_ach()
                            user_vent_series = rule_obj.ventilation_series_for_day(zone_name, 0)
                            user_vent_ach = rule_obj.ventilation_ach()
                                
                            # Infiltration
                            if (user_infil_series is not None) or (user_infil_ach is not None):
                                if user_infil_series is not None:
                                    lumps = self.schedule_manager._build_weekly_lumps(
                                        rule_obj, "infiltration", clamp_fraction=False
                                    )
                                    infil_sched_name = f"{usage_type}_Infil_{zone_name}"
                                    _create_schedule_compact_obj(
                                        temp_idf, infil_sched_name, "Fraction", lumps
                                    )
                                else:
                                    infil_sched_name = "On 24/7"
                                infiltration_rate = user_infil_ach if user_infil_ach else 0.3

                                temp_idf.newidfobject(
                                    "ZONEINFILTRATION:DESIGNFLOWRATE",
                                    Name=f"{zone_name}_infiltration",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Schedule_Name=infil_sched_name,
                                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                                    Air_Changes_per_Hour=infiltration_rate,
                                    Constant_Term_Coefficient=1.0,
                                    Temperature_Term_Coefficient=0.0,
                                    Velocity_Term_Coefficient=0.0,
                                    Velocity_Squared_Term_Coefficient=0.0
                                )
                            else:
                                zone_infiltration_dict = copy.deepcopy(self.infiltration_dict)
                                zone_infiltration_dict["Name"] = f"{zone_name}_infiltration"
                                zone_infiltration_dict["Zone_or_ZoneList_Name"] = zone_name
                                zone_infiltration_dict["Schedule_Name"] = "On 24/7"
                                infiltration_rate = row.get("infiltration_rate", 0.2)
                                zone_infiltration_dict["Air_Changes_per_Hour"] = infiltration_rate
                                temp_idf.newidfobject(**zone_infiltration_dict)

                            # Ventilation
                            if (user_vent_series is not None) or (user_vent_ach is not None):
                                if user_vent_series is not None:
                                    lumps = self.schedule_manager._build_weekly_lumps(
                                        rule_obj, "ventilation", clamp_fraction=False
                                    )
                                    vent_sched_name = f"{usage_type}_Vent_{zone_name}"
                                    _create_schedule_compact_obj(
                                        temp_idf, vent_sched_name, "Fraction", lumps
                                    )
                                else:
                                    vent_sched_name = "On 24/7"

                                ventilation_rate = user_vent_ach if user_vent_ach else 0.3
                                temp_idf.newidfobject(
                                    "ZONEVENTILATION:DESIGNFLOWRATE",
                                    Name=f"{zone_name}_ventilation",
                                    Zone_or_ZoneList_Name=zone_name,
                                    Schedule_Name=vent_sched_name,
                                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                                    Air_Changes_per_Hour=ventilation_rate,
                                    Ventilation_Type="Natural",
                                    Constant_Term_Coefficient=1.0
                                )
                            else:
                                zone_ventilation_dict = copy.deepcopy(self.ventilation_dict)
                                zone_ventilation_dict["Name"] = f"{zone_name}_ventilation"
                                zone_ventilation_dict["Zone_or_ZoneList_Name"] = zone_name
                                zone_ventilation_dict["Schedule_Name"] = occ_sched_name
                                ventilation_rate = row.get("ventilation_rate", 0.2)
                                zone_ventilation_dict["Air_Changes_per_Hour"] = ventilation_rate
                                temp_idf.newidfobject(**zone_ventilation_dict)

            # Cleanup infiltration & ventilation
            _cleanup_infiltration_and_ventilation(temp_idf)
            _fix_infiltration_vent_schedules(temp_idf)
                
            # Store the idf object for this built island
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
        shading_df.apply(
            ialgs._shading_volumes,
            args=(self._df, temp_idf, origin,),
            axis=1
            )

        # Polygons with zones converted to thermal zones based on floor number
        zones_df = bi_df.loc[bi_df['shading'] == False]
        zone_use_dict = {}
        
        # Built the thermal zone geometry
        zones_df.apply(
            ialgs._thermal_zones,
            args=(
                bi_df,
                temp_idf,
                origin,
                self.min_avail_width_for_window,
                self.min_avail_height,
                zone_use_dict,
                ),
            axis=1
            )

        # Extract names of thermal zones:
        zones = temp_idf.idfobjects['ZONE']
        zone_names = [z.Name for z in zones]

        # Handle mixed use by grouping zones
        ialgs._mixed_use(temp_idf, zone_use_dict)

        # Ideal loads system
        for zone_name in zone_names:
            system_name = f"{zone_name}_HVAC"
            eq_name = f"{zone_name}_Eq"
            supp_air_node = f"{zone_name}_supply"
            air_node = f"{zone_name}_air_node"
            ret_air_node = f"{zone_name}_return"

            temp_idf.newidfobject(
                'ZONEHVAC:IDEALLOADSAIRSYSTEM',
                Name=system_name,
                Zone_Supply_Air_Node_Name=supp_air_node,
                Dehumidification_Control_Type='None'
                )

            temp_idf.newidfobject(
                'ZONEHVAC:EQUIPMENTLIST',
                Name=eq_name,
                Zone_Equipment_1_Object_Type='ZONEHVAC:IDEALLOADSAIRSYSTEM',
                Zone_Equipment_1_Name=system_name,
                Zone_Equipment_1_Cooling_Sequence=1,
                Zone_Equipment_1_Heating_or_NoLoad_Sequence=1
                )

            temp_idf.newidfobject(
                'ZONEHVAC:EQUIPMENTCONNECTIONS',
                Zone_Name=zone_name,
                Zone_Conditioning_Equipment_List_Name=eq_name,
                Zone_Air_Inlet_Node_or_NodeList_Name=supp_air_node,
                Zone_Air_Node_Name=air_node,
                Zone_Return_Air_Node_or_NodeList_Name=ret_air_node
                )
            
            # If user is *not* in diversity mode, do infiltration fallback here
            # otherwise, the fallback is done in the create_model_idf function
            if not self._diversity:

                # Get specified inputs for zone
                infiltration_rate = self._get_osgb_value("infiltration_rate", zones_df, zone_name)
                ventilation_rate = self._get_osgb_value("ventilation_rate", zones_df, zone_name)
                
                # infiltration fallback
                zone_infil_dict = copy.deepcopy(self.infiltration_dict)
                zone_infil_dict["Name"] = zone_name + "_infiltration"
                zone_infil_dict["Zone_or_ZoneList_Name"] = zone_name
                zone_infil_dict["Air_Changes_per_Hour"] = infiltration_rate
                zone_infil_dict["Schedule_Name"] = "On 24/7"
                
                # ventilation fallback
                zone_vent_dict = copy.deepcopy(self.ventilation_dict)
                zone_vent_dict["Name"] = zone_name + "_ventilation"
                zone_vent_dict["Zone_or_ZoneList_Name"] = zone_name
                zone_vent_dict["Air_Changes_per_Hour"] = ventilation_rate
                zone_vent_dict["Schedule_Name"] = "On 24/7"
                
                temp_idf.newidfobject(**zone_infil_dict)
                temp_idf.newidfobject(**zone_vent_dict)


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
            raise SimstockException(msg)

        # Iterate over the list of idfs that have been created
        # and save each in a seperate file in out_dir
        for j, idf in enumerate(self.bi_idf_list):
            fname = os.path.join(self.out_dir, f"built_island_{j}.idf")
            idf.saveas(fname)


    def run(
        self,
        save_idfs: bool = False,
        include_cooling: bool = True,
        include_heating: bool = True,
        **kwargs
        ) -> pd.Series:
        """
        Function to run an EnergyPlus simulation on each of the model
        IDF objects created by :py:meth:`create_model_idf`. The settings
        used for the simulation will be those specified within the :class:`SimstockDataframe`.

        The EnergyPlus output files resulting from the simulations will be saved into a directory. 
        By default, this directory will be called "outs/" and be located in the working directory. 
        A different directory can be specified by the parameter or keyword argument "out_dir".
        Within this directory, a further subdirectory will be made for each simulation (one per built island) 
        containind all E+ files. Each subdirectory will be called "built_island_i_ep_outputs" where "i" 
        will be the index of the built island. If built island mode is not being used (bi_mode=False), 
        then only a single such subdirectory will be created. 

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
            print(f"Running simulation for built island {j} of {len(self.bi_idf_list)} ...")
            
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
            idf.run(output_directory=new_dir_path, verbose="q")
            
            # Save the idf if requested
            if save_idfs:
                idf.saveas(os.path.join(new_dir_path, f"built_island_{j}.idf"))

        # Now do output handling by default
        print("Compiling outputs")
        _make_output_csvs(self.out_dir, self._readVarsESO_path)
        building_dict = _get_building_file_dict(self.out_dir)

        # Populate a summary database
        power_ts = _build_summary_database(self.out_dir, building_dict)

        # Add some summary stats back into the dataframe and return that
        self._df = _add_building_totals(
            self.out_dir,
            self._df,
            include_cooling=include_cooling,
            include_heating=include_heating
            )
        self._df = _add_overheating_flags(
            self.out_dir,
            self._df,
            28.0,
            10.0,
            6.0,
            6.0
            )
        print("Simulations complete.")

        return power_ts, self._df
