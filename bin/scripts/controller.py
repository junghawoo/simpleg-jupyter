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
import sys
from scripts.SIMPLEUtil import SIMPLEUtil

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
            
            #Manage Tab Display Button, single model display
            self.view.display_btn.on_click(self.cb_display_btn)
            
            #View Tab Submit Button Display the model
            self.view.view_button_submit.on_click(self.cb_tif_display)
            
            #View Tab If the system component dropdown changes
            self.view.system_component.observe(self.cb_model_mapping)
            
            #View Tab If the spatial resolution dropdown changes
            self.view.resolution.observe(self.cb_model_mapping_name)
            
            #View Tab If the model selection dropdown changes
            self.view.name_dd.observe(self.cb_model_mapping_type)
            
            #View Tab If the type of result dropdown changes
            self.view.type_of_result.observe(self.cb_submit_button_enable)
            
            #View Tab If the result to view dropdown changes
            self.view.result_to_view.observe(self.cb_result_to_view)
            
            #Manage Tab Compare Button, two jobs
            self.view.compare_btn.on_click(self.cb_compare_models)
            
            #Manage Tab Refresh Button to refresh job list
            self.view.refresh_btn.on_click(self.refresh_manage_jobs_status)
            
            #Create Tab Submit job to cluster
            self.view.submit_button.on_click(self.cb_upload_btn_create)
            

        except Exception:
            self.logger.error('EXCEPTION\n' + traceback.format_exc())
            raise
            
    def cb_test(self, _):
        print(self.view.model_dd.value)
     
    #Setting the system component options when the user selcts a job to display or compare
    def view_layer_options(self,_):
       
        system_component = list(self.view.dynamic_options.keys())
        system_component.insert(0,"-")
        #Updating the options of the system component dropdown
        self.view.system_component.options = system_component
        self.view.system_component.value =  self.view.system_component.options[0]
        #Remaining options will just be "-" and will be updated when the preceeding option changes
        self.view.resolution.options = ["-"]
        self.view.resolution.value =  self.view.resolution.options[0]
        self.view.type_of_result.options = ["-"]
        self.view.type_of_result.value =  self.view.type_of_result.options[0]
        self.view.result_to_view.options = ["-"]
        self.view.result_to_view.value =  self.view.result_to_view.options[0]
        self.view.name_dd.options = ["-"]
        self.view.name_dd.value =  self.view.name_dd.options[0]
        return
    
    def cb_upload_btn_create(self, _):
        self.view.submit_button.disabled = True
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
        self.view.refresh_btn.disabled = True
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
        submit = subprocess.run(["submit", "--detach" ,"-w","15","-i",command,command_simple ], capture_output=True ,cwd= file_location)
        # Path needs to be outputs not out
        get_id = submit.stdout.decode("utf-8")
        print("get_id:{}".format(get_id))
        start = get_id.find("run") + 4
        end = get_id.find(".\n")
        remote_job_id = get_id[start:end]
        print("job_id {} remote_job_id:{}".format(job_id, remote_job_id))
        sys.stdout.flush()
        
        self.db_class_import.updateRemoteID(job_id,remote_job_id)
        self.db_class_import.updateJobStatus(job_id,"Pending")
        self.refresh_manage_jobs("None")
        self.view.upload_btn.value.clear()
        self.view.upload_btn._counter = 0
        self.view.refresh_btn.disabled = False
        self.view.submit_button.disabled = False 
        return 
    
    def jobs_selected(self,_):
        #This will return a list of the job ids which are selected in the job_selection variable
        #Running a loop to check selected checkboxes for the box
        #['job_id','private or public']
        #1 for private 0 for public
        #self.model_type = 0
        #0 for all crops 1 for cornsoy
        self.view.job_selection = []
        row_counter = 0
        self.model_type = []
        for jobid,checkbox in self.view.checkboxes.items():
            #print(self.view.selectable_window[row_counter,2].value + " all")
            if(checkbox.value == True):
                self.view.job_selection.append([jobid,1])
                #print(self.view.selectable_window)
                #print(self.view.selectable_window[row_counter,2].value + " selected")
                if(self.view.selectable_window[row_counter,2].value == "Custom Crops"):
                    self.model_type.append(0)
                else:
                    self.model_type.append(1)
                #print(self.model_type[-1])
            row_counter +=1
        row_counter = 0
        for jobid,checkbox in self.view.shared_checkboxes.items():
            if(checkbox.value == True):
                self.view.job_selection.append([jobid,0])
                if(self.view.shared_selectable_window[row_counter,2].value == "AllCrops"):
                    self.model_type.append(0)
                else:
                    self.model_type.append(1)
            row_counter +=1
        #print(self.model_type)
        temp = self.model_type[0]
        self.model_type = temp
        #print(self.model_type)        

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
        
        
        #check if job table is empty.
        if len(rows) > 0 :
            #For alignment finding the max length of each column
            col_width = max(len(str(word)) for row in rows for word in row) + 2  # padding
            for row in rows:
                str_row = "".join(str(word).ljust(col_width) for word in row)
                list_of_jobs.append(str_row)
                
                
        cursor.close()
        conn.close()
        
        
         
        #prepare header table 
        self.comparetab_header = ui.GridspecLayout(1,11,height="auto")
        self.comparetab_header[0,:1] = ui.HTML(value = f"<b><font color='#1167b1'>Select</b>")
        self.comparetab_header[0,1] = ui.HTML(value = f"<b><font color='#1167b1'>Job ID</b>")
        self.comparetab_header[0,2] = ui.HTML(value = f"<b><font color='#1167b1'>Model Type</b>" )
        self.comparetab_header[0,3:5] = ui.HTML(value = f"<b><font color='#1167b1'>Job Name</b>" )
        self.comparetab_header[0,5:10] = ui.HTML(value = f"<b><font color='#1167b1'>Description</b>")
        self.comparetab_header[0,10] = ui.HTML(value = f"<b><font color='#1167b1'>Job Status</b>")
        
        
        #Selectable multiple widget / Checkboxes for each
        self.view.checkboxes = {}
        # to make sure at least one row will be displayed even when there is no job 
        mininum_rows_to_display = max(1, len(rows))
        
        self.view.selectable_window = ui.GridspecLayout(mininum_rows_to_display,11,height="auto")
        self.view.job_selection = []
        row_counter = 0
        #Create a new dictionary key value pair for each jobid and checkbox
        for row in rows:
            self.view.checkboxes[str(row_counter)]=ui.Checkbox(value=False,disabled=False,description="",indent=False,layout=ui.Layout(width="auto",height="auto"))
            self.view.selectable_window[row_counter,:1] = self.view.checkboxes[list(self.view.checkboxes.keys())[-1]]
            self.view.selectable_window[row_counter,1] = ui.HTML(str(row[0]))
            self.view.selectable_window[row_counter,2] = ui.HTML(row[6])
            self.view.selectable_window[row_counter,3:5] = ui.HTML(row[5])
            self.view.selectable_window[row_counter,5:10] = ui.HTML(row[7])
            self.view.selectable_window[row_counter,10] = ui.HTML(row[4])
            row_counter = row_counter + 1
        
        self.view.selectable_window_vbox.children=[self.comparetab_header, self.view.selectable_window]
        return
    
    #Refresh the job list when the refresh button is clicked on the manage tab 
    def refresh_manage_jobs_status(self,_):
        self.view.refresh_btn.disabled = True
        #Temporary Database Access will be refreshed with a global variable and the callback function
        dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/DatabaseFile(DONOTDELETE).db"
        conn = sqlite3.connect(dbfile)
        cursor = conn.cursor()
        #Database is always created first so the next statement should not give an error
        cursor.execute("SELECT * FROM SIMPLEJobs")
        rows = cursor.fetchall()
        #Storing the contents of the db in list_of_jobs
        list_of_jobs = []
        cursor.close()
        conn.close()
        #For alignment finding the max length of each column
        for row in rows:
            # job_id was incorrectly set to row[1] which is the submitId
            job_id = row[0]
            #Jungha Woo
            #We will use submitId for remote job id. Remote job id field will be deleted later.
            remote_job_id = row[1]
            if row[4] in ['Pending', 'Queued', 'Running']:
                submit = subprocess.run(["submit", "--status" ,str(remote_job_id) ], capture_output=True)
                output = submit.stdout.decode("utf-8")
                if len(output) < 5 or 'Completing' in output:
                    file_location = os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/job/" + str(job_id) + "/out"
                    if os.path.isdir(file_location):
                        self.db_class_import.updateJobStatus(job_id,"Completed")
                        file_location = os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/job/" + str(job_id)
                        os.rename(file_location+"/out",file_location+"/outputs")
                    continue
                if 'Registered' in output or 'Submitted' in output:
                    self.db_class_import.updateJobStatus(job_id,"Pending")
                    continue
                if 'Queued' in output:
                    self.db_class_import.updateJobStatus(job_id,"Queued")
                    continue
                if 'Running' in output:
                    self.db_class_import.updateJobStatus(job_id,"Running")
                    continue
        self.refresh_manage_jobs("None")        
        self.view.refresh_btn.disabled = False
        return
    
    
    #Building the list of options for the view tab according to the job
    def buildResultList(self,folder):
            #The job is public or private depends on the input to the function, the input will a list of the format
            #[job_id, is_private]
            #0 is public, 1 is private
            if folder[1] == 0:
                root =  "/data/groups/simpleggroup/job/"+folder[0]+"/outputs/results"
            else:
                root = os.path.expanduser("~") + "/SimpleGTool/job/"+folder[0]+"/outputs/results"
            #print("root :"+ root)

            resultList = {}

            dirlist = [ item for item in os.listdir(root) if os.path.isdir(os.path.join(root, item)) ]
            #print( "dirlist: ",dirlist)

            for dir in dirlist:
                resultList[dir] = {}
                root2 = root + "/" + dir
                dirlist2 = [ item for item in os.listdir(root2) if os.path.isdir(os.path.join(root2, item)) ]
                for dir2 in dirlist2:
                    resultList[dir][dir2] = {}
                    root3 = root + "/" + dir + "/" + dir2
                    dirlist3 = [ item for item in os.listdir(root3) if os.path.isdir(os.path.join(root3, item)) ]
                    for dir3 in dirlist3:
                        resultList[dir][dir2][dir3] = []
                        root4 = root + "/" + dir + "/" + dir2 + "/" + dir3
                        dirlist4 = [ item for item in os.listdir(root4) if os.path.isdir(os.path.join(root4, item)) ]
                        dirlist4.sort()
                        for dir4 in dirlist4:
                            resultList[dir][dir2][dir3].append(dir4)

            #print("resultsList: " )
            #debug
            #print(resultList)
            #for k,v in resultList:
                #print(k,v )

            return resultList
        
    #Callback for the Manage Tab Display Button, this is for single job alone
    def cb_display_btn(self,_):
        self.view.system_component.value = self.view.system_component.options[0]
        self.view.job_display = []
        content = self.view.view_vbox.children[0]
        self.view.view_vbox.children = tuple([content])
        self.jobs_selected("Garbage Value")
            
        if(len(self.view.job_selection)!=1):
            self.view.instructions_label.value ="Select one model only for display, check shared jobs as well"
            return
        else:    
            self.view.instructions_label.value ="Select one model for Display, select two for Compare. After clicking Display/Compare head to the View Tab"
        #print(self.view.checkboxes)
        #print(self.view.checkboxes.keys())
        #Getting the options to fill the options in the View Tab
        #This dynamic options variable will be used to fill the options of the 
        self.view.dynamic_options=self.buildResultList(self.view.job_selection[0])
        #print(self.view.dynamic_options)
        self.view_layer_options("Garbage")
        for job in self.view.checkboxes.keys():
            if self.view.checkboxes[job].value == True:
                self.create_map_widget(job,1)
                self.view.job_display.append([job,1])
                #print(self.view.checkboxes[job])
                break
        for job in self.view.shared_checkboxes.keys():
            if self.view.shared_checkboxes[job].value == True:
                self.create_map_widget(job,0)
                self.view.job_display.append([job,0])
                break
        return 
    
    def create_map_widget(self,map_id,is_private):
        map_wid = CustomMap("1200px","720px")
        if is_private == 1:
            mapbox=section("Map ID(Private Job): "+str(map_id),[map_wid])
        else:
            mapbox=section("Map ID(Shared Job): "+str(map_id),[map_wid])
        temp_list = list(self.view.view_vbox.children)
        temp_list.append(mapbox)
        self.view.view_vbox.children = tuple(temp_list)
        return
    def create_map_widget_compare(self,map_id):
        
        map_wid = CustomMap("600px","720px")
        map_wid_1 = CustomMap("600px","720px")
        map_wid.link(map_wid_1)
        if map_id[0][1] == 1:
            map_1 = "Private JobID "+str(map_id[0][0])
        else:
            map_1 = "Public JobID "+str(map_id[0][0])
        if map_id[1][1] == 1:
            map_2 = "Private JobID "+str(map_id[1][0])
        else:
            map_2 = "Public JobID "+str(map_id[1][0])
        mapbox=section_horizontal("Map: "+map_1+" and "+map_2,[map_wid,map_wid_1])
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
                try:  
                    #print("Compare")
                    mapbox = self.view.view_vbox.children[i].children[0]
                    map_id = self.view.job_selection[0][0]
                    map_id_1 = self.view.job_selection[1][0]
                    
                    variable_model = VariableModel(map_id,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value,self.view.job_selection[0][1])
                    
                    variable_model_1 = VariableModel(map_id_1,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value,self.view.job_selection[1][1])
                    
                    map_wid = mapbox.children[0]
                    map_wid_1 =mapbox.children[1]
                    if len(map_wid.layers) == 2: 
                        map_wid.remove_layer(map_wid.layers[1])
                    if len(map_wid_1.layers) == 2:
                        map_wid_1.remove_layer(map_wid_1.layers[1])
                    #break
                    
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
                        map_wid_1.add_layer(layer)
                        layer_util.create_legend(map_wid_1)
                      

                    break     
                except Exception as e:
                    #print(e)
                    self.view.longname.value = "This Comparison is not possible"
                    break
            #Below is single map processing
            try:
                mapbox = self.view.view_vbox.children[i]
                map_id = self.view.job_selection[0][0]
                variable_model = VariableModel(map_id,self.view.system_component.value, self.view.resolution.value,self.view.type_of_result.value,self.view.result_to_view.value,min(self.view.min_max_slider.value), max(self.view.min_max_slider.value),self.view.name_dd.value,self.view.job_selection[0][1])
                mapbox.children[0].children[0].close()
                mapbox.children[0].children = [CustomMap("1200px","720px")]
                map_wid = mapbox.children[0].children[0]
                if len(map_wid.layers) == 2:
                    #print("Deleting Layers")
                    map_wid.remove_layer(map_wid.layers[1]) 
                if variable_model.is_raster():
                    layer_util = RasterLayerUtil(variable_model)
                    layer = layer_util.create_layer()
                    map_wid.visualize_raster(layer, layer_util.processed_raster_path)
                elif variable_model.is_vector():
                    layer_util = VectorLayerUtil(variable_model)
                    layer = layer_util.create_layer()
                    map_wid.add_layer(layer)
                    layer_util.create_legend(map_wid)           
                break
            except Exception as e:
                print(e)
                self.view.longname.value = "This file does not exist"
        return
    #System Component dropdown changes
    def cb_model_mapping(self,_):
        #If the map is present or not
        if (len(self.view.view_vbox.children) <= 1):
            return
        if self.view.system_component.value == "-":
            return
        self.view.view_button_submit.disabled = True
        options = list(self.view.dynamic_options[self.view.system_component.value].keys())
        options.insert(0,"-")
        self.view.resolution.options = options
        self.view.resolution.value =  self.view.resolution.options[0]
        #Remaining options will just be "-" and will be updated when the preceeding option changes
        self.view.type_of_result.options = ["-"]
        self.view.type_of_result.value =  self.view.type_of_result.options[0]
        self.view.result_to_view.options = ["-"]
        self.view.result_to_view.value =  self.view.result_to_view.options[0]
        self.view.name_dd.options = ["-"]
        self.view.name_dd.value =  self.view.name_dd.options[0]
        return 
    
    #Spatial Resolution Changes 
    def cb_model_mapping_name(self,_):
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        if(self.view.system_component.value=="-" or self.view.resolution.value=="-"):
            return
        self.view.result_to_view.options = ["-"]
        self.view.result_to_view.disabled = True
        self.view.name_dd.value = self.view.name_dd.options[0]
        #Change the name_dd (Model Selection) options
        options = list(self.view.dynamic_options[self.view.system_component.value][self.view.resolution.value].keys())
        options.insert(0,"-")
        self.view.name_dd.options = options
        self.view.name_dd.value =  self.view.name_dd.options[0]        

        #Remaining options will just be "-" and will be updated when the preceeding option changes
        self.view.result_to_view.options = ["-"]
        self.view.result_to_view.value =  self.view.result_to_view.options[0]

        self.view.type_of_result.options = ["-"]
        self.view.type_of_result.value =  self.view.type_of_result.options[0]
        return
    #Checking to see if the model has an additional irrigated and rainfed subdivision
    def result_to_view_needed(self):
        results = []
        path = ""
        if self.view.job_selection[0][1] == 0:
            path =  "/data/groups/simpleggroup/job/"+self.view.job_selection[0][0]+"/outputs/results"
        else:
            path = os.path.expanduser("~") + "/SimpleGTool/job/"+self.view.job_selection[0][0]+"/outputs/results"
        
        path = path + "/" + self.view.system_component.value + "/" + self.view.resolution.value + "/" + self.view.name_dd.value 
        type_of_result = os.listdir(path)
        path = path + "/" + type_of_result[0]
        for file in os.listdir(path):
            if "irrigated" in file:
                results.append("Irrigated")
            if "rainfed" in file:
                results.append("Rainfed")
                
        return list(set(results))
    #If the name drop down changes
    def cb_model_mapping_type(self,_):
        self.view.type_of_result.value=self.view.type_of_result.options[0]
        self.view.view_button_submit.disabled = True
        self.view.type_of_result.options = ["-"]
        self.view.type_of_result.value =  self.view.type_of_result.options[0]
        if(self.view.system_component.value=="-" or self.view.resolution.value=="-" or self.view.name_dd.value=="-"):
            return
        result_to_view = self.result_to_view_needed()
        if result_to_view == []:
            self.view.result_to_view.disabled = True
            self.view.result_to_view.options = ["-"]
            self.view.result_to_view.value = self.view.result_to_view.options[0]
        else:
            self.view.result_to_view.disabled = False
            result_to_view.insert(0,"-")
            self.view.result_to_view.options = result_to_view
            self.view.result_to_view.value = self.view.result_to_view.options[0]
        COMMENT  = """
        final_result={"N-use Grid":"Nitrogen Use by Grid, Type (in MT)","Water Use Grid":"Water Use by Grid (in 1000 m^3 yr)","Water Use Region":"Water Use by Region (in 1000 m^3 yr)","Water per Ha":"Water per Ha by Region (in m^3 yr / ha)","Land Use Region Type":"Cropland Area by Region, Type (in 1000 ha)","Land Use-Region":"Cropland Area by Region (in 1000 ha)","Output Grid":"Corn Soy Output by Grid, Type (in 1000 MT Corn eq)","Yield Region":"Crop Yield by Region (in MT per ha)","Regional Price":"Corn Soy Supply Price by Region (in USD / MT)","Net Export":"Corn Soy Net Exports by Region (in 1000 MT Corn eq)","Output Region":"Corn Soy Output by Region (in 1000 MT Corn eq)","World Price":"World Corn Soy Price(in USD / MT)","Land Use Grid":"Cropland Area by Grid, Type (in 1000 ha)","N use Grid":"Nitrogen Leaching by Grid Type (in kg per ha)","N Leach Int - Grid":"Nitrogen Leaching Intensity by Grid Type (in MT per USD N use)","Price of N - Grid":"Price of Nitrogen by Grid Type (in USD / MT)","Output - Grid":"Corn Soy Output by Grid, Type (in 1000 MT Corn eq)","Output - Region":"Corn Soy Output by Region (in 1000 MT Corn eq)"}
        """
        self.cb_result_to_view("Garbage")
        self.cb_submit_button_enable("Garbage")
        return
    #If the result to view was changed
    def cb_result_to_view(self,_):
        if self.view.system_component.value == "-" or self.view.resolution.value == "-" or self.view.name_dd.value == "-":
            return
        options = self.view.dynamic_options[self.view.system_component.value][self.view.resolution.value][self.view.name_dd.value]
        if options[0] != "-":
            options.insert(0,"-")
        self.view.type_of_result.options = options
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
    
    def find_common(self,model1,model2):
        results = {}
        for system_component in model1.keys():
                if system_component not in model2.keys():
                    continue
                for spatial_resolution in model1[system_component].keys():
                    if spatial_resolution not in model2[system_component].keys():
                        continue
                    for model in model1[system_component][spatial_resolution].keys():
                        if model not in model2[system_component][spatial_resolution].keys():
                            continue
                        if model1[system_component][spatial_resolution][model] != model2[system_component][spatial_resolution][model]:
                            continue
                        if system_component not in results.keys(): 
                            results[system_component] = {spatial_resolution:{model:model1[system_component][spatial_resolution][model]}}
                        else:
                            if spatial_resolution not in results[system_component].keys():
                                results[system_component][spatial_resolution] = {model:model1[system_component][spatial_resolution][model]}
                            else:
                                results[system_component][spatial_resolution][model] = model1[system_component][spatial_resolution][model]
        return results
    
    def cb_compare_models(self,_):
        content = self.view.view_vbox.children[0]
        self.view.view_vbox.children = tuple([content])
        self.jobs_selected("Garbage Value")
        if(len(self.view.job_selection)!=2):
            self.view.instructions_label.value = "Select exactly 2 models to compare"
            return
        else:
            self.view.instructions_label.value ="Select one model for Display, select two for Compare. After clicking Display/Compare head to the View Tab"
            model_1_options = self.buildResultList(self.view.job_selection[0])
            model_2_options = self.buildResultList(self.view.job_selection[1])
            #print(model_1_options)
            #print( model_2_options)
            self.view.dynamic_options = self.find_common(model_1_options,model_2_options)
            if self.view.dynamic_options == {}:
                self.view.instructions_label.value = "There are no common elements for comparison"
                return
            #print(self.view.dynamic_options)
            #Fill the system component dropdown
            self.view_layer_options("Garbage")
            self.create_map_widget_compare(self.view.job_selection)
        return
    