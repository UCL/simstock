"""
Module containing algorithms for manipulating lists of 
coordinates. The functions are used internally for 
geometric simplification etc. and not intended to 
be used directly through the API.
"""

from typing import Any
import math
from shapely.geometry import (
    LineString, 
    LinearRing,
    MultiLineString
)

# Also import some algorithms that act on polygons
import simstock._algs._polygon_algs as algs


def _remove_dups_from_list(lst : list) -> list:
    """
    Function to remove any duplicated coordinates
    from a list of coordinates. If the list is a 
    closed ring of coordinates, then this closure
    is maintained.
    """
    lst_no_dup = list(dict.fromkeys(lst))
    if lst[0] == lst[-1]:
        lst_no_dup.append(lst_no_dup[0])
    return lst_no_dup


def _dist_within_tol(coords : list, tol : float) -> bool:
    """
    Function that takes a list of coordinates and measures
    the pair-wise distance between each successive point.
    If any of the points are closed together than the 
    tolerance, then the function returns True.
    """
    for i in range(len(coords)-1):
        if LineString([coords[i], coords[i+1]]).length < tol:
            return True
    return False


def _remove_item_from_list(lst : list, item : Any) -> list:
    """
    Function that takes a list and removes the specified 
    item. List closure is respected.
    """
    if lst[0] == lst[-1]:
        lst_ammended = [x for x in lst if x != item]
        if lst_ammended[0] != lst_ammended[-1]:
            lst_ammended.append(lst_ammended[0])
        return lst_ammended
    return [x for x in lst if x != item]


# Could be improved -- this implementation is inefficient
def _remove_items_from_list(coords : list, items : list) -> list:
    """
    Function that takes a list and removes any number of items
    as specified in the items list. List closure is respected.
    """
    if coords[0] == coords[-1]:
        for i in items:
            coords = [x for x in coords if x != i]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
    else:
        for i in items:
            coords = [x for x in coords if x != i]
    return coords


def _radial_dist_simplify(coords : list, tol : float) -> tuple:
    """
    Function that goes through a list of coordinated and tests
    each connsecutive pair to see if they are closer to each other
    than some tolerance. If one such pair is found, then one is
    removed and one is kept. The function then exits, returning
    the list minus the removed point, and a list containing 
    the pair that flagged the removal: the remove-leave pair.
    """
    for i in range(len(coords) - 1):
        first = coords[i]
        second = coords[i+1]
        if LineString([first, second]).length < tol:
            if i < (len(coords) - 2):
                coord_remove = second
                coord_leave = first
            else:
                coord_remove = first
                coord_leave = second
            coords = _remove_item_from_list(coords, coord_remove)
            return coords, [coord_remove, coord_leave]
    return coords, []


# Could potentially simplify
# Add tolerance to state 
def _coords_cleaning(coords : list, remove_leave_pairs : list) -> tuple:
    """
    Function that keeps applying radial distance simplification
    until the list of coordinates settles to a fixed state.
    """
    coords_lenght = len(coords) + 1
    while (len(coords) < coords_lenght) and (len(coords) > 3):
        coords_lenght = len(coords)
        coords, r_l_pair = _radial_dist_simplify(coords, 0.1)
        if r_l_pair:
            remove_leave_pairs.append(r_l_pair)
    return coords, remove_leave_pairs


def _remove_cleaned_coordinates(
        coords : list,
        remove_leave_pairs : list
        ) -> list:
    """
    Function that makes sure all of the 
    coordinates flagged as needing to be
    removed are indeed removed
    """
    for pair in remove_leave_pairs:
        for i, coord in enumerate(coords):
            if coord == pair[0]:
                coords[i] = pair[1]
    coords = _remove_dups_from_list(coords)
    return coords

def _ccw_interior_ring(coords : list) -> list:
    """
    Function that ensures the coords
    are ccw
    """
    if not LinearRing(coords).is_ccw:
        coords = coords[::-1]
    return coords


