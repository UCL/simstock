import simstock as sim
from eppy.modeleditor import IDF

sdf = sim.read_csv("tests/data/test_data.csv")
sdf.preprocessing()

simulation = sim.IDFmanager(sdf)
simulation.create_model_idf_with_bi()

# Have a look at it
idf = IDF("outs/built_island_2.idf")
idf.epw = sdf.epw
idf.run(output_directory="outs")
