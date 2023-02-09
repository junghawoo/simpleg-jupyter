#Map Widget class to generate a map widget using ipyleaflet

import os
from pathlib import Path
import time
import threading
from typing import List
from typing import Optional

from IPython.core.display import display
from ipyleaflet import DrawControl, TileLayer
from ipyleaflet import FullScreenControl
from ipyleaflet import LayersControl
from ipyleaflet import Map
from ipyleaflet import ScaleControl
from ipyleaflet import SearchControl
from ipyleaflet import WidgetControl
from ipyleaflet import ZoomControl
from ipywidgets import Output, VBox, jslink, Checkbox, HTML, Button, ButtonStyle
from ipywidgets import Layout
from osgeo import gdal

from model.variableutil import VariableModel
from utils.misc import NODATA
# PYTHON GOTCHAS: https://gdal.org/api/python_gotchas.html
gdal.UseExceptions()


class CustomMap(Map):
    def __init__(self, width: str, height: str):
        super().__init__(scroll_wheel_zoom=True, zoom_control=False,world_copy_jump = True)
        self.layout = Layout(width=width, height=height, margin="8px 0px 0px 0px")
        self.center = (39.5, -98.35)
        self.zoom = 4

        self._legend_bar = LegendBar()
        self._gdal_layer: Optional[TileLayer] = None  # Can be a raster layer or a vector layer.
        self._raster_service: Optional[RasterService] = None
        self._variable_model = None
        self._linked_map: Optional[CustomMap] = None

        self._coordinates_text = HTML("Coordinates: -", style_={"font-size": '11px'})
        self._value_text = HTML("Value: -", style_={"font-size": '11px'})
        continuos_update_text = HTML("Continuos update:", style_={"font-size": '11px',
                                                                        "margin": "0px 4px 0px 0px"})
        self._continuos_update_checkbox = Checkbox(font_size="15px",
                                                         style_={"width": "15px",
                                                                 "height": "15px",
                                                                 "padding": "0px 0px 0px 0px"
                                                                 })
        self._continuos_update_checkbox.checked = True
        self._continuos_update_checkbox.observe(self._onclick_checkbox)
        wrapper = VBox(children=[continuos_update_text, self._continuos_update_checkbox],
                            style_={
                                "display": "flex",
                                "flex-direction": "row",
                                "justify-content": "flex-start",
                                "align-items": "center",
                                "padding": "0px 0px 0px 0px",
                                "margin": "0px 0px 0px 0px",
                            }
                            )
        self._value_area = VBox(children=[self._coordinates_text, self._value_text, wrapper],
                                layout=Layout(min_width="174px", height="55px", padding="4px 4px 4px 4px"))

        self.add_control(WidgetControl(widget=self._legend_bar, position="bottomleft"))
        self.add_control(ZoomControl(position="topleft"))
        self.add_control(FullScreenControl(position="topleft"))
        self.dc = DrawControl(position='topleft', marker={"shapeOptions": {"color": "#0000FF"}})

        self.selected_markers=[]

        #https://github.com/jupyter-widgets/ipyleaflet/blob/master/examples/DrawControl.ipynb
        #
        #https://notebook.community/rjleveque/binder_experiments/misc/ipyleaflet_polygon_selector
        def handle_draw(target, action, geo_json):
            """Do something with the GeoJSON when it's drawn on the map"""
            #print("action:", action)

            if action == 'created':
                self.selected_markers.append(geo_json['geometry']['coordinates'])
                #print("coordinates:", geo_json['geometry']['coordinates'])

            elif action == 'deleted':
                self.selected_markers.remove(geo_json['geometry']['coordinates'])
                #print("removed coordinates:", geo_json['geometry']['coordinates'])

            #returned coordinate is [longitude, latitude] which correspond to x and y of mercator projection
            #print("selected_markers coordinates:", self.selected_markers)
            #print("dc.data", dc.data)

        self.dc.on_draw(handle_draw)

        self.add_control(self.dc)
        self.add_control(LayersControl(position="topright"))
        self.add_control(WidgetControl(widget=self._value_area, position="bottomright"))
        self.on_interaction(self._mouse_event)

            #print("dc.marker", dc.marker)

    def link(self, map_):
        assert isinstance(map_, self.__class__)
        jslink((self, "zoom"), (map_, "zoom"))
        jslink((self, "center"), (map_, "center"))
        self._linked_map = map_

    def visualize_vector(self, layer: TileLayer):
        # TODO: Implement this
        self.add_layer(layer)
        self._gdal_layer = layer
        self._raster_service = None
        self._legend_bar.refresh(None, None)
        self.center = (39.5, -98.35)
        self.zoom = 4

    def visualize_raster(self, layer: TileLayer, raster_path: Path):
        """ The raster path should have been processed and filtered, if needed. """

        #self._raster_service = RasterService(raster_path)
        gtif = gdal.Open(str(raster_path))
        srcband = gtif.GetRasterBand(1)

        # Get raster statistics
        stats = srcband.GetStatistics(True, True)
        self.add_layer(layer)
        self._gdal_layer = layer
        #print(stats[0],stats[1])
        #print(raster_path)
        self._legend_bar.refresh(stats[0], stats[1])
        self.center = (39.5, -98.35)
        self.zoom = 4
        gtif = None

    def _onclick_checkbox(self, widget, event, data):
        assert isinstance(widget, CustomCheckbox)
        widget.checked = not widget.checked
        if self._linked_map:
            self._linked_map._continuos_update_checkbox.checked = widget.checked

    def _mouse_event(self, **kwargs):
        if (not self._continuos_update_checkbox.checked) and (kwargs.get("type") != "click"):
            return
        coordinates = kwargs.get('coordinates')
        latitude = float(coordinates[0])
        longitude = float(coordinates[1])

        self._update_value(latitude, longitude)
        if self._linked_map:
            self._linked_map._update_value(latitude, longitude)

    def _update_value(self, latitude: float, longitude: float):
        coordinates_text = 'Coordinates:  ({:.4f},{:.4f})'.format(latitude, longitude)
        if self._raster_service is None:
            value_text = "Value: -"
        else:
            value = self._raster_service.value(latitude, longitude)
            value_text = "Value: -" if value is None else "Value: {}".format(value)

        #print("coordinate change", coordinates_text, value_text)
        self._coordinates_text.children = coordinates_text
        self._value_text.children = value_text


