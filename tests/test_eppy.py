import os 
import shutil 
import unittest 
from eppy.modeleditor import IDF 
from tests.golden import GoldenTestCase 


def decap(path) -> None: 
    for p in path:
        with open(p, 'r') as fin:
            data = fin.read().splitlines(True) 
        with open(p, 'w') as fout: 
            fout.writelines(data[1:]) 


#### These tests need modifying to make them 
#### OS agnostic

# class EppyGoldenTestCase(GoldenTestCase): 

#     temp_dir = 'tests/data/actual_eppy_outputs' 
#     expected_dir = 'tests/data/golden_files/golden_eppy'
#     temp_expected_dir = 'tests/data/golden_files/golden_eppy_temp'

#     def setUp(self):

#         #Run the eppy script and put results in temp dir
#         print("\nRunning EnergyPlus test simulation...\n")
#         iddfile = "/Applications/EnergyPlus-22-2-0/Energy+.idd"
#         IDF.setiddname(iddfile)

#         idfname = "/Applications/EnergyPlus-22-2-0/ExampleFiles/BasicsFiles/Exercise1A.idf"
#         epwfile = "/Applications/EnergyPlus-22-2-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"

#         idf = IDF(idfname, epwfile)
#         idf.run(output_directory=self.temp_dir, verbose='q')  

#         #Make another temp dir, copy the pre-computed golden files into it 
#         shutil.copytree(self.expected_dir, self.temp_expected_dir) 

#     def test_eppy_golden(self):
#         """
#         Test EnergyPlus utils work.
#         """

#         expected_esofile = os.path.join(self.temp_expected_dir, 'eplusout.eso') 
#         expected_mtrfile = os.path.join(self.temp_expected_dir, 'eplusout.mtr') 
#         generated_esofile = os.path.join(self.temp_dir, 'eplusout.eso')
#         generated_mtrfile = os.path.join(self.temp_dir, 'eplusout.mtr') 
        
#         #Decapitate files to remove timestamps 
#         decap([expected_esofile, expected_mtrfile, 
#                 generated_esofile, generated_mtrfile]) 

#         self.assertGolden(expected_esofile, generated_esofile) 
#         self.assertGolden(expected_mtrfile, generated_mtrfile) 

#     def tearDown(self):
#         if os.path.exists(self.temp_dir): 
#             shutil.rmtree(self.temp_dir)  
#         if os.path.exists(self.temp_expected_dir): 
#             shutil.rmtree(self.temp_expected_dir)  


if __name__ == '__main__':
    unittest.main() 