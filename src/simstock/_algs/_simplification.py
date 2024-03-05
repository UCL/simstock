"""
Module containing algorithms for simplifying
polygons. These algorithms apply the coordinate
list simplification algorithms defined
in _coords_algs.py, togther with some of the
polygon handling algorithms defined in _polygon_algs.py

These functions are used internally and not 
intended to be used directly through the API.
"""

from shapely.geometry import Polygon
from shapely.ops import unary_union
import simstock._algs._coords_algs as calgs
import simstock._algs._polygon_algs as algs
from ast import literal_eval
from pandas.core.frame import DataFrame

# Should be redundant -- test this
tolerance = 0.1

def _simplified_coords(
        polygon: Polygon,
        ring_position: str,
        remove_leave_pairs: list
        ):
        """
        Function that simplifies either the outer
        or inner ring of a polygon, as specified by
        the ``ring_position`` argument. 

        It returns the coordinate list of the simplified
        outer or inner ring, togther with a list of 
        the remove-leave pairs. 

        See _coords_cleaning in coords_algs.py for 
        further details.
        """
        if ring_position == 'outer':
            coords = list(polygon.exterior.coords)
            coords, remove_leave_pairs = calgs._coords_cleaning(
                coords, remove_leave_pairs)
            return coords, remove_leave_pairs
        elif ring_position == 'inner':
            inner_coords_list = list()
            for inner in polygon.interiors:
                coords = list(inner.coords)
                coords, remove_leave_pairs = calgs._coords_cleaning(
                    coords, remove_leave_pairs)
                if len(coords) > 3:
                    inner_coords_list.append(coords)
            return inner_coords_list, remove_leave_pairs
        

def _simplification_affects_inner_ring(
            adjacent_polygon: Polygon,
            polygon: Polygon,
            remove_leave_pairs: list
            ) -> Polygon:
        """
        Function to perform simplification
        on the interior rings of a polygon.
        """
        adjacent_inner_coords_list = list()
        for inner in adjacent_polygon.interiors:
            inner_coords = list(inner.coords)
            inner_polygon = Polygon(inner_coords)
            if inner_polygon.contains(polygon):
                inner_coords = calgs._remove_cleaned_coordinates(
                    inner_coords, remove_leave_pairs)
            adjacent_inner_coords_list.append(inner_coords)
        adjacent_polygon = Polygon(adjacent_polygon.exterior,
                                    adjacent_inner_coords_list)
        return adjacent_polygon


def _remove_hole_if_inner_is_removed(
                df: DataFrame,
                inner_polygon: Polygon,
                polygon_within_hole: list[Polygon]
                ) -> DataFrame:
            """
            Function to remove hole within each 
            polygon in the data frame if their
            inner polygons are removed.
            """
            for p in polygon_within_hole:
                p_polygon = df.loc[
                    df['osgb'] == p, 'polygon'
                    ].values[0]
                if p_polygon:
                    if inner_polygon.contains(p_polygon):
                        df.loc[df['osgb'] == p, 'polygon'] = False
                        p_polygon_within_hole = literal_eval(
                            df.loc[df['osgb'] == p,
                                    'polygon_within_hole'].values[0])
                        if p_polygon_within_hole:
                            df = _remove_holes(
                                df, p_polygon_within_hole)
            return df


def _remove_holes(
        df: DataFrame,
        polygon_within_hole: list[Polygon]
        ) -> DataFrame:
        """
        Recursive function to remove holes from 
        polygons in the dataframe df.
        """
        if polygon_within_hole:
            for p in polygon_within_hole:
                p_polygon = df.loc[df['osgb'] ==
                                    p, 'polygon'].values[0]
                p_polygon_within_hole = literal_eval(
                    df.loc[df['osgb'] == p, 'polygon_within_hole'].values[0])
                if p_polygon and p_polygon_within_hole:
                    df = _remove_holes(df, p_polygon_within_hole)
                df.loc[df['osgb'] == p, 'polygon'] = False
        return df


