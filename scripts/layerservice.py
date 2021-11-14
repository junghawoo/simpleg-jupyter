from multiprocessing import cpu_count
import shutil
from pathlib import Path
from typing import Tuple, Optional
import os, datetime
import sys
from ipyleaflet import TileLayer
from osgeo import gdal
from osgeo.gdal import DEMProcessing
from osgeo.gdal import DEMProcessingOptions

# from lib.gdal2tiles import gdal2tiles
from gdalscripts import gdal_calc
from gdalscripts import gdal2tiles
from gdalscripts import gdal_edit
from model.variableutil import VariableModel
from utils import SIMPLEUtil
from utils.misc import NODATA
from utils.experimentutil import ExperimentManager
import pandas as pd
import geopandas as gpd
from ipyleaflet import GeoData,Choropleth
import branca.colormap as cm
import fiona 
import numpy as np
import json
import branca.colormap as cm

# PYTHON GOTCHAS: https://gdal.org/api/python_gotchas.html
gdal.UseExceptions()


class RasterLayerUtil:
    def __init__(self, variable_model: VariableModel):
        print(variable_model.file_path())
        assert variable_model.file_path().exists()
        assert variable_model.is_raster()

        self.variable_model: VariableModel = variable_model
        #Delete the temporary files to make sure that if GDAL crashed then it would recreate the files
        # Temporary files
        self._tif_basename = self.variable_model.file_path().stem
        self._temp_working_directory = self._get_temp_working_directory()
        self.processed_raster_path = self._temp_working_directory / (self._tif_basename + "_temp.tiff")
        self._warped_tif_path = self._temp_working_directory / (self._tif_basename + "_temp_warped.tiff")
        self._color_file_path = self._temp_working_directory / (self._tif_basename + "_temp_color.txt")
        self._filtered_tif_path = self._temp_working_directory / (self._tif_basename + "_temp_filter.tiff")
        self._colorized_tif_path = self._temp_working_directory / (self._tif_basename + "_temp_color.tiff")
        self.remove_old_temp_files()
        self._remove_temp_files()  # Remove existing temp files, if exist

    def _get_temp_working_directory(self) -> Path:
        if self.variable_model.is_private == 0:
            id_str = self.variable_model.id_str
            users_tooldirectory = os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/shared_jobs"
            os.makedirs(users_tooldirectory+"/"+id_str, exist_ok=True)
            return Path(users_tooldirectory+"/"+id_str)     
            
        temp_working_directory = self.variable_model.file_path().parent
        return temp_working_directory

    @property
    def _tile_folder_path(self) -> Path:
        # Cannot be accessed until self.process_raster_path is ready
        assert self.processed_raster_path.exists()

        filter_min = self.variable_model.filter_min
        filter_max = self.variable_model.filter_max
        path = self._temp_working_directory / self._tif_basename
        return path

    @property
    def _tile_folder_url(self) -> Path:
        # Cannot be accessed until self.process_raster_path is ready
        assert self.processed_raster_path.exists()

        home = str(Path.home())
        tile_folder = str(self._tile_folder_path)
        suffix = tile_folder.split(home)[1].replace("\\", "/")
        return SIMPLEUtil.BASE_URL + suffix + '/{z}/{x}/{-y}.png'

    def create_layer(self) -> TileLayer:
        if self._process_raster() and self._colorize_raster() and self._tile_raster():
            #self._remove_temp_files()
            return TileLayer(url=self._tile_folder_url, opacity=0.7, name=self._tif_basename)
        else:
            print("Failed to create layer")
            return TileLayer(name=self._tif_basename)

    def _process_raster(self) -> bool:
        # Filter and warp the raster
        # self.processed_raster_path will be created

        options = gdal.WarpOptions(dstSRS="EPSG:4326", dstNodata=NODATA, format="GTiff",
                                   resampleAlg="bilinear")
        # Python-GDAL binding does not support
        gdal.Warp(str(self._warped_tif_path), str(self.variable_model.file_path()), options=options)
        if self._filter_raster():
            # Make sure the projection is correct, reset the NODATA value, and create processed_raster_path
            gdal.Warp(str(self.processed_raster_path), str(self._filtered_tif_path), options=options)
            return True
        else:
            # Make sure the projection is correct, reset the NODATA value, and create processed_raster_path
            gdal.Warp(str(self.processed_raster_path), str(self._filtered_tif_path), options=options)
            return False

    def _filter_raster(self) -> bool:
        min_, max_ = self._min_max_of_raster(self._warped_tif_path)
        #print(self._warped_tif_path)
        if (min_ is None) or (max_ is None):  # All nodata
            print("filtering failed")
            return False
        range_ = max_ - min_
        new_min = min_ + self.variable_model.filter_min / float(100) * float(range_)
        new_max = min_ + self.variable_model.filter_max / float(100) * float(range_)
        # How to use - https://gdal.org/programs/gdal_calc.html
        #print(new_min,new_max)
        filter_expression = "A*logical_and(A>={},A<={})".format(new_min, new_max)
        args = ["--outfile={}".format(str(self._filtered_tif_path)),
                "-A", str(self._warped_tif_path),
                "--calc={}".format(filter_expression),
                "--NoDataValue=0",   # Do not change this. Explanation is in the comment below.
                "--overwrite",
                "--quiet",
                ]
        # Filter the raster data. After running this, data outside of the range will be converted to 0 and all data with
        # the value 0 will be set to NODATA. Note: It seems like the statistics metadata will not be updated properly
        # too.
        gdal_calc.run(args)

        # Remove any set statistics metadata
        gdal_edit.gdal_edit(["argv_placeholder", "-unsetstats", str(self._filtered_tif_path)])
        print("filtering succeeded")
        return True

    def _min_max_of_raster(self, tif_path: Path):
        #gdal_edit.gdal_edit(["argv_placeholder", "-unsetstats", str(tif_path)])
        #print("Min Max Path")
        #print(tif_path)
        # open the image
        gtif = gdal.Open(str(tif_path))
        srcband = gtif.GetRasterBand(1)
        assert gtif is not None

        try:
            # Get raster statistics
            stats = srcband.GetStatistics(True, True)
        except:
            # All values are nodata
            return None, None

        gtif = None  # Close the dataset -https://gdal.org/tutorials/raster_api_tut.html
        return stats[0],stats[1]

    def _colorize_raster(self) -> bool:
        if self._create_color_file():
            options = DEMProcessingOptions(colorFilename=str(self._color_file_path), format="GTiff", addAlpha=True)
            DEMProcessing(str(self._colorized_tif_path), str(self.processed_raster_path), "color-relief", options=options)
            return True
        return False

    def _create_color_file(self) -> bool:
        # Get raster statistics
        min_, max_ = self._min_max_of_raster(self.processed_raster_path)
        if (min_ is None) or (max_ is None):
            return False
        file_content = "nv 0 0 0 0\n" \
                       "0% 255 0 0 255\n" \
                       "10% 255 51 0 255\n" \
                       "20% 255 119 0 255\n" \
                       "30% 255 187 0 255\n" \
                       "40% 255 255 0 255\n" \
                       "50% 204 255 0 255\n" \
                       "60% 153 255 0 255\n" \
                       "70% 102 255 0 255\n" \
                       "80% 38 191 0 255\n" \
                       "90% 0 102 0 255\n"

        if min_ == max_:
            file_content = "0% 0 102 0 255\n" \
                           "nv 0 0 0 0\n" \
                           "0 0 0 0 255\n"

        if self._color_file_path.exists():
            self._color_file_path.unlink()

        with open(str(self._color_file_path), "w+"):
            self._color_file_path.write_text(file_content)
        gtif = None  # Close the dataset -https://gdal.org/tutorials/raster_api_tut.html
        return True

    def _tile_raster(self) -> bool:
        from utils.misc import REBUILD_RASTER_TILE
        if self._tile_folder_path.exists() and self._tile_folder_path.is_dir() and REBUILD_RASTER_TILE:
            shutil.rmtree(str(self._tile_folder_path))
        #print(self.processed_raster_path)
        print("min, max", self._min_max_of_raster(self.processed_raster_path))
        print("tile folder", self._tile_folder_path)
        # if self.variable_model.is_filtered() and self._tile_folder_path.exists():
        #     shutil.rmtree(str(self._tile_folder_path))
        #print(cpu_count())
        #print(str(self._colorized_tif_path))
        #print(str(self._tile_folder_path))
        
        # Using 2 cpu cores instead of all to prevent gdal from crashing
        # It will take longer but more reliable
        # Removed the -e to make sure new temp files and processing is done again
        #print(str(self._colorized_tif_path))
        gdal2tiles.run(["-z", "0-8", "-a", "0, 0, 0", "--processes=2", str(self._colorized_tif_path), str(self._tile_folder_path)])
        return True

    def _remove_temp_files(self) -> bool:
        # The processed_raster_path is not removed. The map will read from it directly to display cell value.
        # The tile folder is also not be removed. The map will use it to display the layer
        if self._filtered_tif_path.exists():
            self._filtered_tif_path.unlink()
        if self._colorized_tif_path.exists():
            self._colorized_tif_path.unlink()
        if self._color_file_path.exists():
            self._color_file_path.unlink()
        return True

    def remove_old_temp_files(self):
        #try:
        #    print(self._temp_working_directory)
        #    shutil.rmtree(self._temp_working_directory)
        #except:
        #        comment = "do nothing"
        try:
            if os.path.exists(self.processed_raster_path):
                #print(self.processed_raster_path)
                os.remove(self.processed_raster_path)
            if os.path.exists(self._warped_tif_path):
                #print(self._warped_tif_path)
                os.remove(self._warped_tif_path)
            if os.path.exists(self._color_file_path):
                #-print(self._color_file_path)
                os.remove(self._color_file_path)
            if os.path.exists( self._filtered_tif_path):
                #print(self._filtered_tif_path)
                os.remove( self._filtered_tif_path)
            if os.path.exists( self._colorized_tif_path):
                #print(self._colorized_tif_path)
                os.remove( self._colorized_tif_path)
            if os.path.exists(str(self._warped_tif_path)+".aux.xml"):
                os.remove( str(self._warped_tif_path)+".aux.xml")
            if os.path.exists(str(self.processed_raster_path)+".aux.xml"):
                os.remove( str(self.processed_raster_path)+".aux.xml")
            shutil.rmtree(self._temp_working_directory/self._tif_basename)
        except Exception as e:
               print(e)
               
        
    
