========================
Usage and basic examples
========================

.. _Overview:

Overview: reading in data and running a simulation
--------------------------------------------------

Simstock reads in geographical data, performs some geometric simplification steps, creates EnergyPlus idf objects, and then finally runs an EnergyPlus simulation. Simstock also provides a convenient interface to modify EnergyPlus settings such as materials, constructions, and schedules. 

Simstock is structured around two objects: the ``SimstockDataframe`` and the ``IDFmanager``. The ``SimstockDataframe`` is an extension of a `Pandas Dataframe <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html>`_. It allows data to be read in from a variety of formats. It also performs geometruc simplification on the data. The ``SimstockDataframe`` also contains the EnergyPlus settings, allowing easy manipulation of materials etc. Once these settings have been set, and any geometrical simplification perfomed, the ``IDFmanager`` then creates the necessary thermal zones from the ``SimstockDataframe``. The ``IDFmanager`` can also be used to run an EnergyPlus simulation. 

Below is an example of a typical Simstock work flow.

.. code-block:: python 

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


By default this will create all the EnergyPlus output files and save them into a directory call ``outs``.

----

.. _Data requirements:
Data requirements
-----------------

The input data may be in csv, json, geopackage, or parquet formats. The rows of the data should represent different buildings or premises. Simstock requires the following fields for each building or premises:

.. admonition:: Required fields \ \ 

   - ``polygon`` The geometric data for the building/premises. Allowable formats:
    - Shapely geometries
    - ``wkb`` strings
    - ``wkt`` strings
   - ``osgb`` :: ``string`` or ``integer`` (unique ID)
   - ``shading`` :: ``bool`` (whether or not the building is purely a shading object)
   - ``height`` :: ``integer`` or ``float`` (height of building)
   - ``wwr`` :: ``integer`` or ``float`` (window to wall ratio)
   - ``nofloors`` :: ``integer`` (number of floors)
   - ``construction`` :: ``string`` (the type of contrucion)

If your geometry and unique ID columns are named something other than ``polygon`` or ``osgb``, then you must specify their names during the creation of a SimstockDataframe. This is done using the ``polygon_column_name`` and ``uid_columm_name`` parameters. E.g., if you have a data file called ``test_data.csv``, whereing your geometry column is named ``building_geom`` and your osgb unique ID is called ``building_ID``, then:

.. code-block:: python 

    sdf = sim.read_csv(
            "test_data.csv",
            polygon_column_name = "building_geom"
            uid_column_name = "building_ID"
        )

.. hint:: \ \ 

    You can input data that contains only the ``osgb`` and ``polygon`` fields, without the rest of the required fields. If you do this, Simstock will append empty columns with the required names and raise a message telling you to fill them in.


----

Reading different data formats
------------------------------

SimstockDataframes can be insantiated from an already `Pandas Dataframe <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html>`_, a python dictionary, or another SimstockDataframe. However, SimstockDataframes can also be created directly from data files using the ``read`` functions. Below is a summary of reading different formats. 

csv files
~~~~~~~~~

SimstockDataframes can be insantiated from csv files using the ``read_csv`` function. E.g.:

.. code-block:: python 

    sdf = sim.read_csv("test_data.csv")

The input csv must conform to the standard outlined above in the data requirements section.

Parquet files
~~~~~~~~~~~~~

SimstockDataframes can be insantiated from parquet files using the ``read_parquet`` function. E.g.:

.. code-block:: python 

    sdf = sim.read_parquet("test_data.parquet")

The input parquet file must conform to the standard outlined above in the data requirements section.

json files
~~~~~~~~~~

SimstockDataframes can be insantiated from json files using the ``read_json`` function. E.g.:

.. code-block:: python 

    sdf = sim.read_json("test_data.json")

The input json file must conform to the standard outlined above in the data requirements section.

Geopackage files
~~~~~~~~~~~~~~~~

A layer of a geopackage can be read in and turned into a SimstockDataframe using the ``read_geopackage_layer`` function, while specifying the layer name in the ``layer_name`` parameter. E.g., if you have a geopackage named ``london.gpkg`` containing a layer called ``croydon``, then you can read in this layer via the command 

.. code-block:: python

    sdf = sim.read_geopackage_layer("london.gpkg", layer_name="croydon")

Note that when reading in a geopackage, you do not need to explicitly set the ``polygon`` column or field in the data. Once the geopackage has been read, the resulting SimstockDataframe will contain the extracted geometries in a column called polygon. E.g.:

