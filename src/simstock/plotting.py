"""
Plotting module containing routines for plotting
basic geometries.
"""

from functools import singledispatch
from typing import Any
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.collections import PatchCollection
from matplotlib.axes._axes import Axes
from shapely.geometry import (
    Polygon,
    Point,
    LineString
)
from pandas.core.series import Series
from pandas.core.frame import DataFrame
from simstock.base import SimstockDataframe


def plot(sdf : SimstockDataframe | Series | DataFrame, **kwargs) -> Axes:
    """
    Plot a SimstockDataframe's geometric data.

    Parameters
    ----------
    ``sdf : SimstockDataframe or Pandas Series or Dataframe``
        The data to be plotted. One column must be called 
        ``polygon`` and contain shapely geometries.

    ``**kwargs, optional``
        All additional keyword arguments to be passed to 
        ``matplotlib``

    Returns
    -------
    ``ax : matplotlib Axes``
        Matplotlib axis object instance containing 
        the plotted geometric data

    Examples
    --------
    ### Basic usage

    ```python
    import matplotlib.pyplot as plt
    import simstock as sim

    # Create test simstockdataframe
    sdf = sim.read_csv("testdata.csv")

    # Plot
    sim.plot(sdf, facecolor="lightblue", edgecolor="red")
    plt.show()
    ```

    ### More advanced usage

    ```python
    import matplotlib.pyplot as plt
    import simstock as sim

    # Create test simstockdataframe
    sdf = sim.read_csv("testdata.csv")

    # Create matplotlib figure and axis
    fig = plt.figure()
    ax = fig.add_subplot(111)

    # Plot to the existing axis
    sim.plot(
        sdf,
        facecolor="lightblue",
        edgecolor="red",
        ax=ax)

    # Set some ttributes
    ax.title("Test Plot")
    ax.set_xticks([])
    ax.set_yticks([])

    # Display plot
    plt.show()
    ```
    """
    
    # Select the polygon data and feed into the
    # plotting function
    return _plot_geometries(sdf.polygon, **kwargs)


def _plot_geometries(geoms : list, **kwargs) -> Axes:
    """
    Function that takes a list of shapely geometries, 
    and plots each of them togther in a single plot.

    This is utility function, not designed to be exposed
    to the user API.
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


@singledispatch
def _plot_geometry(geom : Any, _ : Axes):
    """
    Function to plot an individual shapely geometry.
    Each type of geometry (Point, Polygon, LineString)
    needs to be plotted differently. To handle this, this
    function is overloaded using singledispatch to accept
    each of these three types.

    This is utility function, not designed to be exposed
    to the user API.
    """

    # If geom is not of a type for which an overloaded
    # function definition is given, then this
    # code will be reached, giving a type error.
    msg = f"Type: {type(geom)} cannot be used with function plot_geometry()"
    raise TypeError(msg)


@_plot_geometry.register
def _(geom : Polygon, ax : Axes, **kwargs) -> PatchCollection:
    """
    Overloaded Polygon implementation of the
    _plot_geometry function.

    This is utility function, not designed to be exposed
    to the user API.
    """
    path = Path.make_compound_path(
        Path(np.asarray(geom.exterior.coords)[:, :2]),
        *[Path(np.asarray(ring.coords)[:, :2]) for ring in geom.interiors])
    patch = PathPatch(path, **kwargs)
    collection = PatchCollection([patch], **kwargs)
    ax.add_collection(collection, autolim=True)
    ax.autoscale_view()
    return collection


@_plot_geometry.register
def _(geom : Point, ax : Axes, **kwargs) -> None:
    """
    Overloaded Point implementation of the
    _plot_geometry function.

    This is utility function, not designed to be exposed
    to the user API.
    """
    ax.plot(geom.x, geom.y, **kwargs)


@_plot_geometry.register
def _(geom : LineString, ax : Axes, **kwargs) -> None:
    """
    Overloaded LineString implementation of the
    _plot_geometry function.

    This is utility function, not designed to be exposed
    to the user API.
    """
    ax.plot(*geom.xy, **kwargs)
