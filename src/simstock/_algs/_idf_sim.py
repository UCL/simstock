import os
import math
import random
import platform
import pandas as pd
from ast import literal_eval
from shapely.wkt import loads
from eppy.modeleditor import IDF, IDDAlreadySetError
from time import time, localtime, strftime
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union
import json


# Do not place window if the wall width is less than this number
min_avail_width_for_window = 1
# Do not place window if partially exposed external wall is less than this number % of zone height
min_avail_height = 80


def _sim_main(idf, df, buffer_radius = 50):
    
    # Function which creates the idf(s)
    def createidfs(bi_df, df):
    
        # Move all objects towards origins
        origin = bi_df['polygon'].iloc[0]
        origin = list(origin.exterior.coords[0])
        origin.append(0)

        # Shading volumes converted to shading objects
        shading_df = bi_df.loc[bi_df['shading'] == True]
        shading_df.apply(shading_volumes, args=(df, idf, origin,), axis=1)

        # Polygons with zones converted to thermal zones based on floor number
        zones_df = bi_df.loc[bi_df['shading'] == False]
        zone_use_dict = {} 
        zones_df.apply(thermal_zones, args=(bi_df, idf, origin, zone_use_dict,), axis=1)

        # Extract names of thermal zones:
        zones = idf.idfobjects['ZONE']
        zone_names = list()
        for zone in zones:
            zone_names.append(zone.Name)
        

        # Plugin feature: mixed-use
        mixed_use(idf, zone_use_dict)

        # Ideal loads system
        for zone in zone_names:
            system_name = '{}_HVAC'.format(zone)
            eq_name = '{}_Eq'.format(zone)
            supp_air_node = '{}_supply'.format(zone)
            air_node = '{}_air_node'.format(zone)
            ret_air_node = '{}_return'.format(zone)

            idf.newidfobject('ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Name=system_name,
                                Zone_Supply_Air_Node_Name=supp_air_node,
                                Dehumidification_Control_Type='None')

            idf.newidfobject('ZONEHVAC:EQUIPMENTLIST',
                                Name=eq_name,
                                Zone_Equipment_1_Object_Type='ZONEHVAC:IDEALLOADSAIRSYSTEM',
                                Zone_Equipment_1_Name=system_name,
                                Zone_Equipment_1_Cooling_Sequence=1,
                                Zone_Equipment_1_Heating_or_NoLoad_Sequence=1)

            idf.newidfobject('ZONEHVAC:EQUIPMENTCONNECTIONS',
                                Zone_Name=zone,
                                Zone_Conditioning_Equipment_List_Name=eq_name,
                                Zone_Air_Inlet_Node_or_NodeList_Name=supp_air_node,
                                Zone_Air_Node_Name=air_node,
                                Zone_Return_Air_Node_or_NodeList_Name=ret_air_node)
       

            def get_osgb_value(val_name, zones_df, zone):
                """Gets the value of a specified attribute for the zone"""
                osgb_from_zone = "_".join(zone.split("_")[:-2])
                return zones_df[zones_df["osgb"]==osgb_from_zone][val_name].to_numpy()[0]

            # Get specified inputs for zone
            ventilation_rate = get_osgb_value("ventilation_rate", zones_df, zone)
            infiltration_rate = get_osgb_value("infiltration_rate", zones_df, zone)

            # Get the rest of the default obj values from dict
            zone_ventilation_dict = ventilation_dict
            zone_infiltration_dict = infiltration_dict

            # Set the name, zone name and ventilation rate
            zone_ventilation_dict["Name"] = zone + "_ventilation"
            zone_ventilation_dict["Zone_or_ZoneList_Name"] = zone
            zone_ventilation_dict["Air_Changes_per_Hour"] = ventilation_rate
            zone_ventilation_dict["Schedule_Name"] = zone_use_dict[zone] + "_Occ"

            # Same for infiltration
            zone_infiltration_dict["Name"] = zone + "_infiltration"
            zone_infiltration_dict["Zone_or_ZoneList_Name"] = zone
            zone_infiltration_dict["Air_Changes_per_Hour"] = infiltration_rate

            # Add the ventilation idf object
            idf.newidfobject(**zone_ventilation_dict)
            idf.newidfobject(**zone_infiltration_dict)

    bi_list = df['bi'].unique().tolist()
        
    for bi in bi_list:
        # Change the name field of the building object
        building_object = idf.idfobjects['BUILDING'][0]
        building_object.Name = bi
        
        # Get the data for the BI
        bi_df = df[df['bi'] == bi]

        # Get the data for other BIs to use as shading
        rest  = df[df['bi'] != bi]

        # Buffer the BI geometry to specified radius
        bi_geom = list(bi_df.polygon)
        buffer = unary_union(bi_geom).convex_hull.buffer(buffer_radius)

        # Find polygons which are within this buffer and create mask
        lst = []
        index = []
        for row in rest.itertuples():
            poly = row.polygon
            # The following is True if poly intersects buffer and False if not
            lst.append(poly.intersects(buffer))
            index.append(row.Index)
        mask = pd.Series(lst, index=index)

        # Get data for the polygons within the buffer
        within_buffer = rest.loc[mask].copy()

        # Set them to be shading
        within_buffer["shading"] = True

        # Include them in the idf for the BI
        bi_df = pd.concat([bi_df, within_buffer])
        
        # Only create idf if the BI is not entirely composed of shading blocks
        shading_vals = bi_df['shading'].to_numpy()
        # print(shading_vals)
        # if not shading_vals.all():
        createidfs(bi_df, df)
        # else:
        #     continue


