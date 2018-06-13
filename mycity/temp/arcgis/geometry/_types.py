
from __future__ import absolute_import
import json
import copy
import sys
from arcgis._impl.common._mixins import PropertyMap
from six import add_metaclass
try:
    import arcpy
    HASARCPY = True
except ImportError:
    HASARCPY = False
try:
    import shapely
    from shapely.geometry.base import BaseGeometry as _BaseGeometry
    from shapely.geometry import shape as _shape
    from shapely.wkt import loads as _loads
    HASSHAPELY = True
except:
    HASSHAPELY = False

list_types = (list, tuple)
if sys.version_info.major == 3:
    number_type = (int, float)
else:
    number_type = (int, float, long)
###########################################################################
def trace():
    """
        trace finds the line, the filename
        and error message and returns it
        to the user
    """
    import traceback
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    # script name + line number
    line = tbinfo.split(", ")[1]
    # Get Python syntax error
    #
    synerror = traceback.format_exc().splitlines()[-1]
    return line, __file__, synerror
#--------------------------------------------------------------------------
def _is_valid(value):
    """checks if the value is valid"""
    if isinstance(value, Point):
        if hasattr(value, 'x') and \
           hasattr(value, 'y') :
            return True
        elif 'x' in value and \
             (value['x'] is None or \
             value['x'] == "NaN"):
            return True
        return False
    elif isinstance(value, Envelope):
        if all(hasattr(value, a) for a in ('xmin', 'ymin',
                                           'xmax', 'ymax')) and \
           all(isinstance(getattr(value,a), number_type) for a in ('xmin', 'ymin',
                                                                   'xmax', 'ymax')):
            return True
        elif hasattr(value, "xmin") and \
           (value.xmin is None or value.xmin == "NaN"):
            return True
        else:
            return False
    elif isinstance(value, (MultiPoint,
                            Polygon,
                            Polyline)):
        if 'paths' in value:
            if len(value['paths']) == 0:
                return True
            else:
                return _is_line(coords=value['paths'])
        elif 'rings' in value:
            if len(value['rings']) == 0:
                return True
            else:
                return _is_polygon(coords=value['rings'])
        elif 'points' in value:
            if len(value['points']) == 0:
                return True
            else:
                return _is_point(coords=value['points'])
        return False
    else:
        return False
    return False
#--------------------------------------------------------------------------
def _is_polygon(coords):
    lengths = all(len(elem) >= 4 for elem in coords)
    valid_pts = all(_is_line(part) for part in coords)
    isring = all(elem[0] == elem[-1] for elem in coords)
    return lengths and isring and valid_pts
#--------------------------------------------------------------------------
def _is_line(coords):
    """
    checks to see if the line has at
    least 2 points in the list
    """
    if isinstance(coords, list_types) and \
       len(coords) > 0: # list of lists
        return all(_is_point(elem) for elem in coords)
    else:
        return True
    return False
#--------------------------------------------------------------------------
def _is_point(coords):
    """
    checks to see if the point has at
    least 2 coordinates in the list
    """
    if isinstance(coords, (list, tuple)) and \
       len(coords) > 1:
        for coord in coords:
            if isinstance(coord, number_type):
                return all(isinstance(v, number_type) for v in coords) and \
                       len(coords) > 1
            else:
                return _is_point(coord)
    return False
###########################################################################
class GeometryFactory(type):
    """
    Generates a geometry object from a given set of
    JSON (dictionary or iterable)
    """
    def __call__(cls, iterable=None, **kwargs):
        if iterable is None:
            iterable = ()
        if hasattr(iterable, 'JSON') and \
           (HASARCPY or HASSHAPELY):
            if type(iterable.JSON) == str:
                iterable = json.loads(iterable.JSON)
            elif type(iterable.JSON) == dict:
                iterable = iterable.JSON
        if cls is Geometry:
            if len(iterable) > 0:
                if isinstance(iterable, dict):
                    if 'x' in iterable and \
                       'y' in iterable:
                        return Point(iterable=iterable)
                    elif 'type' in iterable and \
                         'coordinates' in iterable:
                        if iterable['type'].lower() == "point":
                            return Point._from_geojson(data=iterable)
                        elif iterable['type'].lower() in ['polygon', 'multipolygon']:
                            return Polygon._from_geojson(iterable)
                        elif iterable['type'].lower() in ['linestring', 'multilinestring']:
                            return Polyline._from_geojson(iterable,
                                                          sr=None)
                        elif iterable['type'].lower() == "multipoint":
                            return MultiPoint._from_geojson(data=iterable)
                        else:
                            raise Exception("Invalid GeoJSON")
                    elif 'xmin' in iterable:
                        return Envelope(iterable)
                    elif 'wkt' in iterable or \
                         'wkid' in iterable:
                        return SpatialReference(iterable)
                    elif 'rings' in iterable:
                        return Polygon(iterable)
                    elif 'paths' in iterable:
                        return Polyline(iterable)
                    elif 'points' in iterable:
                        return MultiPoint(iterable)
            elif len(kwargs) > 0:
                if 'x' in kwargs or \
                   'y' in kwargs:
                    return Point(**kwargs)
                elif 'xmin' in kwargs:
                    return Envelope(iterable, **kwargs)
                elif 'wkt' in kwargs or \
                     'wkid' in kwargs:
                    return SpatialReference(**kwargs)
                elif 'rings' in kwargs:
                    return Polygon(**kwargs)
                elif 'paths' in kwargs:
                    return Polyline(**kwargs)
                elif 'points' in kwargs:
                    return MultiPoint(**kwargs)
        return type.__call__(cls, iterable, **kwargs)
###########################################################################
class BaseGeometry(dict):
    """base geometry class"""
    #----------------------------------------------------------------------
    @property
    def is_valid(self):
        """boolean to see if input  is valid"""
        return _is_valid(self)
    #----------------------------------------------------------------------
    def __getattr__(self, name):
        """
        dictionary items to be retrieved like object attributes
        :param name: attribute name
        :type name: str, int
        :return: dictionary value
        """
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    #----------------------------------------------------------------------
    def __setattr__(self, name, value):
        """
        dictionary items to be set like object attributes.
        :param name: key of item to be set
        :type name: str
        :param value: value to set item to
        """
        if name == 'spatial_reference':
            if isinstance(value, PropertyMap):
                value = dict(value)
            self['spatialReference'] = value
        else:
            self[name] = value
    #----------------------------------------------------------------------
    def __delattr__(self, name):
        """
        dictionary items to be deleted like object attributes
        :param name: key of item to be deleted
        :type name: str
        """

        del self[name]
