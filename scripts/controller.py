# controller.py - Central logic for scsa notebook

import logging
import time
import traceback
import warnings  # Avoids warning: "numpy.dtype size changed, may indicate binary incompatibility"
from matplotlib import pyplot as plt
from IPython.core.display import display, clear_output
import sqlite3
import os
import ipywidgets as ui
from scripts.constants import *
from scripts.sqlitedb import Sqlitedatabase
from scripts.mapwidget import CustomMap
from scripts.layerservice import RasterLayerUtil
from model.variableutil import VariableModel
from scripts.DBManager import *
#from JobManager.py import *
from IPython.display import clear_output
from IPython.display import HTML
from scripts.view import section,section_horizontal
from scripts.layerservice import VectorLayerUtil
import pandas as pd
import geopandas as gpd
from ipyleaflet import GeoData,Choropleth
import branca.colormap as cm
import fiona 
import numpy as np
import json
import branca.colormap as cm
from pathlib import Path
import subprocess

warnings.filterwarnings('ignore')  # TODO Confirm still needed?

PLOT_LINE_DATA_MARKER = 'o'
PLOT_WIDTH = 12  # inches
PLOT_HEIGHT = 6  # inches
PLOT_EMPTY_X_AXIS = 'X Axis'
PLOT_EMPTY_Y_AXIS = 'Y Axis'


class CombineLogFields(logging.Filter):
    def filter(self, record):
        record.filename_lineno = "%s:%d" % (record.filename, record.lineno)
        return True


