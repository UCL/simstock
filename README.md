# Simstock
---

This is the refactored core version of Simstock. User docs are available in ``docs/build/html/index.html`` (open in your web browser). 

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

Running unit tests
------------------

This version of simstock comes with a unit test suite, located within the ``tests/`` subdirectory. To run these tests, ensure you are in the base of the Simstock directory and run the following command: 

.. code-block:: bash

    poetry run python -m unittest -b -v

If you are using Conda instead of Poetry, then omit the ``poetry run`` command. For more information on modifying and adding tests, consult the ``unittest`` `documentation <https://docs.python.org/3/library/unittest.html>`_.

Generating and modifying the docs
---------------------------------

HTML docs are automatically generated from the docstrings within the Simstock source code. You can also include additional pages (such as this one) giving tutorials etc. 

To compile the docs into html, navigate into the ``docs`` subdirectory and run 

.. code-block:: bash

    poetry run make clean
    poetry run make html

If not using Poetry, then omit the ``poetry run`` directives.

All pages and docstrings within the documentation must be written in ``.rst`` format. This is similar to markdown. Refer to the `rst cheatsheet <https://bashtage.github.io/sphinx-material/rst-cheatsheet/rst-cheatsheet.html>`_ for a quick guide. All documentation .rst files are contained within ``docs/source/``. To add a new page to the documentation, create a new .rst file within ``docs/source/`` and then add the file name (minus the .rst extension)  into toctree list within ``docs/source/index.rst``.

Once compiled, the html documents can be found within ``docs/build/html``.