###########################################################################
@add_metaclass(GeometryFactory)
class Geometry(BaseGeometry):
    """
    The base class for all geometries.

    You can create a Geometry even when you don't know the exact type. The Geometry constructor is able
    to figure out the geometry type and returns the correct type as the example below demonstrates:

    .. code-block:: python

        geom = Geometry({
          "rings" : [[[-97.06138,32.837],[-97.06133,32.836],[-97.06124,32.834],[-97.06127,32.832],
                      [-97.06138,32.837]],[[-97.06326,32.759],[-97.06298,32.755],[-97.06153,32.749],
                      [-97.06326,32.759]]],
          "spatialReference" : {"wkid" : 4326}
        })
        print (geom.type) # POLYGON
        print (isinstance(geom, Polygon) # True

    """
    def __init__(self, iterable=None, **kwargs):
        if iterable is None:
            iterable = ()
        super(Geometry, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    def __iter__(self):
        """
        """
        import numpy as np
        if isinstance(self, Polygon):
            avgs = []
            shape = 2
            for ring in self['rings']:
                a = np.array(ring)
                if a.shape[1] != shape:
                    shape = a.shape[1]
                avgs.append([np.array(ring)[:, 0].mean(), np.array(ring)[:,1].mean()])
            avgs = np.array(avgs)
            if shape == 2:
                res = [avgs[:,0].mean(),
                       avgs[:,1].mean()]
            elif shape > 2:
                res = [avgs[:,0].mean(),
                       avgs[:,1].mean(),
                       avgs[:,2].mean()]
            for a in res:
                yield a
                del a
        elif isinstance(self, Polyline):
            avgs = []
            shape = 2
            for ring in self['paths']:
                a = np.array(ring)
                if a.shape[1] != shape:
                    shape = a.shape[1]
                avgs.append([np.array(ring)[:, 0].mean(), np.array(ring)[:,1].mean()])
            avgs = np.array(avgs)
            if shape == 2:
                res = [avgs[:,0].mean(),
                       avgs[:,1].mean()]
            elif shape > 2:
                res = [avgs[:,0].mean(),
                       avgs[:,1].mean(),
                       avgs[:,2].mean()]
            for a in res:
                yield a
                del a
        elif isinstance(self, MultiPoint):
            a = np.array(self['points'])
            if a.shape[1] == 2:
                for i in [a[:,0].mean(),
                          a[:,1].mean()]:
                    yield i
            elif a.shape[1] >= 3: #has z
                for i in [a[:,0].mean(),
                          a[:,1].mean(),
                          a[:,2].mean()]:
                    yield i
        elif isinstance(self, Point):
            keys = ['x', 'y', 'z']
            for k in keys:
                if k in self:
                    yield self[k]
                del k
        elif isinstance(self, Envelope):
            for i in [(self['xmin'] + self['xmax'])/2,
                      (self['ymin'] + self['ymax'])/2]:
                yield i

    #----------------------------------------------------------------------
    @property
    def __geo_interface__(self):
        """converts an ESRI JSON to GeoJSON"""

        if HASARCPY:
            if isinstance(self.as_arcpy, arcpy.Point):
                return arcpy.PointGeometry(self.as_arcpy).__geo_interface__
            else:
                return self.as_arcpy.__geo_interface__
        else:
            if isinstance(self, Point):
                return {'type': 'Point', 'coordinates': (self.x,
                                                         self.y)}
            elif isinstance(self, Polygon):
                def split_part(a_part):
                    part_list = []
                    for item in a_part:
                        if item is None:
                            if part_list:
                                yield part_list
                            part_list = []
                        else:
                            part_list.append((item[0], item[1]))
                    if part_list:
                        yield part_list
                part_json = [list(split_part(part))
                             for part in self['rings']]
                return {'type': 'MultiPolygon', 'coordinates': part_json}
            elif isinstance(self, Polyline):
                return {'type': 'MultiLineString', 'coordinates': [[((pt[0], pt[1]) if pt else None)
                                                                    for pt in part]
                                                                   for part in self['paths']]}
            elif isinstance(self, MultiPoint):
                return {'type': 'Multipoint', 'coordinates': [(pt[0], pt[1]) for pt in self['points']]}
            from arcgis._impl.common._arcgis2geojson import arcgis2geojson
            return arcgis2geojson(arcgis=self)
        return {}

    #----------------------------------------------------------------------
    def _wkt(obj, fmt='%.16f'):
        """converts an arcgis.Geometry to WKT"""
        if isinstance(obj, Point):
            coords = [obj['x'], obj['y']]
            if 'z' in obj:
                coords.append(obj['z'])
            return "POINT (%s)" % ' '.join(fmt % c for c in coords)
        elif isinstance(obj, Polygon):
            coords = obj['rings']
            pt2 = []
            b = "MULTIPOLYGON (%s)"
            for part in coords:
                c2 = []
                for c in part:
                    c2.append("(%s,  %s)" % (fmt % c[0], fmt % c[1]))
                j = "(%s)" % ", ".join(c2)
                pt2.append(j)
            b = b % ", ".join(pt2)
            return b
        elif isinstance(obj, Polyline):
            coords = obj['paths']
            pt2 = []
            b = "MULTILINESTRING (%s)"
            for part in coords:
                c2 = []
                for c in part:
                    c2.append("(%s,  %s)" % (fmt % c[0], fmt % c[1]))
                j = "(%s)" % ", ".join(c2)
                pt2.append(j)
            b = b % ", ".join(pt2)
            return b
        elif isinstance(obj, MultiPoint):
            coords = obj['points']
            b = "MULTIPOINT (%s)"
            c2 = []
            for c in coords:
                c2.append("(%s,  %s)" % (fmt % c[0], fmt % c[1]))
            return b % ", ".join(c2)
        return ""
    #----------------------------------------------------------------------
    @property
    def geoextent(self):
        """
        Returns the current feature's extent
        """
        import numpy as np
        if hasattr(self, 'type'):
            if str(self.type).upper() == "POLYGON":
                a = self['rings']
            elif str(self.type).upper() == "POLYLINE":
                a = self['paths']
            elif str(self.type).upper() == "MULTIPOINT":
                a = self['points']
                x_max = max(np.array(a)[:,0])
                x_min = min(np.array(a)[:,0])
                y_min = min(np.array(a)[:,1])
                y_max = max(np.array(a)[:,1])
                return x_min, y_min, x_max, y_max
            elif str(self.type).upper() == "POINT":
                return self['x'], self['y'], self['x'],  self['y']
            else:
                return None
            if len(a) == 0:
                return None
            elif len(a) > 1: # single part
                x_max = max(a[0], key=lambda x: x[0])[0]
                x_min = min(a[0], key=lambda x: x[0])[0]
                y_max = max(a[0], key=lambda x: x[1])[1]
                y_min = min(a[0], key=lambda x: x[1])[1]
                return x_min, y_min, x_max, y_max
            else:
                xs = []
                ys = []
                for pt in a: # multiple part geometry
                    x_max = max(pt, key=lambda x: x[0])[0]
                    x_min = min(pt, key=lambda x: x[0])[0]
                    y_max = max(pt, key=lambda x: x[1])[1]
                    y_min = min(pt, key=lambda x: x[1])[1]
                    xs.append(x_max)
                    xs.append(x_min)
                    ys.append(y_max)
                    ys.append(y_min)
                    del pt
                return min(xs), min(ys), max(xs), max(ys)
        return None
    #----------------------------------------------------------------------
    def skew(self, x_angle=0,
             y_angle=0, inplace=False):
        from .affine import skew
        if inplace:
            self = skew(geom=self, x_angle=45, y_angle=-20)
            return self
        return skew(geom=self, x_angle=45, y_angle=-20)
    #----------------------------------------------------------------------
    def rotate(self, theta,
               inplace=False):
        """rotates a shape by some degree theta"""
        from .affine import rotate
        r = rotate(self, theta)
        if inplace:
            self = r
        return r
    #----------------------------------------------------------------------
    def scale(self, x_scale=1, y_scale=1, inplace=False):
        """scales in either the x,y or both directions"""
        from .affine import scale
        g = copy.copy(self)
        s = scale(g, *(x_scale, y_scale))
        if inplace:
            self = s
        return s
    #----------------------------------------------------------------------
    def translate(self, x_offset=0,
                  y_offset=0, inplace=False):
        """moves a geometry in a given x and y distance"""
        from .affine import translate
        t = translate(self, x_offset, y_offset)
        if inplace:
            self = t
        return t
    #----------------------------------------------------------------------
    @property
    def is_empty(self):
        """boolean value that determines if the geometry is empty or not"""
        if isinstance(self, Point):
            return False
        elif isinstance(self, Polygon):
            return len(self['rings']) == 0
        elif isinstance(self, Polyline):
            return len(self['paths']) == 0
        elif isinstance(self, MultiPoint):
            return len(self['points']) == 0
        return True
    #----------------------------------------------------------------------
    @property
    def as_arcpy(self):
        """returns the arcpy.Geometry object"""
        if HASARCPY:
            esri_json = True
            if 'coordinates' in self:
                esri_json = False
            if isinstance(self, Envelope):
                if 'spatialReference' in self:
                    sr = arcpy.SpatialReference(self['spatialReference']['wkid'])
                    return arcpy.Extent(XMax=self['xmax'],
                                 YMax=self['ymax'],
                                 YMin=self['ymin'],
                                 XMin=self['xmin']).projectAs(sr)
                return arcpy.Extent(XMax=self['xmax'],
                                    YMax=self['ymax'],
                                    YMin=self['ymin'],
                                    XMin=self['xmin'])
            return arcpy.AsShape(self, esri_json)
        return None
    #----------------------------------------------------------------------
    @property
    def as_shapely(self):
        """returns a shapely geometry object"""
        if HASSHAPELY:
            if isinstance(self,(Point, Polygon, Polyline, MultiPoint)):
                from shapely.geometry import shape
                return shape(self.__geo_interface__)
        return None
    #----------------------------------------------------------------------
    @property
    def JSON(self):
        """"""
        if HASARCPY and \
           isinstance(self.as_arcpy, arcpy.Geometry):
            return getattr(self.as_arcpy, "JSON", None)
        elif HASSHAPELY:
            try:
                return self.as_shapely.__geo_interface__
            except:
                return json.dumps(self)
        else:
            return json.dumps(self)
        return
    #----------------------------------------------------------------------
    @property
    def WKT(self):
        """
        Returns the well-known text (WKT) representation for OGC geometry.
        It provides a portable representation of a geometry value as a text
        string.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "WKT", None)
        elif HASSHAPELY:
            try:
                return self.as_shapely.wkt
            except:
                return self._wkt(fmt='%.16f')
        else:
            return self._wkt(fmt='%.16f')
        return
    #----------------------------------------------------------------------
    @property
    def WKB(self):
        """
        Returns the well-known binary (WKB) representation for OGC geometry.
        It provides a portable representation of a geometry value as a
        contiguous stream of bytes.
        """
        if HASARCPY:
            try:
                return getattr(self.as_arcpy, "WKB", None)
            except:
                return None
        elif HASSHAPELY:
            try:
                return self.as_shapely.wkb
            except:
                return None
        return None
    #----------------------------------------------------------------------
    @property
    def area(self):
        """
        The area of a polygon feature. Empty for all other feature types.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "area", None)
        elif HASSHAPELY:
            return self.as_shapely.area
        elif isinstance(self, Polygon):
            return self._shoelace_area(parts=self['rings'])
        return None
    #----------------------------------------------------------------------
    def _shoelace_area(self, parts):
        """calculates the shoelace area"""
        area = 0.0
        area_parts = []
        for part in parts:
            n = len(part)
            for i in range(n):
                j = (i + 1) % n

                area += part[i][0] * part[j][1]
                area -= part[j][0] * part[i][1]
                # print((n, area, i, j))
            area_parts.append(area / 2.0)
            area = 0.0
        return sum(area_parts)
    #----------------------------------------------------------------------
    @property
    def centroid(self):
        """
        Returns the center of the geometry

        :returns: a arcgis.geometry.Point
        """
        if HASARCPY:
            if isinstance(self, Point):
                return tuple(self)
            else:
                return tuple(Geometry(
                    arcpy.PointGeometry(
                    getattr(self.as_arcpy, "centroid", None),
                    self.spatial_reference)
                                ))
        elif HASSHAPELY:
            c = tuple(list(self.as_shapely.centroid.coords)[0])
            return c
        return
    #----------------------------------------------------------------------
    @property
    def extent(self):
        """
        The extent of the geometry.
        """
        ptX = []
        ptY = []
        if HASARCPY:
            return getattr(self.as_arcpy, "extent", None)
        elif HASSHAPELY:
            return self.as_shapely.bounds
        elif isinstance(self, Polygon):
            for pts in self['rings']:
                for part in pts:
                    ptX.append(part[0])
                    ptY.append(part[1])
            return min(ptX), min(ptY), max(ptX), max(ptY)

        elif isinstance(self, Polyline):
            for pts in self['paths']:
                for part in pts:
                    ptX.append(part[0])
                    ptY.append(part[1])
            return min(ptX), min(ptY), max(ptX), max(ptY)
        elif isinstance(self, MultiPoint):
            ptX = [ pt['x'] for pt in self['points']]
            ptY = [ pt['y'] for pt in self['points']]
            return min(ptX), min(ptY), max(ptX), max(ptY)
        elif isinstance(self, Point):
            return self['x'], self['y'], self['x'], self['y']
        return
    #----------------------------------------------------------------------
    @property
    def first_point(self):
        """
        The first coordinate point of the geometry.
        """
        if HASARCPY:
            return Geometry(json.loads(arcpy.PointGeometry(getattr(
                self.as_arcpy,
                "firstPoint",
                None), self.spatial_reference).JSON))
        elif isinstance(self, Point):
            return self
        elif isinstance(self, MultiPoint):
            if len(self['points']) == 0:
                return
            geom = self['points'][0]
            return Geometry(
                {'x': geom[0], 'y': geom[1],
                 'spatialReference' : {'wkid' : 4326}}
            )
        elif isinstance(self, Polygon):
            if len(self['rings']) == 0:
                return
            geom = self['rings'][0][0]
            return Geometry(
                {'x': geom[0], 'y': geom[1],
                 'spatialReference' : {'wkid' : 4326}}
            )
        elif isinstance(self, Polyline):
            if len(self['paths']) == 0:
                return
            geom = self['paths'][0][0]
            return Geometry(
                {'x': geom[0], 'y': geom[1],
                 'spatialReference' : {'wkid' : 4326}}
            )
        return
    #----------------------------------------------------------------------
    @property
    def hull_rectangle(self):
        """
        A space-delimited string of the coordinate pairs of the convex hull
        rectangle.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "hullRectangle", None)
        elif HASSHAPELY:
            return self.as_shapely.convex_hull
        return
    #----------------------------------------------------------------------
    @property
    def is_multipart(self):
        """
        True, if the number of parts for this geometry is more than one.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "isMultipart", None)
        elif HASSHAPELY:
            if self.type.lower().find("multi") > -1:
                return True
            else:
                return False
        return
    #----------------------------------------------------------------------
    @property
    def label_point(self):
        """
        The point at which the label is located. The label_point is always
        located within or on a feature.

        :returns: arcgis.geometry.Point
        """
        if HASARCPY:
            return Geometry(arcpy.PointGeometry(getattr(self.as_arcpy, "labelPoint", None),
                                       self.spatial_reference))
        else:
            return self.centroid
        return
    #----------------------------------------------------------------------
    @property
    def last_point(self):
        """
        The last coordinate of the feature.

        :returns: arcgis.geometry.Point
        """
        if HASARCPY:
            return Geometry(arcpy.PointGeometry(getattr(self.as_arcpy, "lastPoint", None),
                                       self.spatial_reference))
        elif isinstance(self, Point):
            return self
        elif isinstance(self, Polygon):
            if self['rings'] == 0:
                return
            geom = self['rings'][-1][-1]
            return Geometry(
                {'x': geom[0], 'y': geom[1],
                 'spatialReference' : {'wkid' : 4326}}
            )
        elif isinstance(self, Polyline):
            if self['paths'] == 0:
                return
            geom = self['paths'][-1][-1]
            return Geometry(
                {'x': geom[0], 'y': geom[1],
                 'spatialReference' : {'wkid' : 4326}}
            )
        return
    #----------------------------------------------------------------------
    @property
    def length(self):
        """
        The length of the linear feature. Zero for point and multipoint feature types.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "length", None)
        elif HASSHAPELY:
            return self.as_shapely.length
        else:
            return None
    #----------------------------------------------------------------------
    @property
    def length3D(self):
        """
        The 3D length of the linear feature. Zero for point and multipoint
        feature types.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "length3D", None)
        elif HASSHAPELY:
            return self.as_shapely.length
        else:
            return self.length
        return
    #----------------------------------------------------------------------
    @property
    def part_count(self):
        """
        The number of geometry parts for the feature.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "partCount", None)
        elif isinstance(self, Polygon):
            return len(self['rings'])
        elif isinstance(self, Polyline):
            return len(self['paths'])
        elif isinstance(self, MultiPoint):
            return len(self['points'])
        elif isinstance(self, Point):
            return 1
        return
    #----------------------------------------------------------------------
    @property
    def point_count(self):
        """
        The total number of points for the feature.
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "pointCount", None)
        elif isinstance(self, Polygon):
            return sum([len(part) for part in self['rings']])
        elif isinstance(self, Polyline):
            return sum([len(part) for part in self['paths']])
        elif isinstance(self, MultiPoint):
            return sum([len(part) for part in self['points']])
        elif isinstance(self, Point):
            return 1
        return
    #----------------------------------------------------------------------
    @property
    def spatial_reference(self):
        """
        The spatial reference of the geometry.
        """
        if HASARCPY:
            return SpatialReference(self['spatialReference']).as_arcpy
        if 'spatialReference' in self:
            return SpatialReference(self['spatialReference'])
        return None
    #----------------------------------------------------------------------
    @property
    def true_centroid(self):
        """
        The center of gravity for a feature.

        :returns: arcgis.geometry.Point
        """
        if HASARCPY:
            return Geometry(arcpy.PointGeometry(getattr(self.as_arcpy, "trueCentroid", None),
                                                self.spatial_reference))
        elif HASSHAPELY:
            return self.centroid
        elif isinstance(self, Point):
            return self
        return
    #----------------------------------------------------------------------
    @property
    def geometry_type(self):
        """
        The geometry type: polygon, polyline, point, multipoint

        :returns: string
        """
        if HASARCPY:
            return getattr(self.as_arcpy, "type", None)
        elif isinstance(self, Geometry):
            return self.type
        return
    #Functions#############################################################
    #----------------------------------------------------------------------
    def angle_distance_to(self, second_geometry, method="GEODESIC"):
        """
        Returns a tuple of angle and distance to another point using a
        measurement type.

        Paramters:
         :second_geometry: - a second geometry
         :method: - PLANAR measurements reflect the projection of geographic
          data onto the 2D surface (in other words, they will not take into
          account the curvature of the earth). GEODESIC, GREAT_ELLIPTIC,
          LOXODROME, and PRESERVE_SHAPE measurement types may be chosen as
          an alternative, if desired.
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.angleAndDistanceTo(other_geometry=second_geometry,
                                                    method=method)
        return None
    #----------------------------------------------------------------------
    def boundary(self):
        """
        Constructs the boundary of the geometry.

        """
        if HASARCPY:
            return Geometry(self.as_arcpy.boundary())
        elif HASSHAPELY:
            return Geometry(self.as_shapely.boundary.buffer(1).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def buffer(self, distance):
        """
        Constructs a polygon at a specified distance from the geometry.

        Parameters:
         :distance: - length in current projection.  Only polygon accept
          negative values.
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.buffer(distance))
        elif HASSHAPELY:
            return Geometry(self.as_shapely.buffer(
                distance).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def clip(self, envelope):
        """
        Constructs the intersection of the geometry and the specified extent.

        Parameters:
         :envelope: - arcpy.Extent object
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.clip(envelope))
        return None
    #----------------------------------------------------------------------
    def contains(self, second_geometry, relation=None):
        """
        Indicates if the base geometry contains the comparison geometry.

        Paramters:
         :second_geometry: - a second geometry
        Returns:
         Boolean
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.contains(second_geometry=second_geometry,
                                   relation=relation)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.contains(second_geometry)
        return None
    #----------------------------------------------------------------------
    def convex_hull(self):
        """
        Constructs the geometry that is the minimal bounding polygon such
        that all outer angles are convex.
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.convexHull())
        elif self.type.lower() == "polygon":
            from ._convexhull import convex_hull
            combine_pts = [pt for part in self['rings'] for pt in part]
            return convex_hull(pts=combine_pts)
        elif self.type.lower() == "polyline":
            from ._convexhull import convex_hull
            combine_pts = [pt for part in self['paths'] for pt in part]
            return convex_hull(pts=combine_pts)
        elif self.type.lower() == "multipoint":
            from ._convexhull import convex_hull
            combine_pts = self['points']
            return convex_hull(pts=combine_pts)
        return None
    #----------------------------------------------------------------------
    def crosses(self, second_geometry):
        """
        Indicates if the two geometries intersect in a geometry of a lesser
        shape type.


        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.crosses(second_geometry=second_geometry)
        elif HASSHAPELY:
            return self.as_shapely.crosses(other=second_geometry.as_shapely)
        return None
    #----------------------------------------------------------------------
    def cut(self, cutter):
        """
        Splits this geometry into a part left of the cutting polyline, and
        a part right of it.

        Parameters:
         :cutter: - The cutting polyline geometry.
        """
        if isinstance(cutter, Polyline) and HASARCPY:
            if isinstance(cutter, Geometry):
                cutter = cutter.as_arcpy
            return Geometry(self.as_arcpy.cut(other=cutter))
        return None
    #----------------------------------------------------------------------
    def densify(self, method, distance, deviation):
        """
        Creates a new geometry with added vertices

        Parameters:
         :method: - The type of densification, DISTANCE, ANGLE, or GEODESIC
         :distance: - The maximum distance between vertices. The actual
          distance between vertices will usually be less than the maximum
          distance as new vertices will be evenly distributed along the
          original segment. If using a type of DISTANCE or ANGLE, the
          distance is measured in the units of the geometry's spatial
          reference. If using a type of GEODESIC, the distance is measured
          in meters.
         :deviation: - Densify uses straight lines to approximate curves.
          You use deviation to control the accuracy of this approximation.
          The deviation is the maximum distance between the new segment and
          the original curve. The smaller its value, the more segments will
          be required to approximate the curve.
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.densify(method=method,
                                         distance=distance,
                                         deviation=deviation))
        return None
    #----------------------------------------------------------------------
    def difference(self, second_geometry):
        """
        Constructs the geometry that is composed only of the region unique
        to the base geometry but not part of the other geometry. The
        following illustration shows the results when the red polygon is the
        source geometry.

        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return Geometry(self.as_arcpy.difference(other=second_geometry))
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return Geometry(self.as_shapely.difference(second_geometry).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def disjoint(self, second_geometry):
        """
        Indicates if the base and comparison geometries share no points in
        common.

        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.disjoint(second_geometry=second_geometry)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.disjoint(second_geometry)
        return None
    #----------------------------------------------------------------------
    def distance_to(self, second_geometry):
        """
        Returns the minimum distance between two geometries. If the
        geometries intersect, the minimum distance is 0.
        Both geometries must have the same projection.

        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.distanceTo(other=second_geometry)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.distance(other=second_geometry)
        return None
    #----------------------------------------------------------------------
    def equals(self, second_geometry):
        """
        Indicates if the base and comparison geometries are of the same
        shape type and define the same set of points in the plane. This is
        a 2D comparison only; M and Z values are ignored.
        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.equals(second_geometry=second_geometry)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.equals(other=second_geometry)
        return None
    #----------------------------------------------------------------------
    def generalize(self, max_offset):
        """
        Creates a new simplified geometry using a specified maximum offset
        tolerance.

        Parameters:
         :max_offset: - The maximum offset tolerance.
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.generalize(distance=max_offset))
        elif HASSHAPELY:

            return Geometry(self.as_shapely.simplify(
                max_offset).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def get_area(self, method, units=None):
        """
        Returns the area of the feature using a measurement type.

        Parameters:
         :method: - PLANAR measurements reflect the projection of
          geographic data onto the 2D surface (in other words, they will not
          take into account the curvature of the earth). GEODESIC,
          GREAT_ELLIPTIC, LOXODROME, and PRESERVE_SHAPE measurement types
          may be chosen as an alternative, if desired.
         :units: - Areal unit of measure keywords: ACRES | ARES | HECTARES
          | SQUARECENTIMETERS | SQUAREDECIMETERS | SQUAREINCHES | SQUAREFEET
          | SQUAREKILOMETERS | SQUAREMETERS | SQUAREMILES |
          SQUAREMILLIMETERS | SQUAREYARDS

        """
        if HASARCPY:
            return self.as_arcpy.getArea(method=method,
                                         units=units)
        return None
    #----------------------------------------------------------------------
    def get_length(self, method, units):
        """
        Returns the length of the feature using a measurement type.

        Parameters:
         :method: - PLANAR measurements reflect the projection of
          geographic data onto the 2D surface (in other words, they will not
          take into account the curvature of the earth). GEODESIC,
          GREAT_ELLIPTIC, LOXODROME, and PRESERVE_SHAPE measurement types
          may be chosen as an alternative, if desired.
         :units: - Linear unit of measure keywords: CENTIMETERS |
          DECIMETERS | FEET | INCHES | KILOMETERS | METERS | MILES |
          MILLIMETERS | NAUTICALMILES | YARDS

        """
        if HASARCPY:
            return self.as_arcpy.getLength(method=method,
                                         units=units)
        return None
    #----------------------------------------------------------------------
    def get_part(self, index=None):
        """
        Returns an array of point objects for a particular part of geometry
        or an array containing a number of arrays, one for each part.

        Parameters:
         :index: - The index position of the geometry.
        """
        if HASARCPY:
            return self.as_arcpy.getPart(index)
        return None
    #----------------------------------------------------------------------
    def intersect(self, second_geometry, dimension=1):
        """
        Constructs a geometry that is the geometric intersection of the two
        input geometries. Different dimension values can be used to create
        different shape types. The intersection of two geometries of the
        same shape type is a geometry containing only the regions of overlap
        between the original geometries.

        Paramters:
         :second_geometry: - a second geometry
         :dimension: - The topological dimension (shape type) of the
          resulting geometry.
            1  -A zero-dimensional geometry (point or multipoint).
            2  -A one-dimensional geometry (polyline).
            4  -A two-dimensional geometry (polygon).

        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.intersect(other=second_geometry,
                                           dimension=dimension)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return Geometry(self.as_shapely.intersection(
                other=second_geometry).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def measure_on_line(self, second_geometry, as_percentage=False):
        """
        Returns a measure from the start point of this line to the in_point.

        Paramters:
         :second_geometry: - a second geometry
         :as_percentage: - If False, the measure will be returned as a
          distance; if True, the measure will be returned as a percentage.
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.measureOnLine(in_point=second_geometry,
                                               use_percentage=as_percentage)
        return None
    #----------------------------------------------------------------------
    def overlaps(self, second_geometry):
        """
        Indicates if the intersection of the two geometries has the same
        shape type as one of the input geometries and is not equivalent to
        either of the input geometries.


        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.overlaps(second_geometry=second_geometry)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.overlaps(other=second_geometry)
        return None
    #----------------------------------------------------------------------
    def point_from_angle_and_distance(self, angle, distance, method='GEODESCIC'):
        """
        Returns a point at a given angle and distance in degrees and meters
        using the specified measurement type.

        Parameters:
         :angle: - The angle in degrees to the returned point.
         :distance: - The distance in meters to the returned point.
         :method: - PLANAR measurements reflect the projection of geographic
          data onto the 2D surface (in other words, they will not take into
          account the curvature of the earth). GEODESIC, GREAT_ELLIPTIC,
          LOXODROME, and PRESERVE_SHAPE measurement types may be chosen as
          an alternative, if desired.
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.pointFromAngleAndDistance(angle=angle,
                                                    distance=distance,
                                                    method=method))
        return None
    #----------------------------------------------------------------------
    def position_along_line(self, value, use_percentage=False):
        """
        Returns a point on a line at a specified distance from the beginning
        of the line.

        Parameters:
         :value: - The distance along the line.
         :use_percentage: - The distance may be specified as a fixed unit
          of measure or a ratio of the length of the line. If True, value
          is used as a percentage; if False, value is used as a distance.
          For percentages, the value should be expressed as a double from
          0.0 (0%) to 1.0 (100%).
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.positionAlongLine(value=value,
                                                  use_percentage=use_percentage))
        return None
    #----------------------------------------------------------------------
    def project_as(self, spatial_reference, transformation_name=None):
        """
        Projects a geometry and optionally applies a geotransformation.


        Parameter:
         :spatial_reference: - The new spatial reference. This can be a
          SpatialReference object or the coordinate system name.
         :transformation_name: - The geotransformation name.
        """
        from six import string_types, integer_types
        if HASARCPY:
            if isinstance(spatial_reference, SpatialReference):
                spatial_reference = spatial_reference.as_arcpy
            elif isinstance(spatial_reference, arcpy.SpatialReference):
                spatial_reference = spatial_reference
            elif isinstance(spatial_reference, integer_types):
                spatial_reference = arcpy.SpatialReference(spatial_reference)
            elif isinstance(spatial_reference, string_types):
                spatial_reference = arcpy.SpatialReference(
                    text=spatial_reference)
            else:
                raise ValueError("Invalid spatial reference object.")
            return Geometry(self.as_arcpy.projectAs(spatial_reference=spatial_reference,
                                                    transformation_name=transformation_name))
        return None
    #----------------------------------------------------------------------
    def query_point_and_distance(self, second_geometry,
                              use_percentage=False):
        """
        Finds the point on the polyline nearest to the in_point and the
        distance between those points. Also returns information about the
        side of the line the in_point is on as well as the distance along
        the line where the nearest point occurs.

        Paramters:
         :second_geometry: - a second geometry
         :as_percentage: - if False, the measure will be returned as
          distance, True, measure will be a percentage
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.queryPointAndDistance(in_point=second_geometry,
                                                       use_percentage=use_percentage)
        return None
    #----------------------------------------------------------------------
    def segment_along_line(self, start_measure,
                         end_measure, use_percentage=False):
        """
        Returns a Polyline between start and end measures. Similar to
        Polyline.positionAlongLine but will return a polyline segment between
        two points on the polyline instead of a single point.

        Parameters:
         :start_measure: - The starting distance from the beginning of the
          line.
         :end_measure: - The ending distance from the beginning of the
          line.
         :use_percentage: - The start and end measures may be specified as
          fixed units or as a ratio. If True, start_measure and end_measure
          are used as a percentage; if False, start_measure and end_measure
          are used as a distance. For percentages, the measures should be
          expressed as a double from 0.0 (0 percent) to 1.0 (100 percent).
        """
        if HASARCPY:
            return Geometry(self.as_arcpy.segmentAlongLine(
                start_measure=start_measure,
                end_measure=end_measure,
                use_percentage=use_percentage))
        return None
    #----------------------------------------------------------------------
    def snap_to_line(self, second_geometry):
        """
        Returns a new point based on in_point snapped to this geometry.

        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return Geometry(self.as_arcpy.snapToLine(in_point=second_geometry))
        return None
    #----------------------------------------------------------------------
    def symmetric_difference (self, second_geometry):
        """
        Returns a new point based on in_point snapped to this geometry.

        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return Geometry(self.as_arcpy.symmetricDifference(other=second_geometry))
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return Geometry(self.as_shapely.symmetric_difference(
                other=second_geometry).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def touches(self, second_geometry):
        """
        Indicates if the boundaries of the geometries intersect.


        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.touches(second_geometry=second_geometry)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.touches(second_geometry)
        return None
    #----------------------------------------------------------------------
    def union(self, second_geometry):
        """
        Constructs the geometry that is the set-theoretic union of the input
        geometries.


        Paramters:
         :second_geometry: - a second geometry
        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return Geometry(self.as_arcpy.union(other=second_geometry))
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return Geometry(self.as_shapely.union(
                second_geometry).__geo_interface__)
        return None
    #----------------------------------------------------------------------
    def within(self, second_geometry, relation=None):
        """
        Indicates if the base geometry is within the comparison geometry.
        Paramters:
         :second_geometry: - a second geometry
         :relation: - The spatial relationship type.
          BOUNDARY  - Relationship has no restrictions for interiors or boundaries.
          CLEMENTINI  - Interiors of geometries must intersect. Specifying CLEMENTINI is equivalent to specifying None. This is the default.
          PROPER  - Boundaries of geometries must not intersect.

        """
        if HASARCPY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_arcpy
            return self.as_arcpy.within(second_geometry=second_geometry,
                                        relation=relation)
        elif HASSHAPELY:
            if isinstance(second_geometry, Geometry):
                second_geometry = second_geometry.as_shapely
            return self.as_shapely.within(second_geometry)
        return None
###########################################################################
class SpatialReference(Geometry):
    """
    A spatial reference can be defined using a well-known ID (wkid) or
    well-known text (wkt). The default tolerance and resolution values for
    the associated coordinate system are used. The xy and z tolerance
    values are 1 mm or the equivalent in the unit of the coordinate system.
    If the coordinate system uses feet, the tolerance is 0.00328083333 ft.
    The resolution values are 10x smaller or 1/10 the tolerance values.
    Thus, 0.0001 m or 0.0003280833333 ft. For geographic coordinate systems
    using degrees, the equivalent of a mm at the equator is used.
    The well-known ID (WKID) for a given spatial reference can occasionally
    change. For example, the WGS 1984 Web Mercator (Auxiliary Sphere)
    projection was originally assigned WKID 102100, but was later changed
    to 3857. To ensure backward compatibility with older spatial data
    servers, the JSON wkid property will always be the value that was
    originally assigned to an SR when it was created.
    An additional property, latestWkid, identifies the current WKID value
    (as of a given software release) associated with the same spatial
    reference.
    A spatial reference can optionally include a definition for a vertical
    coordinate system (VCS), which is used to interpret the z-values of a
    geometry. A VCS defines units of measure, the location of z = 0, and
    whether the positive vertical direction is up or down. When a vertical
    coordinate system is specified with a WKID, the same caveat as
    mentioned above applies. There are two VCS WKID properties: vcsWkid and
    latestVcsWkid. A VCS WKT can also be embedded in the string value of
    the wkt property. In other words, the WKT syntax can be used to define
    an SR with both horizontal and vertical components in one string. If
    either part of an SR is custom, the entire SR will be serialized with
    only the wkt property.
    Starting at 10.3, Image Service supports image coordinate systems.
    """
    _type = "SpatialReference"
    def __init__(self,
                 iterable=None,
                 **kwargs):
        if iterable is None:
            iterable = ()
        super(SpatialReference, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    @property
    def as_arcpy(self):
        """returns the class as an arcpy SpatialReference object"""
        if HASARCPY:
            if 'wkid' in self:
                return arcpy.SpatialReference(self['wkid'])
            elif 'wkt' in self:
                sr = arcpy.SpatialReference()
                sr.loadFromString(self['wkt'])
                return sr
        return None
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = SpatialReference(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
###########################################################################
class Envelope(Geometry):
    """
    An envelope is a rectangle defined by a range of values for each
    coordinate and attribute. It also has a spatialReference field. The
    fields for the z and m ranges are optional. An empty envelope has no
    in space and is defined by the presence of an xmin field a null value
    or a "NaN" string.
    """
    _type = "Envelope"
    def __init__(self, iterable=None, **kwargs):
        if iterable is None:
            iterable = ()
        super(Envelope, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    def coordinates(self):
        """returns the coordinates as a np.array"""
        import numpy as np
        if 'xmin' in self and \
           'xmax' in self and \
           'ymin' in self and \
           'ymax' in self:
            if 'zmin' in self and 'zmax' in self:
                return np.array([self['xmin'], self['ymin'], self['zmin'],
                                 self['xmax'], self['ymax'], self['zmax']])
            return np.array([self['xmin'], self['ymin'], self['xmax'], self['ymax']])
        else:
            return np.array([])
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = Evelope(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
###########################################################################
class Point(Geometry):
    """
    A point contains x and y fields along with a spatialReference field. A
    point can also contain m and z fields. A point is empty when its x
    field is present and has the value null or the string "NaN". An empty
    point has no location in space.
    """
    _type = "Point"
    def __init__(self, iterable=None, **kwargs):
        if iterable is None:
            iterable = ()
        super(Point, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = Point(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
    #----------------------------------------------------------------------
    def coordinates(self):
        """returns the coordinates as a np.array"""
        import numpy as np
        if 'x' in self and 'y' in self and 'z' in self:
            return np.array([self['x'], self['y'], self['z']])
        elif 'x' in self and 'y' in self:
            return np.array([self['x'], self['y']])
        else:
            return np.array([])
    @classmethod
    def _from_geojson(cls, data, sr=None):
        if sr == None:
            sr = {'wkid' : 4326}
        coordkey = ([d for d in data if d.lower() == 'coordinates']
                     or ['coordinates']).pop()
        coordinates = data[coordkey]

        return cls({
            "x" : coordinates[0],
            "y" : coordinates[1],
            "spatialReference" : sr
        })

###########################################################################
class MultiPoint(Geometry):
    """
    A multipoint contains an array of points, along with a spatialReference
    field. A multipoint can also have boolean-valued hasZ and hasM fields.
    These fields control the interpretation of elements of the points
    array. Omitting an hasZ or hasM field is equivalent to setting it to
    false.
    Each element of the points array is itself an array of two, three, or
    four numbers. It will have two elements for 2D points, two or three
    elements for 2D points with Ms, three elements for 3D points, and three
    or four elements for 3D points with Ms. In all cases, the x coordinate
    is at index 0 of a point's array, and the y coordinate is at index 1.
    For 2D points with Ms, the m coordinate, if present, is at index 2. For
    3D points, the Z coordinate is required and is at index 2. For 3D
    points with Ms, the Z coordinate is at index 2, and the M coordinate,
    if present, is at index 3.
    An empty multipoint has a points field with no elements. Empty points
    are ignored.
    """
    _type = "Multipoint"
    def __init__(self, iterable=None,
                 **kwargs):
        if iterable is None:
            iterable = ()
        super(MultiPoint, self).__init__(iterable)
        self.update(kwargs)
    @property
    def __geo_interface__(self):
        return {'type': 'Multipoint', 'coordinates': [(pt[0], pt[1]) for pt in self['points']]}
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    def coordinates(self):
        """returns the coordinates as a np.array"""
        import numpy as np
        if 'points' in self:
            return np.array(self['points'])
        else:
            return np.array([])
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = MultiPoint(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
    #----------------------------------------------------------------------
    @classmethod
    def _from_geojson(cls, data, sr=None):
        if sr is None:
            sr = {'wkid' : 4326}
        coordkey = ([d for d in data if d.lower() == 'coordinates']
                     or ['coordinates']).pop()
        coordinates = data[coordkey]
        return cls({'points' : [p for p in coordinates],
                    'spatialReference' : sr})
###########################################################################
class Polyline(Geometry):
    """
    A polyline contains an array of paths or curvePaths and a
    spatialReference. For polylines with curvePaths, see the sections on
    JSON curve object and Polyline with curve. Each path is represented as
    an array of points, and each point in the path is represented as an
    array of numbers. A polyline can also have boolean-valued hasM and hasZ
    fields.
    See the description of multipoints for details on how the point arrays
    are interpreted.
    An empty polyline is represented with an empty array for the paths
    field. Nulls and/or NaNs embedded in an otherwise defined coordinate
    stream for polylines/polygons is a syntax error.
    """
    _type = "Polyline"
    def __init__(self, iterable=None,
                 **kwargs):
        if iterable is None:
            iterable = ()
        super(Polyline, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    def coordinates(self):
        """returns the coordinates as a np.array"""
        import numpy as np
        if 'paths' in self:
            return np.array(self['paths'])
        else:
            return np.array([])
    #----------------------------------------------------------------------
    @property
    def __geo_interface__(self):
        return {'type': 'MultiLineString', 'coordinates': [[((pt[0], pt[1]) if pt else None)
                                                                for pt in part]
                                                                    for part in self['paths']]}
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = Polyline(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
    @classmethod
    def _from_geojson(cls, data, sr=None):
        if sr is None:
            sr = {'wkid' : 4326}
        coordkey = ([d for d in data if d.lower() == 'coordinates']
                     or ['coordinates']).pop()
        if data['type'].lower() == 'linestring':
            coordinates = [data[coordkey]]
        else:
            coordinates = data[coordkey]
        return cls(
            {'paths' : [[p for p in part] for part in coordinates],
             'spatialReference' : sr
             })
###########################################################################
class Polygon(Geometry):
    """
    A polygon contains an array of rings or curveRings and a
    spatialReference. For polygons with curveRings, see the sections on
    JSON curve object and Polygon with curve. Each ring is represented as
    an array of points. The first point of each ring is always the same as
    the last point. Each point in the ring is represented as an array of
    numbers. A polygon can also have boolean-valued hasM and hasZ fields.

    An empty polygon is represented with an empty array for the rings
    field. Nulls and/or NaNs embedded in an otherwise defined coordinate
    stream for polylines/polygons is a syntax error.
    Polygons should be topologically simple. Exterior rings are oriented
    clockwise, while holes are oriented counter-clockwise. Rings can touch
    at a vertex or self-touch at a vertex, but there should be no other
    intersections. Polygons returned by services are topologically simple.
    When drawing a polygon, use the even-odd fill rule. The even-odd fill
    rule will guarantee that the polygon will draw correctly even if the
    ring orientation is not as described above.
    """
    _type = "Polygon"
    def __init__(self, iterable=None,
                 **kwargs):
        if iterable is None:
            iterable = ()
        super(Polygon, self).__init__(iterable)
        self.update(kwargs)
    #----------------------------------------------------------------------
    @property
    def type(self):
        return self._type
    #----------------------------------------------------------------------
    def coordinates(self):
        """returns the coordinates as a np.array"""
        import numpy as np
        if 'rings' in self:
            return np.array(self['rings'])
        else:
            return np.array([])
    #----------------------------------------------------------------------
    def __setstate__(self, d):
        """unpickle support """
        self.__dict__.update(d)
        self = Polygon(iterable=d)
    #----------------------------------------------------------------------
    def __getstate__(self):
        """ pickle support """
        return dict(self)
    @classmethod
    def _from_geojson(cls, data, sr=None):
        if sr is None:
            sr = {'wkid' : 4326}
        coordkey = ([d for d in data if d.lower() == 'coordinates']
                     or ['coordinates']).pop()
        coordinates = data[coordkey]
        typekey = ([d for d in data if d.lower() == 'type']
                     or ['type']).pop()
        if data[typekey].lower() == "polygon":
            coordinates = [coordinates]
        part_list = []
        for part in coordinates:
            part_item = []
            for idx, ring in enumerate(part):
                #if idx:
                #    part_item.append(None)
                for coord in ring:
                    part_item.append(coord)
            if part_item:
                part_list.append(part_item)
        return cls({'rings' : part_list,
                'spatialReference' : sr
                })