class Controller(logging.Handler):
    VALUE = 'value'  # for observe calls
    map_widgets = []
    
    def __init__(self, log_mode):  # 0=none 1=info 2=debug

        # TODO Remove testing code below
        # log_mode += 2

        self.display_log = log_mode > 0
        self.debug_buffer = []
        self.display_ready = False

        if log_mode == 2:
            log_format = '%(levelname)1.1s %(asctime)s %(filename_lineno)-18s %(message)s (%(funcName)s)'
            log_level = logging.DEBUG
        else:
            log_format = '%(asctime)s %(message)s'
            log_level = logging.INFO

        self.plot_figure = None

        logging.Handler.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.setFormatter(logging.Formatter(log_format, '%Y-%m-%dT%H:%M:%S'))
        self.logger.addHandler(self)
        self.logger.addFilter(CombineLogFields())
        self.logger.setLevel(log_level)
        self.setLevel(log_level)

        self.model = None
        self.view = None
        self.db_class_import = None
        self.cursor= None

    def intro(self, model, view):
        """Introduce MVC modules to each other"""
        self.model = model
        self.view = view

    def emit(self, message):
        """Pass new log msg to view for display"""
        if self.display_log:

            text = self.format(message)
            self.debug_buffer.append(text)

            if self.display_ready:

                for line in self.debug_buffer:
                    self.view.debug(line)

                self.debug_buffer = []

    def start(self):
        """Load data, build UI, setup callbacks"""
        self.logger.debug('At')

        try:
                        
            #Set up the database
            self.db_class_import = DBManager()
            
            
            # Set up user interface
            self.view.display(self.display_log)
            self.display_ready = True
            
            # Connect UI widgets to callback methods ("cb_...").
            #   Methods listed below will be called when user activates widget.
            #   Format: <widget>.on_click/observe(<method_to_be_called>...)
            #self.view.submit_button.on_click(self.cb_submit_model)
            #self.view.selectable_window.observe(self.refresh_manage_jobs)
            self.view.display_btn.on_click(self.cb_display_btn)
            self.view.view_button_submit.on_click(self.cb_tif_display)
            self.view.system_component.observe(self.cb_model_mapping)
            self.view.resolution.observe(self.cb_model_mapping_name)
            self.view.name_dd.observe(self.cb_model_mapping_type)
            self.view.type_of_result.observe(self.cb_submit_button_enable)
            self.view.result_to_view.observe(self.cb_result_to_view)
            self.view.compare_btn.on_click(self.cb_compare_models)
            self.view.refresh_btn.on_click(self.refresh_manage_jobs)
            self.view.submit_button.on_click(self.cb_upload_btn_create)
            

        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise
            
    def cb_test(self, _):
        print(self.view.model_dd.value)
    
    def cb_upload_btn_create(self, _):
        #Checking to see if the input is valid
        myupload = self.view.upload_btn.value
        #print(myupload)
        uploaded_filename = list(myupload.keys())[0]
        content = myupload[uploaded_filename]['content']
        if uploaded_filename[-4:] != ".cmf":
            return
        if self.view.model_dd.value == "-":
            return
        
        #Creating the sql entry 
        user = os.popen("whoami").read().rstrip('\n')
        job_id = self.db_class_import.createNewJob(self.view.model_dd.value,self.view.name_tb.value,self.view.description_ta.value,"Processing",user,"0")
        file_location = os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/job/" + str(job_id)
        Path(file_location).mkdir(parents=True, exist_ok=True)
        command = None
        command_simple = None
        self.refresh_manage_jobs("None")
        #Create File to submit and set the parameters
        if self.view.model_dd.value == "Custom Crops":
            with open(file_location+'/SIMPLE_G_AllCrops.cmf', 'w') as f: f.write(content.decode("utf-8"))
            command = "SIMPLE_G_AllCrops.cmf"
            command_simple = "simpleg_us_all"
        if self.view.model_dd.value == "Custom CornSoy":
            with open(file_location+'/SIMPLE_G_CornSoy.cmf', 'w') as f: f.write(content.decode("utf-8"))
            command = "SIMPLE_G_CornSoy.cmf"
            command_simple = "simpleg_us_corn"
        #Run the submit tool    
        submit = subprocess.run(["submit", "-w","15","-i",command,command_simple ], capture_output=True ,cwd= file_location)
        # Path needs to be outputs not out
        os.rename(file_location+"/out",file_location+"/outputs")
        get_id = submit.stdout.decode("utf-8")
        start = get_id.find("Run") + 4
        end = get_id.find("registered") -1
        remote_job_id = get_id[start:end]
        self.db_class_import.updateRemoteID(job_id,remote_job_id)
        self.db_class_import.updateJobStatus(job_id,"Completed")
        self.refresh_manage_jobs("None")
        
         
        return 
    
    def jobs_selected(self,_):
        #This will return a list of the job ids which are selected in the job_selection variable
        #Running a loop to check selected checkboxes for the box
        self.view.job_selection = []
        for jobid,checkbox in self.view.checkboxes.items():
            if(checkbox.value == True):
                self.view.job_selection.append(jobid)
        return
    
    
    def refresh_manage_jobs(self,_):
        self.view.selectable_window_vbox.children = []
        #Temporary Database Access will be refreshed with a global variable and the callback function
        dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/DatabaseFile(DONOTDELETE).db"
        conn = sqlite3.connect(dbfile)
        cursor = conn.cursor()
        #Database is always created first so the next statement should not give an error
        cursor.execute("SELECT * FROM SIMPLEJobs")
        rows = cursor.fetchall()
        #Storing the contents of the db in list_of_jobs
        list_of_jobs = []
        #For alignment finding the max length of each column
        col_width = max(len(str(word)) for row in rows for word in row) + 2  # padding
        for row in rows:
            str_row = "".join(str(word).ljust(col_width) for word in row)
            list_of_jobs.append(str_row)
        cursor.close()
        conn.close()
        
        #Selectable multiple widget / Checkboxes for each
        self.view.checkboxes = {}
        self.view.selectable_window = ui.GridspecLayout(len(rows),11,height="auto")
        self.view.job_selection = []
        row_counter = 0
        #Create a new dictionary key value pair for each jobid and checkbox
        for row in rows:
            self.view.checkboxes[str(row[0])]=ui.Checkbox(value=False,disabled=False,description="",indent=False,layout=ui.Layout(width="auto",height="auto"))
            self.view.selectable_window[row_counter,:1] = self.view.checkboxes[list(self.view.checkboxes.keys())[-1]]
            self.view.selectable_window[row_counter,1] = ui.HTML(str(row[0]))
            self.view.selectable_window[row_counter,2] = ui.HTML(row[6])
            self.view.selectable_window[row_counter,3:5] = ui.HTML(row[5])
            self.view.selectable_window[row_counter,5:10] = ui.HTML(row[8])
            self.view.selectable_window[row_counter,10] = ui.HTML(row[4])
            row_counter = row_counter + 1
        self.view.checkboxes["0"].disabled = True
        self.view.selectable_window_vbox.children=[self.view.selectable_window]
        return
    
    def cb_display_btn(self,_):
        self.jobs_selected("Garbage Value")
        if(len(self.view.job_selection)!=1):
            self.view.instructions_label.value ="Select one model only for display"
        else:    
            self.view.instructions_label.value ="Select one model for Display, select two for Compare. After clicking Display/Compare head to the View Tab"
        #print(self.view.checkboxes)
        #print(self.view.checkboxes.keys())
        for job in self.view.checkboxes.keys():
            if self.view.checkboxes[job].value == True:
                self.create_map_widget(job)
                #print(self.view.checkboxes[job])
                break
        return
    
    def create_map_widget(self,map_id):
        map_wid = CustomMap("1200px","720px")
        mapbox=section("Map ID: "+str(map_id),[map_wid])
        
        temp_list = list(self.view.view_vbox.children)
        temp_list.append(mapbox)
        self.view.view_vbox.children = tuple(temp_list)
        return
    def create_map_widget_compare(self,map_id):
        
        map_wid = CustomMap("600px","720px")
        map_wid_1 = CustomMap("600px","720px")
        map_wid.link(map_wid_1)
        mapbox=section_horizontal("Map: "+str(map_id[0])+" and "+str(map_id[1]),[map_wid,map_wid_1])
        mapbox.children[0].children[0].layout= ui.Layout(border='solid',width="600px",height="720px")
        mapbox.children[0].children[1].layout= ui.Layout(border='solid',width="600px",height="720px")
        temp_list = list(self.view.view_vbox.children)
        temp_list.append(mapbox)
        self.view.view_vbox.children = tuple(temp_list)
        return
    
    def cb_tif_display(self,_):
        
        for i in range(1,len(self.view.view_vbox.children)):
            #Checking to see whether the Accordian has a single map or multiple maps
            if(len(self.view.view_vbox.children[i].children[0].children)>1):
                mapbox = self.view.view_vbox.children[i].children[0]
                map_id = self.view.view_vbox.children[i].get_title(0)
                map_id = map_id.replace("Map: ","")
                map_id = map_id.replace(" ","")
                map_id_1 = map_id.split("and")[-1]
                map_id = map_id.split("and")[0]
                variable_model = VariableModel(map_id,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value)
                variable_model_1 = VariableModel(map_id_1,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value)
                map_wid = mapbox.children[0]
                if len(map_wid.layers) > 1: 
                    map_wid.remove_layer(map_wid.layers[-1])
                map_wid_1 =mapbox.children[1]
                if len(map_wid_1.layers) > 1:
                    map_wid_1.remove_layer(map_wid_1.layers[-1])
                if variable_model.is_raster():
                    layer_util = RasterLayerUtil(variable_model)
                    layer = layer_util.create_layer()
                    map_wid.visualize_raster(layer, layer_util.processed_raster_path)
                    
                    layer_util = RasterLayerUtil(variable_model_1)
                    layer = layer_util.create_layer()
                    map_wid_1.visualize_raster(layer, layer_util.processed_raster_path)
                    
                elif variable_model.is_vector():
                    layer_util = VectorLayerUtil(variable_model)
                    layer = layer_util.create_layer()
                    map_wid.add_layer(layer)
                    layer_util.create_legend(map_wid)
                    
                    layer_util = VectorLayerUtil(variable_model_1)
                    layer = layer_util.create_layer()
                    map_wid.add_layer(layer)
                    layer_util.create_legend(map_wid_1)
                continue
            #Below is single map processing
            mapbox = self.view.view_vbox.children[i]
            map_id = mapbox.get_title(0)
            map_id = map_id.replace("Map ID: ","")
            variable_model = VariableModel(map_id,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value)

            map_wid = mapbox.children[0].children[0]
            if len(map_wid.layers) > 1:
                map_wid.remove_layer(map_wid.layers[-1])
            if variable_model.is_raster():
                layer_util = RasterLayerUtil(variable_model)
                layer = layer_util.create_layer()
                map_wid.visualize_raster(layer, layer_util.processed_raster_path)
            elif variable_model.is_vector():
                layer_util = VectorLayerUtil(variable_model)
                layer = layer_util.create_layer()
                map_wid.add_layer(layer)
                layer_util.create_legend(map_wid)
        return
    
    def cb_model_mapping(self,_):
        if (len(self.view.view_vbox.children) <= 1):
            return
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        if(self.view.system_component.value=="Environment"):
                self.view.resolution.options = ["-","Geospatial"]
                self.view.name_dd.options = ["-","N-use Grid"]
                self.view.result_to_view.options = ["-","Irrigated","Rainfed"]
                self.view.result_to_view.disabled = False
                self.view.longname.value="Geospatial:Nitrogen Use by Grid, Type (in MT)"
                
        if(self.view.system_component.value=="Water"):
            self.view.resolution.options = ["-","Geospatial","Regional"]
            self.view.name_dd.options = ["-"]#"Water Use Grid","Water Use - Region","Water per Ha - Region"
            self.view.result_to_view.options = ["-"]
            self.view.result_to_view.disabled = True
            self.view.longname.value="<br>Geospatial:Water Use by Grid (in 1000 m^3 yr)<br>Regional:[Water Use by Region (in 1000 m^3 yr),Water per Ha by Region (in m^3 yr / ha)]<br>"
            
        if(self.view.system_component.value=="Land"):
            self.view.resolution.options = ["-","Geospatial","Regional"]
            self.view.name_dd.options = ["-"]#,"Land Use Grid","Land Use - Region,Type","Land Use - Region"]
            self.view.result_to_view.options = ["-"]
            self.view.result_to_view.disabled = True
            self.view.longname.value="<br>Geospatial:Cropland Area by Grid, Type (in 1000 ha)<br>Regional:[Cropland Area by Region, Type (in 1000 ha),Cropland Area by Region (in 1000 ha)]<br>"
            
        if(self.view.system_component.value=="Production"):
            self.view.resolution.options = ["-","Geospatial","Regional","Global"]
            self.view.name_dd.options = ["-"]#,"Yield Region","Regional Price","Net Export","Output Region","Ouput Grid","World Price"
            self.view.result_to_view.options = ["-"]#,"Irrigated","Rainfed"]
            self.view.result_to_view.disabled = False
            self.view.longname.value="<br>Geospatial:Corn Soy Output by Grid, Type (in 1000 MT Corn eq)<br> Regional:[Crop Yield by Region (in MT per ha),Corn Soy Supply Price by Region (in USD / MT),Corn Soy Net Exports by Region (in 1000 MT Corn eq),Corn Soy Output by Region (in 1000 MT Corn eq)]<br>Global:World Corn Soy Price(in USD / MT) "
        return 
    
    def cb_model_mapping_name(self,_):
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        if(self.view.system_component.value=="-" or self.view.resolution.value=="-"):
            return
        self.view.result_to_view.options = ["-"]
        self.view.result_to_view.disabled = True
        self.view.name_dd.value = self.view.name_dd.options[0]
        if(self.view.system_component.value=="Environment"):
            if(self.view.resolution.value=="Geospatial"):
                self.view.name_dd.options = ["-","N-use Grid"]
                self.view.longname.value="<br><br>Nitrogen Use by Grid, Type (in MT)"
                
        if(self.view.system_component.value=="Water"):
            if(self.view.resolution.value=="Geospatial"):
                self.view.name_dd.options = ["-","Water Use Grid"]
                self.view.longname.value="<br><br>Water Use by Grid (in 1000 m^3 yr)]"
            if(self.view.resolution.value=="Regional"):
                self.view.name_dd.options = ["-","Water Use Region","Water per Ha"]
                self.view.longname.value="<br><br>Water Use by Region (in 1000 m^3 yr),Water per Ha by Region (in m^3 yr / ha)<br>"
        
        if(self.view.system_component.value=="Land"):
            if(self.view.resolution.value=="Geospatial"):
                self.view.name_dd.options = ["-","Land Use Grid"]
                self.view.longname.value="<br><br>Cropland Area by Grid, Type (in 1000 ha)<br>"
            if(self.view.resolution.value=="Regional"):
                self.view.name_dd.options = ["-","Land Use Region Type"," Land Use-Region"]
                self.view.longname.value="<br><br>Cropland Area by Region, Type (in 1000 ha),Cropland Area by Region (in 1000 ha)<br>"
        
        if(self.view.system_component.value=="Production"):
            if(self.view.resolution.value=="Geospatial"):
                self.view.name_dd.options = ["-","Output Grid"]
                self.view.longname.value="<br><br>Corn Soy Output by Grid, Type (in 1000 MT Corn eq)"
            if(self.view.resolution.value=="Regional"):
                self.view.name_dd.options = ["-","Yield Region","Regional Price","Net Export","Output Region"]
                self.view.longname.value="<br><br>Crop Yield by Region (in MT per ha),Corn Soy Supply Price by Region (in USD / MT),Corn Soy Net Exports by Region (in 1000 MT Corn eq),Corn Soy Output by Region (in 1000 MT Corn eq)"
            if(self.view.resolution.value=="Global"):
                self.view.name_dd.options = ["-","World Price"]
                self.view.longname.value="<br><br>World Corn Soy Price(in USD / MT)"
        return
    
    def cb_model_mapping_type(self,_):
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        if(self.view.system_component.value=="-" or self.view.resolution.value=="-" or self.view.name_dd.value=="-"):
            return
        final_result={"N-use Grid":"Nitrogen Use by Grid, Type (in MT)","Water Use Grid":"Water Use by Grid (in 1000 m^3 yr)","Water Use Region":"Water Use by Region (in 1000 m^3 yr)","Water per Ha":"Water per Ha by Region (in m^3 yr / ha)","Land Use Region Type":"Cropland Area by Region, Type (in 1000 ha)"," Land Use-Region":"Cropland Area by Region (in 1000 ha)","Output Grid":"Corn Soy Output by Grid, Type (in 1000 MT Corn eq)","Yield Region":"Crop Yield by Region (in MT per ha)","Regional Price":"Corn Soy Supply Price by Region (in USD / MT)","Net Export":"Corn Soy Net Exports by Region (in 1000 MT Corn eq)","Output Region":"Corn Soy Output by Region (in 1000 MT Corn eq)","World Price":"World Corn Soy Price(in USD / MT)","Land Use Grid":"Cropland Area by Grid, Type (in 1000 ha)"}
        self.view.longname.value="<br><br><br>"+final_result[self.view.name_dd.value]
        if(self.view.system_component.value=="Production" and self.view.resolution.value=="Geospatial" and self.view.name_dd.value=="Output Grid"):
            self.view.result_to_view.disabled = False
            self.view.result_to_view.options = ["-","Irrigated","Rainfed"]
        elif(self.view.system_component.value=="Land" and self.view.resolution.value=="Geospatial" and self.view.name_dd.value=="Land Use Grid"):
            self.view.result_to_view.disabled = False
            self.view.result_to_view.options = ["-","Irrigated","Rainfed"]
        elif(self.view.system_component.value=="Land" and self.view.resolution.value=="Regional" and self.view.name_dd.value=="Land Use Region Type"):
            self.view.result_to_view.disabled = False
            self.view.result_to_view.options = ["-","Irrigated","Rainfed"]
        elif(self.view.system_component.value=="Environment" and self.view.resolution.value=="Geospatial" and self.view.name_dd.value=="N-use Grid"):
            self.view.result_to_view.disabled = False
            self.view.result_to_view.options = ["-","Irrigated","Rainfed"]
        else:          
            self.view.result_to_view.options = ["-"]
            self.view.result_to_view.disabled = True
        return
    
    def cb_result_to_view(self,_):
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        return
    
    
    def cb_submit_button_enable(self,_):
        self.view.view_button_submit.disabled = True
       
        if(self.view.system_component.value=="-" or self.view.resolution.value=="-" or self.view.name_dd.value=="-" or self.view.type_of_result.value=="-"):
            self.view.view_button_submit.disabled = True
            return
        
        if(self.view.result_to_view.disabled == False and self.view.result_to_view.value=="-"):
            self.view.view_button_submit.disabled = True
            return
        
        self.view.view_button_submit.disabled = False
        return
    
    def cb_compare_models(self,_):
        self.jobs_selected("Garbage Value")
        if(len(self.view.job_selection)!=2):
            self.view.instructions_label.value = "Select exactly 2 models to compare"
        else:
            self.view.instructions_label.value ="Select one model for Display, select two for Compare. After clicking Display/Compare head to the View Tab"
            self.create_map_widget_compare(self.view.job_selection)
        return
    ################################################################################
    comment = '''def cb_data_source_selected(self, change):
        """User selected a data file"""
        self.logger.debug('At')

        try:
            choice = change['owner'].value

            if not choice == self.view.EMPTY:
                self.view.update_data_status(self.view.DATA_LOAD)
                self.model.get_data(choice)
                self.view.update_data_status(self.model.data)
                self.view.update_dynamic_selections()
        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_model_selected(self, change):
        """User changed their model filter selection"""
        self.logger.debug('At')

        try:
            self.view.model_selected(change['owner'].value)
        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_apply_filter(self, _):
        """User hit button to search for data"""
        self.logger.debug('At')

        if not self.model.valid:
            return

        try:
            self.view.output(FILTER_PROG, self.view.filter_output)
            self.view.filter_out_export.clear_output()

            # Use specified criteria to search for data, (results stored in model)
            self.model.clear_filter_results()
            self.model.search(
                list(self.view.filter_mod.value),
                list(self.view.filter_scn.value),
                list(self.view.filter_reg.value),
                list(self.view.filter_ind.value),
                list(self.view.filter_sec.value),
                list(self.view.filter_yrs.value)
            )

            # Refresh output widgets
            self.view.update_filtered_output()
            self.view.set_plot_status()
            self.cb_refresh_harmonizers()

        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_ndisp_changed(self, _):
        """User changed number of recs to display"""
        try:
            self.view.update_filtered_output()
        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_fill_data_export(self, _):
        """User hit button to bulk download all data"""
        self.logger.debug('At')

        try:
            # First, clear _RESULTS_ link because it might point to same file
            self.view.export_msg('', self.view.filter_out_export)

            # Create link for bulk data
            if self.model.valid:
                self.view.export_msg(CREATING_LINK, self.view.data_out_export)
                filename = self.model.create_download_file(self.model.data, self.view.data_ddn_format.value)
                self.view.export_link(filename, self.view.data_out_export)
            else:
                self.view.export_msg(NO_DATA_AVAIL, self.view.data_out_export)
        except Exception:
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_fill_plot_export(self, _):
        """User hit button to download image of plot"""
        self.logger.debug('At')

        try:
            self.view.export_msg('...', self.view.viz_out_plot_export)
            time.sleep(1)

            # First, to save space, delete existing download file(s)
            self.model.delete_downloads(DOWNLOAD_PLOT_NAME)

            # Create link for image file
            filename = DOWNLOAD_DATA_NAME + self.view.viz_ddn_plot_format.value
            self.plot_figure.savefig(filename)
            self.view.export_link(filename, self.view.viz_out_plot_export)
        except Exception:
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_fill_results_export(self, _):
        """User hit button to download results"""
        self.logger.debug('At')

        try:
            # First, clear _DATA_ link because it might point to same file
            self.view.export_msg('', self.view.data_out_export)

            # Create link for filter results
            if self.model.res_row_count > 0:
                self.view.export_msg(CREATING_LINK, self.view.filter_out_export)
                filename = self.model.create_download_file(self.model.results, self.view.filter_ddn_format.value)
                self.view.export_link(filename, self.view.filter_out_export)
            else:
                self.view.export_msg(NO_RECS_AVAIL, self.view.filter_out_export)
        except Exception:
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_refresh_harmonizers(self, _=None):
        """User changed plot options, update harmonize widgets with values"""
        self.logger.debug('At')

        try:
            self.view.set_harmonize(self.model.get_uniques_for(self.view.viz_ddn_plot_xaxis.value),
                                    self.model.get_uniques_for(self.view.viz_ddn_plot_pivot.value))
        except Exception:
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())
            raise

    def cb_plot_menu(self, change):
        """User selected item from plot menu"""
        # noinspection PyBroadException
        try:
            if not change['owner'].value == PLOT_SET_CUSTOM:
                self.set_plot_config(change['owner'].value)
                self.process_and_plot()
        except Exception:
            self.empty_plot(error=True)
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())

    def cb_plot_button(self, _):
        """User pressed plot button"""
        # noinspection PyBroadException
        try:
            self.view.viz_ddn_plot_set.value = PLOT_SET_CUSTOM
            self.process_and_plot()
        except Exception:
            self.empty_plot(error=True)
            self.logger.debug('EXCEPTION\n' + traceback.format_exc())

    def process_and_plot(self):
        """Process data and plot it"""
        self.logger.debug('At')

        x = self.view.viz_ddn_plot_xaxis.value
        y = self.view.viz_ddn_plot_yaxis.value
        pivot = self.view.viz_ddn_plot_pivot.value
        fill = self.view.viz_ddn_plot_fill.value
        harm_row = self.view.viz_ddn_plot_harm_row.value
        harm_col = self.view.viz_ddn_plot_harm_col.value

        # Specify numeric axis(es)
        numeric_xy = (x == F_VAL or x == F_YER,
                      y == F_VAL or y == F_YER)

        # Plot will be based on model's "processed" data
        self.model.init_processed()

        # Clear pivot table data
        with self.view.viz_out_plot_data:
            clear_output(wait=True)

        self.model.pivot(x, pivot, y, self.view.viz_ddn_plot_aggfunc.value)

        # Fill missing values (interpolate)?
        if not fill == NONE_ITEM:
            self.model.fill(fill)

        # Index to year?

        indexed_by = None

        if self.view.viz_ckb_plot_index.value:

            if x == F_YER and not harm_row == NONE_ITEM:
                indexed_by = harm_row
            elif y == F_YER and not harm_col == NONE_ITEM:
                self.model.index(harm_col, on_row=False)
                indexed_by = harm_col

            if indexed_by is not None:
                self.model.index(indexed_by)

        # Harmonize?

        harmonized = False

        if (not harm_row == NONE_ITEM) and (not harm_col == NONE_ITEM):
            self.model.harmonize(harm_row, harm_col)
            harmonized = True

        # Title

        title = y + ' for ' + pivot + ' by ' + x

        if indexed_by is not None:
            if harmonized:
                title += ', Harmonized: '

                if indexed_by == harm_row:
                    title += str(harm_col)
                else:
                    title += str(harm_row)

            title += ', Index: ' + str(indexed_by) + '=100'

        elif harmonized:
            title += ', Harmonized: ' + str(harm_row) + ', ' + str(harm_col)

        self.model.dropna()

        # Show plot data
        with self.view.viz_out_plot_data:
            self.model.set_disp(self.model.processed, wide=True)
            clear_output(wait=True)
            display(self.model.processed)

        # Draw plot based on processed data
        self.draw_plot(title, x, y, numeric_xy)

    def set_plot_config(self, choice):
        """Update plot options"""
        self.logger.debug('At, choice='+str(choice))

        if choice == PLOT_SET_1:
            self.view.viz_ddn_plot_type.value = PLOT_TYPE_LINE
            self.view.viz_ddn_plot_xaxis.value = F_YER
            self.view.viz_ddn_plot_yaxis.value = F_VAL
            self.view.viz_ddn_plot_pivot.value = F_MOD
            self.view.viz_ddn_plot_aggfunc.value = AGGF_SUM
            self.view.viz_ddn_plot_fill.value = FILL_LINEAR
        elif choice == PLOT_SET_2:
            self.view.viz_ddn_plot_type.value = PLOT_TYPE_BAR
            self.view.viz_ddn_plot_xaxis.value = F_MOD
            self.view.viz_ddn_plot_yaxis.value = F_VAL
            self.view.viz_ddn_plot_pivot.value = F_SCN
            self.view.viz_ddn_plot_aggfunc.value = AGGF_MEAN
            self.view.viz_ddn_plot_fill.value = NONE_ITEM
        elif choice == PLOT_SET_3:
            self.view.viz_ddn_plot_type.value = PLOT_TYPE_LINE
            self.view.viz_ddn_plot_xaxis.value = F_YER
            self.view.viz_ddn_plot_yaxis.value = F_VAL
            self.view.viz_ddn_plot_pivot.value = F_MOD
            self.view.viz_ddn_plot_aggfunc.value = AGGF_SUM
            self.view.viz_ddn_plot_fill.value = FILL_CUBIC
            self.view.viz_ddn_plot_harm_row.value = self.view.viz_ddn_plot_harm_row.options[1]
            self.view.viz_ddn_plot_harm_col.value = self.view.viz_ddn_plot_harm_col.options[1]

    def empty_plot(self, error=None):
        """Display empty plot frame, with optional error message, in provided output widget"""
        self.logger.debug('At, error='+str(error))

        # noinspection PyBroadException
        try:
            if error:
                title = self.view.PLOT_ERROR_MSG
            else:
                title = 'Plot'

            with self.view.viz_out_plot_output:
                clear_output(wait=True)
                print()
                fig, ax = plt.subplots(figsize=(PLOT_WIDTH, PLOT_HEIGHT))
                ax.set_xlabel(PLOT_EMPTY_X_AXIS)
                ax.set_ylabel(PLOT_EMPTY_Y_AXIS)
                plt.title(title)
                plt.grid()
                self.plot_figure = plt.gcf()
                plt.show()
        except Exception:
            plt.close()  # Clear any partial plot output
            self.logger.debug('raising exception')
            raise

    def draw_plot(self, title, x_label, y_label, numeric_xy):
        """Create plot image and display it in provided output widget"""
        self.logger.debug('title=%s labels="%s","%s" num-xy=%s' % (title, x_label, y_label, str(numeric_xy)))

        # noinspection PyBroadException
        try:
            with self.view.viz_out_plot_output:
                # Clear existing plot output, including previous error msg
                clear_output(wait=True)
                print()

                # Render plot - NOTE Assumes data is pandas datatframe TODO Abstract that?

                fig, ax = plt.subplots()

                if self.view.viz_ddn_plot_type.value == PLOT_TYPE_LINE:
                    self.model.processed.plot(kind=PLOT_TYPE_LINE,
                                              ax=ax, grid=True, title=title,
                                              figsize=(PLOT_WIDTH, PLOT_HEIGHT),
                                              marker=PLOT_LINE_DATA_MARKER)
                else:
                    self.model.processed.plot(kind=self.view.viz_ddn_plot_type.value,
                                              ax=ax, grid=True, title=title,
                                              figsize=(PLOT_WIDTH, PLOT_HEIGHT))
                # Label axes
                ax.set_xlabel(x_label)
                ax.set_ylabel(y_label)

                # Avoid scientific notation for limits on numeric axis(es)
                if numeric_xy[0]:
                    ax.ticklabel_format(axis='x', useOffset=False, style='plain')
                if numeric_xy[1]:
                    ax.ticklabel_format(axis='y', useOffset=False, style='plain')

                # Update output widget with new plot
                self.plot_figure = plt.gcf()
                plt.show()
                self.logger.debug('after plt.show()')
        except Exception:
            plt.close()  # Clear any partial plot output
            self.logger.debug('raising exception')
            raise
'''