class RasterService:
    def __init__(self, raster_path: Path):
        self._path = raster_path
        self._data = None

        driver = gdal.GetDriverByName('GTiff')
        dataset = gdal.Open(str(self._path))

        if not dataset:
            print("RasterService cannot open raster file. Please check the geotiff file")
            return


        band = dataset.GetRasterBand(1)

        try:
            stats = band.GetStatistics(False, True)
        except:  # All values are nodata
            stats = None
        self.min_value: float = float(stats[0]) if stats is not None else None
        self.max_value: float = float(stats[1]) if stats is not None else None

        transform = dataset.GetGeoTransform()
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize
        self._pixel_width = float(transform[1])
        self._pixel_height = -float(transform[5])
        self._x_origin = float(transform[0])
        self._y_origin = float(transform[3])
        self._x_end = self._x_origin + self._pixel_width * cols
        self._y_end = self._y_origin - self._pixel_height * rows

        self._data = band.ReadAsArray(0, 0, cols, rows)
        dataset = None  # Close the dataset - https://gdal.org/tutorials/raster_api_tut.html

    def value(self, latitude: float, longitude: float) -> Optional[float]:
        if (longitude < self._x_origin) or (longitude > self._x_end):
            return None
        elif (latitude > self._y_origin) or (latitude < self._y_end):
            return None

        col = int((longitude - self._x_origin) / self._pixel_width)
        row = int((self._y_origin - latitude) / self._pixel_height)
        value = self._data[row][col]
        return value if value > NODATA else None


class LegendBar(VBox):

    def __init__(self):
        super().__init__()
        self._bucket_width = 44
        self.style_ = self._create_style(hidden=True)

        # color for each bucket from 0% to 90%
        self.colors: List[str] = [self._rgb_to_hex(255, 0, 0),
                                  self._rgb_to_hex(255, 51, 0),
                                  self._rgb_to_hex(255, 119, 0),
                                  self._rgb_to_hex(255, 187, 0),
                                  self._rgb_to_hex(255, 255, 0),
                                  self._rgb_to_hex(204, 255, 0),
                                  self._rgb_to_hex(153, 255, 0),
                                  self._rgb_to_hex(102, 255, 0),
                                  self._rgb_to_hex(38, 191, 0),
                                  self._rgb_to_hex(0, 102, 0),
                                  ]
        self.refresh(None, None)

    def _create_style(self, bucket_number=10, hidden=False):
        style_ = {
            "width": str(self._bucket_width * bucket_number) + "px",
            "height": "16px",
            "border-radius": "15px",
            "display": "none" if hidden else "flex",
            "flex-direction": "row",
            "align-items": "center",
            "justify-content": "flex-start",
            "padding": "0px 0px 0px 0px",
        }
        return style_

    def refresh(self, min_, max_):
        if (min_ is None) or (max_ is None):
            # Possible when every value in raster is nodata(?)
            self.style_ = self._create_style(hidden=True)
            return
        buckets = []
        if min_ == max_:
            bucket = self._create_bucket(min_, self.colors[-1])
            buckets.append(bucket)
        else:
            increment = (max_ - min_) / len(self.colors)
            for i in range(0, len(self.colors)):
                current_value = min_ + (i * increment)
                bucket = self._create_bucket(current_value, self.colors[i])
                buckets.append(bucket)
        buckets.reverse()
        self.children = buckets
        self.style_ = self._create_style(bucket_number=len(buckets), hidden=False)

    def _create_bucket(self, value: float, color: str):

        value_str = "{:.2f}".format(value)
        legend_layout = Layout(
                               width= "auto",
                               height= "auto",
                               display="flex",
                               flex_flow= "column",
                               #align_items= "stretch",
                               justify_content= "center",
                               button_color= color,
                               margin= "0px 0px 0px 0px",
                               opacity= "0.75"
                           )
        #text = Button(description=value_str, style =ButtonStyle(font_size= "8.5px", opacity= "1.0",button_color=color,padding="0px 0px 0px 0px",height="auto", width="auto"))
        text = Button(description=value_str, layout = legend_layout)
        text.style.button_color = color
        bucket = VBox(children=[text],layout=legend_layout)
        return bucket

    def _rgb_to_hex(self, r: int, g: int, b: int):
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255
        return "#{:02x}{:02x}{:02x}".format(r,g,b)
