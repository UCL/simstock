import os
import matplotlib.pyplot as plt
import simstock as sim
from eppy.modeleditor import IDF


# Path to test data
s7data = os.path.join("tests", "data", "S7_data.gpkg")

# # Initialise
sdf = sim.read_geopackage_layer(s7data, "test_full", uid_column_name="UID", index="fid", use_base=True)
sdf.preprocessing()

simulation = sim.IDFmanager(sdf)
simulation.create_model_idf_with_bi()
print(sdf.materials)

# # Have a look at it
# idf = IDF("built_island_2.idf")
# idf.epw = sdf.epw
# idf.run(output_directory="outs")