def mixed_use(idf, zone_use_dict):

    # Check for missing values
    for key, value in zone_use_dict.items():
        if not isinstance(value, str) and math.isnan(value):
            raise ValueError("{} has no value for 'use'.".format(key))

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


def shading_volumes(row, df, idf, origin):
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
    hor_poly_coord_dict = polygon_coordinates_dictionary(hor_polygon)
    # List of adjacent polygons
    adj_osgb_list = literal_eval(str(row.touching))
    # Load the polygon which defines only external surfaces
    ext_surf_polygon = row.polygon_exposed_wall
    # List of external surface only coordinates (ext_surf_polygon +
    # inner rings)
    ext_surf_coord = surface_coordinates(ext_surf_polygon, origin)
    # # List of horizontal surfaces coordinates (roof/floor/ceiling)
    horiz_surf_coord = horizontal_surface_coordinates(
        hor_poly_coord_dict, origin)
    # Zone bottom/top vertical vertex
    zone_floor_h = 0
    zone_ceiling_h = row.height
    # Include adiabatic roof
    adiabatic_roof(idf, osgb, horiz_surf_coord, zone_ceiling_h)
    adiabatic_wall_name = 'AdiabaticWall'
    # Create external walls
    adiabatic_external_walls(idf, osgb, ext_surf_coord, zone_ceiling_h,
                             zone_floor_h, adiabatic_wall_name,
                             adj_osgb_list, df, polygon, origin)
    return




def polygon_coordinates_dictionary(polygon):
    '''
    Function which stores data form POLYGON((,,,),(,,,),(,,,)) in dictionary.
    Data are in the shape Polygon(exterior[, interiors=None])
   '''
    # Load the polygon data by using shapely
    polygon = polygon
    # Empty dictionary
    polygon_coordinates_dict = dict()
    # Outer ring (exterior) coordinates
    polygon_coordinates_dict['outer_ring'] = [polygon.exterior.coords]
    # If there are inner rings (holes in polygon) than loop through then and
    # store them in the list
    if polygon.interiors:
        polygon_coordinates_dict['inner_rings'] = list()  # empty list
        for item in polygon.interiors:
            polygon_coordinates_dict['inner_rings'].append(item.coords)
    # Return the dictionary
    return polygon_coordinates_dict



def surface_coordinates(polygon, origin):
    '''
    Function which creates a list of coordinates lists depending on the polygon
    type.
   '''
    # Empty coordinates list
    coordinates_list = list()
    # If polygon geometry type is 'MultiLineString' than loop through it and
    # extract coordinates for each 'LineString'. If polygon type is
    # GeometryCollection than it is composed of 'Point' and 'LineString' (it
    # can also be 'MultiLineString' but not as part of this module processing).
    # Exclude 'Point' coordinates. When polygon geometry type is 'LinearRing'
    # or 'LineString' than take their coordinates and append the coordinates
    # list
    if polygon.geom_type in ['MultiLineString', 'GeometryCollection']:
        for item in polygon.geoms:
            if not item.geom_type == 'Point':
                coordinates_list.append(item.coords)
    elif polygon.geom_type == 'LineString':
        coordinates_list.append(polygon.coords)
    # Position coordinates relative to origin
    coordinates = coordinates_move_origin(coordinates_list, origin)
    # Return coordinates
    return coordinates


def coordinates_move_origin(coordinates_list, origin):
    '''
    Function which positions a coordinates relative to the origin
   '''
    coordinates_list_moved_origin = list()
    # Loop through the list of coordinates
    for coordinates in coordinates_list:
        # Empty list which to hold coordinates
        coordinates_moved_origin = list()
        # Loop through coordinates
        for ordered_pair in coordinates:
            # Position ordered pairs relative to origin
            ordered_pair_moved_origin = [i - j for i, j in zip(ordered_pair,
                                                               origin)]
            # Round ordered pairs to 2 decimal spaces
            ordered_pair_moved_origin = [
                round(coord, 2) for coord in ordered_pair_moved_origin]
            coordinates_moved_origin.append(ordered_pair_moved_origin)
        coordinates_list_moved_origin.append(coordinates_moved_origin)
    # Return list of coordinates converted to text strings
    return coordinates_list_moved_origin


def horizontal_surface_coordinates(coordinates_dictionary, origin):
    '''
    Function which adjust coordinates to be suitable for creating E+ horizontal
    surfaces. If polygon has no holes than it just converts polygon coordinates
    to a list of text strings positioned relative to the origin. Coordinates
    for polygon with holes are slightly more complex since hole areas has to be
    subtracted from polygon area by following counter-clock rule.
   '''
    if len(coordinates_dictionary) == 1:
        coordinates_list = coordinates_dictionary['outer_ring']
    else:
        coordinates_list = polygon_with_holes(coordinates_dictionary)
    # Position coordinates relative to the origin
    coordinates = coordinates_move_origin(coordinates_list, origin)
    # Return coordinates converted to text
    return coordinates




