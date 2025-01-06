"""
Module containing routines for generating 
objects for E+
"""
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
from typing import Any, Union
import math
from shapely.geometry import LineString
import simstock._algs._coords_algs as calgs
import simstock._algs._polygon_algs as palgs
from pandas.core.series import Series
from pandas.core.frame import DataFrame
from eppy.modeleditor import IDF
from shapely.geometry import Polygon


def _set_construction(construction: str, element: str) -> str:
    """
    Returns the relevant name of the building surface depending on the 
    construction name.
    """
    if element == "ground_floor":
        return f"{construction}_solid_ground_floor"
    if element == "wall":
        return f"{construction}_wall"
    if element == "roof":
        return f"{construction}_flat_roof"
    if element == "ceiling":
        return "ceiling"
    if element == "ceiling_inverse":
        return "ceiling_inverse"
    

def _mixed_use(idf: IDF, zone_use_dict: dict) -> None:

    # Check for missing values
    for key, value in zone_use_dict.items():
        if not isinstance(value, str) and math.isnan(value):
            raise ValueError(f"{key} has no value for 'use'.")

    # Create a zonelist for each use
    use_list = list(zone_use_dict.values())
    use_list = list(map(str.lower, use_list)) #remove case-sensitivity
    use_list = list(set(use_list))
    for use in use_list:
        zone_list = list()
        for key, value in zone_use_dict.items():
            if value.lower() == use:
                zone_list.append(key)
        idf.newidfobject('ZONELIST', Name=use)
        objects = idf.idfobjects['ZONELIST'][-1]
        for i, zone in enumerate(zone_list):
            exec('objects.Zone_%s_Name = zone' % (i + 1))
    
    objects_to_delete = list()
    for obj in ['PEOPLE', 'LIGHTS', 'ELECTRICEQUIPMENT',
                'ZONEINFILTRATION:DESIGNFLOWRATE',
                'ZONECONTROL:THERMOSTAT']:
        objects = idf.idfobjects[obj]
        for item in objects:
            if item.Zone_or_ZoneList_Name.lower() not in use_list:
                objects_to_delete.append(item)

    for item in objects_to_delete:
        idf.removeidfobject(item)