def _not_valid_polygons(
        osgb: str,
        polygon: Polygon,
        df: DataFrame,
        outer_coords: list,
        polygon_within_hole: Polygon,
        remove_leave_pairs: list
        ):
    """
    Recursive function that attempts to rectify polygons where
    their interiors are intersecting with their exteriors. This
    is done by applying simplifications to the interior rings.
    Finally any holes are removed where the interior has also 
    been removed.
    """
    if algs._poly_is_not_valid(polygon):
        eroded_outer = Polygon(outer_coords).buffer(-tolerance)
        eroded_inner_list = list()
        for inner in polygon.interiors:
            inner_polygon = Polygon(inner.coords)
            if inner_polygon.within(eroded_outer):
                eroded_inner_list.append(inner)
            else:
                if eroded_outer.intersects(inner_polygon):
                    new_inner_polygon = eroded_outer.intersection(
                        inner_polygon)
                    new_inner_coords = list(
                        new_inner_polygon.exterior.coords)
                    if len(new_inner_coords) > 3:
                        if polygon_within_hole:
                            for p in polygon_within_hole:
                                p_polygon = df.loc[
                                    df['osgb'] == p, 'polygon'
                                    ].values[0]
                                if p_polygon:
                                    if inner_polygon.contains(p_polygon):
                                        p_outer_coords = list(
                                            p_polygon.exterior.coords)
                                        p_outer_coords = calgs._remove_cleaned_coordinates(
                                            p_outer_coords, remove_leave_pairs)
                                        new_p_polygon = Polygon(new_inner_coords).intersection(
                                            Polygon(p_outer_coords))
                                        new_inner_diff = Polygon(new_inner_coords).difference(
                                            Polygon(p_outer_coords))
                                        united_inner_polygon = unary_union(
                                            (new_inner_diff, new_p_polygon))
                                        remove_leave_pairs_inner = list()
                                        new_inner_coords, remove_leave_pairs_inner = _simplified_coords(
                                            united_inner_polygon, 'outer', remove_leave_pairs_inner)
                                        p_outer_coords = list(
                                            new_p_polygon.exterior.coords)
                                        p_outer_coords = calgs._remove_cleaned_coordinates(
                                            p_outer_coords, remove_leave_pairs_inner)
                                        if len(p_outer_coords) > 3:
                                            if p_polygon.interiors:
                                                new_p_polygon = Polygon(
                                                    p_outer_coords, p_polygon.interiors)
                                                p_polygon_within_hole = literal_eval(
                                                    df.loc[df['osgb'] == p, 'polygon_within_hole'].values[0])
                                                mock_list = list()
                                                df, new_p_polygon = _not_valid_polygons(
                                                    p, new_p_polygon, df, p_outer_coords, p_polygon_within_hole, mock_list)
                                            else:
                                                new_p_polygon = Polygon(
                                                    p_outer_coords)
                                            df.loc[df['osgb'] == p, 'polygon'] = new_p_polygon
                                        else:
                                            df.loc[df['osgb'] == p,
                                                    'polygon'] = False
                        else:
                            mock_list = list()
                            new_inner_coords, _ = _simplified_coords(
                                new_inner_polygon, 'outer', mock_list)
                        if len(new_inner_coords) > 3:
                            new_inner_coords = calgs._ccw_interior_ring(
                                new_inner_coords)
                            eroded_inner_list.append(
                                new_inner_coords)
                    elif polygon_within_hole:
                        df = _remove_hole_if_inner_is_removed(
                            df, inner_polygon, polygon_within_hole)
                elif polygon_within_hole:
                    df = _remove_hole_if_inner_is_removed(
                        df, inner_polygon, polygon_within_hole)
        polygon = Polygon(outer_coords, eroded_inner_list)
    return df, polygon


# This can all be simplified
def _polygon_simplifying(
        polygon: Polygon,
        df: DataFrame,
        osgb: str,
        osgb_touching: str
        ) -> DataFrame:
    """
    Function that attempts to simplify a polygon by applying
    simplification rules to its exterior and interior components.
    Various checks are algorithms are then applied to handle cases
    where simplifications lead to unexpected intersections.
    """
    polygon_within_hole = df.loc[df['osgb'] == osgb, 'poly_within_hole'].values[0]
    rlp = list()
    outer_coords, rlp = _simplified_coords(polygon, 'outer', rlp)
    if len(outer_coords) > 3:
        if polygon.interiors:
            inner_coords_list, rlp = _simplified_coords(
                polygon, 'inner', rlp)
            new_polygon = Polygon(outer_coords, inner_coords_list)
            if not inner_coords_list:
                df = _remove_holes(df, polygon_within_hole)
            df, new_polygon = _not_valid_polygons(
                osgb, new_polygon, df, outer_coords,
                polygon_within_hole, rlp)
        else:
            new_polygon = Polygon(outer_coords)
        df.loc[
            df['osgb'] == osgb, 'polygon'
            ] = new_polygon
    else:
        df.loc[df['osgb'] == osgb, 'polygon'] = False
        df = _remove_holes(df, polygon_within_hole)

    if rlp and osgb_touching:
        for t in osgb_touching:
            t_polygon = df.loc[df['osgb'] == t, 'polygon'].values[0]
            if t_polygon:
                t_polygon_within_hole = df.loc[
                    df['osgb'] == t, 'poly_within_hole'
                    ].values[0]
                osgb_polygon = df.loc[
                    df['osgb'] == osgb, 'polygon'
                    ].values[0]
                if osgb_polygon and t_polygon_within_hole and (osgb in t_polygon_within_hole):
                    t_polygon = _simplification_affects_inner_ring(
                        t_polygon, polygon, rlp)
                t_outer_coords = list(t_polygon.exterior.coords)
                t_outer_coords = calgs._remove_cleaned_coordinates(
                    t_outer_coords, rlp)
                if len(t_outer_coords) > 3:
                    if t_polygon.interiors:
                        t_polygon = Polygon(t_outer_coords,
                                            t_polygon.interiors)
                        df, t_polygon = _not_valid_polygons(
                            t, t_polygon, df, t_outer_coords,
                            t_polygon_within_hole, rlp)
                    else:
                        t_polygon = Polygon(t_outer_coords)
                    df.loc[df['osgb'] == t, 'polygon'] = t_polygon
                else:
                    df.loc[df['osgb'] == t, 'polygon'] = False
                    df = _remove_holes(df, t_polygon_within_hole)
    return df