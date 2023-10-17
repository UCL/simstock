"""
Module containing functions that operate on 
shapely polygon objects. These are functions
used internally by the SimstockDataframe 
object as part of the geometric simplification
algorithms.

All of these functions are meant to be used
internally only and are not exposed through the
user-facing API.
"""

from typing import Union
from shapely.geometry import (
    Polygon, 
    LinearRing,
    LineString,
    MultiLineString,
    MultiPolygon
)
from pandas.core.frame import DataFrame
import simstock._algs._coords_algs as calgs
from simstock._utils._serialisation import _load_gdf
from shapely.wkt import loads
from shapely.ops import unary_union


def _check_for_multi(
        polygon: Union[Polygon, MultiPolygon]
        ) -> tuple[bool, Polygon]:
    """
    Hand-drawn polygons can be multipolygons with len 1, i.e. a nested 
    polygon within a multipolygon wrapper. This aims to extract them.

    This function takes a shapely object and returns a bool (indicating if
    the object is a non-trivial multipolygon) and a shapely object. This 
    object will be a polygon, if one could be successfully extracted, or
    it will be a multipolygon if is a multipolgon containing more 
    that one polygons. A True value for the boolean flag indicates
    a multipolygon object has been found.
    """
    if isinstance(polygon, MultiPolygon):
        if len(list(polygon.geoms)) == 1:
            return (False, list(polygon.geoms)[0])
        else:
            return (True, polygon)
    return (False, polygon)


def _shading_buffer(
        shading_buffer_radius: Union[float, int],
        df: DataFrame,
        rest: DataFrame
        ) -> DataFrame:
    """
    Includes polygons which fall within a specified shading buffer radius in the main DataFrame.

    Inputs:
        - shading_buffer_radius: Radius in metres within which other polygons are included. An
            empty string is interpreted as an infinite radius.
        - df: The main DataFrame containing the thermal zones of interest
        - rest: DataFrame containing all other polygons (i.e. shading and those from other BIs)
    """
    gdf = _load_gdf(df)
    rest_gdf = _load_gdf(rest)
    if shading_buffer_radius != '':
    
        # Buffer the df geometry to specified radius for shading
        dissolved = gdf.dissolve().geometry.convex_hull.buffer(shading_buffer_radius)

        # Find polygons which are within this buffer and create mask
        mask = rest_gdf.intersects(dissolved[0])
        
        # Get data for the polygons within the buffer
        within_buffer = rest.loc[mask].copy()

        # Set them to be shading
        within_buffer["shading"] = True
    
    else:
        # All other buildings are to be included as shading
        within_buffer = rest.copy()
        within_buffer["shading"] = True

    # Include them in the idf
    #df = pd.concat([df, within_buffer])

    return within_buffer


def _orientate(poly: Polygon) -> Polygon:
    """
    Function that ensures polygon exteriors
    are clockwise and interiors 
    are anti-clockwise.
    """
    if poly.exterior.is_ccw:
        ext_coords = list(poly.exterior.coords[::-1])
    else:
        ext_coords = list(poly.exterior.coords)
    int_ring = list()
    if poly.interiors:
        for item in poly.interiors:
            if not item.is_ccw:
                item_coords = list(item.coords[::-1])
            else:
                item_coords = list(item.coords)
            int_ring.append(item_coords)
    return Polygon(ext_coords, int_ring)


def _is_exterior_ccw(poly: Polygon) -> bool:
    """
    Function to determine whether a polgon's
    exterior is anti-clockwise.
    """
    return poly.exterior.is_ccw


def _remove_duplicate_coords(poly: Polygon) -> Polygon:
    """
    Function to remove any duplicate coordinates
    from both the exterior and any interior
    rings of a polygon.
    """
    ext_ring = list(poly.exterior.coords)
    ext_ring_no_dup = calgs._remove_dups_from_list(ext_ring)
    int_ring_no_dup_list = list()
    if poly.interiors:
        for item in poly.interiors:
            int_ring_no_dup = calgs._remove_dups_from_list(list(item.coords))
            int_ring_no_dup_list.append(int_ring_no_dup)
    return Polygon(ext_ring_no_dup, int_ring_no_dup_list)


def _is_touching(poly1: Polygon, poly2: Polygon) -> bool:
    """
    Function to determine if polygon 1 touches
    polygon 2. A ValueError is raised if the
    polygons interect rather than touch.
    """
    touches = poly1.touches(poly2)
    intersects = poly1.intersects(poly2)
    if not poly1.intersection(poly2).geom_type not in ['Point']:
        return False
    if intersects and not touches:
        raise ValueError
    if touches:
        return True
    return False


def _has_interior(poly: Polygon) -> bool:
    """
    Function to determine whether a polygon
    has any interior
    """
    if poly.interiors:
        return True
    return False


def _poly_tol(poly: Polygon, tol: float) -> bool:
    """
    Function to determine whether any consective
    coordinate points within a polygon are 
    closer together than some tolerance.
    """
    ext_ring_coords = list(poly.exterior.coords)
    if calgs._dist_within_tol(ext_ring_coords, tol):
        return True
    if poly.interiors:
        for item in poly.interiors:
            item_coords = list(item.coords)
            if calgs._dist_within_tol(item_coords, tol):
                return True
    return False


# Could simplify
def _poly_is_not_valid(poly: Polygon) -> bool:
    """
    Function to determine whether a polygon
    has any interior components that 
    intersect with the exterior. 
    This function returns True if so.
    """
    ex = LinearRing(poly.exterior)
    for inner in poly.interiors:
        in_i = Polygon(inner.coords)
        if not ex.touches(in_i):
            if ex.intersects(in_i):
                return True
    return False


