# Simstock
---

This is the refactored core version of Simstock. User docs are available in ``docs/simstock.html`` (open in your web browser). 

See also the ``demo.ipynb`` Jupyter notebook in this repository for an interactive demo.

---
## Installation

 Either ``poetry`` or ``conda`` can be used to set up the environment and manage depenencies.


> **NOTE 1:** To use Simstock, you will need to have EnergyPlus version 8.9 or above installed. This can be found on the official EnergyPlus website.

> **NOTE 2:** These installation docs will be adjusted when there is a public release, after which Simstock will be available from PyPI. After the public release, the user docs will be hosted in readthedocs.com.

### via Poetry (recommended)

First, ensure Poetry is installed. See [poetry homepage](https://python-poetry.org/) for an introduction to Poetry, and [poetry installation docs](https://python-poetry.org/docs/#installation) for platform specific instructions.

Next, download or clone this simstock repository. Navigate into this repository and type into the command line:
```bash
poetry install
```

And that's it.




### via Conda

First, ensure Conda is installed. See [Conda docs](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).

Next, download or clone this simstock repository. Navigate into this repository and type the commands below into the commnd line, one at a time:
```bash
conda env create -f environment.yaml
conda activate simstock
```

And that's it.

---

## Using Simstock

After activating the repository using either Poetry or Conda, Simstock can be used within python. E.g. create a python script called, say, ``example.py`` and populate it with the following code:
```python
import simstock as sim

# Create test simstockdataframe
sdf = sim.read_csv("tests/data/test_data.csv")
```

This code can then be run from the command line via:
```bash
# If using poetry
poetry run python example.py
```

```bash
# If using conda
python example.py
```

Simstock can also be run within the interactive python shell. To do this simply type into the command line:
```bash
poetry run python # if using poetry
```
or
```bash
python # if using conda
```
Within the resulting interactive python shell, you can then invoke simstock as normal:
```python
import simstock as sim
```

----

## Running tests (dev notes)

This version of simstock has a testing suite. To run tests, type into the command line:
```bash
# If using poetry
poetry run python -m unittest -b -v
```
or
```bash
# If using conda
python -m unittest -b -v
```

> **NOTE:** If using Conda, you must first ensure that unittest is installed on your system.

----

## Regenerating docs (dev notes)

To generate html docs, type into the command line:
```bash
# If using poetry
poetry run python -m pdoc simstock/src -o docs
```
or
```bash
# If using conda
python -m pdoc simstock/src -o docs
```

> **NOTE:** If using Conda, you must first ensure that pdoc is installed on your system. Ensure you are using pdoc and NOT pdoc3.