# This could be broken into two functions
def _thermal_zones(row: Series,
                   df: DataFrame,
                   idf: IDF,
                   origin: list,
                   min_avail_width_for_window: Union[float, int],
                   min_avail_height: Union[float, int],
                   zone_use_dict: dict
                   ) -> None:
    """
    Internal function to create thermal zone objects
    for use by E+
    """
    polygon = row.polygon
    # Polygon with removed collinear point to be used for ceiling/floor/roof
    hor_polygon = row.polygon_horizontal
    # Convert polygon coordinates to dictionary of outer and inner (if any)
    # coordinates
    hor_poly_coord_dict = palgs._polygon_coordinates_dictionary(hor_polygon)
    # List of horizontal surfaces coordinates (roof/floor/ceiling)
    horiz_surf_coord = calgs._horizontal_surface_coordinates(
        hor_poly_coord_dict, origin)
    # Load the polygon which defines only external surfaces
    ext_surf_polygon = row.polygon_exposed_wall
    # List of external surface only coordinates (ext_surf_polygon + in. rings)
    ext_surf_coord = palgs._surface_coordinates(ext_surf_polygon, origin)
    # List of adjacent polygons
    adj_osgb_list = row.touching

    height = row.height
    glazing_ratio = row.wwr
    floors = range(int(row.nofloors))

    construction = row.construction
    glazing_const = f'{construction}_glazing'

    try:
        overhang_depth = row.overhang_depth
    except AttributeError:
        overhang_depth = 0.0

    if len(floors) == 1:

        floor_no = int(1)
        x = row.osgb
        zone_name = f'{x}_floor_{floor_no}'
        try:
            zone_use_dict[zone_name] = row["FLOOR_1: use"]
        except KeyError:
            zone_use_dict[zone_name] = "Dwell"
        zone_floor_h = 0
        space_below_floor = 'Ground'
        zone_ceiling_h = height
        space_above_floor = 'Outdoors'

        idf.newidfobject('ZONE', Name=zone_name)

        floor_const = _set_construction(construction, "ground_floor")
        _floor(idf, zone_name, space_below_floor, horiz_surf_coord,
              zone_floor_h, floor_const)

        roof_const = _set_construction(construction, "roof")
        _roof_ceiling(idf, zone_name, space_above_floor,
                     horiz_surf_coord, zone_ceiling_h, roof_const)

        zone_height = zone_ceiling_h - zone_floor_h
        wall_const = _set_construction(construction, "wall")
        _external_walls(idf, zone_name, floor_no, ext_surf_coord,
                       zone_ceiling_h, zone_floor_h, zone_height,
                       min_avail_height, min_avail_width_for_window,
                       wall_const, glazing_const, glazing_ratio,
                       overhang_depth)

        # Partition walls where adjacent polygons exist
        if adj_osgb_list:
            # Surface type; no sun exposure; no wind exposure
            partition_const = 'partition'
            # Loop through the list of adjacent objects
            for adj_osgb in adj_osgb_list:
                opposite_zone = adj_osgb
                # Extract polygon from the adjacent objects DataFrame
                adj_polygon = df.loc[df['osgb'] == adj_osgb,
                                           'polygon'].values[0]
                adj_height = df.loc[df['osgb'] == adj_osgb,
                                    'height'].values[0]
                # Find the intersection between two polygons (it will be
                # LineString or MultiLineString) and position coordinates
                # relative to origin
                part_wall_polygon = polygon.intersection(adj_polygon)
                adj_wall_parti_surf_coord = palgs._surface_coordinates(
                    part_wall_polygon, origin)
                if zone_ceiling_h < adj_height + 1e-6:
                    _partition_walls(idf, zone_name, opposite_zone,
                                    adj_wall_parti_surf_coord,
                                    zone_ceiling_h, zone_floor_h,
                                    partition_const)
                else:
                    if zone_floor_h > adj_height - 1e-6:
                        _external_walls(idf, zone_name, floor_no,
                                       adj_wall_parti_surf_coord,
                                       zone_ceiling_h, zone_floor_h,
                                       zone_height, min_avail_height,
                                       min_avail_width_for_window,
                                       wall_const, glazing_const,
                                       glazing_ratio, overhang_depth)
                    else:
                        _external_walls(idf, zone_name, floor_no,
                                       adj_wall_parti_surf_coord,
                                       zone_ceiling_h, adj_height,
                                       zone_height, min_avail_height,
                                       min_avail_width_for_window,
                                       wall_const, glazing_const,
                                       glazing_ratio, overhang_depth)
                        _partition_walls(idf, zone_name, opposite_zone,
                                        adj_wall_parti_surf_coord,
                                        adj_height, zone_floor_h,
                                        partition_const)


    else:
        f2f = round(height / row.nofloors, 1)
        for item in floors:
            floor_no = item + 1
            if item == 0:
                x = row.osgb
                zone_name = f'{x}_floor_{floor_no}'
                try:
                    zone_use_dict[zone_name] = row[f"FLOOR_{floor_no}: use"]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = 'Ground'
                zone_ceiling_h = floor_no * f2f
                space_above_floor = f'{row.osgb}_floor_{floor_no + 1}'

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = _set_construction(construction, "ground_floor")
                _floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = _set_construction(construction, "ceiling")
                _roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h, roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = _set_construction(construction, "wall")
                _external_walls(
                    idf, zone_name, floor_no, ext_surf_coord, zone_ceiling_h,
                    zone_floor_h, zone_height, min_avail_height,
                    min_avail_width_for_window, wall_const, glazing_const,
                    glazing_ratio, overhang_depth)

                # Partition walls where adjacent polygons exist
                if adj_osgb_list:
                    # Surface type; no sun exposure; no wind exposure
                    partition_const = 'partition'
                    # Loop through the list of adjacent objects
                    for adj_osgb in adj_osgb_list:
                        opposite_zone = adj_osgb
                        # Extract polygon from the adjacent objects DataFrame
                        adj_polygon = df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0]
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = palgs._surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            _partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                _partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)

            elif item == row.nofloors - 1:
                zone_name = f'{row.osgb}_floor_{floor_no}'
                try:
                    zone_use_dict[zone_name] = row[f"FLOOR_{floor_no}: use"]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = f'{row.osgb}_floor_{floor_no-1}'
                zone_ceiling_h = height
                space_above_floor = 'Outdoors'

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = _set_construction(construction, "ceiling_inverse")
                _floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = _set_construction(construction, "roof")
                _roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h, roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = _set_construction(construction, "wall")
                _external_walls(
                    idf, zone_name, floor_no, ext_surf_coord, zone_ceiling_h,
                    zone_floor_h, zone_height, min_avail_height,
                    min_avail_width_for_window, wall_const, glazing_const,
                    glazing_ratio, overhang_depth)

                # Partition walls where adjacent polygons exist
                if adj_osgb_list:
                    # Surface type; no sun exposure; no wind exposure
                    partition_const = 'partition'
                    # Loop through the list of adjacent objects
                    for adj_osgb in adj_osgb_list:
                        opposite_zone = adj_osgb
                        # Extract polygon from the adjacent objects DataFrame
                        adj_polygon = df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0]
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = palgs._surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            _partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                _partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)

            else:
                zone_name = f'{row.osgb}_floor_{floor_no}'
                try:
                    zone_use_dict[zone_name] = row[f"FLOOR_{floor_no}: use"]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = f'{row.osgb}_floor_{floor_no-1}'
                zone_ceiling_h = floor_no * f2f
                space_above_floor = f'{row.osgb}_floor_{floor_no+1}'

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = _set_construction(construction, "ceiling_inverse")
                _floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = _set_construction(construction, "ceiling")
                _roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h,
                             roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = _set_construction(construction, "wall")
                _external_walls(
                    idf, zone_name, floor_no, ext_surf_coord, zone_ceiling_h,
                    zone_floor_h, zone_height, min_avail_height,
                    min_avail_width_for_window, wall_const, glazing_const,
                    glazing_ratio, overhang_depth)

                # Partition walls where adjacent polygons exist
                if adj_osgb_list:
                    # Surface type; no sun exposure; no wind exposure
                    partition_const = 'partition'
                    # Loop through the list of adjacent objects
                    for adj_osgb in adj_osgb_list:
                        opposite_zone = adj_osgb
                        # Extract polygon from the adjacent objects DataFrame
                        adj_polygon = df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0]
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = palgs._surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            _partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                _external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                _partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)


    return


