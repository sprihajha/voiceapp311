from .._layer import ImageryLayer
from arcgis.gis import Item
import numbers

def _raster_input(raster, raster2=None):
    if raster2 is not None:
        if isinstance(raster2, ImageryLayer) and isinstance(raster, ImageryLayer):
            layer = raster2
            raster_ra = _get_raster_ra(raster2)
            if raster2._fn is not None:
                if raster._url == raster2._url:
                    raster2 = raster2._fn
                else:
                    raster2 = _replace_raster_url(raster2._fn, raster2._url)
            else:
                if raster2._url == raster._url:
                    oids = raster2.filtered_rasters()
                    if oids is None:
                        raster2 = '$$'
                    elif len(oids) == 1:
                        raster2 = '$' + str(oids[0])
                    else:
                        raster2 = ['$' + str(x) for x in oids]
                else:
                    raster2 = raster2._url
        elif isinstance(raster2, ImageryLayer) and not isinstance(raster, ImageryLayer):
            layer = raster2
            raster_ra = _get_raster_ra(raster2)
            raster2 = _get_raster(raster2)

        elif isinstance(raster2, list):
            mix_and_match = False # mixing rasters from two image services
            # try:
            #     r0 = raster2[0]
            #     r1 = raster2[1]
            #     if r0._fn is None and r1._fn is None and r0._url != r1._url:
            #         mix_and_match = True
            # except:
            #     pass

            for r in raster2: # layer is first non numeric raster in list
                if not isinstance(r, numbers.Number):
                    layer = r
                    break

            for r in raster2:
                if not isinstance(r, numbers.Number):
                    if r._url != layer._url:
                        mix_and_match = True

            raster_ra = [_get_raster_ra(r) for r in raster2]
            if mix_and_match:
                raster2 = [_get_raster_url(r, layer) for r in raster2]
            else:
                raster2 = [_get_raster(r) for r in raster2]
        else: # secondinput maybe scalar for arithmetic functions, or a chained raster fn
            layer = None
            # raster = raster
            raster_ra = raster2
        return layer, raster2, raster_ra

    if isinstance(raster, ImageryLayer):
        layer = raster
        raster_ra = _get_raster_ra(raster)
        raster = _get_raster(raster)

    elif isinstance(raster, list):
        mix_and_match = False # mixing rasters from two image services
        # try:
        #     r0 = raster[0]
        #     r1 = raster[1]
        #     if r0._fn is None and r1._fn is None and r0._url != r1._url:
        #         mix_and_match = True
        # except:
        #     pass

        for r in raster: # layer is first non numeric raster in list
            if not isinstance(r, numbers.Number):
                layer = r
                break

        for r in raster:
            if not isinstance(r, numbers.Number):
                if r._url != layer._url:
                    mix_and_match = True

        raster_ra = [_get_raster_ra(r) for r in raster]
        if mix_and_match:
            raster = [_get_raster_url(r, layer) for r in raster]
        else:
            raster = [_get_raster(r) for r in raster]
    else: # maybe scalar for arithmetic functions, or a chained raster fn
        layer = None
        # raster = raster
        raster_ra = raster

    return layer, raster, raster_ra

def _get_raster(raster):
    if isinstance(raster, ImageryLayer):
        if raster._fn is not None:
            raster = raster._fn
        else:
            oids = raster.filtered_rasters()
            if oids is None:
                raster = '$$'
            elif len(oids) == 1:
                raster = '$' + str(oids[0])
            else:
                raster = ['$' + str(x) for x in oids]
    return raster


def _replace_raster_url(obj, url=None):
    # replace all "Raster" : '$$' with url
    if isinstance(obj, dict):
        value = {k: _replace_raster_url(v, url)
                 for k, v in obj.items()}
    elif isinstance(obj, list):
        value = [_replace_raster_url(elem, url)
                 for elem in obj]
    else:
        value = obj

    if value == '$$':
        return url
    elif isinstance(value, str) and len(value) > 0 and value[0] == '$':
        return url + '/' + value.replace('$', '')
    else:
        return value


def _get_raster_url(raster, layer):
    if isinstance(raster, ImageryLayer):
        if raster._fn is not None:
            if raster._url == layer._url:
                raster = raster._fn
            else:
                raster = _replace_raster_url(raster._fn, raster._url)

        else:
            if raster._url == layer._url:
                raster = '$$'
            else:
                raster = raster._url

            # oids = raster.filtered_rasters()
            # if oids is None:
            #     raster = '$$'
            # elif len(oids) == 1:
            #     raster = '$' + str(oids[0])
            # else:
            #     raster = ['$' + str(x) for x in oids]
    return raster


def _get_raster_ra(raster):
    if isinstance(raster, ImageryLayer):
        if raster._fnra is not None:
            raster_ra = raster._fnra
        else:
            raster_ra = raster._url


            #if raster._mosaic_rule is not None:
            #    raster_ra['mosaicRule'] = raster._mosaic_rule
    elif isinstance(raster, Item):
        raise RuntimeError('Item not supported as input. Use ImageryLayer - e.g. item.layers[0]')
        #raster_ra = {
        #    'itemId': raster.itemid
        #}
    else:
        raster_ra = raster

    return raster_ra

