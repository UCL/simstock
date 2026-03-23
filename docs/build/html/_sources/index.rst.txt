.. Simstock documentation master file

.. figure:: logo.svg
   :width: 450px
   :height: 150px
   :scale: 250 %
   :alt: alternate text
   :align: left

Simstock 
========

Simstock is a python package for taking geographical data, processing it into a form compatible with EnergyPlus, and running thermal simulations. SimStock thereby provides an intermediate
layer between various data types and EnergyPlus, allowing
UBEMs to be run straightforwardly from QGIS etc. The software performs the following setps: 

   1. Geometrical pre-processing. This ensures the input data is compatible with EnergyPlus.
   2. The creation of thermal zone object data for EnergyPlus.
   3. Running the simulation and handling the results. 


Simstock is provided by  `Building Stock Lab <https://www.ucl.ac.uk/bartlett/energy/research/building-stock-lab>`_ within UCL's Bartlett Energy Institute `Bartlett Energy Institute <https://www.ucl.ac.uk/bartlett/energy/>`_.

---- 

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   examples
   simstockqgis
   simstock
   devinstructions
   