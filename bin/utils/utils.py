import os
from os import listdir
from os.path import isfile, isdir, join, basename, splitext

import branca.colormap
import ipywidgets as widgets
import branca.colormap as cm
from statistics import stdev, quantiles
import xarray as xr
import pandas as pd
import re
import io
from zipfile import ZipFile

# For DownloadButton
import base64
import hashlib
from typing import Callable
from IPython.display import HTML
# from rpy2.robjects.packages import importr
# from rpy2.robjects import r
# import rpy2.robjects as robjects
# from rpy2.robjects import pandas2ri
# from rpy2.robjects.conversion import localconverter
from IPython.display import HTML, display, Javascript
import subprocess


def is_float(n):
    """check if number is float

    :n: The number to be checked
    :returns: Boolean

    """
    try:
        float(n)
        return True
    except (ValueError, TypeError):
        return False


def get_dir_content(dirpath):
    """ Get all files from a given directory.

    :dirpath: the path of the directory to be listed.
    :returns: a list of file names, empty if directory doesn't exist or there is no file in the directory.

    """
    return [f for f in listdir(dirpath) if isfile(join(dirpath, f))] if isdir(dirpath) else []


def get_file_content(filepath):
    with open(filepath, "rb") as f:
        return f.read()


def get_yield_variable(f):
    variables = [key for key in f.variables.keys() if key.startswith("yield_")]
    return next(iter(variables), None)


def get_colormap(colormap_data, colormap_mode='zero_to_yellow'):
    """get a branca.colormap object adapted to the data

    :data: list of data
    :colormap_mode: mode of the colormap, ['quantile', 'equal_interval', 'zero_to_yellow]
    :returns: a colormap

    """
    # colors = ['#d7191c', '#ffffbf', '#1a9641']
    # colors = list(cm.linear.RdYlGn_03.colors)
    # colors = list(cm.linear.RdYlGn_05.colors)
    # colors = list(cm.linear.RdYlGn_07.colors)
    # colors = list(cm.linear.RdYlGn_11.colors)
    # colors.reverse()
    # colors = list(cm.linear.Oranges_05.colors)

    # if colormap_data is None:
    #     return cm.LinearColormap(colors=list(cm.linear.RdYlGn_05.colors))

    if colormap_mode == 'zero_to_yellow':
        colors = ['#d7191c', '#ffffbf', '#1a9641']
    else:
        colors = list(cm.linear.RdYlGn_05.colors)

    if colormap_mode == 'equal_interval':
        index = None
    else:
        index = colormap_data

    # index = None
    # if colormap_mode == 'Quantile':
    #     data_nozero = [d for d in data if d != 0]
    #     qt = quantiles(data_nozero, n=5 - 1)
    #     index = [mn, *qt, mx]
    # index = [mn, 0, mx]

    return cm.LinearColormap(colors=colors,
                             index=index,
                             vmin=round(colormap_data[0], 2),
                             vmax=round(colormap_data[-1], 2))


def get_summary_info1(data):
    return {
        "Max": round(max(data), 2),
        "Min": round(min(data), 2),
        "Standard Deviation": round(stdev(data), 2)
    }


def get_summary_info2(data):
    qt1, qt2, qt3 = quantiles(data)
    return {
        "1st Quantile": round(qt1, 2),
        "2nd Quantile": round(qt2, 2),
        "3rd Quantile": round(qt3, 2),
    }


year_regex = re.compile(r"(?P<base>.*)_(?P<start>[0-9]{4})_(?P<end>[0-9]{4})\.(?P<ext>\w{1,3})")


def get_start_year_from_year_path(path):
    return int(year_regex.match(path).group("start"))


def get_end_year_from_year_path(path):
    return int(year_regex.match(path).group("end"))


def get_base_from_year_path(path):
    return year_regex.match(path).group("base")


def get_ext_from_year_path(path):
    return year_regex.match(path).group("ext")


