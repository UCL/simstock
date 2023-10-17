"""
Plotting module containing routines for plotting
basic geometries.
"""

from typing import Any, Union
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.collections import PatchCollection
from matplotlib.axes._axes import Axes
from shapely.geometry import (
    Polygon,
    Point,
    LineString,
    MultiPolygon
)
from pandas.core.series import Series
from pandas.core.frame import DataFrame
from simstock.base import SimstockDataframe


def plot(
        sdf: Union[SimstockDataframe, Series, DataFrame],
        facecolor: str= "lightblue",
        edgecolor: str = "red",
        polygon_column_name: str = "polygon",
        **kwargs
        ) -> Axes:
    """
    Function to plot geometric data from either a :py:class:`SimstockDataframe`, Pandas :py:class:`DataFrame`, or Pandas :py:class:`Series` using `matplotlib.pyplot`. The geometric data column should be named ``polygon``; if it is named anything else then it should be specified using the `polygon_column_name` parameter. You may also pass a matplotlib :py:class:`Axes` object via the optional parameter `ax`, in order to plot onto an existing axis (see examples below).

    :param sdf:
        The :py:class:`SimstockDataframe`, Pandas :py:class`DataFrame`, or Pandas :py:class:`Series` containing the geometric data to be plotted. This data must be in the form of shapely geometries: either :py:class:`Polygon`, :py:class:`Point`, or :py:class:`LineString`.
    :type sdf:
        Union[SimstockDataframe, Series, DataFrame]
    :param facecolor:
        *Optional*. The fill colour of the shapesm defaults to ``lightblue``
    :type facecolor:
        str
    :param edgecolor:
        *Optional*. The border colour of the shapes, defaults to ``red``
    :type edgecolor:
        str
    :param polygon_column_name:
        *Optional*. The name of the column containing the geographical data to be plotted, defaults to ``polygon``
    :type polygon_column_name:
        str

    :param \**kwargs:
        Optional keyword parameters to be passed to matplotlib; e.g. ``ax``

    :return:
        A :py:class:`Axes` objects containing 
        the plotted geometric data

    :raises TypeError:
        If the geometric data are not valid Shapely :py:class:`Polygon`, :py:class:`Point`, or :py:class:`LineString`

    Example
    ~~~~~~~
    .. code-block:: python 

        # Basic usage
        import matplotlib.pyplot as plt
        import simstock as sim

        # Create test simstockdataframe
        sdf = sim.read_csv("testdata.csv")

        # Plot
        sim.plot(sdf, facecolor="lightblue", edgecolor="red")
        plt.show()

    Advanced example: plotting to an already existing 
    axes in order to add a background image

    .. code-block:: python

        import matplotlib.pyplot as plt
        import simstock as sim

        # Create test simstockdataframe
        sdf = sim.read_csv("testdata.csv")

        # Create matplotlib figure and axis
        fig = plt.figure()
        ax = fig.add_subplot(111)

        # Read in an image to be used as a background map
        bg_img = plt.imread("pathto/background_map.png")

        # Plot the background map
        ax.imshow(bg_img)  

        # Plot the data the existing axis, thereby overlaying 
        # it onto the background map
        sim.plot(
            sdf,
            facecolor="lightblue",
            edgecolor="red",
            ax=ax
            )

        # Set some attributes
        ax.title("Test Plot")
        ax.set_xticks([])
        ax.set_yticks([])

        # Display plot
        plt.show()
    """
    
    # Select the polygon data and feed into the
    # plotting function
    return _plot_geometries(
        sdf[polygon_column_name], facecolor=facecolor,edgecolor=edgecolor, **kwargs
        )


def _plot_geometries(geoms: list, **kwargs) -> Axes:
    """
    Function that takes a list of shapely geometries, 
    and plots each of them togther in a single plot.
    """

    # If a matplotlib axis object has already been
    # specified, then we plot to that axis,
    # else we create a new figure and axis
    if "ax" in kwargs:
        ax = kwargs["ax"]
        kwargs.pop("ax")
    else:
        _, ax = plt.subplots()

    try:
        for geom in geoms:
            # Plot each geometry
            _plot_geometry(geom, ax, **kwargs)
    except TypeError:
        # If geoms was not a list, but is instead
        # only a single instance of a shapely
        # geometry, then this will be caught
        # by this type error and we handle it
        # by just plotting the individual item.
        _plot_geometry(geoms, ax, **kwargs)

    # Turn off ticks by default
    ax.set_xticks([])
    ax.set_yticks([])
    return ax

def _plot_geometry(geom: Any, ax: Axes, **kwargs) -> None:
    """
    Function that takes a shapely geometry, finds its type, 
    and assigns it to the appropriate plotting function.
    """

    if isinstance(geom, Polygon):
        _plot_polygon(geom, ax, **kwargs)
    elif isinstance(geom, Point):
        _plot_point(geom, ax, **kwargs)
    elif isinstance(geom, LineString):
        _plot_linestring(geom, ax, **kwargs)
    elif isinstance(geom, MultiPolygon):
        _plot_multipolygon(geom, ax, **kwargs)
    else:
        raise TypeError(f"Could not plot {type(geom)}")



def _plot_polygon(geom: Polygon, ax: Axes, **kwargs) -> None:
    """
    Function to plot a polygon to ax
    """
    path = Path.make_compound_path(
        Path(np.asarray(geom.exterior.coords)[:, :2]),
        *[Path(np.asarray(ring.coords)[:, :2]) for ring in geom.interiors])
    patch = PathPatch(path, **kwargs)
    collection = PatchCollection([patch], **kwargs)
    ax.add_collection(collection, autolim=True)
    ax.autoscale_view()

def _plot_point(geom: Point, ax: Axes, **kwargs) -> None:
    """
    Function to plot a point to ax
    """
    ax.plot(geom.x, geom.y, **kwargs)


def _plot_linestring(geom: LineString, ax: Axes, **kwargs) -> None:
    """
    Function to plot a linestring to ax
    """
    ax.plot(*geom.xy, **kwargs)

def _plot_multipolygon(geom: MultiPolygon, ax: Axes, **kwargs) -> None:
    """
    Function to plot as multipolygon to ax
    """
    for p in list(geom.geoms):
        _plot_geometry(p, ax, **kwargs)


