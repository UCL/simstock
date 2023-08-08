"""

Package for creating ``EnergyPlus`` input files (IDF files) from geographic data. 

Introduction
------------

``Simstock`` is a project to allow easy data passing and processing to ``EnergyPlus``. The package stores input data internally as a ``SimstockDataFrame``. The package can perform various prepossing actions on this data, before outputting an IDF file for ``EnergyPlus`` simulations.


Documentation is available at [placeholder.com](x)
(current release) and
[Read the Docs](x)
(release and development versions).

This package is also available as a QGIS plugin. See [placeholder.com](x) plugin installation and usage details. 

Basic usage
-----------

Given a file ``data.csv`` containing ``osgb`` and ``polygon`` data, ``Simstock`` can be used to create an ``IDF`` file as follows:

>>> import simstock as sim
>>> 
>>> # Read in data and preprocess
>>> sdf = sim.read_csv("data.csv")
>>> sdf.preprocessing()
>>> 
>>> # Create IDF file
>>> sim.create_idf(sdf, "sample.idf")

This will create an ``IDF`` file using some default parameters and preprocessing techniques. For a finer grained control of the proprocessing and ``IDF`` creation, refer to ``Advanced usage`` and the API documentation below.


Installation (pending)
----------------------

**Note: Simstock requires EnergyPlus to be installed.**

Simstock can be installed via your favourite package and environment manager:

Using poetry (recommended)
>>> poetry add simstock

Using pip: 
>>> pip install simstock 

Using conda:
>>> conda install simstock


Simstock can then be used within a python environment via:
>>> import simstock as sim



Advanced usage
--------------

``Simstock`` allows fine grained control over the preprocessing and ``IDF`` file creation steps. Interally, ``Simstock`` is based around two objects: 
- The ``SimstockDataframe`` class.
- The ``IDFcreator`` class.

The ``SimstockDataframe`` object is responsible for reading in data and preprocessing it. The ``IDFcreator`` object then computes various data needed for an EnergyPlus run. This data is then stored as an ``IDF`` file or an ``idf`` object for further use within Python. See the following code snippet as an example:

>>> import simstock as sim
>>> 
>>> # Read in data
>>> sdf = sim.read_csv("data.csv")
>>> 
>>> # Ensure exteriors and interiors are oriented correctly
>>> sdf.orientate_polygons(**kwargs)
>>> 
>>> # Remove duplicate coordinates from polygons
>>> sdf.remove_duplicate_coords(**kwargs)
>>> 
>>> # Check for polygons intersecting each other
>>> sdf.polygon_topology(**kwargs)
>>> 
>>> # Assess which polygons need simplifying
>>> sdf.polygon_tolerace(**kwargs)
>>> 
>>> # Simplify relevant polygons
>>> sdf.polygon_simplification(**kwargs)
>>> 
>>> # Check again that polygons are not intersecting each other
>>> sdf.polygon_topology(**kwargs)
>>> 
>>> # Remove collinear points, determine exterior surfaces coordinates
>>> sdf.collinear_exterior(**kwargs)
>>> 
>>> # Final check that nothing is interecting after the above processing
>>> # It pays to repeatedly check this
>>> sdf.ploygon_topology(**kwargs)
>>> 
>>> # We now have proprocessed data ready to be turned into an IDF file
>>> # To turn it into an IDF file, we can either call create_idf,
>>> # or instantiate an IDFcreator object for finer grained control:
>>> ob = sim.IDFcreator(sdf)
>>> 
>>> # Move all objects towards origin
>>> ob.move_towards_origin(**idfkwargs)
>>> 
>>> # Create shading objects
>>> ob.create_shading_objects(**idfkwargs)
>>> 
>>> # Create thermal zones based on floor number
>>> ob.create_thermal_zones(**idfkwargs)
>>> 
>>> Compute ideal load systems
>>> ob.create_load_systems(**idfkwargs)
>>> 
>>> # All relevant data for an E+ run have now been created
>>> # The results can be saved to a file:
>>> ob.save_to_file("output.idf")
>>> # Or kept as an eppy idf object for further processing:
>>> idf = ob.idf

In all the obove function calls, the user can specify ket word arguments ``kwargs`` and ``idfkwargs``. Refer to the detailed API documentation for a full list of arguments.



Dev install
-----------

To install a developer's verion of Simstock, follow these steps:
- Install ``poetry``
- Clone the simstock repository from [github](x)
- In the base of the Simstock-Model repository, run ``poetry install``

To then launch python in the command line, just run:

```console
~$ poetry run python
```

"""

from simstock.io import (
    read_csv,
    read_parquet,
    read_json,
    read_geopackage_layer,
    to_csv,
    to_parquet,
    to_json,
    get_gpkg_layer_names
)
from simstock.base import (
    SimstockDataframe,
    IDFmanager
)
from simstock.plotting import (
    plot
)


__all__ = [
    "SimstockDataframe",
    "read_csv",
    "read_geopackage_layer",
    "read_parquet",
    "read_json",
    "to_csv",
    "to_parquet",
    "to_json",
    "get_gpkg_layer_names"
    "IDFmanager",
    "create_idf",
    "plot"
    ]
