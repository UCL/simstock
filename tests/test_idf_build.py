import os
import tempfile
import unittest
from pathlib import Path
import pandas as pd
import simstock as sim


@unittest.skipUnless(
    os.environ.get("IDD_FILE"),
    "Set IDD_FILE to an EnergyPlus .idd file to run this test.",
)

class IDFTestBuild(unittest.TestCase):
    def test_build_idf_from_buildings1(self) -> None:
        """
        Main end-to-end test without built island mode:
        read input data, preprocess geometry, create an IDF, and save it.
        We assert that one IDF is created, that it contains some zones, and that the file is saved.
        """
        csv_path = Path(__file__).resolve().parent / "data" / "buildings1.csv"

        sdf = sim.read_csv(str(csv_path))
        sdf.preprocessing()

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "outs"

            manager = sim.IDFmanager(
                sdf,
                bi_mode=False,
                buffer_radius=0,
                out_dir=str(out_dir),
            )
            manager.create_model_idf()

            self.assertEqual(len(manager.bi_idf_list), 1)
            self.assertGreater(len(manager.bi_idf_list[0].idfobjects["ZONE"]), 0)

            manager.save_idfs()
            self.assertTrue((out_dir / "built_island_0.idf").exists())


    def test_build_bi_mode_from_buildings1(self) -> None:
        """
        Main end-to-end test with built island mode enabled:
        read input data, preprocess geometry, create an IDF, and save it.
        Assert that one IDF is created, that it contains some zones, that the file is saved,
        and that the algorithm for creating built islands is working
        (this input data is known to have 5 separate physically unconnected building clusters, 
        so we expect 5 built islands and thus 5 IDFs).
        """
        csv_path = Path(__file__).resolve().parent / "data" / "buildings1.csv"

        sdf = sim.read_csv(str(csv_path))
        sdf.preprocessing()

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "outs"

            manager = sim.IDFmanager(
                sdf,
                bi_mode=True,
                buffer_radius=0,
                out_dir=str(out_dir),
            )
            manager.create_model_idf()

            self.assertEqual(len(manager.bi_idf_list), 5)
            self.assertGreater(len(manager.bi_idf_list[0].idfobjects["ZONE"]), 0)

            manager.save_idfs()
            self.assertTrue((out_dir / "built_island_0.idf").exists())

if __name__ == "__main__":
    unittest.main()