def is_contiguous(ranges):
    """check whether the year ranges are contiguous

    :ranges: sequence of tuples, containing integers
    :returns: Boolean, indicating whether the values are contiguous

    Each start number must be 1 greater than the end number of the previous tuple
    e.g.    (1981, 1990), (1991, 2000) => True
            (1971, 1980), (1991, 2000) => False
            (1971, 1980), (1980, 2000) => False

    """
    for prev, nxt in zip(ranges[:-1], ranges[1:]):
        if prev[1] + 1 != nxt[0]:
            return False
    return True


def get_combine_info(paths):
    """compute the filename used to store the combined cache of the given files
    example paths: [
    'data/raw/IMAGE_LEITAP/GFDL-ESM2M/hist/ssp2/co2/firr/maize/image_gfdl-esm2m_hist_ssp2_co2_firr_yield_mai_annual_1971_1980.nc4',
    'data/raw/IMAGE_LEITAP/GFDL-ESM2M/hist/ssp2/co2/firr/maize/image_gfdl-esm2m_hist_ssp2_co2_firr_yield_mai_annual_1981_1990.nc4',
    ]

    :files: a list of strings containing the file names
    :returns: a dict in the form of { 'start_year': 1971, 'end_year': 1990, 'file_name': ..., 'base': ... }, an empty dict if not combinable

    """
    assert paths and len(paths) > 0, "paths must not be empty"
    # if not paths:
    #     return None
    ranges = sorted([(get_start_year_from_year_path(p), get_end_year_from_year_path(p)) for p in paths])
    if not is_contiguous(ranges):
        return {}
    start, end = ranges[0][0], ranges[-1][1]
    path = basename(paths[0])
    base = get_base_from_year_path(path)
    ext = get_ext_from_year_path(path)

    file_name = f"{base}_{start}_{end}.{ext}"
    return {'start_year': start, 'end_year': end, 'file_name': file_name, 'base': base}


def can_combine(paths):
    return len(paths) > 0 and bool(get_combine_info(paths))


def set_time_unit(ds):
    # TODO: support other units apart from years <2022-04-12, David Deng> #
    unit, reference_date = ds.time.attrs['units'].split('since')
    unit_map = {
        # See https://pandas.pydata.org/docs/user_guide/timeseries.html#timeseries-offset-aliases for more
        "years": "AS",
    }
    unit = unit.strip()
    freq = unit_map[unit]
    ds['time'] = pd.date_range(start=reference_date, periods=ds.sizes['time'], freq=freq)
    return ds


def combine_nc4(inputs, output):
    assert len(inputs) > 0, "inputs must not be empty"
    it = iter(inputs)
    first_input_file = next(it)
    ds = set_time_unit(xr.open_dataset(first_input_file, decode_times=False))
    for input_file in it:
        ds = ds.merge(set_time_unit(xr.open_dataset(input_file, decode_times=False)))
    ds.to_netcdf(output)


def zipped(inputs):
    """ return a byte sequence of the zipped files """
    assert len(inputs) > 0, "inputs must not be empty"
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "a") as zipfile:
        for file in inputs:
            zipfile.write(file, basename(file))
    return zip_buffer.getvalue()


def zip_files(inputs, output):
    with open(output, "wb") as f:
        f.write(zipped(inputs))


def remap_dict_keys(d, key_map):
    return {key_map.get(old_key, old_key): val for old_key, val in d.items()}


