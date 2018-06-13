"""
The **env** module provides a shared environment used by the different modules.
It stores globals such as the currently active GIS, the default geocoder and so on.
It also stores environment settings that are common among all geoprocessing tools,
such as the output spatial reference.

active_gis
==========

.. py:data:: active_gis
The currently active GIS, that is used for analysis functions unless explicitly specified
when calling the functions.
Creating a new GIS object makes it active unless set_active=False is passed in the GIS constructor.


analysis_extent
===============

.. py:data:: analysis_extent
The processing extent used by analysis tools, specified as an arcgis.geometry.Envelope.

out_spatial_reference
=====================

.. py:data:: out_spatial_reference
The spatial reference of the output geometries. If not specified, the output geometries are in the
spatial reference of the input geometries. If process_spatial_reference is specified and out_spatial_reference
is not specified, the output geometries are in the spatial reference of the process spatial reference.

process_spatial_reference
=========================

.. py:data:: process_spatial_reference
The spatial reference that the geoprocessor will use to perform geometry operations. If specified and
out_spatial_reference is not specified, the output geometries are in the spatial reference of the
process spatial reference.

output_datastore
================

.. py:data:: output_datastore
The data store where GeoAnalytics results should be stored. The supported values of this parameter are "relational" and
"spatiotemporal". By default, results are stored in the spatiotemporal data store. It is recommended that results are
stored in the spatiotemporal data store due to the scalability of the spatiotemporal big data store.

return_z
========

.. py:data:: return_z
If true, Z values will be included in the geoprocessing results if the features have Z values.
Otherwise Z values are not returned. The default is False.


return_m
========

.. py:data:: return_m
If true, M values will be included in the results if the features have M values.
Otherwise M values are not returned. The default is False.

verbose
========

.. py:data:: verbose
#: If True, messages from geoprocessing tools will be printed to stdout.
#: In any case, all geoprocessing messages are available through Python logging module.

"""

#: The currently active GIS, that is used for analysis functions unless explicitly specified.
#: Creating a new GIS object makes it active by default unless set_active=False is passed in the GIS constructor.
active_gis = None

#: The spatial reference of the output geometries. If not specified, the output geometries are in the
#: spatial reference of the input geometries. If process_spatial_reference is specified and out_spatial_reference
#: is not specified, the output geometries are in the spatial reference of the process spatial reference.
out_spatial_reference = None

#: The spatial reference that analysis and geoprocessing tools will use to perform geometry operations. If specified and
#: out_spatial_reference is not specified, the output geometries are in the spatial reference of the
#: process spatial reference.
process_spatial_reference = None

#: The data store where GeoAnalytics results should be stored. The supported values of this parameter are "relational" and
#: "spatiotemporal". By default, results are stored in the spatiotemporal data store. It is recommended that results be
#: stored in the spatiotemporal data store due to the scalability of the spatiotemporal big data store.
output_datastore = None

#: The processing extent used by analysis tools
analysis_extent = None

#: If True, Z values will be included in the geoprocessing results if the features have Z values.
#: Otherwise Z values are not returned. The default is False.
return_z = False

#: If True, M values will be included in the results if the features have M values.
#: Otherwise M values are not returned. The default is False.
return_m = False

#: If True, messages from geoprocessing tools will be printed to stdout
verbose = False
