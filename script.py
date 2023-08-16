import matplotlib.pyplot as plt
import simstock as sim
from eppy.modeleditor import IDF

# How to compile: just set up a new sdf from base,
# and then do overwite with csvs and replace settings 
# with that

# Try compiling the csvs again into a new
# settings file; save the old one as settings_old 
# for now
# Check it works.
# Now compile with csvs that have more materials
# Check it still works.

sdf = sim.read_csv("tests/data/test_data.csv")

# Add a new material 
mat_dict = {
    "Name" : "Useless_Material",
    "Roughness" : "Rough",
    "Thickness" : 0.05,
    "Conductivity" : 0.4,
    "Density" : 10,
    "Specific_Heat" : 1000,
    "Thermal_Absorptance" : 0.9,
    "Solar_Absorptance" : 0.7,
    "Visible_Absorptance" : 0.7
}
sdf.settings.newidfobject("Material", **mat_dict)
sdf.preprocessing()


simulation = sim.IDFmanager(sdf)
simulation.create_model_idf_with_bi()

# Have a look at it
idf = IDF("outs/built_island_2.idf")
idf.epw = sdf.epw
idf.run(output_directory="outs")