class VectorLayerUtil:
    def __init__(self, variable_model: VariableModel):
        print(variable_model.file_path())
        assert variable_model.file_path().exists()
        assert variable_model.is_vector()
        self.variable_model: VariableModel = variable_model
        self.map_df = None 

    def create_layer(self):
        shp_file = gpd.read_file(self.variable_model.file_path())
        self.map_df=shp_file.to_crs(4326)
        #csv_data = pd.read_csv(str(self.variable_model.file_path())[:-3]+"csv")

        if self.variable_model.is_private == 0:
            id_str = self.variable_model.id_str
            users_tooldirectory = os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool"
            os.makedirs(users_tooldirectory+"/"+id_str, exist_ok=True)
            temp_file =  users_tooldirectory + "/temp.geojson"
        else:
            #Temporary File to store GeoJSON version of data
            temp_file = str(self.variable_model.file_path().parent) + ".geojson"
        self.map_df.to_file(temp_file, driver='GeoJSON')
        #Using the GeoJSON version of the file to process the data
        with open(temp_file, 'r') as f:
            geo_json_data = json.load(f)
            #Region based data extraction
            for d in geo_json_data["features"]:
               d["REG"] = d["properties"]["REG"]

            #print(geo_json_data)
        #Taking out Region Vs Value dictionary to map out a color scheme based on number values
        mapping  = dict(zip(self.map_df["REG"].str.strip(), self.map_df["DATA"]))
        #Creating the color scheme to match the legend
        linear = cm.LinearColormap([(255,0,0),(255,51,0),(255,119,0),(255,187,0),(255,255,0),(204,255,0),(153,255,0),(102,255,0),(38,191,0),(0,102,0)],
                 vmin=min(self.map_df['DATA']), vmax=max(self.map_df['DATA']))
        #display(linear) #Display the color scheme
        #The Choropleth widget is used to add color to the regions
        if(min(self.map_df['DATA']) == max(self.map_df['DATA'])):
             layer = GeoData(geo_dataframe=self.map_df,style = {'color':'black','fillColor':'rgb(0,102,0)','fillOpacity':0.7})
        else:
             layer = Choropleth(
                    geo_data=geo_json_data,
                    choro_data=mapping,
                    colormap=linear,
                    style={'fillOpacity': 0.7, "color":"black"},
                    key_on="REG"
                    )
        return layer
    
    def create_legend(self,map_wid):
       
        if(min(self.map_df['DATA']) == max(self.map_df['DATA'])):
                map_wid._legend_bar.refresh(min(self.map_df['DATA']), max(self.map_df['DATA'])) 
        else:
                map_wid._legend_bar.refresh(min(self.map_df['DATA']), max(self.map_df['DATA'])/0.9)
        return
    