def get_citation(selection_info, aggregation_info):
    """ get citation based on the selection and aggregation info, should fail if keys don't exist

    :selection_info: {
    'crop': Maize|Managed grass|...,
    'model': EPIC|GEPIC|...,
    'gcm': HadGEM2-ES|...
    'rcp': ...
    'irr': ...
    'co2': ...
    'start_year': ..., 'end_year': ...,
    }
    e.g.
    {'start_year': 2016, 'end_year': 2099, 'Global Gridded Crop Models (GGCM)': 'crover', 'Global Circulation Models (GCM)': 'gfdl-esm4', 'Representative Concentration Pathways (RCP)': 'ssp126', 'Crops': 'maize'}

    :aggregation_info: {
    'option': pr|yi|st|wa,
    }
    :returns: a citation text string

    User defined aggregation of barley yields for the period 1980-2010 generated by the EPIC crop model using climate data from the GFDL-ESM2M GCM under representative concentration pathway Historical (scenario SSP2) with irrigation and with CO2 fertilization as documented in Rosenzweig et al. (2014). Data and modeling protocols are described in Elliott (2014). Details of the aggregation procedures are in Villoria et al. (2015).


    """
    # values from selection_info
    # print(selection_info)
    crop = selection_info['Crops']
    start_year = selection_info['start_year']
    end_year = selection_info['end_year']
    model = selection_info['model']
    gcm = selection_info['gcm']
    rcp = selection_info['rcp']
    irr = selection_info['irr']
    co2 = selection_info['co2']

    # TODO: map crop name to upper case <2022-05-03, David Deng> #

    # values from aggregation_info
    aggregation_option = aggregation_info['option']

    # some processing
    aggregation_phrase_map = {
        'pr': f'{crop}',
        'yi': f'Area weighted, {crop.lower()} yields',
        'st': f'Summary statics for {crop.lower()} yields',
        'wa': f'User defined aggregation of {crop.lower()} yields',
    }
    aggregation_phrase = aggregation_phrase_map[aggregation_option]

    rcp_phrase_map = {
        "hist": "Historical",
        "rcp2p6": "RCP 2.6",
        "rcp4p5": "RCP 4.5",
        "rcp6p0": "RCP 6.0",
        "rcp8p5": "RCP 8.5",
    }
    rcp_phrase = rcp_phrase_map[rcp]

    irr_phrase_map = {
        "firr": "with",
        "noirr": "without"
    }
    irr_phrase = irr_phrase_map[irr]

    co2_phrase_map = {
        "co2": "with",
        "noco2": "without"
    }
    co2_phrase = co2_phrase_map[co2]

    # combine into citation string
    citation_string = f"{aggregation_phrase} production for the period {start_year}-{end_year} generated by the {model} crop model using climate data from the {gcm} GCM under representative concentration pathway {rcp_phrase} (scenario SSP2) {irr_phrase} irrigation and {co2_phrase} CO2 fertilization as documented in Rosenzweig et al. (2014). Data and modeling protocols are described in Elliott (2014). Details of the aggregation procedures are in Villoria et al. (2015)."
    return citation_string


def labeled_widget(w, title, level=3):
    """ add a heading to the widget """
    ret = widgets.VBox([widgets.HTML(f"<h{level}>{title}</h{level}>"), w])
    ret._title = title
    ret._widget = w
    ret._level = level
    return ret


def hbox_scattered(*items):
    """Create a horizontal list of items

    :*items: the list of items
    :returns: TODO

    """
    ret = widgets.HBox(children=items)
    ret.add_class("scatter_content")
    return ret


# https://stackoverflow.com/questions/61708701/how-to-download-a-file-using-ipywidget-button
class DownloadButton(widgets.Button):
    """Download button with dynamic content

    The content is generated using a callback when the button is clicked.
    """

    def __init__(self, filename: str = None, contents: Callable[[], bytes] = None, **kwargs):
        super(DownloadButton, self).__init__(**kwargs)
        self.filename = filename
        self.contents = contents
        self.on_click(self.__on_click)

    def set_content_from_df(self, df, filename):
        s_buf = io.BytesIO()
        df.to_csv(s_buf)
        s_buf.seek(0)
        self.filename = filename
        self.contents = lambda: s_buf.read()

    def __on_click(self, b):
        contents: bytes = self.contents()  # .encode('utf-8')
        b64 = base64.b64encode(contents)
        payload = b64.decode()
        digest = hashlib.md5(contents).hexdigest()  # bypass browser cache
        id = f'dl_{digest}'

        display(HTML(f"""
            <html>
            <body>
            <a id="{id}" download="{self.filename}" href="data:text/csv;base64,{payload}" download>
            </a>
            
            <script>
            (function download() {{
                document.getElementById('{id}').click();
                
            }})()
            </script>
            
            </body>
            </html>
        """))


def is_dev():
    userdir = os.path.expanduser('~')
    if 'jovyan' in userdir or 'yirugi' in userdir:
        return True
    return False


