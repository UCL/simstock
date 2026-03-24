============
Installation
============


.. admonition:: Requirements \ \ 

   SimStock supports Python versions 3.11 to 3.13 and requires an installation of EnergyPlus 8.9. It is recommended that EnergyPlus .idd files are installed to ``C:\\EnergyPlus*\\Energy+.idd`` if using Windows, where ``*`` will be the EnergyPlus version number. If using Mac or Linux, it is recommended to have the EnergyPlus idd files at either ``/usr/local/EnergyPlus*/Energy+.idd`` or ``/Applications/EnergyPlus*/Energy+.idd``. Silicone Mac users should also have Rosetta installed.

SimStock can either being installed from PyPI (recommended for most users) or in developer mode by cloning the repository.

----

Installation from PyPI (recommended)
====================================

After ensuring you have EnergyPlus installed, simply run 

.. code-block:: bash

    pip install simstock

in the command line.

----

.. _idd-troubleshooting:

EnergyPlus IDD file location
----------------------------

SimStock requires an EnergyPlus 8.9 IDD file (typically called ``Energy+.idd``).
When creating a ``SimstockDataframe``, SimStock first looks for 
a user-specified IDD location. User can specify the location of their IDD file
either by seeting it with an environment variable:

.. code-block:: bash

   export IDD_FILE="/path/to/Energy+.idd"

or by passing the location as an optional parameter in Python, e.g.:

.. code-block:: python

   import simstock as sim
   sdf = sim.read_csv("test.csv", idd_file="/path/to/Energy+.idd")

If no user-specified location is found, SimStock looks for an IDD file in the default locations:
   - Windows: ``C:\\EnergyPlus*\\Energy+.idd``
   - macOS/Linux: ``/usr/local/EnergyPlus*/Energy+.idd`` or ``/Applications/EnergyPlus*/Energy+.idd``

If no IDD file is found, SimStock raises ``FileNotFoundError``.

---

Installation for developers
===========================

First, clone the SimStock repository from `Github <https://github.com/UCL/simstock>`_ by typing into the command line: 

.. code-block:: bash

    git clone https://github.com/UCL/simstock.git

Alternatively, download the `zip <https://github.com/UCL/simstock>`_ from Github and unzip. Either way, this will create a directory called ``simstock`` with the following internal structure:

| simstock/
| ├── src/
| │   └── simstock/
| ├── README.md
| ├── environment.yaml
| ├── poetry.lock
| ├── pyproject.toml
| ├── tests/
| └── docs/

The source code for SimStock is contained within ``src/simstock``. The ``docs`` folder contains the documentation you are currently reading. The ``tests`` folder contains unit tests that can be run with Python's unittest suite. 

Handling dependencies
*********************

You will need to handle the project's dependencies. This can be done either using `Poetry <https://python-poetry.org/>`_ (recommended), or Conda. This is what the ``.toml``, ``.lock`` and ``.yaml`` files are for.

Using Poetry
^^^^^^^^^^^^

First, download and install Poetry on your system by following the `Poetry installation guide <https://python-poetry.org/docs/>`_. Once installed, navigate into the base of the ``simstock`` directory and type into the command line (or power shell):

.. code-block:: bash

    poetry install

This installs all the requisite dependencies in a local virtual environment. You can now enter the python interactive shell using 

.. code-block:: bash

    poetry run python

To varify installation of simstock, you may then type into the python shell:

.. code-block:: python

    import simstock as sim

Alternatively, you could create a python script called, say, ``script.py`` which should be located in the base of the ``simstock`` directory. Inside this file write

.. code-block:: python

    import simstock as sim

This script can now be run from the command line using 

.. code-block:: bash

    poetry run python script.py 

Note the inclusion of the ``poetry run`` before the usual python commands.

Using Conda
^^^^^^^^^^^

First, ensure Conda is installed (see `Conda installation guide <https://conda.io/projects/conda/en/latest/user-guide/install/index.html>`_).

Navigate into the base of the ``Simstock`` directory and type the commands below into the commnd line, one at a time:

.. code-block:: bash

    conda env create -f environment.yaml
    conda activate simstock
    pip install -e .

The interactive python shell can now be invoked simply by typing ``python`` into the command line. Inside the interactive shell, you could type

.. code-block:: python

    import simstock as sim

to varify the ``simstock`` installation. Any scripts can be run by the usual python command; e.g., to run a script you have created called ``script.py``:

.. code-block:: bash

    python script.py
