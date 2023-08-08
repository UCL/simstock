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
    Function to read in a ``csv`` file and return a ``SimstockDataframe,
    i.e. it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar.

    Parameters
    ----------

    ``path: str``
        The file path including the ``csv`` file

    ``kwargs: dict``
        optional keyword argumetns to be passed to the
        SimstockDataframe initialiser. See SimstockDataframe
        docs for details of allowed arguments.

    Returns
    -------

    ``sdf: SimstockDataframe``
        See SimstockDataframe docs for full list of attributes
        and methods.

    Raises
    ------

    ``TypeError``
    If ``csv`` file does not conform to Simstock standards.

    Dictionary of key-words arguments to be passed to the SimstockDataframe
    constructor. See Simstockbase for full list of recognised key word
    arguments.

    Example
    -------
    ```python
    import simstock as sim
    sdf = sim.read_csv("/pathtofile/examplefile.csv")
    ```
    """
    df = pd.read_csv(path)
    return SimstockDataframe(df, **kwargs)


def read_geopackage_layer(
        path: str,
        layer_name: str,
        **kwargs
        ) -> SimstockDataframe:
    """
    Read a layer from a GeoPackage file as a pandas DataFrame using only sqlite3 and pandas.

    Parameters:
        path (str): The path to the GeoPackage file.
        layer_name (str): The name of the layer to read from the GeoPackage.

    Returns:
        SimstockDataframe
    """
    # Read the specific layer from the GeoPackage file as a GeoDataFrame
    gdf = gpd.read_file(path, layer=layer_name)
    cols = gdf.columns
    df = pd.DataFrame(columns=cols)
    for col in cols:
        df[col] = gdf[col]
    return SimstockDataframe(df, polygon_column_name="geometry", **kwargs)

    


def get_gpkg_layer_names(path: str) -> list:
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


def read_parquet(path : str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``parquet`` file and return a ``SimstockDataframe,
    i.e. it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar.

    Parameters
    ----------

    ``path : str``
        The file path including the ``parquet`` file

    ``kwargs : dict``
        optional keyword argumetns to be passed to the
        SimstockDataframe initialiser. See SimstockDataframe
        docs for details of allowed arguments.

    Returns
    -------

    ``sdf : SimstockDataframe``
        See SimstockDataframe docs for full list of attributes
        and methods.

    Raises
    ------

    ``TypeError``
    If the data in the ``parquet`` file does not conform to Simstock standards.

    Dictionary of key-words arguments to be passed to the SimstockDataframe
    constructor. See Simstockbase for full list of recognised key word
    arguments.

    Example
    -------
    ```python
    import simstock as sim
    sdf = sim.read_parquet("/pathtofile/examplefile.parquet")
    ```
    """
    df = pd.read_parquet(path)
    return SimstockDataframe(df, **kwargs)


def read_json(path : str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``json`` file and return a ``SimstockDataframe,
    i.e. it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar.

    Parameters
    ----------

    ``path : str``
        The file path including the ``json`` file

    ``kwargs : dict``
        optional keyword argumetns to be passed to the
        SimstockDataframe initialiser. See SimstockDataframe
        docs for details of allowed arguments.

    Returns
    -------

    ``sdf : SimstockDataframe``
        See SimstockDataframe docs for full list of attributes
        and methods.

    Raises
    ------

    ``TypeError``
    If the data in the ``json`` file does not conform to Simstock standards.

    Dictionary of key-words arguments to be passed to the SimstockDataframe
    constructor. See Simstockbase for full list of recognised key word
    arguments.

    Example
    -------
    ```python
    import simstock as sim
    sdf = sim.read_json("/pathtofile/examplefile.json")
    ```
    """
    df = pd.read_json(path)
    return SimstockDataframe(df, **kwargs)


def to_csv(sdf : SimstockDataframe, path : str, **kwargs) -> None:
    """
    Function to save a SimstockDataframe object to a csv file

    Parameters
    ----------

    ``sdf : SimstockDataframe``
        The simstock dataframe to save.

    ``path : str``
        The file path to save to.

    ``kwargs : dict``
        optional keyword argumetns to be passed to the
        SimstockDataframe initialiser. See SimstockDataframe
        docs for details of allowed arguments.


    Example
    -------
    ```python
    sim.to_csv(sdf, "/pathtofile/examplefile.csv")
    ```
    """
    sdf._df.to_csv(path, **kwargs)


def to_parquet(sdf : SimstockDataframe, path : str) -> None:
    """
    Function to save a SimstockDataframe object to a parquet file

    Parameters
    ----------

    ``sdf : SimstockDataframe``
        The simstock dataframe to save.

    ``path : str``
        The file path to save to.


    Example
    -------
    ```python
    sim.to_csv(sdf, "/pathtofile/examplefile.parquet")
    ```
    """
    sdf._df.to_parquet(path, engine="fastparquet")


def to_json(sdf : SimstockDataframe, path : str) -> None:
    """
    Function to save a SimstockDataframe object to a json file

    Parameters
    ----------

    ``sdf : SimstockDataframe``
        The simstock dataframe to save.

    ``path : str``
        The file path to save to.


    Example
    -------
    ```python
    sim.to_csv(sdf, "/pathtofile/examplefile.json")
    ```
    """
    sdf._df.to_json(path)

