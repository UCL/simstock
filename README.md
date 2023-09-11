# Simstock

Simstock is a python package for taking geographical
and contextual data, processing it into a form compatible with EnergyPlus, and running thermal simulations. SimStock thereby provides an intermediate
layer between various data types and EnergyPlus, allowing
UBEMs to be run straightforwardly from QGIS etc. The software performs the following setps: 

   1. Geometrical pre-processing. This ensures the input data is compatible with EnergyPlus.
   2. The creation of thermal zone object data for EnergyPlus.
   3. Running the simulation an handling the results. 

---

Full docs are available at [ReadtheDocs](https://simstock.readthedocs.io/en/latest/index.html).

## Installation

> **_NOTE:_**  Simstock requires Python 3.8 or above, as well as an EnergyPlus installation.


Simstock can be installed directly from PyPI (recommended) or in developer mode by cloning this repository. 

## Installing from PyPI (recommended)


After ensuring you have EnergyPlus installed, and python >= v3.8, simply run 

``` bash
    pip install simstock
```

in the command line.

## Installing from Github (for developers)

First, clone the Simstock repository from `Github <https://github.com/UCL/simstock>`_ by typing into the command line: 

``` bash
    git clone https://github.com/UCL/simstock.git
```

Alternatively, download the `zip <https://github.com/UCL/simstock>`_ from Github and unzip. Either way, this will create a directory called ``simstock`` with the following internal structure:

```
    simstock/ 
    ├── src/ 
    │   └── simstock/ 
    ├── README.md
    ├── environment.yaml
    ├── poetry.lock
    ├── pyproject.toml
    ├── tests/
    └── docs/
```


The source code for Simstock is contained within ``src/simstock``. The ``docs`` folder contains the documentation you are currently reading. The ``tests`` folder contains unit tests that can be run with Python's unittest suite. 

### Handling dependencies


You will need to handle the project's dependencies. This can be done either using `Poetry <https://python-poetry.org/>`_ (recommended), or Conda. This is what the ``.toml``, ``.lock`` and ``.yaml`` files are for.

#### Using Poetry

First, download and install Poetry on your system by following the `installation guide <https://python-poetry.org/docs/>`_. Once installed, navigate into the base of the ``simstock`` directory and type into the command line (or power shell):

``` bash
    poetry install
```

This installs all the requisite dependencies in a local virtual environment. You can now enter the python interactive shell using 

``` bash
    poetry run python
```

To varify installation of simstock, you may then type into the python shell:

``` python
    import simstock as sim
```

Alternatively, you could create a python script called, say, ``script.py`` which should be located in the base of the ``simstock`` directory. Inside this file write

``` python
    import simstock as sim
```

This script can now be run from the command line using 

``` bash
    poetry run python script.py
``` 

Note the inclusion of the ``poetry run`` before the usual python commands.

#### Using Conda

First, ensure Conda is installed (see `installation guide <https://conda.io/projects/conda/en/latest/user-guide/install/index.html>`_).

Navigate into the base of the ``Simstock`` directory and type the commands below into the commnd line, one at a time:

``` bash
    conda env create -f environment.yaml
    conda activate simstock
```

The interactive python shell can now be invoked simply by typing ``python`` into the command line. Inside the interactive shell, you could type

``` python
    import simstock as sim
```

to varify the ``Simstock`` installation. Any scripts can be run by the usual python command; e.g., to run a script you have created called ``script.py``:

``` bash
    python script.py
```

--- 

## Usage

Simstock is structured around two objects: the ``SimstockDataframe`` and the ``IDFmanager``. The ``SimstockDataframe`` is an extension of a `Pandas Dataframe <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html>`_. It allows data to be read in from a variety of formats. It also performs geometruc simplification on the data. The ``SimstockDataframe`` also contains the EnergyPlus settings, allowing easy manipulation of materials etc. Once these settings have been set, and any geometrical simplification perfomed, the ``IDFmanager`` then creates the necessary thermal zones from the ``SimstockDataframe``. The ``IDFmanager`` can also be used to run an EnergyPlus simulation. 

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


