import numpy as np
import pandas as pd

class Schedule:
    def __init__(self, name, csv_path=None, seed=None):
        """
        Initialise the Schedule object.

        Parameters:
            name (str): Name of the schedule.
            csv_path (str, optional): Path to the CSV file for archetypal schedules.
            seed (int, optional): Seed for random number generator (for reproducibility).
        """
        self.name = name
        self.csv_path = csv_path
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def generate(self, building_properties=None):
        """
        Generate schedule data.

        Parameters:
            building_properties (dict, optional): Properties of the building or zone.

        Returns:
            list: A list of 24 hourly schedule values.
        """
        if self.csv_path:
            return self._read_csv_schedule()
        else:
            return self._default_random_schedule()

    def _read_csv_schedule(self):
        """
        Read schedule data from a CSV file.

        Returns:
            list: A list of 24 hourly schedule values.
        """
        try:
            df = pd.read_csv(self.csv_path)
            # Assume the CSV has a single row with 24 columns for each hour
            if df.shape[0] < 1:
                raise ValueError(f"CSV file {self.csv_path} is empty.")
            schedule_data = df.iloc[0].tolist()
            if len(schedule_data) != 24:
                raise ValueError(f"CSV file {self.csv_path} must contain 24 hourly values.")
            return schedule_data
        except Exception as e:
            print(f"Error reading CSV schedule from {self.csv_path}: {e}")
            # Fallback to default random schedule
            return self._default_random_schedule()

    def _default_random_schedule(self):
        """
        Generate a default random schedule.

        Returns:
            list: A list of 24 hourly schedule values.
        """
        # Example: Random occupancy fractions between 0 and 1
        occupancy_levels = self.rng.uniform(0, 1, 24)
        return occupancy_levels.tolist()
