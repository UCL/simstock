"""
IO  module containing routines to read and write to 
various file types. Currently supported:
    - csv
    - parquet
    - json
"""

import pandas as pd
import fastparquet
from simstock.base import SimstockDataframe

# Need to ensure index column is handled correctly.
def read_csv(path : str, **kwargs) -> SimstockDataframe:
    """
    Function to read in a ``csv`` file and return a ``SimstockDataframe,
    i.e. it must contain a ``polygon`` column or key or field containing
    shapely geometry data or similar.

    Parameters
    ----------

    ``path : str``
        The file path including the ``csv`` file

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