def polygon_with_holes(coordinates_dictionary):
    '''
    Function which merges outer and inned rings in suitable format (coordinate
    pairs order) so EnergyPlus can recognise it as a surface with holes. The
    logic is to find the minimum distance between outer ring coordinates and
    inner ring coordinates which are connected with the LineString. There might
    be more than oneLineString connecting outer and inner ring if there is more
    than one hole. The LineString is used to split outer and inner LineStrings
    in MultiLineStrings (in case that the closest coordinate is not the first
    coordinate of outer/inner LineString). Outer and inner LineStrings are
    reorganised in suitable order. For example, first LineString from outer
    MultiLineString is extended with the LineString connecting outer and inner
    rings than inner ring LineString are added in CCW order followed by the
    same LineString connecting inner and outer rings. The last outer LineString
    is added to close the ring
    '''

    def polygon_with_holes_coordinates(coordinates, outer_ring_linestring,
                                       interceptors_op_dict):
        '''
        Internal function which links inner ring coordinates to outer ring
        connection point
        '''
        # Get the first outer ring LineStings's ordered pair
        first_op = outer_ring_linestring.coords[0]
        # Check whether the first outer ring LineStings's ordered pair is the
        # point from which the inner ring is connected to the outer ring. It
        # won't be only for the first LineString of the outer ring
        # MultiLineString when the hole is not connected to the outer ring in
        # the first ordered pair
        if first_op in interceptors_op_dict:
            # Append the list with the first outer ring LineStings's ordered
            # pair
            coordinates.append(first_op)
            # Extract from the dictionary the inner ring LineString /
            # MultiLineString which is connected to the outer ring in the
            # first_op. It can be more than one inner ring connecting to this
            # ordered pair
            holes = interceptors_op_dict[first_op]
            # Loop through the list of inner rings
            for hole in holes:
                # When the inner ring is LineString it means that the inner
                # ring is connected to the outer ring via the first ordered
                # pair of inner ring. In that case append coordinates of the
                # inner ring to the first ordered pair of outer ring
                if hole.geom_type == 'LineString':
                    for coord in hole.coords:
                        coordinates.append(coord)
                # In case of MultiLineString than first append the second
                # LineString of inner ring followed by the first LineString
                # (excluding the first ordered pair of the first LineString
                # which is the same as the last ordered pair of the second
                # LineString)
                if hole.geom_type == 'MultiLineString':
                    for coord in hole[1].coords:
                        coordinates.append(coord)
                    for coord in hole[0].coords[1:]:
                        coordinates.append(coord)
                # Close the coordinates by adding the first outer ring
                # LineStings's ordered pair
                coordinates.append(first_op)
            # Add the rest of outer ring LineString coordinates to the
            # coordinate list
            for coord in outer_ring_linestring.coords[1:-1]:
                coordinates.append(coord)
        # If the first outer ring LineStings's ordered pair is not linked to
        # the inner ring that append coordinates with outer ring LineString
        # (excluding the last ordered pair which is actually the link to the
        # inner ring but it is covered in the next outer ring LineString)
        else:
            for coord in outer_ring_linestring.coords[:-1]:
                coordinates.append(coord)
        # Return coordinates of outer ring LineString with inner ring
        return coordinates

    def dist_two_points(p1, p2):
        '''
        Internal function which calculates the Euclidean distance between two
        points
        '''
        distance = math.sqrt(math.pow(
            (p1[0] - p2[0]), 2) + math.pow((p1[1] - p2[1]), 2))
        # Return distance between two points
        return distance

    def inner_string(inner_ring_coordinates, irop):
        inner_coordinates = list(inner_ring_coordinates)

        for i, coord in enumerate(inner_coordinates):
            if coord == irop:
                split_position = i
                break
        if split_position == 0:
            inner_linestring = LineString(inner_coordinates)
        else:
            first = inner_coordinates[:(split_position + 1)]
            last = inner_coordinates[split_position:]
            inner_linestring = MultiLineString([first, last])
        return inner_linestring

    # Coordinates of the outer ring extracted from the coordinates dictionary
    outer_ring_coordinates = coordinates_dictionary['outer_ring']
    # Interceptors ordered pairs dictionary
    interceptors_op_dict = {}
    # List of LineStings connecting outer ring and inner ring coordinates
    oi_min_linestring_list = []
    # Loop through the list of inner rings (holes)
    for inner_ring_coordinates in coordinates_dictionary['inner_rings']:
        # orop / irop: outer / inner ring ordered pair
        # Loop through the coordinates of outer ring
        for i, orop in enumerate(outer_ring_coordinates[0][:-1]):
            # Loop through coordinates of inner ring
            for j, irop in enumerate(inner_ring_coordinates[:-1]):
                # Set an initial minimum distance between outer and inner rings
                # for first ordered pairs of outer and inner rings
                if i == 0 and j == 0:
                    # outer ring - inner ring coordinates minimum distance
                    oi_min_distance = dist_two_points(orop, irop)
                    if oi_min_distance > 0.015:
                        # outer ring - inner ring minimum distance LineString
                        oi_min_linestring = LineString([orop, irop])
                        # Get the difference between inner ring and
                        # intersection point between inner ring and LineSting
                        # connecting inner ring and outer ring. If intersection
                        # point is not the first coordinate of inner ring than
                        # inner ring will be broken to a MultiLineString
                        inner_linestring = inner_string(inner_ring_coordinates,
                                                        irop)

                    else:
                        oi_min_distance = 1e9
                # Update the minimum distance between outer and inner rings,
                # LineString connecting these outer and inner ring along the
                # minimum distance and inner ring LineSting (MultiLineSting) by
                # checking the distance between other inner and outer
                # coordinates
                else:
                    distance = dist_two_points(orop, irop)
                    if (distance < oi_min_distance) and (distance > 0.015):
                        oi_min_distance = distance
                        oi_min_linestring = LineString([orop, irop])
                        inner_linestring = inner_string(inner_ring_coordinates,
                                                        irop)

        # Append the dictionary with the key: ordered pair at outer ring /
        # value: list of inner rings LineSting or MultiLineString
        if oi_min_linestring.coords[0] in interceptors_op_dict:
            interceptors_op_dict[oi_min_linestring.coords[0]].append(
                inner_linestring)
        else:
            interceptors_op_dict[
                oi_min_linestring.coords[0]] = [inner_linestring]
        # Populate the list of LineStrings connecting outer and inner rings
        oi_min_linestring_list.append(oi_min_linestring)
    # Intersect outer ring with LineStrings connecting outer ring with inner
    # rings in order to identify points where inner holes are connected to
    # outer ring
    outer_ring = MultiLineString(coordinates_dictionary['outer_ring'])
    for oi_min_linestring in oi_min_linestring_list:
        outer_ring = outer_ring.difference(oi_min_linestring)
    # Empty list to hold arranged coordinates
    coordinates = []
    # When outer ring is LineString it means that there is only one hole and it
    # is connected to outer ring from the first ordered pair of outer ring
    # coordinate list
    if outer_ring.geom_type == 'LineString':
        # First and last coordinate of polygon with holes coordinates is equal
        # to the first ordered pair of outer ring. It is appended to the end of
        # the coordinates list
        start_end_op = outer_ring.coords[0]
        # Get the polygon with holes coordinates
        coordinates = polygon_with_holes_coordinates(coordinates, outer_ring,
                                                     interceptors_op_dict)
    # When outer ring is MultiLineString it means that it can be (1) only one
    # hole which is connected to outer ring at other than first ordered pair of
    # outer ring coordinate list, (2) more than one hole: (a) where one hole
    # can be connected to outer ring at the first ordered pair of outer ring
    # coordinate list or (b) no holes are connected to outer ring at the first
    # ordered pair of outer ring coordinate list
    elif outer_ring.geom_type == 'MultiLineString':
        # Loop through LineString in a MultiLineString
        for i, linestring in enumerate(outer_ring):
            # First and last ordered pair of polygon with holes coordinates is
            # the first coordinate of the first LineString
            if i == 0:
                start_end_op = linestring.coords[0]
            # Get the polygon with holes coordinates
            coordinates = polygon_with_holes_coordinates(coordinates,
                                                         linestring,
                                                         interceptors_op_dict)
    # Append the polygon with holes coordinates with start-end ordered pair
    coordinates.append(start_end_op)
    # Return the list of polygon with holes coordinates
    return [coordinates]

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def adiabatic_roof(idf, polygon_name, horizontal_surface_coordinates,
                   ceiling_height):
    ceiling_coordinates_list = coordinates_add_height(
        ceiling_height, horizontal_surface_coordinates)
    coordinates_list = idf_ceiling_coordinates_list(ceiling_coordinates_list)
    randstr = str(random.randint(1, 1000))
    surface_name = polygon_name + '_AdiabaticRoof' + randstr
    for coordinates in coordinates_list:
        shading_building_detailed(idf, surface_name, coordinates)
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def coordinates_add_height(height, coordinates_list):
    '''
    Function which adds Z coordinate to coordinate pairs
    '''
    coordinates_with_height = []
    # Loop through the coordinates in the list of coordinates
    for coordinates in coordinates_list:
        # Empty list for ordered pairs with height
        ordered_pair_with_height = []
        # Loop through coordinates and append each ordered pair with height
        # rounded to 2 decimal spaces
        for op in coordinates:
            op_with_height = op + [round(height, 2)]
            ordered_pair_with_height.append(op_with_height)
        # Append coordinates with height list with ordered pair with height lst
        coordinates_with_height.append(ordered_pair_with_height)
    # Return ordered pair with height list
    return coordinates_with_height

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def idf_ceiling_coordinates_list(ceiling_coordinates_list):
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

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def shading_building_detailed(idf, surface_name, coordinates):
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
        exec('objects.Vertex_{}_Xcoordinate = ordered_pair[0]'.format(i + 1))
        exec('objects.Vertex_{}_Ycoordinate = ordered_pair[1]'.format(i + 1))
        exec('objects.Vertex_{}_Zcoordinate = ordered_pair[2]'.format(i + 1))
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def adiabatic_external_walls(idf, polygon_name, perimeter_surface_coordinates,
                             ceiling_height, floor_height, wall_name,
                             adjacent_polygons_list, df,
                             polygon_shapely, origin):
    '''
    Function which generates energyplus object for adiabatic external walls. It
    is composed of two parts (1) external walls which are not parts of adjacent
    surfaces and (2) external walls which are parts of adjacent surfaces. the
    second case will have other elements as well which are defined somewhere
    else within the main function
    '''

    def adiabatic_walls(idf, polygon_name, perimeter_surface_coordinates,
                        ceiling_height, floor_height, wall_name):
        '''
        Internal function which creates energyplus object for adiabatic
        external walls based on horizontal coordinates. Firstly, it appends
        horizontal coordinates with floor and ceiling height and than loop
        through coordinates in order to pick up adjacent coordinate pairs. Wall
        is formed of two top and two bottom coordinates while in the horizontal
        coordinate list can be a lot of adjacent coordinates pairs
        '''
        # Append the perimeter coordinates with the ceiling and floor heights
        ceiling_coordinates = coordinates_add_height(
            ceiling_height, perimeter_surface_coordinates)
        floor_coordinates = coordinates_add_height(
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
                wcc = wall_centre_coordinate(
                    ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
                # Generate the name form polygon name, wall name and centre
                # coordinate
                surface_name = polygon_name + '_' + wall_name + '_' + wcc
                # Generate wall coordinates in format used by energyplus
                coordinates = idf_wall_coordinates(i, ceil_coord, floor_coord)
                # Creates shading elements which represent the adiabatic
                # external wall
                shading_building_detailed(idf, surface_name, coordinates)
        return

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
            ajd_wall_parti_surf_coord = surface_coordinates(part_wall_polygon,
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

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def wall_centre_coordinate(ceil_1, ceil_0, floor_0):
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

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def idf_wall_coordinates(i, ceiling_coordinates, floor_coordinates):
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

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def thermal_zones(row, df, idf, origin, zone_use_dict):
    polygon = loads(row.polygon)
    # Polygon with removed collinear point to be used for ceiling/floor/roof
    hor_polygon = row.polygon_horizontal
    # Convert polygon coordinates to dictionary of outer and inner (if any)
    # coordinates
    hor_poly_coord_dict = polygon_coordinates_dictionary(hor_polygon)
    # List of horizontal surfaces coordinates (roof/floor/ceiling)
    horiz_surf_coord = horizontal_surface_coordinates(
        hor_poly_coord_dict, origin)
    # Load the polygon which defines only external surfaces
    ext_surf_polygon = loads(row.polygon_exposed_wall)
    # List of external surface only coordinates (ext_surf_polygon + in. rings)
    ext_surf_coord = surface_coordinates(ext_surf_polygon, origin)
    # List of adjacent polygons
    adj_osgb_list = literal_eval(row.touching)

    height = row.height
    glazing_ratio = row.wwr
    floors = range(int(row.nofloors))

    construction = row.construction
    glazing_const = '{}_glazing'.format(construction)

    ########### Added features for Simstock QGIS plugin ########################
    overhang_depth = row.overhang_depth
    #for i in floors:
    #    print(row["FLOOR_{}: use".format(i)])

    # Select constructions
    #glazing_const = "glazing"
    def set_construction(construction, element):
        # TODO: generalise this
        """
        Returns the relevant name of the building surface depending on the 
        construction name.
        """
        if element == "ground_floor":
            return "{}_solid_ground_floor".format(construction)
        if element == "wall":
            return "{}_wall".format(construction)
        if element == "roof":
            return "{}_flat_roof".format(construction)
        if element == "ceiling":
            # Use the following to raise an error if a certain construction cannot have more than one floor
            #if construction.lower() == "const1":
            #    raise RuntimeError("Quincha constructions cannot have multiple floors. Check polygon '%s'" % row.osgb)
            return "ceiling"#.format(construction)
        if element == "ceiling_inverse":
            return "ceiling_inverse"#.format(construction)

    ############################################################################

    if len(floors) == 1:
        floor_no = int(1)
        zone_name = '{}_floor_{}'.format(row.osgb, floor_no)
        try:
            zone_use_dict[zone_name] = row["FLOOR_1: use"]
        except KeyError:
            zone_use_dict[zone_name] = "Dwell"
        zone_floor_h = 0
        space_below_floor = 'Ground'
        zone_ceiling_h = height
        space_above_floor = 'Outdoors'

        idf.newidfobject('ZONE', Name=zone_name)

        floor_const = set_construction(construction, "ground_floor")
        floor(idf, zone_name, space_below_floor, horiz_surf_coord,
              zone_floor_h, floor_const)

        roof_const = set_construction(construction, "roof")
        roof_ceiling(idf, zone_name, space_above_floor,
                     horiz_surf_coord, zone_ceiling_h, roof_const)

        zone_height = zone_ceiling_h - zone_floor_h
        wall_const = set_construction(construction, "wall")
        external_walls(idf, zone_name, floor_no, ext_surf_coord,
                       zone_ceiling_h, zone_floor_h, zone_height,
                       min_avail_height, min_avail_width_for_window,
                       wall_const, glazing_const, glazing_ratio, overhang_depth)

        # Partition walls where adjacent polygons exist
        if adj_osgb_list:
            # Surface type; no sun exposure; no wind exposure
            partition_const = 'partition'
            # Loop through the list of adjacent objects
            for adj_osgb in adj_osgb_list:
                opposite_zone = adj_osgb
                # Extract polygon from the adjacent objects DataFrame
                adj_polygon = loads(df.loc[df['osgb'] == adj_osgb,
                                           'polygon'].values[0])
                adj_height = df.loc[df['osgb'] == adj_osgb,
                                    'height'].values[0]
                # Find the intersection between two polygons (it will be
                # LineString or MultiLineString) and position coordinates
                # relative to origin
                part_wall_polygon = polygon.intersection(adj_polygon)
                adj_wall_parti_surf_coord = surface_coordinates(
                    part_wall_polygon, origin)
                if zone_ceiling_h < adj_height + 1e-6:
                    partition_walls(idf, zone_name, opposite_zone,
                                    adj_wall_parti_surf_coord,
                                    zone_ceiling_h, zone_floor_h,
                                    partition_const)
                else:
                    if zone_floor_h > adj_height - 1e-6:
                        external_walls(idf, zone_name, floor_no,
                                       adj_wall_parti_surf_coord,
                                       zone_ceiling_h, zone_floor_h,
                                       zone_height, min_avail_height,
                                       min_avail_width_for_window,
                                       wall_const, glazing_const,
                                       glazing_ratio, overhang_depth)
                    else:
                        external_walls(idf, zone_name, floor_no,
                                       adj_wall_parti_surf_coord,
                                       zone_ceiling_h, adj_height,
                                       zone_height, min_avail_height,
                                       min_avail_width_for_window,
                                       wall_const, glazing_const,
                                       glazing_ratio, overhang_depth)
                        partition_walls(idf, zone_name, opposite_zone,
                                        adj_wall_parti_surf_coord,
                                        adj_height, zone_floor_h,
                                        partition_const)

    else:
        f2f = round(height / row.nofloors, 1)
        for item in floors:
            floor_no = item + 1
            if item == 0:
                zone_name = '{}_floor_{}'.format(row.osgb, floor_no)
                try:
                    zone_use_dict[zone_name] = row["FLOOR_{}: use".format(floor_no)]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = 'Ground'
                zone_ceiling_h = floor_no * f2f
                space_above_floor = '{}_floor_{}'.format(
                    row.osgb, (floor_no + 1))

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = set_construction(construction, "ground_floor")
                floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = set_construction(construction, "ceiling")
                roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h, roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = set_construction(construction, "wall")
                external_walls(
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
                        adj_polygon = loads(df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0])
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)

            elif item == row.nofloors - 1:
                zone_name = '{}_floor_{}'.format(row.osgb, floor_no)
                try:
                    zone_use_dict[zone_name] = row["FLOOR_{}: use".format(floor_no)]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = '{}_floor_{}'.format(
                    row.osgb, (floor_no - 1))
                zone_ceiling_h = height
                space_above_floor = 'Outdoors'

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = set_construction(construction, "ceiling_inverse")
                floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = set_construction(construction, "roof")
                roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h, roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = set_construction(construction, "wall")
                external_walls(
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
                        adj_polygon = loads(df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0])
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)

            else:
                zone_name = '{}_floor_{}'.format(row.osgb, floor_no)
                try:
                    zone_use_dict[zone_name] = row["FLOOR_{}: use".format(floor_no)]
                except KeyError:
                    zone_use_dict[zone_name] = "Dwell"
                zone_floor_h = item * f2f
                space_below_floor = '{}_floor_{}'.format(
                    row.osgb, (floor_no - 1))
                zone_ceiling_h = floor_no * f2f
                space_above_floor = '{}_floor_{}'.format(
                    row.osgb, (floor_no + 1))

                idf.newidfobject('ZONE', Name=zone_name)

                floor_const = set_construction(construction, "ceiling_inverse")
                floor(idf, zone_name, space_below_floor,
                      horiz_surf_coord, zone_floor_h, floor_const)
                roof_const = set_construction(construction, "ceiling")
                roof_ceiling(idf, zone_name, space_above_floor,
                             horiz_surf_coord, zone_ceiling_h,
                             roof_const)

                zone_height = zone_ceiling_h - zone_floor_h
                wall_const = set_construction(construction, "wall")
                external_walls(
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
                        adj_polygon = loads(df.loc[df['osgb'] == adj_osgb,
                                                   'polygon'].values[0])
                        adj_height = df.loc[df['osgb'] == adj_osgb,
                                            'height'].values[0]
                        # Find the intersection between two polygons (it will
                        # be LineString or MultiLineString) and position
                        # coordinates relative to origin
                        part_wall_polygon = polygon.intersection(adj_polygon)
                        adj_wall_parti_surf_coord = surface_coordinates(
                            part_wall_polygon, origin)
                        if zone_ceiling_h < adj_height + 1e-6:
                            partition_walls(idf, zone_name, opposite_zone,
                                            adj_wall_parti_surf_coord,
                                            zone_ceiling_h, zone_floor_h,
                                            partition_const)
                        else:
                            if zone_floor_h > adj_height - 1e-6:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, zone_floor_h,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                            else:
                                external_walls(idf, zone_name, floor_no,
                                               adj_wall_parti_surf_coord,
                                               zone_ceiling_h, adj_height,
                                               zone_height, min_avail_height,
                                               min_avail_width_for_window,
                                               wall_const, glazing_const,
                                               glazing_ratio, overhang_depth)
                                partition_walls(idf, zone_name, opposite_zone,
                                                adj_wall_parti_surf_coord,
                                                adj_height, zone_floor_h,
                                                partition_const)

    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def floor(idf, zone_name, space_below_floor, horizontal_surface_coordinates,
          floor_height, ground_floor_const):
    '''
    Function which generates floor energyplus object
    '''

    def idf_floor_coordinates_list(floor_coordinates_list):
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
    floor_coordinates_list = coordinates_add_height(
        floor_height, horizontal_surface_coordinates)
    # Convert floor coordinates list to format used in energyplus
    coordinates_list = idf_floor_coordinates_list(floor_coordinates_list)
    # For each coordinates list in a list of coordinates lists creates building
    # surface detailed element which represents the floor
    for coordinates in coordinates_list:
        building_surface_detailed(idf, surface_name, surface_type,
                                  ground_floor_const, zone_name,
                                  outside_boundary_condition,
                                  outside_boundary_condition_object,
                                  sun_exposure, wind_exposure, coordinates)
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def building_surface_detailed(idf, surface_name, surface_type,
                              construction_name, zone_name,
                              outside_boundary_condition,
                              outside_boundary_condition_object,
                              sun_exposure, wind_exposure, coordinates):
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

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def roof_ceiling(idf, zone_name, space_above_floor,
                 horizontal_surface_coordinates, ceiling_height, roof_const):
    '''
    Function which generates roof/ceiling energyplus object
    '''
    # If space above the ceiling is Outdoors than set up outside boundary
    # condition to the 'Outdoors'
    if space_above_floor == 'Outdoors':
        # Surface name made of the zone name appended with '_Roof' string
        surface_name = zone_name + '_Roof'
        # Surface type; sun exposure; wind exposure
        surface_type = 'Roof'
        sun_exposure = 'SunExposed'
        wind_exposure = 'WindExposed'
        outside_boundary_condition = space_above_floor
        outside_boundary_condition_object = ''
    else:
        # Surface name made of the zone name appended with '_Ceiling' string
        surface_name = zone_name + '_Ceiling'
        # Surface type; sun exposure; wind exposure
        surface_type = 'Ceiling'
        sun_exposure = 'NoSun'
        wind_exposure = 'NoWind'
        # Set up outside boundary condition to the 'Surface' and outside
        # boundary condition object to the zone above name appended with
        # '_Floor' string
        outside_boundary_condition = 'Surface'
        outside_boundary_condition_object = space_above_floor + '_Floor'
    # Append the roof/ceiling horizontal coordinates with the height
    ceiling_coordinates_list = coordinates_add_height(
        ceiling_height, horizontal_surface_coordinates)
    # Convert roof/ceiling coordinates list to format used in energyplus
    coordinates_list = idf_ceiling_coordinates_list(ceiling_coordinates_list)
    # For each coordinates list in a list of coordinates lists creates building
    # surface detailed element which represents the roof/ceiling
    for coordinates in coordinates_list:
        building_surface_detailed(idf, surface_name, surface_type,
                                  roof_const, zone_name,
                                  outside_boundary_condition,
                                  outside_boundary_condition_object,
                                  sun_exposure, wind_exposure, coordinates)
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def external_walls(idf, zone_name, floor_number,
                   vertical_surface_coordinates, ceiling_height,
                   floor_height, zone_height, min_avail_height,
                   min_window_width, wall_const, glazing_const, glazing_ratio, overhang_depth):
    '''
    Function which generates external wall energyplus object and return exposed
    walls and glazings areas
    
    Added overhang depth for the Simstock QGIS plugin
    '''

    def wall_width_height(i, ceil_coord, floor_coord):
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

    def window(idf, surface_name, construction_name, building_surface_name,
               starting_x_coordinate, starting_z_coordinate, length, height):
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
        return
    
    ############################################################################
    def overhang(idf, window_name, depth):
        """Adds a shading overhang to window with the specified depth. 
        Used in the Simstock QGIS plugin."""
        if isinstance(depth, float) or isinstance(depth, int):
            if depth > 0:
                idf.newidfobject('SHADING:OVERHANG',
                                Name=window_name+"_Overhang",
                                Window_or_Door_Name=window_name,
                                Height_above_Window_or_Door=0.0,
                                Tilt_Angle_from_WindowDoor=90.0,
                                Left_extension_from_WindowDoor_Width=0.0,
                                Right_extension_from_WindowDoor_Width=0.0,
                                Depth=depth)
        return
    ############################################################################

    # surface type
    surface_type = 'Wall'
    outside_boundary_condition_object = ''
    sun_exposure = 'SunExposed'
    wind_exposure = 'WindExposed'
    outside_boundary_condition = 'Outdoors'
    # Append the vertical surface coordinates with the ceiling and floor height
    ceiling_coordinates = coordinates_add_height(ceiling_height,
                                                 vertical_surface_coordinates)
    floor_coordinates = coordinates_add_height(floor_height,
                                               vertical_surface_coordinates)
    # Loop through the list of ceiling coordinates lists
    for n, _ in enumerate(ceiling_coordinates):
        # Floor and ceiling coordinates lists
        ceil_coord = ceiling_coordinates[n]
        floor_coord = floor_coordinates[n]
        # Loop through ceiling coordinate list up to the next to the last item
        for i, _ in enumerate(ceil_coord[:-1]):
            # Calculate wall centre coordinate in 3D plane (used for naming)
            wcc = wall_centre_coordinate(
                ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
            # Generate the surface name form zone name, '_Wall_' string and
            # centre coordinate
            surface_name = zone_name + '_Wall_' + wcc
            # Generate wall coordinates in format used by energyplus
            coordinates = idf_wall_coordinates(i, ceil_coord, floor_coord)
            # Creates building surface detailed element which represent wall
            building_surface_detailed(idf, surface_name, surface_type,
                                      wall_const, zone_name,
                                      outside_boundary_condition,
                                      outside_boundary_condition_object,
                                      sun_exposure, wind_exposure, coordinates)
            # Calculates wall width and height
            w, h = wall_width_height(i, ceil_coord, floor_coord)
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
                win_surface_name = surface_name + '_Window'
                # Base surface name
                building_surface_name = surface_name
                # Coordinates converted into strings
                starting_x_coordinate = '%.2f' % x
                starting_z_coordinate = '%.2f' % z
                win_length = '%.2f' % wl
                win_height = '%.2f' % wh
                # Add the window energyplus object
                window(idf, win_surface_name, glazing_const,
                       building_surface_name, starting_x_coordinate,
                       starting_z_coordinate, win_length, win_height)

                ################################################################
                # Plugin: add overhang to each window of custom depth
                overhang(idf, win_surface_name, overhang_depth)
                ################################################################
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def partition_walls(idf, zone_name, adj_osgb, vertical_surface_coordinates,
                    ceiling_height, floor_height, partition_const):
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
    ceiling_coordinates = coordinates_add_height(ceiling_height,
                                                 vertical_surface_coordinates)
    floor_coordinates = coordinates_add_height(floor_height,
                                               vertical_surface_coordinates)
    # Loop through the list of ceiling coordinates lists
    for n, item in enumerate(ceiling_coordinates):
        # Floor and ceiling coordinates lists
        ceil_coord = ceiling_coordinates[n]
        floor_coord = floor_coordinates[n]
        # Loop through ceiling coordinate list up to the next to the last item
        for i, p in enumerate(ceil_coord[:-1]):
            # Calculate wall centre coordinate in 3D plane (used for naming)
            wcc = wall_centre_coordinate(
                ceil_coord[i + 1], ceil_coord[i], floor_coord[i])
            # Generate the surface name form zone name, '_Part_' string,
            # opposite zone name and centre coordinate
            surface_name = zone_name + '_Part_' + opposite_zone + '_' + wcc
            # Generate wall coordinates in format used by energyplus
            coordinates = idf_wall_coordinates(i, ceil_coord, floor_coord)
            # Creates partition building surface detailed element
            building_surface_detailed(idf, surface_name, surface_type,
                                      partition_const, zone_name,
                                      outside_boundary_condition, obco,
                                      sun_exposure, wind_exposure, coordinates)
    return

# END OF FUNCTION  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

################################################################################
# Simstock QGIS plugin
# This is used as default values to build the per zone ventilation objects
ventilation_dict = {'key': 'ZoneVentilation:DesignFlowRate',
                    'Name': 'Dwell Nat Vent',
                    'Zone_or_ZoneList_Name': '',
                    'Schedule_Name': 'Dwell_Occ',
                    'Design_Flow_Rate_Calculation_Method': 'AirChanges/Hour',
                    'Design_Flow_Rate': '',
                    'Flow_Rate_per_Zone_Floor_Area': '',
                    'Flow_Rate_per_Person': '',
                    'Air_Changes_per_Hour': '',
                    'Ventilation_Type': 'NATURAL',
                    'Fan_Pressure_Rise': 0.0,
                    'Fan_Total_Efficiency': 1.0,
                    'Constant_Term_Coefficient': 1.0,
                    'Temperature_Term_Coefficient': 0.0,
                    'Velocity_Term_Coefficient': 0.0,
                    'Velocity_Squared_Term_Coefficient': 0.0,
                    'Minimum_Indoor_Temperature': 18.0,
                    'Minimum_Indoor_Temperature_Schedule_Name': '',
                    'Maximum_Indoor_Temperature': 100.0,
                    'Maximum_Indoor_Temperature_Schedule_Name': '',
                    'Delta_Temperature': 0.0,
                    'Delta_Temperature_Schedule_Name': '',
                    'Minimum_Outdoor_Temperature': -100.0,
                    'Minimum_Outdoor_Temperature_Schedule_Name': '',
                    'Maximum_Outdoor_Temperature': 100.0,
                    'Maximum_Outdoor_Temperature_Schedule_Name': '',
                    'Maximum_Wind_Speed': 40.0}

infiltration_dict = {'key': 'ZoneInfiltration:DesignFlowRate',
                     'Name': '',
                     'Zone_or_ZoneList_Name': '',
                     'Schedule_Name': 'On 24/7',
                     'Design_Flow_Rate_Calculation_Method': 'AirChanges/Hour',
                     'Design_Flow_Rate': '',
                     'Flow_per_Zone_Floor_Area': '',
                     'Flow_per_Exterior_Surface_Area': '',
                     'Air_Changes_per_Hour': '',
                     'Constant_Term_Coefficient': 1.0,
                     'Temperature_Term_Coefficient': 0.0,
                     'Velocity_Term_Coefficient': 0.0,
                     'Velocity_Squared_Term_Coefficient': 0.0}