.. code-block:: python

    # Read in geopackage layer
    sdf = sim.read_geopackage_layer("london.gpkg", layer_name="croydon")

    # Print the extracted geomtric data from the geopackage
    print(sdf['polygon'])

    # Equivalently
    print(sdf.polygon)


If you wish to see the names of the layers in your geopackage before creating a SimstockDataframe you can use the function ``get_gpkg_layer_names``. E.g.:

.. code-block:: python

    # Print the names of layers in the geopackage 
    layers = sim.get_gpkg_layer_names("london.gpkg")

You could then, for example, read all the layers in as a list of SimstockDataframes:

.. code-block:: python

    # Create empty list
    sdf_list = []

    # Iteraate over all layers in the geopackage
    for layer in sim.get_gpkg_layer_names("london.gpkg"):
        
        # Read in the layer as a SimstockDataframe and add to list
        sdf = sim.read_geopackage_layer("london.gpkg", layer_name=layer)
        sdf_list.append(sdf)

----

Working with the SimstockDataframe
----------------------------------

The purpose of the SimstockDataframe is to process geographic information into a form that is valid for an EnergyPlus simulation. It also allows an interface to adjust various settings like materials and schedules. 

The geographic and contextual data, such as the ``polygon`` data or the ``height`` data (see the :ref:`Data requirements` section), can be accessed in exactly the same way as the data in a `Pandas Dataframe <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html>`_. Indexing works in the same way, and all other pandas-like functionality is supported, such as filtering and mapping. The section provides some examples of this functionality.

Accessing data
~~~~~~~~~~~~~~

The data stored in a SimstockDataframe can be accessed using the standard Pandas method. For example, the SimstockDataframe contains a column called ``Height``; this can accessed like

.. code-block:: python 

    height_column = sdf["Height"]

You could select the first value in the ``Height`` column using the `iloc accessor <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html>`_:

.. code-block:: python

    first_height = sdf["Height"].iloc[0]

You can iterate over the rows using via

.. code-block:: python

    for row in sdf.itertuples(index=False):
        print(row)

You can also perform filtering. E.g. to select all rows with a height of less than 10m:

.. code-block:: python 

    short_buildings = sdf[sdf["Height"] < 10]



Performing calculations
~~~~~~~~~~~~~~~~~~~~~~~

You can you Panda's `apply <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.apply.html>`_ method to manipulate columns. E.g., to square all of the values in the ``Height`` column (for some reason):

.. code-block:: python

    sdf["Height"] = sdf["Height"].apply(lambda x: x**2)

Or perhaps create a new column containing ``Height squared``:

.. code-block:: python

    sdf["Height squared"] = sdf["Height"].apply(lambda x: x**2)

You could make this conditional. E.g., only square the values if their height is less than 10:

.. code-block:: python

    sdf["Height squared"] = sdf["Height"].apply(lambda x: x**2 if x < 10 else x)

We can also perform arithmetic on the columns. E.g., let's say we can to calculate the approximate floor to ceiling height by dividing the the height of the building by the number of floors:

.. code-block:: python

    sdf["Floor to Ceiling"] = sdf["Height"]/sdf["nofloors"]

Saving data
~~~~~~~~~~~

SimstockDataframes can be easily saved to either ``csv``, ``parquet``, or ``json`` using the ``to_csv``, ``to_parquet`` and ``to_json`` functions, respectively. E.g., to save to a csv:

.. code-block:: python

    # To save a SimstockDataframe called sdf to a csv file
    sim.to_csv(sdf, "output_file_name.csv")

----

Plotting data
-------------

Simstock comes with some basic options for visualising the geographic data stored in the SimstockDataframe, utilising ``matplotlib``. 

E.g. the following code 

.. code-block:: python 

    import matplotlib.pyplot as plt

    # Assuming we have previously instantiated a SimstockDataframe called sdf
    sim.plot(sdf, facecolor="lightblue", edgecolor="red")
    plt.show()

would produce the figure below.

.. figure:: plotoutput.png
   :width: 150px
   :height: 100px
   :scale: 250 %
   :alt: alternate text
   :align: left


|
|
|
|
|
|
|
|
|
|
|


----

.. _Specifying weather data:
Specifying weather data
-----------------------

In addition to containing the geographic and contextual data outlined in the  :ref:`Data requirements` section, SimstockDataframes also contain the settings and weather data, in ``epw`` format, to be used in the EnergyPlus simulation. This weather data can be accessed via 

.. code-block:: python

    # Assuming we have previously instantiated a SimstockDataframe called sdf
    sdf.epw

By default, Simstock will use the weather data for St. James's Park, London. To specifiy a different epw file, you can either point the epw attribute to your some other epw file: 

