import os
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod


class ScheduleManager(ABC):
    """
    Abstract base class defining the interface for schedule managers.
    """

    @abstractmethod
    def get_occupancy_schedule(self, usage_type):
        pass

    @abstractmethod
    def get_equipment_schedule(self, usage_type):
        pass

    @abstractmethod
    def get_lighting_schedule(self, usage_type):
        pass

    @abstractmethod
    def get_heating_schedule(self, usage_type):
        pass

    @abstractmethod
    def get_cooling_schedule(self, usage_type):
        pass
    

class CSVScheduleManager(ScheduleManager):
    """
    ScheduleManager implementation that reads schedules from CSV files.
    """

    def __init__(self, csv_directory):
        self.csv_directory = csv_directory
        self.schedules = {}
        self.load_schedules_from_csv()

    def load_schedules_from_csv(self):
        # Load the schedules from 'DB-Schedules-SCHEDULE_COMPACT.csv'
        schedules_file = os.path.join(self.csv_directory, 'DB-Schedules-SCHEDULE_COMPACT.csv')
        schedules_df = pd.read_csv(schedules_file)
        self.schedules = {}

        # Group schedules by Name
        for name, group in schedules_df.groupby('Name'):
            self.schedules[name] = group

    def get_schedule(self, schedule_name):
        if schedule_name in self.schedules:
            return self.schedules[schedule_name]
        else:
            raise ValueError(f"Schedule '{schedule_name}' not found in CSV files.")

    def get_occupancy_schedule(self, usage_type):
        schedule_name = f"{usage_type}_Occ"
        return self.get_schedule(schedule_name)

    def get_equipment_schedule(self, usage_type):
        schedule_name = f"{usage_type}_Equip"
        return self.get_schedule(schedule_name)

    def get_lighting_schedule(self, usage_type):
        schedule_name = f"{usage_type}_Light"
        return self.get_schedule(schedule_name)

    def get_heating_schedule(self, usage_type):
        schedule_name = f"{usage_type}_Heat"
        return self.get_schedule(schedule_name)

    def get_cooling_schedule(self, usage_type):
        schedule_name = f"{usage_type}_Cool"
        return self.get_schedule(schedule_name)


class StochasticScheduleManager(ScheduleManager):
    """
    ScheduleManager implementation that generates stochastic schedules.
    """

    def __init__(self, random_seed=None):
        self.random_seed = random_seed
        if self.random_seed is not None:
            np.random.seed(self.random_seed)
        self.schedule_rules = {}

    def set_schedule_rule(self, usage_type, schedule_type, rule_function):
        if usage_type not in self.schedule_rules:
            self.schedule_rules[usage_type] = {}
        self.schedule_rules[usage_type][schedule_type] = rule_function

    def get_schedule(self, usage_type, schedule_type):
        rule = self.schedule_rules.get(usage_type, {}).get(schedule_type)
        if rule:
            return rule()
        else:
            raise ValueError(f"No rule defined for usage type '{usage_type}' and schedule type '{schedule_type}'.")

    def get_occupancy_schedule(self, usage_type):
        return self.get_schedule(usage_type, 'occupancy')

    def get_equipment_schedule(self, usage_type):
        return self.get_schedule(usage_type, 'equipment')

    def get_lighting_schedule(self, usage_type):
        return self.get_schedule(usage_type, 'lighting')

    def get_heating_schedule(self, usage_type):
        return self.get_schedule(usage_type, 'heating')

    def get_cooling_schedule(self, usage_type):
        return self.get_schedule(usage_type, 'cooling')