def _idf_ceiling_coordinates_list(ceiling_coordinates_list: list) -> list:
    '''
    Function which converts ceiling coordinates list into format used by E+
    '''
    idf_ceiling_coordinates_list = []
    # Loop through a list of ceiling coordinates lists
    for ceiling_coordinates in ceiling_coordinates_list:
        # For each coordinates list remove the last element (which is same as
        # first since energyplus surfaces don't end in the first coordinate)
        ceiling_coordinates = ceiling_coordinates[:-1]
        # Reverse the list of coordinates in order to have energyplus surface
        # facing outside
        ceiling_coordinates = list(reversed(ceiling_coordinates))
        # Append a list of ceiling coordinates lists
        idf_ceiling_coordinates_list.append(ceiling_coordinates)
    # Return a list of ceiling coordinates lists
    return idf_ceiling_coordinates_list


def _wall_centre_coordinate(
        ceil_1: str,
        ceil_0: str,
        floor_0: str
        ) -> str:
    '''
    Function which calculates centre point of the wall. Return the
    string with centre coordinate (X,Y,Z). Useful for surface naming
    particularly in partition walls due to required opposite surface wall name
    '''
    # List of horizontal/vertical coordinates ordered pair strings
    hor = [ceil_1, ceil_0]
    ver = [ceil_0, floor_0]
    # Exclude Z and X coordinate from horizontal and vertical coordinates resp
    hor = [item[:-1] for item in hor]
    ver = [item[1:] for item in ver]
    # By using shapley obtain the centre coordinate between ordered pairs
    hor = LineString(hor).centroid
    hor = hor.coords[0]
    ver = LineString(ver).centroid
    ver = ver.coords[0]
    # Wall centre coordinate is created from horizontal ordered pair appended
    # with Z coordinate (ver[-1]) from vertical ordered pair
    wcc = hor + (ver[-1],)
    # Format wall centre coordinate as a string
    wcc = ['%.2f' % item for item in wcc]
    wcc = '(' + '_'.join(wcc) + ')'
    # Return wall centre coordinate string
    return wcc


def _idf_wall_coordinates(
        i: int,
        ceiling_coordinates: list,
        floor_coordinates: list
        ) -> list:
    '''
    Function which converts wall coordinates into format used by E+
    (upper left, bottom left, bottom right, upper right)
    '''
    idf_wall_coordinates = [ceiling_coordinates[i + 1],
                            floor_coordinates[i + 1],
                            floor_coordinates[i],
                            ceiling_coordinates[i]]
    # Return wall coordinates
    return idf_wall_coordinates


def _adiabatic_roof(
        idf: IDF,
        polygon_name: str,
        horizontal_surface_coordinates: list,
        ceiling_height: Union[float, int]
        ) -> None:
    ceiling_coordinates_list = calgs._coordinates_add_height(
        ceiling_height, horizontal_surface_coordinates)
    coordinates_list = _idf_ceiling_coordinates_list(ceiling_coordinates_list)
    surface_name = str(polygon_name) + '_AdiabaticRoof'
    for coordinates in coordinates_list:
        _shading_building_detailed(idf, surface_name, coordinates)
    return


def _shading_building_detailed(
        idf: IDF,
        surface_name: str,
        coordinates: list
        ) -> None:
    '''
    Function which creates ShadingBuilding:Detailed energyplus object
    '''
    idf.newidfobject(
        'Shading:Building:Detailed'.upper(),
        Name=surface_name)
    # Add coordinates to the latest added energyplus object
    objects = idf.idfobjects['Shading:Building:Detailed'.upper()][-1]
    # Loop through coordinates list and assign X, Y, and Z vertex of each#
    # ordered pair to the associated Vertex coordinate
    for i, ordered_pair in enumerate(coordinates):
        exec(f'objects.Vertex_{i+1}_Xcoordinate = ordered_pair[0]')
        exec(f'objects.Vertex_{i+1}_Ycoordinate = ordered_pair[1]')
        exec(f'objects.Vertex_{i+1}_Zcoordinate = ordered_pair[2]')
    return