.. code-block:: python

    sdf.epw = "some_other_epw_file_of_your_choosing.epw"

or specifiy the weather file when you first instantiate the SimstockDataframe; e.g., 

.. code-block:: python

    import simstock as sim

    sdf = sim.read_csv(
            "your_data.csv",
            epw_file="some_other_epw_file_of_your_choosing.epw"
        )

----

.. _Specifying settings:
Specifying schedules, materials, and constructions
--------------------------------------------------

As mentioned in the :ref:`Specifying weather data` section, SimstockDataframes contain the settings that specify the EnergyPlus simulation: materials, constructions, and schedules. The SimstockDataframe acts as an interface to view and edit each of these. Internally, these settings are stored as an ``IDF`` object.

Each of these settings can be viewed as attributes of the SimstockDataframe. E.g.:

.. code-block:: python

    import simstock as sim

    sdf = sim.read_csv("test.csv")

    # To view materials
    print(sdf.materials)

    # To view constructions
    print(sdf.constructions)

    # To view schedule information
    print(sdf.schedules)

    # To iterate over materials:
    for material in sdf.materials:

        # The properties of each material (e.g. name) can be accessed like
        print(material.Name)

    # To iterate over constructions:
    for construction in sdf.constructions:

        # The properties of each construction (e.g. name) can be accessed like
        print(construction.Name)

    # To print the entire settings IDF:
    sdf.print_settings()

By default, the SimstockDataframes contain some useful constructions and materials. These can be viewed as shown above. You may want to edit or delete some of these, or add your own. Simstock provides two ways of doing this: either programmatically or via csv files. The two methods are described below.

Editing settings programmatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's say you want to edit one of the materials contained within the SimstockDataframe's materials list. In this example, we will access the first material in the materials list and change its name.

First let's view this material

.. code-block:: python

    # Let's say we have a SimstockDataframe instantiated from a csv file
    sdf = sim.read_csv("test_data.csv")

    # We can view the first material in the default list of materials:
    print(sdf.materials[0])

This will show the following information:

.. code-block:: text 

    MATERIAL,
        10mm_carpet,              !- Name
        Rough,                    !- Roughness
        0.01,                     !- Thickness
        0.058,                    !- Conductivity
        20,                       !- Density
        1000,                     !- Specific Heat
        0.9,                      !- Thermal Absorptance
        0.5,                      !- Solar Absorptance
        0.5;                      !- Visible Absorptance

To change this material's name from 10mm_carpet to 10mm_persian_rug, we simply do:

.. code-block:: python

    # Access its name and change it
    sdf.materials[0].Name = "10mm_persian_rug"

    # Now print the material again to see the change
    print(sdf.materials[0])

This will now produce

.. code-block:: text 

    MATERIAL,
        10mm_persian_rug,         !- Name
        Rough,                    !- Roughness
        0.01,                     !- Thickness
        0.058,                    !- Conductivity
        20,                       !- Density
        1000,                     !- Specific Heat
        0.9,                      !- Thermal Absorptance
        0.5,                      !- Solar Absorptance
        0.5;                      !- Visible Absorptance

Similarly any of the other attributes like Roughness and Thickness etc. can be changed in the same fashion. 

We can also create an entirely new material and add it to the settings. To do, use the ``settings.newidfobject`` function. The example below adds a new material, called 20_mm_frieze_carpet.

.. code-block:: python

    # The first paramter of the function specifies 
    # the type of setting. In this case, material
    sdf.settings.newidfobject(
            "MATERIAL",
            Name="20_mm_frieze_carpet",
            Roughness="Rough",
            Thickness=0.02,
            Conductivity=0.058,
            Density=20,
            Specific_Heat=1000,
            Thermal_Absorptance=0.9,
            Solar_Absorptance=0.5,
            Visible_Absorptance=0.5
        )

    # This will now have been appended to the end of the 
    # list of materials. We can check this by printing
    # the last element of the list
    print(sdf.materials[-1])

The above code would print the new material:

.. code-block:: text

    MATERIAL,
        20_mm_frieze_carpet,      !- Name
        Rough,                    !- Roughness
        0.02,                     !- Thickness
        0.058,                    !- Conductivity
        20,                       !- Density
        1000,                     !- Specific Heat
        0.9,                      !- Thermal Absorptance
        0.5,                      !- Solar Absorptance
        0.5;                      !- Visible Absorptance

You might find it more convenient to first bundle the properties of the material into a dictionary, and then pass the dictionary to the ``settings.newidfobject`` function. This is equivalent to the above method. An example if shown in the code below:

