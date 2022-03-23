import ipywidgets as ui
from IPython.core.display import display
from IPython.display import FileLink
import sqlite3

from scripts.constants import *
from scripts.mapwidget import CustomMap
import os
from scripts.layerservice import RasterLayerUtil
from model.variableutil import VariableModel
from scripts.DBManager import *
import base64

def section(title, contents):
    """Create a collapsible widget container"""

    if type(contents) == str:
        contents = [ui.HTML(value=contents)]

    ret = ui.Accordion(children=tuple([ui.VBox(contents)]))
    ret.set_title(0, title)
    return ret

def section_horizontal(title,contents):
    """Create a collapsible widget container"""

    if type(contents) == str:
        contents = [ui.HTML(value=contents)]

    ret = ui.Accordion(children=tuple([ui.HBox(contents)]))
    ret.set_title(0, title)
    return ret
class View:
    TAB_TITLES = ['Create', 'Manage', 'View', 'About']
    MODEL_DROPDOWN_CREATETAB = ['-','Custom Crops','Custom CornSoy']
    SECTION_TITLE = 'Data'
    DATA_SOURCE_TITLE = 'Source'

    LO10 = ui.Layout(width='10%')
    LO15 = ui.Layout(width='15%')
    LO20 = ui.Layout(width='20%')
    LO25 = ui.Layout(width='25%')
    LOSEL = ui.Layout(width='33%')

    DATA_PRESENT_INDICATOR = '&#x2588'
    DATA_ABSENT_INDICATOR = '&#x2591'

