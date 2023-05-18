import unittest 
import pandas as pd
from simstock.base import SimstockDataframe  


class SimstockDataframeSetUpTestCase(unittest.TestCase):

    # Test polygon object
    x = "POLYGON ((528845.05 186041.6,528840.423 186048.664,528837.2 186046.599,528835.25 186045.35,528839.7 186038.25,528845.05 186041.6))"

    # Test osgb list
    osgbs = ["osgb1000005307038",
             "osgb1000005307041",
             "osgb1000005306983"]

    def setUp(self) -> None:
        """
        Setting up test data structures to be used to initialise 
        the simstock dataframe. 
        """

        # Dicts to initialise from
        self.dict_valid_names = {
            "id":["a","b","c"],
            "polygon":[self.x, self.x, self.x],
            "stats":[0.1,0.2,0.3],
            "osgb":self.osgbs
        }
        self.dict_invalid_names = {
            "id":["a","b","c"],
            "poygon":[self.x, self.x, self.x],
            "stats":[0.1,0.2,0.3],
            "osgb":self.osgbs
        }
        self.dict_invalid_geoms = {
            "id":["a","b","c"],
            "polygon":[1, 1, 1],
            "stats":[0.1,0.2,0.3],
            "osgb":self.osgbs
        }
        self.dict_invalid_osgbs = {
            "id":["a","b","c"],
            "polygon":[self.x, self.x, self.x],
            "stats":[0.1,0.2,0.3],
            "osbgx":self.osgbs
        }

        # Pandas dataframes to initialise from
        self.df_valid_names = pd.DataFrame(self.dict_valid_names)
        self.df_invalid_names = pd.DataFrame(self.dict_invalid_names)
        self.df_invalid_geoms = pd.DataFrame(self.dict_invalid_geoms)
        self.df_invalid_osgbs = pd.DataFrame(self.dict_invalid_osgbs)

    def test_simstockdataframe_dictinit(self) -> None:
        """
        Test that the simstock data frame can be initialised from 
        a dictionary containing a polygon column. 
        """
        sdf = SimstockDataframe(self.dict_valid_names)
        self.assertEqual(sdf.is_valid.all(), True)

    def test_simstockdf_invalid_dict_names(self) -> None:
        """
        Test that initialising a simstock dataframe with
        incorrectly labelled polygon column raises an error.
        """
        with self.assertRaises(KeyError):
            SimstockDataframe(self.dict_invalid_names)

    def test_simstockdf_invalid_geoms(self) -> None:
        """
        Test that initialising a simstock dataframe with
        invalid geometry data raises an error.
        """
        with self.assertRaises(TypeError):
            SimstockDataframe(self.dict_invalid_geoms)

    def test_simstockdf_invalid_osgb(self) -> None:
        """
        Test that initialising a simstock dataframe with
        incorrectly labelled osgb column raises an error.
        """
        with self.assertRaises(KeyError):
            SimstockDataframe(self.dict_invalid_osgbs)

    def test_simstockdataframe_dfinit(self) -> None:
        """
        Test that the simstock data frame can be initialised from 
        a pandas dataframe containing a polygon column. 
        """
        sdf = SimstockDataframe(self.df_valid_names)
        self.assertEqual(sdf.is_valid.all(), True)

    def test_simstockdf_invalid_df_names(self) -> None:
        """
        Test that initialising a simstock dataframe from dataframe with
        incorrectly labelled polygon column raises an error.
        """
        with self.assertRaises(KeyError):
            SimstockDataframe(self.df_invalid_names)

    def test_simstockdf_invalid_df_geoms(self) -> None:
        """
        Test that initialising a simstock dataframe with
        invalid geometry data in a pandas dataframe raises an error.
        """
        with self.assertRaises(TypeError):
            SimstockDataframe(self.df_invalid_geoms)

    def test_simstockdf_invalid_df_osgbnames(self) -> None:
        """
        Test that initialising a simstock dataframe from dataframe with
        incorrectly labelled osgb column raises an error.
        """
        with self.assertRaises(KeyError):
            SimstockDataframe(self.df_invalid_names)

    def tearDown(self) -> None:
        return super().tearDown()


if __name__ == "__main__": 
    unittest.main()
