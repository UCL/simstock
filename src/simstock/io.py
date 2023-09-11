"""
IO  module containing routines to read and write to 
various file types. Currently supported:
    - csv
    - parquet
    - geopackage
    - json
"""

import pandas as pd
import sqlite3
import fastparquet
from simstock.base import SimstockDataframe
import geopandas as gpd


# Need to ensure index column is handled correctly.
def read_csv(path: str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``csv`` file and return a ``SimstockDataframe``. It must conform to Simstock data standards; 
    i.e., it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar as well as a column of unique IDs called "osgb". Additional columns "shading", "height", "wwr", "nofloors" and "construction" must be present. See :class:`simstock.SimstockDataframe` for full data specifications.

    If the unique ID and geometry data columns are named something other than ``osgb`` and ``polygon`` respectively, then their names can be specified using the kwargs. See example below.

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # To read in data with that has column names osgb, polygon etc
        sdf = sim.read_csv("/pathtofile/examplefile.csv")

        # If the data's geometric data is named something other than 
        # polygon, say in this case it is called geom, then we can do
        sdf = sim.read_csv(
            "/pathtofile/examplefile.csv",
            polygon_column_name="geom"
            )

        # Also, if the unique ID column is something other than osgb, 
        # say its called uuid in this case, then we can do
        sdf = sim.read_csv(
            "/pathtofile/examplefile.csv",
            polygon_column_name="geom",
            uid_column_name="uuid"
            )


    :param path:
        The file path including the ``csv`` file
    :type path:
        str
    :param \**kwargs:
        optional keyword argumetns to be passed to the
        SimstockDataframe constructor. See :class:`simstock.SimstockDataframe`
        docs for details of allowed arguments.

    :return: 
        A :class:`simstock.SimstockDataframe` containing the data and settings. See :class:`simstock.SimstockDataframe`
        docs for full list of attributes, properties and methods.

    :raises TypeError:
        If ``csv`` file does not conform to Simstock standards.
    """
    df = pd.read_csv(path)
    return SimstockDataframe(df, **kwargs)


def read_geopackage_layer(
        path: str,
        layer_name: str,
        **kwargs
        ) -> SimstockDataframe:
    """
    Function to read in a layer of a geopackage ``.gpkg`` file and return a ``SimstockDataframe``. The data should contain a column of unique IDs as well as columns "shading", "height", "wwr", "nofloors" and "construction" must be present. See :class:`simstock.SimstockDataframe` for full data specifications.

    The geometric data can need not be specified manually. Once the geopackage layer has been read in, the geometric data will be available to view using the polygon attribute of the the SimstockDataframe.

    .. note:: \ \ 

        The name of the layer must be specified. If you do not know the layer names in your geopackage, you can use the helper function :py:func:`get_gpkg_layer_names`.

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # To read in data with that has column names osgb, polygon etc
        sdf = sim.read_geopackage_layer("/pathtofile/examplefile.gpkg", "my_layer")

    :param path:
        The file path including the ``csv`` file
    :type path:
        str
    :param layer_name:
        The name of the geopackage_layer to be read
    :type layer_name:
        str
    :param \**kwargs:
        optional keyword argumetns to be passed to the
        SimstockDataframe constructor. See :class:`simstock.SimstockDataframe`
        docs for details of allowed arguments.

    :return: 
        A :class:`simstock.SimstockDataframe` containing the data and settings. See :class:`simstock.SimstockDataframe`
        docs for full list of attributes, properties and methods.

    :raises TypeError:
        If ``csv`` file does not conform to Simstock standards.

    **See also**: :py:func:`get_gpkg_layer_names`
    """
    # Read the specific layer from the GeoPackage file as a GeoDataFrame
    gdf = gpd.read_file(path, layer=layer_name)
    cols = gdf.columns
    df = pd.DataFrame(columns=cols)
    for col in cols:
        df[col] = gdf[col]
    return SimstockDataframe(df, polygon_column_name="geometry", **kwargs)

    

def get_gpkg_layer_names(path: str) -> list[str]:
    """
    Function to get thr names of all geographical layers from a 
    geopackage file

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # Print all the layer names in a file
        for layer in sim.get_gpkg_layer_names("pathto/myfile.gpkg"):
            print(layer)

    :param path:
        The file name (including path from your working directory) of the geopackage
    :type path:
        str

    :return: 
        A list of the names of the layers
    """
    connection = None
    layer_names = []

    try:
        # Connect to the SQLite database
        connection = sqlite3.connect(path)
        cursor = connection.cursor()

        # Execute the SQL query to get all layer names that do not start with 'rtree' or 'trigger'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'rtree%' AND name NOT LIKE 'trigger%' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
        rows = cursor.fetchall()

        # Extract the layer names from the query results
        layer_names = [row[0] for row in rows]

    except sqlite3.Error as e:
        print(f"Error accessing the database: {e}")
    finally:
        if connection:
            connection.close()

    return layer_names


def read_parquet(path: str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``parquet`` file and return a ``SimstockDataframe``. It must conform to Simstock data standards; 
    i.e., it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar as well as a column of unique IDs called "osgb". Additional columns "shading", "height", "wwr", "nofloors" and "construction" must be present. See :class:`simstock.SimstockDataframe` for full data specifications.

    If the unique ID and geometry data columns are named something other than ``osgb`` and ``polygon`` respectively, then their names can be specified using the kwargs. See example below.

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # To read in data with that has column names osgb, polygon etc
        sdf = sim.read_parquet("/pathtofile/examplefile.parquet")

        # If the data's geometric data is named something other than 
        # polygon, say in this case it is called geom, then we can do
        sdf = sim.read_parquet(
            "/pathtofile/examplefile.parquet",
            polygon_column_name="geom"
            )

        # Also, if the unique ID column is something other than osgb, 
        # say its called uuid in this case, then we can do
        sdf = sim.read_parquet(
            "/pathtofile/examplefile.parquet",
            polygon_column_name="geom",
            uid_column_name="uuid"
            )


    :param path:
        The file path including the ``parquet`` file
    :type path:
        str
    :param \**kwargs:
        optional keyword argumetns to be passed to the
        SimstockDataframe constructor. See :class:`simstock.SimstockDataframe`
        docs for details of allowed arguments.

    :return: 
        A :class:`simstock.SimstockDataframe` containing the data and settings. See :class:`simstock.SimstockDataframe`
        docs for full list of attributes, properties and methods.

    :raises TypeError:
        If ``parquet`` file does not conform to Simstock standards.
    """
    df = pd.read_parquet(path)
    return SimstockDataframe(df, **kwargs)


def read_json(path: str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``json`` file and return a ``SimstockDataframe``. It must conform to Simstock data standards; 
    i.e., it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar as well as a column of unique IDs called "osgb". Additional columns "shading", "height", "wwr", "nofloors" and "construction" must be present. See :class:`simstock.SimstockDataframe` for full data specifications.

    If the unique ID and geometry data columns are named something other than ``osgb`` and ``polygon`` respectively, then their names can be specified using the kwargs. See example below.

    Example
    ~~~~~~~
    .. code-block:: python

        import simstock as sim

        # To read in data with that has column names osgb, polygon etc
        sdf = sim.read_json("/pathtofile/examplefile.json")

        # If the data's geometric data is named something other than 
        # polygon, say in this case it is called geom, then we can do
        sdf = sim.read_json(
            "/pathtofile/examplefile.json",
            polygon_column_name="geom"
            )

        # Also, if the unique ID column is something other than osgb, 
        # say its called uuid in this case, then we can do
        sdf = sim.read_json(
            "/pathtofile/examplefile.json",
            polygon_column_name="geom",
            uid_column_name="uuid"
            )


    :param path:
        The file path including the ``json`` file
    :type path:
        str
    :param \**kwargs:
        optional keyword argumetns to be passed to the
        SimstockDataframe constructor. See :class:`simstock.SimstockDataframe`
        docs for details of allowed arguments.

    :return: 
        A :class:`simstock.SimstockDataframe` containing the data and settings. See :class:`simstock.SimstockDataframe`
        docs for full list of attributes, properties and methods.

    :raises TypeError:
        If ``json`` file does not conform to Simstock standards.
    """
    df = pd.read_json(path)
    return SimstockDataframe(df, **kwargs)


# def to_csv(sdf: SimstockDataframe, path: str, **kwargs) -> None:
#     """
#     Function to save a SimstockDataframe object to a csv file

#     Parameters
#     ----------

#     ``sdf : SimstockDataframe``
#         The simstock dataframe to save.

#     ``path : str``
#         The file path to save to.

#     ``kwargs : dict``
#         optional keyword argumetns to be passed to the
#         SimstockDataframe initialiser. See SimstockDataframe
#         docs for details of allowed arguments.


#     Example
#     -------
#     ```python
#     sim.to_csv(sdf, "/pathtofile/examplefile.csv")
#     ```
#     """
#     sdf._df.to_csv(path, **kwargs)


# def to_parquet(sdf: SimstockDataframe, path: str) -> None:
#     """
#     Function to save a SimstockDataframe object to a parquet file

#     Parameters
#     ----------

#     ``sdf : SimstockDataframe``
#         The simstock dataframe to save.

#     ``path : str``
#         The file path to save to.


#     Example
#     -------
#     ```python
#     sim.to_csv(sdf, "/pathtofile/examplefile.parquet")
#     ```
#     """
#     sdf._df.to_parquet(path, engine="fastparquet")


# def to_json(sdf: SimstockDataframe, path: str) -> None:
#     """
#     Function to save a SimstockDataframe object to a json file

#     Parameters
#     ----------

#     ``sdf : SimstockDataframe``
#         The simstock dataframe to save.

#     ``path : str``
#         The file path to save to.


#     Example
#     -------
#     ```python
#     sim.to_csv(sdf, "/pathtofile/examplefile.json")
#     ```
#     """
#     sdf._df.to_json(path)

