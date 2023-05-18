"""
Module containing the base simstock objects:
- SimstockDataframe
- IDFcreator
"""

import os
import glob
from typing import Any
from functools import singledispatchmethod
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
from simstock._utils._serialisation import _series_serialiser
from simstock._utils._exceptions import SimstockException
import simstock._algs._polygon_algs as algs
import simstock._algs._simplification as smpl
import simstock._algs._idf_algs as ialgs



class SimstockDataframe:
    """
    A ``SimstockDataframe`` is an object used by simstock to represent all input data. It behaves the in the same way as a Pandas data frame, but with some key additional methods to perform geometric-based pre-processing.

    In order to be a valid ``SimstockDataframe``, there must be one column names ``polygon`` that contains geometric data.

    Additional required column names are: 
    - ``osgb``
    - ``shading``
    - ``height``
    - ``nofloors``
    - ``construction``
    - ``interiors``


    Parameters
    ----------
    ``data : Any``
        The polygon data together with ``osgb`` data etc.

    ``index : array-like or Index``
        The index for the SimstockSeries.

    ``tol : float``
        The tolerance to apply when assessing polygon intersections.

    Usage example
    -------------
    ```python
    import simstock as sim
    sdf = sim.read_csv("text.csv")
    
    # Access data in the smae way as a pandas dataframe:
    print(sdf.columns)
    >>> Index(['polygon', 'osgb', 'shading', 'height', 'wwr', 'nofloors',
       'construction', 'interiors'],
      dtype='object')
    
    print(sdf.loc[sdf["osgb"]=="osgb1000005307038", "polygon"])
    >>> POLYGON ((528883.55 186137, 528878.05 186145.5...
    Name: polygon, dtype: object
    
    # Perform preprocessing
    sdf.preprocessing()
    ```

    Attributes
    ----------

    ``is_ccw : bool or list<bool>``
        Are the geometries counter-clockwise.
    
    ``is_exterior_ccw : bool or list<bool>``
        Are the exterior perimeters counter-clockwise.
    
    ``is_valid : bool or list<bool>`` 
        Are the geometries valid objects.

    ``length : int``
        The length of the data (axis=0).
    
    
    Methods
    -------
    """

    def __init__(
            self,
            inputobject : Any,
            tol : float = 0.1,
            **kwargs
            ) -> None:
        """
        Initialisation function for SimstockDataframe

        Parameters
        ----------

        ``inputdata : Any``
            Can be a dictionary or a Pandas dataframe.
            This input data must include data fields ``osgb``, ``shading``, ``height``, ``wwr``, ``nofloors``, ``construction``, ``interiors``

        ``tol : float``
            Optional tolerance parameter for geomtric simplifications. Default
            value is 0.1m

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.

        """
        self.__dict__.update(kwargs) 

        # Set tolerance
        self.tol = tol

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

        # Check that an osgb column exists
        self._validate_osgb_column()

        # Check that the polygon column exists
        self._validate_polygon_column() 

        # Add additional columns
        self._add_interiors_column()


    def __getattr__(self, attr : str) -> Any:
        """
        Required function to allow user to interface
        with underlying dataframe.
        """
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self._df, attr)

    def __getitem__(self, item : Any) -> Any:
        """
        Required function to allow user to interface
        with underlying dataframe.
        """
        return self._df[item]

    def __setitem__(self, item : Any, data : Any) -> None:
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
    
    def _validate_osgb_column(self) -> None:
        """
        Function to check the existance of a column named ``osgb``.
        If none is found, then a KeyError is raised. The function 
        also puts column name into lower case if not already.
        """
        cols = [e for e in self._df.columns if e.casefold() == "osgb"]
        if len(cols) == 0:
            raise KeyError("No \"osgb\" column dectected!\n")
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
            raise KeyError("No \"polygon\" column dectected!\n")
        try:
            self._df[cols[0]] = _series_serialiser(self._df[cols[0]])
            self._df = self._df.rename(columns={cols[0] : "polygon"})
            return 
        except TypeError as exc:
            errmsg = "Unable to find valid shapely data in \"polygon\"\n"
            raise TypeError(errmsg) from exc
        
    def _add_interiors_column(self) -> None:
        self._df['interiors'] = self._df['polygon'].map(algs._has_interior)
    
    @property
    def is_ccw(self) -> list[bool]:
        """
        ``property : list[bool]``
            Are the polygon column objects counter-clockwise?
        """
        return shp.is_ccw(self._df['polygon'])
    
    @property
    def is_exterior_ccw(self) -> list[bool]:
        """
        ``property : list[bool]``
            Do the polygon column objects have 
            counter-clockwise exteriors?
        """
        return self._df['polygon'].map(algs._is_exterior_ccw)
    
    @property
    def is_valid(self) -> list[bool]:
        """
        ``property : list[bool]``
            Are the polygon column objects valid
            shapley objects?
        """
        return shp.is_valid(self._df['polygon'])
    
    @property
    def length(self) -> int:
        """
        ``property : int``
            The length of the columns in the 
            dataframe.
        """
        return self._df.__len__()
    
    def orientate_polygons(self, **kwargs) -> None:
        """
        Function to ensure that polygon exteriors and interiors 
        are correctly orientated clockwise/anti-clockwise.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.
        """
        self.__dict__.update(kwargs)
        self._df['polygon'] = self._df['polygon'].map(algs._orientate)

    def remove_duplicate_coords(self, **kwargs) -> None:
        """
        Function to remove duplicated coordinates from polygons, while ensuring the polygons remain valid shapely objects.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.

        Usage
        -----

        ```python
        import simstock as sim
        sdf = sim.read_csv("path/to/file.csv")
        sdf.remove_duplicate_coords()
        ```
        """
        self.__dict__.update(kwargs)
        self._df['polygon'] = self._df['polygon'].map(
            algs._remove_duplicate_coords
            )

    def polygon_topology(self, **kwargs) -> None:
        """
        Function that checks whether polygons are touching or interecting each other. If any intersections are detected, an error is thrown. 

        This function adds an additonal column to the SimstockDataframe called ``touching``. The i^th entry in ``touching`` lists the ``osbg`` values of all polygons touching the polygon in row i.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.

        Raises
        ------

        ``ValueError`` 
            If any polygons are touching.

        Usage
        -----

        ```python
        import simstock as sim
        sdf = sim.read_csv("path/to/file.csv")
        sdf.polygon_topology()
        ```
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
        A function to assess which polygons need simplifying, based on a user-specifed tolerance. This can be set via ``tol`` in ``kwargs``. 
        Simplification here means removing intermediate coordinates in 
        a shape while preserving the shapes topology. Coordinates that
        are closer together than some tolerance are candidates for removal.

        This function adds a boolean column named ``simplify`` which specifies whether each polygon needs simplifying or not, based on the tolerance.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.

        Usage example
        -------------
        ```python
        sdf.polygon_toerance(tol=0.1)
        ```
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
    def _touching_poly(self, osgb : str, polygon : Polygon, 
                       osgb_list : list[str], 
                       osgb_touching : list[str]) -> list[str]:
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
                # Not sure if this if statement is necessary
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
        Function that simplifies polygons, by e.g. exploiting transitivity of points and merging points within tolerances. 

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.
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
        self._df = self._df.drop(['simplify', 'poly_within_hole'], axis=1)

    # This could be refactored as a map
    def collinear_exterior(self, **kwargs) -> None:
        """
        Function that removes collinear points from polygons and determines exterior surfaces.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.
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
            
    def preprocessing(self, **kwargs) -> None:
        """
        Function to perform default processing on the SimstockDataframe to ready it for ``IDF`` creation. 

        This function first checks that all polygons are correctly orientated. It then proceeds to remove duplicate coordinates and simplify polygons while ensuring that polygons do not intersect each other.

        Parameters
        ----------

        ``kwargs : dict``
            Dictionary of key-words arguments, see Simstockbase for full list of recognised key word arguments.

        Raises
        ------

        ``ValueError``
            If polygons cannot be simplified without causing intersection.
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




class IDFcreator:
    """
    An ``IDFcreator`` is a container object used to create elements
    for an EnergyPlus simulation. The object contains functions to
    take geometric and contextual data in the form of a 
    SimstockDataframe, and create an IDF file or Eppy IDF
    object for an E+ run.

    Parameters
    ----------
    ``data : dict-like``
        Data containing polygon and contextual information.

    ``idf : IDF``
        The IDF object containing elements for E+.

    ``idd_file : str = None``
        The path to the idd_file on the user's computer.
        If none is given, the initialiser function will
        attempt to find one autmatically.

    ``ep_basic_settings : str = None``
        The path to the idf file containing the basic settings
        for E+. If none is given, then the system reverts to
        the basic_settings.idf.

    ``min_avail_width_for_windows : float | int = 1``
        Windows will not be placed is wall widths are less
        than this distance in metres.

    ``min_avail_height : float | int = 80``
        Windows wil not be placed if partially exposed 
        external wall is less than this number % of zone height.

    Usage example
    -------------
    ```python
    import simtock as sim

    # Assuming the user has a SimstockData frame named sdf,
    # instantiate new IDFcreator object:
    ob = sim.IDFcreator(sdf)

    # Create all necessary E+ objects:
    # First, move all objects towards origin
    ob.move_towards_origin()

    # Create shading objects
    ob.create_shading_objects()
    
    # Create thermal zones based on floor number
    ob.create_thermal_zones()

    # Compute ideal load systems
    ob.create_load_systems()

    # All relevant data for an E+ run have now been created
    # The results can be saved to a file,
    # Or kept as an eppy idf object for further processing:
    idf = ob.idf
    ```

    Attributes
    ----------
    ``is_valid : bool``
        Are all of the necessary column names present in the 
        input data.

    ``missing_columns : list[str]``
        List of the names of necessary columns that are 
        not present in the input data.

    See also
    --------
    ``SimstockDataframe``

    Methods
    -------
    """

    # File locations
    root = os.path.join(os.path.dirname(__file__))
    idd_file = ""
    ep_basic_settings = os.path.join(root, "settings", "basic_settings.idf")

    # Common locations for E+ idd files
    common_windows_paths = ["C:\\EnergyPlus*\\Energy+.idd"]
    common_posix_paths = [
        "/usr/local/EnergyPlus*/Energy+.idd",
        "/Applications/EnergyPlus*/Energy+.idd"
    ]

    building_name = "test"

    # Do not place window if the wall width is less than this number
    min_avail_width_for_window = 1
    # Do not place window if partially exposed external wall is less than this number % of zone height
    min_avail_height = 80

    col_names = [
        'polygon', 'osgb', 'shading', 'height', 'wwr', 'nofloors','construction', 'interiors', 'touching', 'polygon_exposed_wall',
        'polygon_horizontal'
    ]


    def __init__(self,
                 data : SimstockDataframe | DataFrame | str,
                 idd_file : str = None,
                 **kwargs
                 ) -> None:
        """
        Initialisation function for the IDFcreator object.

        Parameters
        ----------
        ``data : SimstockDataframe | DataFrame |str``
            The input data containg geographical data.

        ``idd_file : str = None``
            The filepath of the user's idd file. If none is
            given, then this intialisation will attempt
            to find one automatically.

        ``kwargs``
            Keyword arguments to set class parameters.

        Raises
        ------
        ``TypeError``
            If the input data is in a format that cannot be loaded.
            The data must be either a SimstockDataframe or a Pandas
            DataFrame, or else a filepath containing such data in
            csv, parquet, or json format.

        ``FileNotFoundError``
            If the user specified filepath containing the 
            data cannot be found.

        ``IOError``
            If the user has specified a file path for the data 
            but the file does not have an appropriate extension.

        ``SimstockException``
            If the input data is missing critical values.

        ``SystemError``
            If the user's operating system environment 
            cannot be determined.

        ``Warning``
            If the user has E+ installed correctly, but is 
            using a Silicone Mac (M1,2) without having
            Rosetta installed.
        """
        self.__dict__.update(kwargs)

        # Try and load data from simstockdataframe
        try:
            self.get_df(data)
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
                "Please pre-process the data accordingly using Simstock."
            )
            raise SimstockException(msg)

        # If idd_file == None, then try looking in standard places
        if idd_file == None:
            # Determine OS
            opsys = platform.system().casefold()
            if opsys not in ["windows", "darwin", "linux"]:
                msg = f"OS: {opsys} not recognise."
                raise SystemError(msg)
            self._find_idd(opsys)

        # If silicon mac, ensure rosetta is installed
        if platform.processor().casefold() == "arm":
            try:
                if not os.path.isdir("/usr/libexec/rosetta"):
                    raise Warning
                if len(os.listdir("/usr/libexec/rosetta")) == 0:
                    raise Warning
            except Warning as warn:
                msg = (
                    "This appears to be a Silicone Mac." 
                    "Please ensure Rosetta is installed to enable EnergyPlus functionality."
                )
                raise Warning(msg) from warn
            
        IDF.setiddname(self.idd_file)
        self.idf = IDF(self.ep_basic_settings)

        # Change the name filed of the building object
        building_object = self.idf.idfobjects['BUILDING'][0]
        building_object.Name = self.building_name
            
    
    def __str__(self) -> str:
        msg = (
            "This is an IDFobject, it's function is to create IDF files."
            f"This object uses E+ files located in {self.idd_file}."
        )
        return msg

    def __repr__(self) -> str:
        return "IDFobject()"

    @singledispatchmethod
    def get_df(self, data : Any) -> None:
        """
        Function to extract the simstock or pandas
        data frame from `data` and store it in 
        the IDFcreator object.

        Parameters
        ----------
        ``data : Any``
            The data that should contain somehow a dataframe.
            This data can either already be a simstock or 
            pandas data frame, or it can be a filename 
            (including path) containing such.

        Raises
        ------
        ``TypeError``
            If the data is an invalid format.
        """
        msg = f"Type: {type(data)} cannot be loaded."
        raise TypeError(msg)
    
    @get_df.register
    def _(self, data : SimstockDataframe) -> None:
        self.df = data._df.copy()

    @get_df.register
    def _(self, data : DataFrame) -> None:
        self.df = data.copy()

    @get_df.register
    def _(self, data : str) -> None:
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
        return all(col in self.df.columns for col in self.col_names)
    
    @property
    def missing_columns(self) -> list:
        """
        Necessary column names that are missing from the data
        """
        return list(set(self.col_names).difference(set(self.df.columns)))

    def _find_idd(self, system : str) -> None:
        """
        Function to find IDD file within user's system
        """
        self.idd_file = None
        if system == "windows":
            paths = self.common_windows_paths
        else:
            paths = self.common_posix_paths
        for path in paths:
            # Use glob to handle pattern matching for version number
            matches = glob.glob(path)
            if matches:
                self.idd_file = matches[0]
                break
        if self.idd_file == None:
            raise FileNotFoundError("Could not find EnergyPlus IDD file")
    
    def move_towards_origin(self, **kwargs) -> None:
        """
        Function to move all objects in the data
        towards the origin on the plane.

        Parameters
        ----------
        ``kwargs``
            Keyword arguments. See IDFcreator initialisation
            docs for full list of acceptable keywords.
        """
        self.__dict__.update(kwargs)
        self.origin = self.df['polygon'].iloc[0]
        self.origin = list(self.origin.exterior.coords[0])
        self.origin.append(0)

    def create_shading_objects(self, **kwargs) -> None:
        """
        Function to create shading objects for E+

        Parameters
        ----------
        ``kwargs``
            Keyword arguments. See IDFcreator initialisation
            docs for full list of acceptable keywords.
        """
        self.__dict__.update(kwargs)

        # Shading volumes converted to shading objects
        shading_df = self.df.loc[self.df['shading'] == True]
        shading_df.apply(
            ialgs._shading_volumes, args=(self.df, self.idf, self.origin,), axis=1
        )

    def create_thermal_zones(self, **kwargs) -> None:
        """
        Function to create thermal zone objects for E+

        Parameters
        ----------
        ``kwargs``
            Keyword arguments. See IDFcreator initialisation
            docs for full list of acceptable keywords.
        """
        self.__dict__.update(kwargs)

        # Polygons with zones converted to thermal zones based on floor number
        self.zones_df = self.df.loc[self.df['shading'] == False]
        self.zones_df.apply(ialgs._thermal_zones, args=(self.df, self.idf, self.origin, self.min_avail_width_for_window, self.min_avail_height,), axis=1)

        # Extract names of thermal zones:
        self.zones = self.idf.idfobjects['ZONE']
        self.zone_names = list()
        for zone in self.zones:
            self.zone_names.append(zone.Name)

        # Create a 'Dwell' zone list with all thermal zones. "Dwell" apears
        # in all objects which reffer to all zones (thermostat, people, etc.)
        self.idf.newidfobject('ZONELIST', Name='Dwell')
        objects = self.idf.idfobjects['ZONELIST'][-1]
        for i, zone in enumerate(self.zone_names):
            exec(f'objects.Zone_{i + 1}_Name = zone')


    def create_load_systems(self, **kwargs) -> None:
        """
        Function to create load system objects for E+

        Parameters
        ----------
        ``kwargs``
            Keyword arguments. See IDFcreator initialisation
            docs for full list of acceptable keywords.
        """
        self.__dict__.update(kwargs)

        # Ideal loads system
        for zone in self.zone_names:
            system_name = f'{zone}_HVAC'
            eq_name = f'{zone}_Eq'
            supp_air_node = f'{zone}_supply'
            air_node = f'{zone}_air_node'
            ret_air_node = f'{zone}_return'

            self.idf.newidfobject('ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Name=system_name,
                                Zone_Supply_Air_Node_Name=supp_air_node,
                                Dehumidification_Control_Type='None')
            self.idf.newidfobject('ZONEHVAC:EQUIPMENTLIST',
                                Name=eq_name,
                                Zone_Equipment_1_Object_Type='ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Zone_Equipment_1_Name=system_name,
                                Zone_Equipment_1_Cooling_Sequence=1,
                                Zone_Equipment_1_Heating_or_NoLoad_Sequence=1)
            self.idf.newidfobject('ZONEHVAC:EQUIPMENTCONNECTIONS',
                                Zone_Name=zone,
                                Zone_Conditioning_Equipment_List_Name=eq_name,
                                Zone_Air_Inlet_Node_or_NodeList_Name=supp_air_node,
                                Zone_Air_Node_Name=air_node,
                                Zone_Return_Air_Node_or_NodeList_Name=ret_air_node)
    
    def save_to_file(self, fname : str) -> None:
        """
        Function to save the E+ objects to an idf file

        Parameters
        ----------
        ``fname : str``
            File name to save to.
        """
        self.idf.saveas(fname)


    def create_idf_file(self, fname : str, **kwargs) -> None:
        """
        Function to automatically create the IDF file from the
        data in IDFcreator. This uses default settings.

        Parameters
        ----------
        ``fname : str``
            File name to save the IDF file to
        
        ``kwargs``
            Keyword arguments. See IDFcreator initialisation
            docs for full list of acceptable keywords.

        Usage example
        -------------
        ```python
        import simstock as sim

        # Read in data and create SimstockDataframe
        sdf = sim.read_csv("tests/data/test_data.csv")

        # Process it
        sdf.preprocessing()

        # Instantiate IDF creator object
        ob = sim.IDFcreator(sdf)

        # Create and save the IDF object
        ob.create_idf_file("tests/data/test.idf")
        ```
        """
        self.__dict__.update(kwargs)
        self.move_towards_origin()
        self.create_shading_objects()
        self.create_thermal_zones()
        self.create_load_systems()
        self.save_to_file(fname) 


def create_idf(sdf : SimstockDataframe, fname : str, **kwargs) -> None:
    """
    Function to automatically create the IDF file from a 
    SimstockDataframe. This uses default settings. 

    Parameters
    ----------
    ``sdf : SimstockDataframe``
        The pre-processed SimstockDataframe

    ``fname : str``
        File name to save the IDF file to
    
    ``kwargs``
        Keyword arguments. See IDFcreator initialisation
        docs for full list of acceptable keywords.

    Usage example
    -------------
    ```python
    import simstock as sim

    # Read in data and create SimstockDataframe
    sdf = sim.read_csv("tests/data/test_data.csv")

    # Process it
    sdf.preprocessing()

    # Create and save the IDF object
    sim.create_idf(sdf, "tests/data/test.idf")
    ```

    See also
    --------
    ``IDFcreator`` object
        The IDFcreator object provides finer grained
        control over the IDF file creation process
        by using the object's API. Refer to 
        ``IDFcreator`` docs for more info.
    """
    ob = IDFcreator(sdf, **kwargs)
    ob.create_idf_file(fname)


    












                                



                        

                        

                    