# This could be sped up, perhaps
# by using itertools
def _remove_buffered_coordinates(
        coords : list,
        new : list,
        removed : list
        ) -> list:
    """
    Function that goes through a list of coordinates and 
    selects any that have been flagged for removal, as 
    specified in the removed list. These coordinates are
    then replaced with their nearest new coordinate 
    from the new list. Finally, any duplicated in 
    the coordinate list are removed before the 
    list is returned.
    """
    
    # Iterate through all the coordinates 
    # flagged for removal
    for r_c in removed:

        # Then iterate through each coordinate
        # in the list 
        for i, coord in enumerate(coords):

            # If this coordinate is one of the
            # coordinates flagged for removal 
            if coord == r_c:

                # Then calculate the distance from this removed
                # coordinate to the first of the new ones and 
                # select this first one as a candidate 
                # replacement coordinate
                minimum_dist = LineString([r_c, new[0]]).length
                replacement_coord = new[0]

                # Now go through the rest of the new coords
                # and compute each of their distances to the
                # removed coord. Keep a track of the closest
                # of the new coordinates to the removed one
                for n_c in new:
                    dist = LineString([r_c, n_c]).length
                    if dist < minimum_dist:
                        minimum_dist = dist
                        replacement_coord = n_c

                # Now replace this coordinate, which was flagged
                # for removal, with the closest candiate new 
                # coordinate
                coords[i] = replacement_coord

    # Wash out any duplicates
    return _remove_dups_from_list(coords)


def _coollinear_points(coord_list : list) -> list:
    """
    Function that takes a list of coordinates and
    returns a list of collinear points 
    to be removed.
    """
    removed_coll = list()
    if len(coord_list) >= 3:

        # Go through the coordinates and select
        # a sliding window of three points
        for i in range(len(coord_list) - 2):
            first = coord_list[i]
            middle = coord_list[i + 1]
            last = coord_list[i + 2]

            # Pass these to a function to check their 
            # collinearity. If it returns true, then 
            # add the middle of the three points of the 
            # list of collinear points
            if algs._check_collinearity(first, middle, last):
                removed_coll.append(coord_list[i + 1])
    return removed_coll


def coordinates_move_origin(coordinates_list : list, origin) -> list:
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


def _horizontal_surface_coordinates(coordinates_dictionary : dict, 
                                    origin) -> list:
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
        coordinates_list = _polygon_with_holes(coordinates_dictionary)
    # Position coordinates relative to the origin
    coordinates = coordinates_move_origin(coordinates_list, origin)
    # Return coordinates converted to text
    return coordinates


def _polygon_with_holes(coordinates_dictionary : dict) -> list:
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
                    oi_min_distance = _dist_two_points(orop, irop)
                    if oi_min_distance > 0.015:
                        # outer ring - inner ring minimum distance LineString
                        oi_min_linestring = LineString([orop, irop])
                        # Get the difference between inner ring and
                        # intersection point between inner ring and LineSting
                        # connecting inner ring and outer ring. If intersection
                        # point is not the first coordinate of inner ring than
                        # inner ring will be broken to a MultiLineString
                        inner_linestring = _inner_string(inner_ring_coordinates,
                                                        irop)

                    else:
                        oi_min_distance = 1e9
                # Update the minimum distance between outer and inner rings,
                # LineString connecting these outer and inner ring along the
                # minimum distance and inner ring LineSting (MultiLineSting) by
                # checking the distance between other inner and outer
                # coordinates
                else:
                    distance = _dist_two_points(orop, irop)
                    if (distance < oi_min_distance) and (distance > 0.015):
                        oi_min_distance = distance
                        oi_min_linestring = LineString([orop, irop])
                        inner_linestring = _inner_string(inner_ring_coordinates,
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
        coordinates = _polygon_with_holes_coordinates(coordinates, outer_ring,
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
            coordinates = _polygon_with_holes_coordinates(coordinates,
                                                         linestring,
                                                         interceptors_op_dict)
    # Append the polygon with holes coordinates with start-end ordered pair
    coordinates.append(start_end_op)
    # Return the list of polygon with holes coordinates
    return [coordinates]


def _polygon_with_holes_coordinates(coordinates, outer_ring_linestring,
                                       interceptors_op_dict) -> list:
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


def _dist_two_points(p1 : float | int, p2 : float | int) -> float:
    '''
    Internal function which calculates the Euclidean distance between two
    points
    '''
    return math.sqrt(math.pow((p1[0]-p2[0]), 2) + math.pow((p1[1]-p2[1]), 2))


def _inner_string(inner_ring_coordinates, irop) -> MultiLineString:
    """
    Function to split a line string at a given position and
    stitch togther
    """
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


def _coordinates_add_height(height : float | int, coordinates_list : list):
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