def download_local_file(local_filepath: str) -> None:
    linked_filepath = 'tmp_down_link'
    filename = os.path.basename(local_filepath)
    if os.path.exists(linked_filepath):
        os.remove(linked_filepath)

    os.symlink(local_filepath, linked_filepath)

    display(Javascript(f"""
        var link = document.createElement("a");
        link.setAttribute("href", "{linked_filepath}");
        link.setAttribute("download", "{filename}");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    """))


def hide_loading(loading_selector='.tab-main'):
    display(Javascript('''require(["waitMe"], function() {
        setTimeout( function(){
            $("%s").waitMe("hide");
        }, 100);

    });''' % loading_selector))


def show_loading(msg='', selector='.tab-main'):
    js = ('$(function(){var msg = "%s";' % (msg)) + ('var selector = "%s";' % (selector)) + '''
    require(["waitMe"], function() {
        $(selector).waitMe({
            effect: 'orbit',
            text: msg,
            color: 'black',
            bg: 'rgba(255,255,255,0.9)'
        });
    });
    });
    '''
    display(Javascript(js))


def toast(msg, toast_type='info'):
    # toast_type = info, success, warning, error
    js = '''
        iziToast.%s({
            message: '%s',
            position: 'topCenter',
            progressBar: false,
            
        });
    ''' % (toast_type, msg)

    display(Javascript(js))


def show_info_dialog(msg):
    js = '''
    iziToast.show({
      message:'%s',
      overlay:true,
      position: 'center',
      theme: 'dark',
      icon: 'fa fa-info-circle',
      timeout: false,
      maxWidth: '600px',
      drag: false,
      class: 'izi-info-dialog',
    })
    ''' % msg
    display(Javascript(js))


# class RWrapper:
#     def __init__(self):
#         self.module = importr('GGCMIAGG', './lib')
#         self.agg_data = None
#
#     def run_agg_wrapper(self, datafile, weights, region_map, custom_map, crop):
#         if custom_map is None:
#             custom_map = r['as.null']
#         else:
#             custom_map = self.convert_to_rdf(custom_map)
#
#         ret = self.module.agg_wrapper(datafile=datafile,
#                                       weights=weights,
#                                       region_map=region_map,
#                                       custom_map=custom_map,
#                                       crop=crop)
#
#         self.agg_data = self.convert_to_pd(ret)
#         return self.agg_data
#
#     def convert_to_pd(self, r_object):
#         with localconverter(pandas2ri.converter):
#             pd_from_r_df = robjects.conversion.rpy2py(r_object)
#             return pd_from_r_df
#
#     def convert_to_rdf(self, pd_df):
#         with localconverter(robjects.default_converter + pandas2ri.converter):
#             r_from_pd_df = robjects.conversion.py2rpy(pd_df)
#
#         return r_from_pd_df


class RWrapper2:  # running R aggregation via command line
    # install.packages("lib/GGCMIAGG", repos=NULL, type="source")
    RSCRIPT_TEMP = """
        
        library("GGCMIAGG", lib.loc="./lib")
        
        ret <- agg.wrapper(
            datafile = '%s',
            weights = '%s',
            region.map = '%s',
            custom.map = %s,
            crop = '%s',
            is.ensemble = %s
        )
        
        write.csv(ret, file='./cache/output.csv')
    """

    @staticmethod
    def run_agg_wrapper(datafile, weights, region_map, custom_map, crop, is_ensemble):
        if custom_map is None:
            custom_map = '"NULL"'
        else:  # load uploaded csv
            custom_map = 'read.csv("%s")' % custom_map

        script = RWrapper2.RSCRIPT_TEMP % (datafile, weights, region_map, custom_map, crop,
                                           'TRUE' if is_ensemble else 'FALSE')
        with open('./cache/agg.R', 'w') as f:
            f.write(script)

        result = subprocess.run(['Rscript', './cache/agg.R'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:  # error
            err_msg = result.stderr
            # err_msg = result.stderr.decode()
            # pos = err_msg.find('Error in')  # to remove the meaningless lines
            # if pos != -1:
            #     err_msg = err_msg[pos:]

            raise Exception(err_msg)

        ret = pd.read_csv('./cache/output.csv')

        # remove temp files
        to_remove = ['./cache/output.csv', './cache/agg.R']
        for file in to_remove:
            if os.path.exists(file):
                os.remove(file)

        return ret
