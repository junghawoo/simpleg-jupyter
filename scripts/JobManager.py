import os, glob, pprint, subprocess
import sys
import re
from scripts.SIMPLEUtil import SIMPLEUtil
from scripts.DBManager import DBManager
import time

# This class is modified from Hydroglobetool's JobManager class
class JobManager:
    
    dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool"
    
    db = None
    
    params = {}

    DEFAULT_WALTIME = 300 #minute
    TOOL_REVISION = 'runSIMPLE_US-r112'
    jobid = None

    #######################################
    # params: ['jobname']
    ################################################
    def __init__(self, params = None, control= None):
        if params == None and control == None: #job manage mode
            print("In the if")
            return

        self.params = params
        self.control = control
        self.db = DBManager(self.dbfile)
        print("===== Job submission to Stampede2 cluster =====")
        print("> JOB submission parameters : ")
        print(pprint.pformat(params))


        ###########################################################
        # job submission. Returns status(True,False), jobid
        # Jungha Woo
        # modeltype can be  'AllCrops','CornSoy', 'Custom AllCrops', or 'Custom CornSoy'
        # Please see modelInternalType at simpeGUI.py
        ###########################################################
    def submitJob(self, modeltype):
        # get new job id form DB

        jobid = self.db.createNewJob()
        if jobid == None:
            return False, jobid
        
        #jobid = '1'
        # create job folders
        # Job folder will have 'outputs' and 'supp_files' subdirectory
        jobdir = SIMPLEUtil.PRIVATE_JOBS_DIR+'/' + jobid
        jobOutputDir = SIMPLEUtil.PRIVATE_JOBS_DIR+'/' + jobid + '/outputs'
        SIMPLEUtil.rmdir(jobdir)
        SIMPLEUtil.mkdir(jobdir)
        SIMPLEUtil.mkdir(jobOutputDir)
        # cd to job dir since 'submit' script returns job result here
        os.chdir(jobOutputDir)

        waltime = self.DEFAULT_WALTIME


        # update db
        params = {}
        params['jobname'] = self.params['jobname']

        ret = self.db.updateJobInfo(jobid, params)

        #prepare CMF input file
        sourceDir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

        # 09/07/2019
        # Jungha Woo
        # User can upload custom cmf but there is no guarantee it will work
        # custom cmf file.
        # in the cluster as the file path translation steps are skipped for
        if modeltype == 'CornSoy':
            CMF_DIR      = sourceDir + "/bin"
            CMF_FILE     = 'SIMPLE_G_CornSoy.cmf'
            MODEL_OPTION = 'CornSoy';
            SUPP_DIR     = SIMPLEUtil.CORNSOY_SUPP_DIR;
        elif modeltype == 'AllCrops':
            CMF_DIR      = sourceDir + "/bin"
            CMF_FILE     = 'SIMPLE_G_AllCrops.cmf'
            MODEL_OPTION = 'AllCrops';
            SUPP_DIR     = SIMPLEUtil.ALLCROPS_SUPP_DIR;
        elif modeltype == 'Custom CornSoy':
            CMF_DIR      = SIMPLEUtil.USERHOME_DIR+"/"
            #CMF_DIR      = sourceDir+"/src"
            CMF_FILE     = 'custom.cmf'
            MODEL_OPTION = 'CornSoy';
            SUPP_DIR     = SIMPLEUtil.CORNSOY_SUPP_DIR;
        elif modeltype == 'Custom AllCrops':
            CMF_DIR      = SIMPLEUtil.USERHOME_DIR+"/"
            #CMF_DIR      = sourceDir +"/src"
            CMF_FILE     = 'custom.cmf'
            MODEL_OPTION = 'AllCrops';
            SUPP_DIR     = SIMPLEUtil.ALLCROPS_SUPP_DIR;

        print('cp %s/%s %s' %(CMF_DIR, CMF_FILE, jobOutputDir))
        os.system('cp %s/%s %s' %(CMF_DIR, CMF_FILE, jobOutputDir))
        sys.stdout.flush()
        # SIMPLE-G-mapping_file.csv is required to get readable string for each shock variables in the output dialog
        os.system('cp -r %s %s' %(SUPP_DIR, jobdir))
        print('cp -r %s %s' %(SUPP_DIR, jobdir))

        if jobid != None:
            #write baseline shocks to CMF
            #self.control.applyBaselineShocks(jobid)
            #write policy shocks to the CMF file
            #self.control.setPolicyTab.getAllPolicies(jobid, CMF_FILE);
            command = ''''''
        else :
            print("Job submit failed ")
            return False, None


        # 09/07/2019
        # disabled for simple us short course
        #option_string_customfiles = SIMPLEUtil.get_custom_shocks_options(jobid)
        option_string_customfiles = ''

        # submit job
        # TODO: Add custom file uploads
        jobcmd = 'submit -w ' + str(waltime) + \
            ' --detach' + \
            ' ' + JobManager.TOOL_REVISION + ' '+ MODEL_OPTION +\
            ' -cmf '+ CMF_FILE +\
            option_string_customfiles

        print("jobcmd:", jobcmd)
        sys.stdout.flush()
        print('\n> Job submission command : ')
        print(jobcmd)


        #return True, ''

        ret = subprocess.check_output(jobcmd.split())
        print("[", ret, "]")
        if 'Detaching from run' not in ret:
            # job submission error
            self.db.updateJobStatus(jobid, 'Failed')
            return False, ret.replace('\\n','\n')

        print(ret.replace('\\n','\n'))

        # get job submission id
        #submit_id = ret.split()[3][:-1]
        match = re.search('[0-9]{8}', ret)

        if match:
            submit_id = match.group(0)
            print('\n> Job has been submitted successfully. Cluster job submission id : ', submit_id)

            params = {}
            params['submitId'] = submit_id
            params['jobstatus'] = 'Pending'
            params['modeltype'] = modeltype
            params['published'] = 0
            #params['ModName'] = os.environ['USER']+"-"+jobid

        else:
            # 01/23/2020 Jungha Woo
            # if we failed to get job id from cluster log file, 
            # set job_id to 0 to signal wrong job 
            submit_id = '00000000'
            print('\n> Failed to get valid job_id from cluster: ', submit_id)

            params = {}
            params['submitId'] = submit_id
            params['jobstatus'] = 'Failed'
            params['modeltype'] = modeltype
            params['published'] = 0
            #params['ModName'] = os.environ['USER']+"-"+jobid

        ret = self.db.updateJobInfo(jobid, params)

        if ret == False:
            return False, 'Job info update failure.'

        return True, jobid

    def updateAllJobStatus(self):
        # get job lists
        #called when we click Manage Jobs tab
        job_list = self.db.getJobList()
        for job in job_list:
            #jobstatus is 5th column of the job table
            if job[4] in ['Pending', 'Queued', 'Running', 'Completing']:
                status = self.getJobStatus(job)
                print("jobid :", job[0], " status:", status)
                self.db.updateJobStatus(job[0], status, job[1])

        sys.stdout.flush()


    def getJobStatus(self, job_info): #[Registered, Submitted, Queued, Running, Completed ]
        submit_id = job_info[1]
        jobid = job_info[0]
        cmd = 'submit --status ' + submit_id

        trial = 0
        while True: # status command sometimes returns nothing
            ret = subprocess.check_output(cmd.split())
            ret = ret.split()
            # normally its length is 10
            if len(ret) > 5:
                break

            if trial > 4:
                return self.check_job_success(jobid, submit_id)

            trial += 1


        if ret[8] in ['Registered', 'Submitted']:
            return 'Pending'

        if ret[8] == 'Completing':
            return 'Completed'
            # print 'complete'
            # return self.check_job_success(jobid, submit_id)

        print("getJobStatus[", submit_id,"]: ",ret[8])
        return ret[8]




    def check_job_success(self, jobid, submit_id):


        jobOutputDir = SIMPLEUtil.PRIVATE_JOBS_DIR+'/' + str(jobid) + '/outputs'

        ret = len(glob.glob(jobOutputDir + '/*.sl4'))
        if ret == 0:
            status = 'Failed'
        else:
            status = 'Completed'

        # attach to job to terminate the process
        cmd = 'submit --attach ' + submit_id
        os.system(cmd)  # check_output stuck for some reasons..
        # ret = subprocess.check_output(cmd.split())

        return status

    def deleteJob(self, jobid):
        #get submit id
        job_info = self.db.getJobInfo(jobid)
        if job_info == None:
            return

        #submit_id = job_info[1]
        #if self.getJobStatus(submit_id) in ['Pending', 'Queued', 'Running']:
        if job_info[3] in ['Pending', 'Queued', 'Running', 'Completing']:
            cmd = 'submit --kill ' + submit_id
            ret = subprocess.check_output(cmd.split())


        # delete job files
        SIMPLEUtil.rmdir(SIMPLEUtil.PRIVATE_JOBS_DIR + '/' + str(jobid))
        # delete job from DB
        self.db.deleteJob(jobid)
    
    
    def testSubmit(self):
        jobid = self.db.createNewJob()
        if jobid == None:
            return False, jobid

        jobdir = SIMPLEUtil.PRIVATE_JOBS_DIR+'/'+jobid
        jobOutputDir = SIMPLEUtil.PRIVATE_JOBS_DIR+'/'+jobid+'/outputs'
        SIMPLEUtil.rmdir(jobdir)
        SIMPLEUtil.mkdir(jobdir)
        SIMPLEUtil.mkdir(jobOutputDir)
        os.chdir(jobOutputDir)
        waltime = self.DEFAULT_WALTIME

        params = {}
       # params['jobname'] = self.params['jobname']
        params['jobname'] = "testa"
        ret = self.db.updateJobInfo(jobid, params)

        modeltype='AllCrops'

        jobcmd = 'submit -w 300 --detach  runSIMPLE_US-r112 AllCrops -cmf SIMPLE_G_AllCrops.test.cmf'

        ret = subprocess.check_output(jobcmd.split())
        if 'Detaching from run' not in ret:
            self.db.updateJobStatus(jobid, 'Failed')
            return False, ret.replace('\\n','\n')

        print(ret.replace('\\n','\n'))
        submit_id = ret.split()[3][:-1]
        print('\n> Job has been submitted successfully. Cluster job submission id: ', submit_id)

        params = {}
        params['submitId'] = submit_id
        params['jobstatus'] = 'Pending'
        params['modeltype'] = modeltype
        params['published'] = 0
        
        ret = self.db.updateJobInfo(jobid, params)

        if ret==False:
            return False, 'Job info update failure.'

if __name__ == "__main__":
    jm = JobManager()
    jm.testSubmit()