def _buffered_polygon(
        t_poly: Polygon,
        new_coords: list,
        removed_coords: list
        ) -> Polygon:
    """
    Function that takes a polygon and returns it after having
    removed any coordinates specified in the removed_coords
    list and replaces them with new_coords.
    """
    t_poly_coords = calgs._remove_buffered_coordinates(
                            list(t_poly.exterior.coords), 
                            new_coords, 
                            removed_coords
                        )
    return Polygon(t_poly_coords, t_poly.interiors)


def _check_collinearity(f: list, m: list, l: list) -> bool:
    """
    Boolean function returns True is the polygon formed
    from f,m,l is collinear
    """
    if Polygon([f, m, l]).area <= 1e-9:
        return True
    return False


# Could be sped up
def _collinear_points_list(objects_list: list) -> list:
    """
    Function that returns a list of points that have been
    identified as collinear from within the shapes in
    the input objects_list.
    """
    coll_list = list()
    if objects_list.geom_type in ['MultiLineString',
                                    'GeometryCollection']:
        for item in objects_list.geoms:
            coll_points = calgs._coollinear_points(list(item.coords))
            if coll_points:
                coll_list.append(coll_points)
    elif objects_list.geom_type == 'LineString':
        coll_points = calgs._coollinear_points(list(objects_list.coords))
        if coll_points:
            coll_list.append(coll_points)
    collinear_points_list = list()
    for item in coll_list:
        for i in item:
            collinear_points_list.append(i)
    return collinear_points_list


def _update_polygon(polygon: Polygon, points_to_remove: list) -> Polygon:
    """
    Function that takes a polygon and returns it once 
    all of the coordinates from the points_to_remove
    list have been removed.
    """
    outer_ring = list(polygon.exterior.coords)
    new_outer_ring = calgs._remove_items_from_list(
        outer_ring, points_to_remove)
    new_inner_rings = list()
    if polygon.interiors:
        for item in polygon.interiors:
            inner_ring = list(item.coords)
            new_inner_ring = calgs._remove_items_from_list(inner_ring,
                                                    points_to_remove)
            new_inner_rings.append(new_inner_ring)
    new_polygon = Polygon(new_outer_ring, new_inner_rings)
    return new_polygon


def _update_exposed(exposed_ring, points_to_remove):
    """
    Function that takes an exposed ring and returns it once 
    all of the coordinates from the points_to_remove
    list have been removed.
    """
    if exposed_ring.geom_type == 'MultiLineString':
        new_ms = list()
        for item in list(exposed_ring.geoms):
            new_item = calgs._remove_items_from_list(list(item.coords),
                                                points_to_remove)
            if len(new_item) > 1:
                new_ms.append(new_item)
        if len(new_ms) > 1:
            new_exposed_ring = MultiLineString(new_ms)
        elif len(new_ms) == 1:
            new_exposed_ring = LineString(new_ms[0])
        else:
            new_exposed_ring = loads('GEOMETRYCOLLECTION EMPTY')
    elif exposed_ring.geom_type == 'LineString':
        new_item = calgs._remove_items_from_list(list(exposed_ring.coords),
                                            points_to_remove)
        if len(new_item) > 1:
            new_exposed_ring = LineString(new_item)
        else:
            new_exposed_ring = loads('GEOMETRYCOLLECTION EMPTY')
    else:
        new_exposed_ring = loads('GEOMETRYCOLLECTION EMPTY')
    return new_exposed_ring


# Could be improved
def _remove_collinear_points_horizontal(poly: Polygon) -> Polygon:
    """
    Function that takes a new polygon and returns it
    with all collinear points removed.
    """
    coll_list = list()
    o_r = LineString(poly.exterior)
    i_r = MultiLineString(poly.interiors)
    t_t = unary_union((o_r, i_r))
    if t_t.geom_type == 'MultiLineString':
        for item in list(t_t.geoms):
            coords = list(item.coords)
            coords.append(coords[1])
            coll_points = calgs._coollinear_points(coords)
            if coll_points:
                coll_list.append(coll_points)
    elif t_t.geom_type == 'LineString':
        coords = list(t_t.coords)
        coords.append(coords[1])
        coll_points = calgs._coollinear_points(coords)
        if coll_points:
            coll_list.append(coll_points)
    collinear_points_list = list()
    for item in coll_list:
        for i in item:
            collinear_points_list.append(i)
    new_polygon = _update_polygon(poly, collinear_points_list)
    return new_polygon


def _polygon_coordinates_dictionary(poly: Polygon) -> dict:
    '''
    Function which stores data form POLYGON((,,,),(,,,),(,,,)) in dictionary.
    Data are in the shape Polygon(exterior[, interiors=None])
    '''
    # Load the polygon data by using shapely
    # Empty dictionary
    polygon_coordinates_dict = dict()
    # Outer ring (exterior) coordinates
    polygon_coordinates_dict['outer_ring'] = [poly.exterior.coords]
    # If there are inner rings (holes in polygon) than loop through then and
    # store them in the list
    if poly.interiors:
        polygon_coordinates_dict['inner_rings'] = list()  # empty list
        for item in poly.interiors:
            polygon_coordinates_dict['inner_rings'].append(item.coords)
    # Return the dictionary
    return polygon_coordinates_dict


def _surface_coordinates(poly: Polygon, origin) -> list:
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
    if poly.geom_type in ['MultiLineString', 'GeometryCollection']:
        for item in poly.geoms:
            if not item.geom_type == 'Point':
                coordinates_list.append(item.coords)
    elif poly.geom_type == 'LineString':
        coordinates_list.append(poly.coords)
    # Position coordinates relative to origin
    coordinates = calgs.coordinates_move_origin(coordinates_list, origin)
    # Return coordinates
    return coordinates