#############################################################################################
    def __init__(self):
        # MVC objects
        self.model = None
        self.ctrl = None

        # User interface widgets

        # General
        self.tabs = None  # Main UI container
        self.debug_output = None
        self.display_object = None
        #[['job_id','private or public'],['job_id','private or public']]
        #1 for private 0 for public
        self.job_selection = []
        #When the user selects a job it populates these variables with the possible options
        self.dynamic_options = None
       
        
        #Create Tab
        self.model_dd = None
        self.name_tb = None
        self.submit_button = None
        self.description_ta = None
        self.upload_text = None
        self.upload_btn = None
        self.instructions_label_create = None
        
        # Manage Tab
        self.instructions_label = None
        self.refresh_btn = None
        self.selectable_window = None
        self.display_btn = None
        self.compare_btn = None
        self.checkboxes = {}
        self.shared_selectable_window = None
        self.shared_checkboxes = {}
        
        # View Tab 
        self.job_display = []
        self.system_component = None
        self.spatial_resolution = None
        self.type_of_result = None
        self.result_to_view = None
        self.min_max_slider = None
        self.name_dd = None
        self.view_button_submit = None
        self.view_vbox = None
        self.selectable_window_vbox = None
        self.shared_selectable_window_vbox = None
        self.longname = None
        
        #About Tab
        self.allcrops_download = None
        self.cornsoy_download = None
        #################################

    def intro(self, model, ctrl):
        """Introduce MVC modules to each other"""
        self.ctrl = ctrl
        self.model = model

    def display(self, display_log):
        """Build and show notebook user interface"""
        self.build()

        if display_log:
            self.debug_output = ui.Output(layout={'border': '1px solid black'})

            # noinspection PyTypeChecker
            display(ui.VBox([self.tabs, section('Log', [self.debug_output])]))
        else:
            display(self.tabs)

    def debug(self, text):
        with self.debug_output:
            print(text)

    def build(self):
        """Create user interface"""
        self.tabs = ui.Tab()

        # Set title for each tab
        for i in range(len(self.TAB_TITLES)):
            self.tabs.set_title(i, self.TAB_TITLES[i])

        # Build content (widgets) for each tab
        tab_content = [self.createTab(), self.manageTab(), self.viewTab(), self.aboutTab()]

        # Fill with content
        self.tabs.children = tuple(tab_content)

        # Initialize plotter
        #self.ctrl.empty_plot()
    def testwidget(self):
        freq_slider = ui.FloatSlider(value=2.,min=1.,max=10.0,step=0.1,description='Frequency:', readout_format='.1f',) 
       
        content = [section("test slider",[ui.VBox(children=[freq_slider])])]
        return ui.VBox(content)
    
    def createTab(self):
        
        box_layout = ui.Layout(display='flex',flex_flow='column', align_items='center',width='80%')
        self.instructions_label_create=ui.Label(value="Instructions: Upload the .cmf files here. Upload only one file. Look at the About Tab for cmf templates.")
        #Dropdown for the model Selction
        self.model_dd=ui.Dropdown(options=self.MODEL_DROPDOWN_CREATETAB,value='-',description='Model:',disabled=False)  
        #Name text Box
        self.name_tb=ui.Text(value='model',placeholder='Name of the model',description='Name:',disabled=False)       
        #Description Text Area
        self.description_ta=ui.Textarea(value='Description',placeholder='Description',description='Description:',disabled=False)       
        #Upload Button
        self.upload_text=ui.Label(value="Configuration File:")
        self.upload_btn=ui.FileUpload(
            accept='.cmf',  # Accepted file extension e.g. '.txt', '.pdf', 'image/*', 'image/*,.pdf'
            multiple=False  # True to accept multiple files upload else False
        )
        self.upload_btn.style.button_color = 'gray'
        self.upload_row=ui.HBox([self.upload_text,self.upload_btn])
        #Submit Button
        self.submit_button=ui.Button(description='SUBMIT')
        self.submit_button.style.button_color = 'gray'
        #submit_button.layout = ui.Layout(width="50%")
        #Creating a VBox with the individual widgets
        createTab_widgets = ui.VBox(children=[self.instructions_label_create,self.model_dd,self.name_tb,self.description_ta,self.upload_row,self.submit_button],layout=box_layout)
        #createTab_widgets.align_items = 'center'
        content = [section("New Experiment",[ui.VBox(children=[createTab_widgets])])]
        
        #Align things centrally
        box_layout = ui.Layout(display='flex',flex_flow='column', align_items='stretch',width='100%')
        contentvbox = ui.VBox(content,layout=box_layout)
        #contentvbox.layout.align_items = 'center'
        #self.test_btn=ui.Button(description='Test',icon='download')
        return contentvbox
    
    def manageTab(self):
        
        #Label with refresh and instructions
        self.instructions_label=ui.Label(value="Select one model for Display, select two for Compare. After clicking Display/Compare head to the View Tab")
        self.refresh_btn=ui.Button(description="Refresh",disabled=False)
        self.refresh_btn.style.button_color='gray'
        top_box=ui.HBox([self.refresh_btn,self.instructions_label])
        
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
        self.checkboxes = {}
        # to make sure at least one row will be displayed even when there is no job 
        mininum_rows_to_display = max(1, len(rows))
        self.selectable_window = ui.GridspecLayout(mininum_rows_to_display,11,height="auto")
        row_counter = 0
        #Create a new dictionary key value pair for each jobid and checkbox
        for row in rows:
            print(row)
            self.checkboxes[str(row_counter)]=ui.Checkbox(value=False,disabled=False,description="",indent=False,layout=ui.Layout(width="auto",height="auto"))
            self.selectable_window[row_counter,:1] = self.checkboxes[list(self.checkboxes.keys())[-1]]
            self.selectable_window[row_counter,1] = ui.HTML(str(row[0]))
            self.selectable_window[row_counter,2] = ui.HTML(row[6])
            self.selectable_window[row_counter,3:5] = ui.HTML(row[5])
            self.selectable_window[row_counter,5:10] = ui.HTML(row[7])
            self.selectable_window[row_counter,10] = ui.HTML(row[4])
            row_counter = row_counter + 1
            
        print(self.checkboxes)
        
        #Display Compare Buttons
        self.display_btn=ui.Button(description="Display",disabled=False)
        self.display_btn.style.button_color='gray'
        self.compare_btn=ui.Button(description="Compare",disabled=False)
        self.compare_btn.style.button_color='gray'
        self.bottom_box=ui.HBox([self.display_btn,self.compare_btn])
        self.selectable_window_vbox = ui.VBox(children=[self.comparetab_header, self.selectable_window])
        #Assign the grid layout to the Vbox and the content
        self.selectable_window.options = list_of_jobs        
        #Shared Job Display
        try:
            dbfile = "/data/groups/simpleggroup/job/job.db"
            conn = sqlite3.connect(dbfile)
            cursor = conn.cursor()
            #Database is always created first so the next statement should not give an error
            cursor.execute("SELECT * FROM SIMPLEJobs")
            rows = cursor.fetchall()
        except:
            #Join the widgets
            content=[top_box,section("Compare Tab",[self.selectable_window_vbox]),self.bottom_box] 
            contentvbox = ui.VBox(content)
        else:
            #Storing the contents of the db in list_of_jobs
            list_of_jobs = []
            
            
            if len(rows) > 0:
                #For alignment finding the max length of each column
                col_width = max(len(str(word)) for row in rows for word in row) + 2  # padding
                for row in rows:
                    str_row = "".join(str(word).ljust(col_width) for word in row)
                    list_of_jobs.append(str_row)
                    
            
            cursor.close()
            conn.close()
            self.shared_checkboxes = {}
            self.shared_selectable_window = ui.GridspecLayout(len(rows),11,height="auto")
            row_counter = 0

            #Create a new dictionary key value pair for each jobid and checkbox
            for row in rows:
                self.shared_checkboxes[str(row[0])]=ui.Checkbox(value=False,disabled=False,description="",indent=False,layout=ui.Layout(width="auto",height="auto"))
                self.shared_selectable_window[row_counter,:1] = self.shared_checkboxes[list(self.shared_checkboxes.keys())[-1]]
                self.shared_selectable_window[row_counter,1] = ui.HTML(str(row[0]))
                self.shared_selectable_window[row_counter,2] = ui.HTML(row[6])
                self.shared_selectable_window[row_counter,3:5] = ui.HTML(row[5])
                self.shared_selectable_window[row_counter,5:10] = ui.HTML(row[8])
                self.shared_selectable_window[row_counter,10] = ui.HTML(row[4])
                row_counter = row_counter + 1
            
            self.shared_selectable_window_vbox = ui.VBox(children=[self.comparetab_header, self.shared_selectable_window])
            #Assign the grid layout to the Vbox and the content
            self.shared_selectable_window.options = list_of_jobs        
            #Join the widgets
            content=[top_box,section("Compare Tab",[self.selectable_window_vbox]),section("Shared Jobs",[self.shared_selectable_window_vbox]),self.bottom_box] 
            contentvbox = ui.VBox(content)

        return contentvbox
    
    def viewTab(self):
        #Dropdown Menus Change if the Users makes a selection on the System Component Feature
        # Till there is a map on the View Tab there is no change to the dropdowns
        #The functions cb_model_mapping is for this
        #It would also disable some dropdowns if it is of no use
        box_layout = ui.Layout(display='flex',flex_flow='column', align_items='center',width='80%')
        self.system_component=ui.Dropdown(options = ["-"],value = '-',description='System Component:',disabled=False,style=dict(description_width='initial'))
        
        self.resolution=ui.Dropdown(options = ["-"],value = '-',description='Spatial Resolution:',disabled=False ,style=dict(description_width='initial'))
        
        self.type_of_result=ui.Dropdown(options = ["-"],value = '-',description='Type of Result:',disabled=False ,style=dict(description_width='initial'))
        
        self.result_to_view = ui.Dropdown(options = ["-"],value = '-',description='Result to View:',disabled=False,style=dict(description_width='initial'))
        
        self.name_dd = ui.Dropdown(options = ["-"],value = '-',description='Model Selection:',disabled=False,style=dict(description_width='initial'))
        
        self.min_max_slider = ui.IntRangeSlider(value=[0,100],min=0,max=100,step=1,description="Range of display",disabled = False, continuous_update=False,orientation = 'horizontal', readout =True, readout_format='d',style=dict(description_width='initial'))
        
        self.view_button_submit = ui.Button(description = 'SUBMIT')
        self.longname = ui.HTML(value="Long Name will be displayed here")
        
        content=section_horizontal("Select Options for displaying maps",[ui.VBox(children=[self.system_component,self.resolution,self.name_dd,self.result_to_view,self.type_of_result,self.min_max_slider,self.view_button_submit],layout=box_layout),self.longname])
        
        map_stuff_testing = '''map_wid = CustomMap("1200px","720px")
        freq_slider = ui.FloatSlider(value=0,min=0,max=100,step=0.1,description='Frequency:', readout_format='.1f',)
        mapbox=section("Map 1",[map_wid])
        id_str = "1"
        system_component="Production"
        spatial_resolution = "Geospatial"
        type_of_result = "PCT"
        result_to_view = "irrigated"
        filter_min = 0
        filter_max = 100

        variable_model = VariableModel(id_str, system_component, spatial_resolution, type_of_result,result_to_view, filter_min, filter_max)


        if variable_model.is_raster():
                layer_util = RasterLayerUtil(variable_model)
                layer = layer_util.create_layer()
                map_wid.visualize_raster(layer, layer_util.processed_raster_path)
        elif variable_model.is_vector():
                layer_util = VectorLayerUtil(variable_model)
                layer = layer_util.create_layer()
        '''
        self.view_button_submit.disabled = True
        self.view_vbox = ui.VBox(children=[content])
        return self.view_vbox
    
    def download_button(self,buffer, filename: str, button_description: str):

        """Loads data from buffer into base64 payload embedded into a HTML button. Recommended for small files only.

        buffer: open file object ready for reading.
            A file like object with a read method.
        filename:    str
            The name when it is downloaded.
        button_description: str
            The text that goes into the button.

        """

        payload = base64.b64encode(buffer).decode()

        html_button = f"""<html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
        <a download="{filename}" href="data:text/csv;base64,{payload}" >
        <button class="p-Widget jupyter-widgets jupyter-button widget-button mod-warning" style="width:auto">{button_description}</button>
        </a>
        </body>
        </html>
        """
        return ui.HTML(html_button)

    def aboutTab(self): 
        #Download Button for Custom CornSoy
        with open('SIMPLE_G_CornSoy.cmf', 'r') as f:
            file_content = f.read()
    
        f = file_content
        self.cornsoy_download = self.download_button(bytes(f,"utf-8"), 'SIMPLE_G_CornSoy.cmf','SIMPLE_G_CornSoy Template')
    
        with open('SIMPLE_G_AllCrops.cmf', 'r') as f:
            file_content = f.read()
    
        f = file_content 
        self.allcrops_download = self.download_button(bytes(f,"utf-8"), 'SIMPLE_G_AllCrops.cmf','SIMPLE_G_AllCrops Template')
    
        content = [section("Downloads",[ui.VBox(children=[self.allcrops_download,self.cornsoy_download])])]
        return ui.VBox(content)
    