.. code-block:: python

    # Create a dictionary containing the material's parameters
    d = {
        "Name":"20_mm_frieze_carpet",
        "Roughness":"Rough",
        "Thickness":0.02,
        "Conductivity":0.058,
        "Density":20,
        "Specific_Heat":1000,
        "Thermal_Absorptance":0.9,
        "Solar_Absorptance":0.5,
        "Visible_Absorptance":0.5 
    }

    # Pass this to the newidffunction to add this material to the list
    sdf.settings.newidfobject("MATERIAL", **d)

.. important:: \ \ 
    Material and construction attributes that are named with two or more words such as "Specific Heat" and "Thermal Absorptance" must use an underscore to denote the space; e.g., "Specific_Heat" and "Thermal_Absorptance". 


Editing settings using csv files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You may prefer to specify the settings using csv files containing your materials etc. and their properties. To do this Simstock allows the option of creating a SimstockDataframe containing a blank settings attribute. From this clean slate, you may then add settings by telling Simstock to read in csv files. 

Here is a worked example. We start by creating a SimsstockDataframe as normal, but this time specify the option ``use_base_idf`` to be ``True``. This will force the SimstockDataframe to load in an empty settings object, allowing us to work with a blank slate:

.. code-block:: python

    # Start by instantiating a SimstockDataframe, 
    # and specificy use_base_idf
    sdf = sim.read_csv("test.csv", use_base_idf=True)

We can check that the sdf has a blank settings object by trying to print its constructions and materials. If we do, it will return nothing:

.. code-block:: python

    # This returns nothing
    print(sdf.materials)

We now want to ask Simstock to give us a directory in which to enter our information. Simstock will also populate the diectory with correctly formatted csv files that we can use. To do this, we call the ``create_csv_folder``:

.. code-block:: python

    sdf.create_csv_folder()

By default, this creates a new directory inside your working directory called ``simulation_settings``. It has the contents:

| simulation_settings/
| ├── DB-Fabric-CONSTRUCTION.csv
| ├── DB-Fabric-MATERIAL_NOMASS.csv
| ├── DB-Fabric-MATERIAL.csv
| ├── DB-Fabric-WINDOWMATERIAL_GAS.csv
| ├── DB-Fabric-WINDOWMATERIAL_GLAZING.csv
| ├── DB-HeatingCooling-OnOff.csv
| ├── DB-Loads-ELECTRICEQUIPMENT.csv
| ├── DB-Loads-LIGHTS.csv
| ├── DB-Loads-PEOPLE.csv
| ├── DB-Schedules-SCHEDULE_COMPACT.csv
| ├── infiltration_dict.json
| └── ventilation_dict.json

You can specify a directory name other that ``simulation_settings`` using the ``dirname`` option; e.g.,

.. code-block:: python

    # To place the csv files in some other directory
    sdf.create_csv_folder(dirname="some_other_directory_name")

You may now edit the csv files as you wih to modify, add and remove settings. By default the csv files will already contain some usefule materials and constructions. You may also replace the csv files with your own files, but they must adhere to the names above; i.e., ``DF-Fabric-CONSTRUCTION.csv`` etc.

Once you are satisifed, you can register your csv files back into Simstock with the command

.. code-block:: python

    sdf.override_settings_with_csv()

This will read in all of the settings from the csv directory into your SimstockDataframe. They can then be inspected as usual using the ``sdf.materials`` commands etc.


----


Running a simulation
--------------------

Once you have read in your data, set your settings (as detailed the :ref:`Specifying settings` section), and performed your preprocessing step, you are ready to create and run an EnergyPlus simulation. This is handled using the ``IDFmanager`` object, which uses the processed SimstockDataframe to create EnergyPlus thermal zones and then run a simulation. 

Here is an example:

.. code-block:: python

    # Say we have a processed SimstockDataframe sdf
    # We now use it to create an IDFmanager:
    simulation = sim.IDFmanager(sdf)

    # Now create the thermal zones necessary for EnergyPlus
    simulation.create_model_idf()

    # Finally, run the energy plus simulation
    simulation.run()

This will save EnergyPlus output files into a directory called ``outs/`` in your working directory. To save to another location, use the ``out_dir`` option with instantiating the ``IDFmanager``; e.g.,

.. code-block:: python

    # To save EnergyPlus output files into some other directory:
    simulation = sim.IDFmanager(sdf, out_dir="some_other_directory")


.. Finer grained control
.. ---------------------

.. This can be done like this. 


.. Using built island mode
.. -----------------------

.. That can be switched on or off like this.


.. Common problems
.. ---------------

.. .idd file not found
.. *******************

.. Specifiy this here.