def adiabatic_walls(
        idf: IDF,
        polygon_name: str,
        perimeter_surface_coordinates: list,
        ceiling_height: Union[float, int],
        floor_height: Union[float, int],
        wall_name: str
        ) -> None:
    '''
    Internal function which creates energyplus object for adiabatic
    external walls based on horizontal coordinates. Firstly, it appends
    horizontal coordinates with floor and ceiling height and than loop
    through coordinates in order to pick up adjacent coordinate pairs. Wall
    is formed of two top and two bottom coordinates while in the horizontal
    coordinate list can be a lot of adjacent coordinates pairs
    '''
    # Append the perimeter coordinates with the ceiling and floor heights
    ceiling_coordinates = calgs._coordinates_add_height(
        ceiling_height, perimeter_surface_coordinates)
    floor_coordinates = calgs._coordinates_add_height(
        floor_height, perimeter_surface_coordinates)
    # Loop through list of ceiling coordinates lists to extract ceiling and
    # floor coordinate lists. It can be more than one list pair in case of
    # presence of inner holes
    for n, item in enumerate(ceiling_coordinates):
        ceil_coord = ceiling_coordinates[n]
        floor_coord = floor_coordinates[n]
        # Loop through ceiling coordinate list up to the next to the last
        # item
        for i, p in enumerate(ceil_coord[:-1]):
            # Calculate wall centre coordinate in 3D plane (used for
            # naming)
            wcc = _wall_centre_coordinate(
                ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
            # Generate the name form polygon name, wall name and centre
            # coordinate
            surface_name = str(polygon_name) + '_' + str(wall_name) + '_' + str(wcc)
            # Generate wall coordinates in format used by energyplus
            coordinates = _idf_wall_coordinates(i, ceil_coord, floor_coord)
            # Creates shading elements which represent the adiabatic
            # external wall
            _shading_building_detailed(idf, surface_name, coordinates)
    return


def _wall_width_height(
        i: int,
        ceil_coord: list,
        floor_coord: list
        ):
    '''
    Internal function which calculates wall width and height
    '''
    # upper left corner coordinates
    ulc = ceil_coord[i + 1]
    # bottom left corner coordinates
    blc = floor_coord[i + 1]
    # bottom right corner coordinates
    brc = floor_coord[i]
    # Calculate wall width and height by using the Euclidean distance
    w = math.sqrt(math.pow(
        (brc[0] - blc[0]), 2) + math.pow((brc[1] - blc[1]), 2) +
        math.pow((brc[2] - blc[2]), 2))
    h = math.sqrt(math.pow(
        (ulc[0] - blc[0]), 2) + math.pow((ulc[1] - blc[1]), 2) +
        math.pow((ulc[2] - blc[2]), 2))
    # Return wall width and height
    return w, h


def _idf_floor_coordinates_list(floor_coordinates_list: list) -> list:
    '''
    Internal function which converts list of floor coordinates into format
    used by E+
    '''
    idf_floor_coordinates_list = []
    # Loop through a list of floor coordinates lists
    for floor_coordinates in floor_coordinates_list:
        # For each coordinates list remove the last element (which is same
        # as first since energyplus surfaces don't end in the first
        # coordinate)
        idf_floor_coordinates = floor_coordinates[:-1]
        # Append a list of floor coordinates lists
        idf_floor_coordinates_list.append(idf_floor_coordinates)
    # Return a list of floor coordinates lists
    return idf_floor_coordinates_list


def _floor(
        idf: IDF,
        zone_name: str,
        space_below_floor: str,
        horizontal_surface_coordinates: list,
        floor_height: Union[float, int],
        ground_floor_const: str
        ) -> None:
    '''
    Function which generates floor energyplus object
    '''

    # Surface name made of the zone name appended with '_Floor' string
    surface_name = zone_name + '_Floor'
    # Surface type; no sun exposure; no wind exposure
    surface_type = 'Floor'
    sun_exposure = 'NoSun'
    wind_exposure = 'NoWind'

    # If space below the floor is Ground than set up outside boundary
    # condition to the 'Ground'
    if space_below_floor == 'Ground':
        outside_boundary_condition = space_below_floor
        outside_boundary_condition_object = ''
    # If space below the floor is thermal zone than set up outside boundary
    # condition to the 'Surface', outside boundary condition object to the zone
    # below name appended with '_Ceiling' string
    else:
        outside_boundary_condition = 'Surface'
        outside_boundary_condition_object = space_below_floor + '_Ceiling'
    # Append the floor horizontal coordinates with the height
    floor_coordinates_list = calgs._coordinates_add_height(
        floor_height, horizontal_surface_coordinates)
    # Convert floor coordinates list to format used in energyplus
    coordinates_list = _idf_floor_coordinates_list(floor_coordinates_list)
    # For each coordinates list in a list of coordinates lists creates building
    # surface detailed element which represents the floor
    for coordinates in coordinates_list:
        _building_surface_detailed(idf, surface_name, surface_type,
                                  ground_floor_const, zone_name,
                                  outside_boundary_condition,
                                  outside_boundary_condition_object,
                                  sun_exposure, wind_exposure, coordinates)
    return


def _building_surface_detailed(
        idf: IDF,
        surface_name: str,
        surface_type: str,
        construction_name: str,
        zone_name: str,
        outside_boundary_condition: str,
        outside_boundary_condition_object: Any,
        sun_exposure: Any,
        wind_exposure: Any,
        coordinates: list
        ) -> None:
    '''
    Function which creates BuildingSurface:Detailed energyplus object
    '''
    idf.newidfobject(
        'BuildingSurface:Detailed'.upper(),
        Name=surface_name,
        Surface_Type=surface_type,
        Construction_Name=construction_name,
        Zone_Name=zone_name,
        Outside_Boundary_Condition=outside_boundary_condition,
        Outside_Boundary_Condition_Object=outside_boundary_condition_object,
        Sun_Exposure=sun_exposure,
        Wind_Exposure=wind_exposure)
    # Add coordinates to the latest added energyplus object
    objects = idf.idfobjects['BuildingSurface:Detailed'.upper()][-1]
    # Loop through coordinates list and assign X, Y, and Z vertex of each
    # ordered pair to the associated Vertex coordinate
    for i, ordered_pair in enumerate(coordinates):
        exec('objects.Vertex_%s_Xcoordinate = ordered_pair[0]' % (i + 1))
        exec('objects.Vertex_%s_Ycoordinate = ordered_pair[1]' % (i + 1))
        exec('objects.Vertex_%s_Zcoordinate = ordered_pair[2]' % (i + 1))
    return


def floor(
        idf: IDF,
        zone_name: str,
        space_below_floor: str,
        horizontal_surface_coordinates: list,
        floor_height: Union[float, int],
        ground_floor_const: str
        ) -> None:
    '''
    Function which generates floor energyplus object
    '''

    # Surface name made of the zone name appended with '_Floor' string
    surface_name = zone_name + '_Floor'
    # Surface type; no sun exposure; no wind exposure
    surface_type = 'Floor'
    sun_exposure = 'NoSun'
    wind_exposure = 'NoWind'

    # If space below the floor is Ground than set up outside boundary
    # condition to the 'Ground'
    if space_below_floor == 'Ground':
        outside_boundary_condition = space_below_floor
        outside_boundary_condition_object = ''
    # If space below the floor is thermal zone than set up outside boundary
    # condition to the 'Surface', outside boundary condition object to the zone
    # below name appended with '_Ceiling' string
    else:
        outside_boundary_condition = 'Surface'
        outside_boundary_condition_object = str(space_below_floor) + '_Ceiling'
    # Append the floor horizontal coordinates with the height
    floor_coordinates_list = calgs._coordinates_add_height(
        floor_height, horizontal_surface_coordinates)
    # Convert floor coordinates list to format used in energyplus
    coordinates_list = _idf_floor_coordinates_list(floor_coordinates_list)
    # For each coordinates list in a list of coordinates lists creates building
    # surface detailed element which represents the floor
    for coordinates in coordinates_list:
        _building_surface_detailed(idf, surface_name, surface_type,
                                  ground_floor_const, zone_name,
                                  outside_boundary_condition,
                                  outside_boundary_condition_object,
                                  sun_exposure, wind_exposure, coordinates)
    return


def _roof_ceiling(
        idf: IDF,
        zone_name: str,
        space_above_floor: str,
        horizontal_surface_coordinates: list,
        ceiling_height: Union[float, int],
        roof_const: str
        ) -> None:
    '''
    Function which generates roof/ceiling energyplus object
    '''
    # If space above the ceiling is Outdoors than set up outside boundary
    # condition to the 'Outdoors'
    if space_above_floor == 'Outdoors':
        # Surface name made of the zone name appended with '_Roof' string
        surface_name = str(zone_name) + '_Roof'
        # Surface type; sun exposure; wind exposure
        surface_type = 'Roof'
        sun_exposure = 'SunExposed'
        wind_exposure = 'WindExposed'
        outside_boundary_condition = space_above_floor
        outside_boundary_condition_object = ''
    else:
        # Surface name made of the zone name appended with '_Ceiling' string
        surface_name = str(zone_name) + '_Ceiling'
        # Surface type; sun exposure; wind exposure
        surface_type = 'Ceiling'
        sun_exposure = 'NoSun'
        wind_exposure = 'NoWind'
        # Set up outside boundary condition to the 'Surface' and outside
        # boundary condition object to the zone above name appended with
        # '_Floor' string
        outside_boundary_condition = 'Surface'
        outside_boundary_condition_object = str(space_above_floor) + '_Floor'
    # Append the roof/ceiling horizontal coordinates with the height
    ceiling_coordinates_list = calgs._coordinates_add_height(
        ceiling_height, horizontal_surface_coordinates)
    # Convert roof/ceiling coordinates list to format used in energyplus
    coordinates_list = _idf_ceiling_coordinates_list(ceiling_coordinates_list)
    # For each coordinates list in a list of coordinates lists creates building
    # surface detailed element which represents the roof/ceiling
    for coordinates in coordinates_list:
       _building_surface_detailed(idf, surface_name, surface_type,
                                  roof_const, zone_name,
                                  outside_boundary_condition,
                                  outside_boundary_condition_object,
                                  sun_exposure, wind_exposure, coordinates)
    return



def _window(
        idf: IDF,
        surface_name: str,
        construction_name: str,
        building_surface_name: str,
        starting_x_coordinate: list,
        starting_z_coordinate: list,
        length: Union[float, int],
        height: Union[float, int]
        ) -> None:
    '''
    Function which creates Window energyplus object
    '''
    idf.newidfobject(
        'Window'.upper(),
        Name=surface_name,
        Construction_Name=construction_name,
        Building_Surface_Name=building_surface_name,
        Starting_X_Coordinate=starting_x_coordinate,
        Starting_Z_Coordinate=starting_z_coordinate,
        Length=length,
        Height=height)
    

def _overhang(
        idf: IDF,
        window_name: str,
        depth: Union[float, int]
        ) -> None:
    """Adds a shading overhang to window with the specified depth. 
    Used in the Simstock QGIS plugin."""
    if isinstance(depth, float) or isinstance(depth, int):
        if depth > 0:
            idf.newidfobject('SHADING:OVERHANG',
                            Name=str(window_name)+"_Overhang",
                            Window_or_Door_Name=window_name,
                            Height_above_Window_or_Door=0.0,
                            Tilt_Angle_from_WindowDoor=90.0,
                            Left_extension_from_WindowDoor_Width=0.0,
                            Right_extension_from_WindowDoor_Width=0.0,
                            Depth=depth)


def _external_walls(
        idf: IDF,
        zone_name: str,
        floor_number: int,
        vertical_surface_coordinates: list,
        ceiling_height: Union[float, int],
        floor_height: Union[float, int],
        zone_height: Union[float, int],
        min_avail_height: Union[float, int],
        min_window_width: Union[float, int],
        wall_const: str,
        glazing_const: str,
        glazing_ratio: Union[float, int],
        overhang_depth: Union[float, int]
        ) -> None:
    '''
    Function which generates external wall energyplus object and return exposed
    walls and glazings areas
    '''
    # surface type
    surface_type = 'Wall'
    outside_boundary_condition_object = ''
    sun_exposure = 'SunExposed'
    wind_exposure = 'WindExposed'
    outside_boundary_condition = 'Outdoors'
    # Append the vertical surface coordinates with the ceiling and floor height
    ceiling_coordinates = calgs._coordinates_add_height(ceiling_height,
                                                 vertical_surface_coordinates)
    floor_coordinates = calgs._coordinates_add_height(floor_height,
                                               vertical_surface_coordinates)
    # Loop through the list of ceiling coordinates lists
    for n, _ in enumerate(ceiling_coordinates):
        # Floor and ceiling coordinates lists
        ceil_coord = ceiling_coordinates[n]
        floor_coord = floor_coordinates[n]
        # Loop through ceiling coordinate list up to the next to the last item
        for i, _ in enumerate(ceil_coord[:-1]):
            # Calculate wall centre coordinate in 3D plane (used for naming)
            wcc = _wall_centre_coordinate(
                ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
            # Generate the surface name form zone name, '_Wall_' string and
            # centre coordinate
            surface_name =str(zone_name) + '_Wall_' + str(wcc)
            # Generate wall coordinates in format used by energyplus
            coordinates = _idf_wall_coordinates(i, ceil_coord, floor_coord)
            # Creates building surface detailed element which represent wall
            _building_surface_detailed(idf, surface_name, surface_type,
                                      wall_const, zone_name,
                                      outside_boundary_condition,
                                      outside_boundary_condition_object,
                                      sun_exposure, wind_exposure, coordinates)
            # Calculates wall width and height
            w, h = _wall_width_height(i, ceil_coord, floor_coord)
            # When wall width and height is above limitation (subtract by 1mm
            # due to floating point precision) add the window object as a
            # function of glazing ratio
            if (w >= min_window_width) and (
                    h >= (min_avail_height * zone_height / 100) - 0.001):
                # window length and height
                wl = w * math.sqrt(glazing_ratio / 100)
                wh = h * math.sqrt(glazing_ratio / 100)
                # Starting X and Z coordinates relative to the wall bottom
                # left corner
                x = (w - wl) / 2
                z = (h - wh) / 2
                # Window name made from the surface name appended with
                # the '_Window' string
                win_surface_name = str(surface_name) + '_Window'
                # Base surface name
                building_surface_name = surface_name
                # Coordinates converted into strings
                starting_x_coordinate = '%.2f' % x
                starting_z_coordinate = '%.2f' % z
                win_length = '%.2f' % wl
                win_height = '%.2f' % wh
                # Add the window energyplus object
                _window(idf, win_surface_name, glazing_const,
                       building_surface_name, starting_x_coordinate,
                       starting_z_coordinate, win_length, win_height)
                
                # Add overhang to each window of custom depth
                _overhang(idf, win_surface_name, overhang_depth)


def _partition_walls(
        idf: IDF,
        zone_name: str,
        adj_osgb: str,
        vertical_surface_coordinates: list,
        ceiling_height: Union[float, int],
        floor_height: Union[float, int],
        partition_const: str
        ) -> None:
    '''
    Function which creates partition walls
    '''
    # Surface type; no sun exposure; no wind exposure
    surface_type = 'Wall'
    sun_exposure = 'NoSun'
    wind_exposure = 'NoWind'
    opposite_zone = adj_osgb
    outside_boundary_condition = 'Adiabatic'
    obco = ''
    # Append the vertical surface coordinates with the ceiling and floor height
    ceiling_coordinates = calgs._coordinates_add_height(ceiling_height,
                                                 vertical_surface_coordinates)
    floor_coordinates = calgs._coordinates_add_height(floor_height,
                                               vertical_surface_coordinates)
    # Loop through the list of ceiling coordinates lists
    for n, item in enumerate(ceiling_coordinates):
        # Floor and ceiling coordinates lists
        ceil_coord = ceiling_coordinates[n]
        floor_coord = floor_coordinates[n]
        # Loop through ceiling coordinate list up to the next to the last item
        for i, p in enumerate(ceil_coord[:-1]):
            # Calculate wall centre coordinate in 3D plane (used for naming)
            wcc = _wall_centre_coordinate(
                ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
            # Generate the surface name form zone name, '_Part_' string,
            # opposite zone name and centre coordinate
            surface_name = str(zone_name) + '_Part_' + str(opposite_zone) + '_' + str(wcc)
            # Generate wall coordinates in format used by energyplus
            coordinates = _idf_wall_coordinates(i, ceil_coord, floor_coord)
            # Creates partition building surface detailed element
            _building_surface_detailed(idf, surface_name, surface_type,
                                      partition_const, zone_name,
                                      outside_boundary_condition, obco,
                                      sun_exposure, wind_exposure, coordinates)
            

def _shading_volumes(
        row: Series,
        df: DataFrame,
        idf: IDF,
        origin: list
        ) -> None:
    '''
    Function which generates idf geometry for surrounding Build Blocks. All
    elements are converted to shading objects
    '''
    # Polygon name and coordinates
    osgb, polygon = row.osgb, row.polygon
    # Polygon with removed collinear point to be used for ceiling/floor/roof
    hor_polygon = row.polygon_horizontal
    # Convert polygon coordinates to dictionary of outer and inner
    # (if any) coordinates
    hor_poly_coord_dict = palgs._polygon_coordinates_dictionary(hor_polygon)
    # List of adjacent polygons
    adj_osgb_list = row.touching
    # Load the polygon which defines only external surfaces
    ext_surf_polygon = row.polygon_exposed_wall
    # List of external surface only coordinates (ext_surf_polygon +
    # inner rings)
    ext_surf_coord = palgs._surface_coordinates(ext_surf_polygon, origin)
    # # List of horizontal surfaces coordinates (roof/floor/ceiling)
    horiz_surf_coord = calgs._horizontal_surface_coordinates(
        hor_poly_coord_dict, origin)
    # Zone bottom/top vertical vertex
    zone_floor_h = 0
    zone_ceiling_h = row.height
    # Include adiabatic roof
    _adiabatic_roof(idf, osgb, horiz_surf_coord, zone_ceiling_h)
    adiabatic_wall_name = 'AdiabaticWall'
    # Create external walls
    adiabatic_external_walls(idf, osgb, ext_surf_coord, zone_ceiling_h,
                             zone_floor_h, adiabatic_wall_name,
                             adj_osgb_list, df, polygon, origin)
    return


def adiabatic_external_walls(
        idf: IDF,
        polygon_name: str,
        perimeter_surface_coordinates: list,
        ceiling_height: Union[float, int],
        floor_height: Union[float, int],
        wall_name: str,
        adjacent_polygons_list: list,
        df: DataFrame,
        polygon_shapely: Polygon,
        origin: list
        ) -> None:
    '''
    Function which generates energyplus object for adiabatic external walls. It
    is composed of two parts (1) external walls which are not parts of adjacent
    surfaces and (2) external walls which are parts of adjacent surfaces. the
    second case will have other elements as well which are defined somewhere
    else within the main function
    '''

    # Create adiabatic external walls for non-adjacent surfaces
    adiabatic_walls(idf, polygon_name, perimeter_surface_coordinates,
                    ceiling_height, floor_height, wall_name)
    # Check if there are adjacent objects (can be more than one)
    if adjacent_polygons_list:
        # Loop through the list of adjacent objects
        for polygon in adjacent_polygons_list:
            # Slice the built block DataFrame to include only records for
            # adjacent object
            adjacent_polygon_df = df.loc[df['osgb'] == polygon]
            # Extract polygon from the adjacent objects DataFrame
            adjacent_polygon = adjacent_polygon_df['polygon'].iloc[0]
            # Convert polygon to shapley object
            adjacent_polygon = adjacent_polygon

            # Find the intersection between two polygons (it will be LineString
            # or MultiLineString) and position coordinates relative to origin
            part_wall_polygon = polygon_shapely.intersection(adjacent_polygon)
            ajd_wall_parti_surf_coord = palgs._surface_coordinates(part_wall_polygon,
                                                            origin)
            # Extract the height of an adjacent object
            adjacent_height = adjacent_polygon_df['height'].iloc[0]
            # Check if the ceiling height is above the height of the adjacent
            # object. If not than there is no adiabatic external wall above the
            # adjacent object. If yes, than check the relation of floor height
            # to adjacent object height. If it is above than the whole wall is
            # adiabatic external; if not than only part of the wall is external
            if ceiling_height > adjacent_height + 1e-6:
                ceil_h = ceiling_height
                if floor_height > adjacent_height - 1e-6:
                    floor_h = floor_height
                else:
                    floor_h = adjacent_height
                # Creates adiabatic external walls for adjacent surfaces
                adiabatic_walls(idf, polygon_name, ajd_wall_parti_surf_coord,
                                ceil_h, floor_h, wall_name)
    return


def adiabatic_external_walls(
        idf: IDF,
        polygon_name: str,
        perimeter_surface_coordinates: list,
        ceiling_height: Union[float, int],
        floor_height: Union[float, int],
        wall_name: str,
        adjacent_polygons_list: list,
        df: DataFrame,
        polygon_shapely: Polygon,
        origin: list
        ) -> None:
    '''
    Function which generates energyplus object for adiabatic external walls. It
    is composed of two parts (1) external walls which are not parts of adjacent
    surfaces and (2) external walls which are parts of adjacent surfaces. the
    second case will have other elements as well which are defined somewhere
    else within the main function
    '''

    # Create adiabatic external walls for non-adjacent surfaces
    adiabatic_walls(idf, polygon_name, perimeter_surface_coordinates,
                    ceiling_height, floor_height, wall_name)
    # Check if there are adjacent objects (can be more than one)
    if adjacent_polygons_list:
        # Loop through the list of adjacent objects
        for polygon in adjacent_polygons_list:
            # Slice the built block DataFrame to include only records for
            # adjacent object
            adjacent_polygon_df = df.loc[df['osgb'] == polygon]
            # Extract polygon from the adjacent objects DataFrame
            adjacent_polygon = adjacent_polygon_df['polygon'].iloc[0]
            # Convert polygon to shapley object
            adjacent_polygon = adjacent_polygon

            # Find the intersection between two polygons (it will be LineString
            # or MultiLineString) and position coordinates relative to origin
            part_wall_polygon = polygon_shapely.intersection(adjacent_polygon)
            ajd_wall_parti_surf_coord = palgs._surface_coordinates(part_wall_polygon,
                                                            origin)
            # Extract the height of an adjacent object
            adjacent_height = adjacent_polygon_df['height'].iloc[0]
            # Check if the ceiling height is above the height of the adjacent
            # object. If not than there is no adiabatic external wall above the
            # adjacent object. If yes, than check the relation of floor height
            # to adjacent object height. If it is above than the whole wall is
            # adiabatic external; if not than only part of the wall is external
            if ceiling_height > adjacent_height:
                ceil_h = ceiling_height
                if floor_height > adjacent_height:
                    floor_h = floor_height
                else:
                    floor_h = adjacent_height
                # Creates adiabatic external walls for adjacent surfaces
                adiabatic_walls(idf, polygon_name, ajd_wall_parti_surf_coord,
                                ceil_h, floor_h, wall_name)
    return
