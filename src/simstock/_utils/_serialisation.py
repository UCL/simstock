"""
This module contains routines for serialising various
objects into valid shapely objects. These are used in
simstock/base.py to construct SimstockSeries and
SimstockDataframe objects.

The routines in this module are not meant for use
in the user API.
"""

import numpy as np
import pandas as pd
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry.base import BaseGeometry


def _is_dict_like(obj) -> bool:
    """
    Check if the object is dict-like.
    """
    dict_like_attrs = ("__getitem__", "keys", "__contains__")
    return (
        all(hasattr(obj, attr) for attr in dict_like_attrs)
        and not isinstance(obj, type)
    )


def _is_wkt(obj) -> bool:
    """
    Checks if value is valid wkt data.
    """
    try:
        wkt.loads(obj)
    except (GEOSException, TypeError):
        return False
    return True


def _isna(value) -> bool:
    """
    Check if the value is NaN-like.
    """
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if value is pd.NA:
        return True
    return False


def _geoserialise_dict(dat : dict) -> dict:
    """
    Check if dictionary data is shapely-geometry type.
    """
    for key in dat:
        dat[key] = _shapely_loader(dat[key])
    return dat


def _geoserialise_pdseries(dat : pd.Series) -> pd.Series:
    """
    Check if pandas Series data is shapely-geometry type.
    """
    return dat.apply(_shapely_loader) #(dat.values)


def _geoserialise_array(arr) -> list:
    """
    Check if array is shapely-geometry type.
    """
    return [_shapely_loader(val) for val in arr]


def _shapely_loader(obj):
    """
    Checks if object is geomtry-like.
    """
    if isinstance(obj, BaseGeometry):
        return obj
    if _isna(obj):
        return pd.NA
    if _is_wkt(obj):
        return wkt.loads(obj)
    raise TypeError(
        f"Data object {obj} is neither any form of geometry data nor NaN"
    )


def _series_serialiser(obj) -> pd.Series:
    """
    This is a function that takes some input data and attempts
    to turn it into a pandas series of shapely geometries.
    """

    # If the input data is a regular series, then we just
    # need to try and serialise its values into shapely geoms.
    if isinstance(obj, pd.Series):
        return _geoserialise_pdseries(obj)

    # If the input data is a dictionary, then we first need to
    # serialise its entries as shapely geoms, and then store
    # those as a series.
    if _is_dict_like(obj):
        data = _geoserialise_dict(obj)
        return pd.Series(data)

    # If the input data is single instance of a shapely geometry
    # then it just needs to be stored as a series.
    if isinstance(obj, BaseGeometry):
        return pd.Series(obj)

    # If the input data is some kind of array, then all of its
    # values need to be serialised into shapely geoms and then
    # stored as a series.
    if isinstance(obj, (np.ndarray, list)):
        data = _geoserialise_array(obj)
        return pd.Series(data)

    # If the input data is a single instance of wkt data, then
    # load it in and store as a series
    if _is_wkt(obj):
        data = wkt.loads(obj)
        return pd.Series(data)

    # If it is anything else that cannot be obviously serialised
    # into a shapely object, then a type error is thrown.
    # Type errors will also be thrown if any of the above
    # serialisation attempts fail due to invalid input data.
    raise TypeError("Input data not geometry-like.")
