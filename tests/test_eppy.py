import os 
import platform
import glob
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


# ### These tests need modifying to make them 
# ### OS agnostic
# class EppyGoldenTestCase(GoldenTestCase): 

#     temp_dir = 'tests/data/actual_eppy_outputs' 
#     expected_dir = 'tests/data/golden_files/golden_eppy'
#     temp_expected_dir = 'tests/data/golden_files/golden_eppy_temp'

#     # Common locations for E+ idd files
#     common_windows_paths = ["C:\\EnergyPlus*\\Energy+.idd"]
#     common_posix_paths = [
#         "/usr/local/EnergyPlus*/Energy+.idd",
#         "/Applications/EnergyPlus*/Energy+.idd"
#     ]

#     def setUp(self):

#         # Find iddfile location
#         opsys = platform.system().casefold()
#         if opsys not in ["windows", "darwin", "linux"]:
#             msg = f"OS: {opsys} not recognise."
#             raise SystemError(msg)
#         self._find_idd(opsys)

#         # If silicon mac, ensure rosetta is installed
#         if platform.processor().casefold() == "arm":
#             try:
#                 if not os.path.isdir("/usr/libexec/rosetta"):
#                     raise Warning
#                 if len(os.listdir("/usr/libexec/rosetta")) == 0:
#                     raise Warning
#             except Warning as warn:
#                 msg = (
#                     "This appears to be a Silicone Mac." 
#                     "Please ensure Rosetta is installed to enable EnergyPlus functionality."
#                 )
#                 raise Warning(msg) from warn

#         #Run the eppy script and put results in temp dir
#         print("\nRunning EnergyPlus test simulation...\n")
#         IDF.setiddname(self.idd_file)

#         new_path1 = "ExampleFiles/BasicsFiles/Exercise1A.idf"
#         new_windows_path1 = "ExampleFiles\\BasicsFiles\\Exercise1A.idf"
#         new_path2 = "WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
#         new_windows_path2 = "WeatherData\\USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"

#         stripped_paths = []

#         if opsys == "windows":
#             last_separator_index = self.idd_file.rfind('\\')
#             if last_separator_index != -1:
#                 idfname = self.idd_file[:last_separator_index] + '\\' + new_windows_path1
#                 epwfile = self.idd_file[:last_separator_index] + '\\' + new_windows_path2
#             else:
#                 raise FileNotFoundError("Could not set idf file.")
#         else:
#             last_separator_index = self.idd_file.rfind('/')
#             if last_separator_index != -1:
#                 idfname = self.idd_file[:last_separator_index] + '/' + new_path1
#                 epwfile = self.idd_file[:last_separator_index] + '/' + new_path2
#             else:
#                 raise FileNotFoundError("Could not set idf file.")


#         # idfname = "/Applications/EnergyPlus-22-2-0/ExampleFiles/BasicsFiles/Exercise1A.idf"
#         # epwfile = "/Applications/EnergyPlus-22-2-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"

#         idf = IDF(idfname, epwfile)
#         idf.run(output_directory=self.temp_dir, verbose='q')  

#         #Make another temp dir, copy the pre-computed golden files into it 
#         shutil.copytree(self.expected_dir, self.temp_expected_dir)


#     def _find_idd(self, system: str) -> None:
#         """
#         Function to find IDD file within user's system
#         """
#         self.idd_file = None
#         if system == "windows":
#             paths = self.common_windows_paths
#         else:
#             paths = self.common_posix_paths
#         for path in paths:
#             # Use glob to handle pattern matching for version number
#             matches = glob.glob(path)
#             if matches:
#                 self.idd_file = matches[0]
#                 break
#         if self.idd_file == None:
#             raise FileNotFoundError("Could not find EnergyPlus IDD file")

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


# if __name__ == '__main__':
#     unittest.main() 