# SimStock

![Tests](https://github.com/UCL/simstock/actions/workflows/test.yaml/badge.svg) ![Tests](https://github.com/UCL/simstock/actions/workflows/release.yaml/badge.svg)

SimStock is a python package for taking geographical and contextual data, processing it into a form compatible with EnergyPlus, and running thermal simulations. This provides an intermediate layer between various data types and EnergyPlus, allowing urban building energy models (UBEMs) to be run straightforwardly from QGIS etc. The software performs the following setps: 

   1. Geometrical pre-processing. This ensures the input data is compatible with EnergyPlus.
   2. The creation of thermal zone object data for EnergyPlus.
   3. Running the simulation and handling the results. 

---

Full docs are available at [ReadtheDocs](https://simstock.readthedocs.io/en/latest/index.html).

---

## Installation

> **_NOTE:_**  SimStock requires Python 3.8 or above, as well as an EnergyPlus installation.


After ensuring you have EnergyPlus installed, and python >= v3.8, simply run 

``` bash
    pip install simstock
```

in the command line.


## Usage

SimStock is structured around two objects: the ``SimstockDataframe`` and the ``IDFmanager``. The ``SimstockDataframe`` is an extension of a [Pandas Dataframe](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html). It allows data to be read in from a variety of formats. It also performs geometric simplification on the data to ensure it conforms to EnergyPlus input standards. The ``SimstockDataframe`` also contains the EnergyPlus settings, allowing easy manipulation of materials etc. Once these settings have been set, and any geometrical simplification perfomed, the ``IDFmanager`` then creates the necessary thermal zones from the ``SimstockDataframe``. The ``IDFmanager`` can also be used to run an EnergyPlus simulation. 

Below is an example of a typical Simstock work flow.

``` python
    # Import the simstock package
    import simstock as sim

    # Let's say we have some test data stored in a file called test.csv. 
    # We can read it in as a SimstockDataframe:
    sdf = sim.read_csv("test.csv")

    # We now perform geometrical pre-processing:
    sdf.preprocessing()

    # Now create an new instance of an IDFmanager object that takes the
    # processed SimstockDataframe as an argument:
    simulation = sim.IDFmanager(sdf)

    # Create the thermal zones necessary for EnergyPlus
    simulation.create_model_idf()

    # Run the energy plus simulation
    simulation.run()
```


