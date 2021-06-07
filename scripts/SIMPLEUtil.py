import os,sys,re
import json
import errno
import shutil
import pwd
import grp


class SIMPLEUtil:

    USERHOME_DIR = os.path.expanduser("~")
    WORKING_DIR = os.path.expanduser("~") + "/SimpleGTool"
    PRIVATE_JOBS_DIR = WORKING_DIR +"/job"
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) #/home/mygeohub/yirugi/notebooks/hydroglobe/trunk
    SHARED_JOBS_DIR = '/data/groups/simpleggroup/job'
    SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
    DATA_DIR = SRC_DIR + "/data"
    CORNSOY_SUPP_DIR = SRC_DIR + "/inputs/CornSoy/supp_files"
    ALLCROPS_SUPP_DIR = SRC_DIR + "/inputs/AllCrops/supp_files"

    @staticmethod
    def mkdir(dir):
        if not os.path.exists(dir):
            os.mkdir(dir)

    # recursive directory creation function
    @staticmethod
    def mkdir_p(dir):
        try:
            if not os.path.exists(dir):
                os.makedirs(dir)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(dir) :
                pass
            else:
                raise


    @staticmethod
    def copy(src, dest):
        try:
            shutil.copytree(src, dest)
        except OSError as e:
            # If the error was caused because the source wasn't a directory
            if e.errno == errno.ENOTDIR:
                shutil.copy(src, dest)
            else:
                print('Directory not copied. Error: %s' % e)


    # does not chmod for directories
    @staticmethod
    def makeReadable_recursive(dest):
        for root, dirs, files in os.walk(dest):

          for momo in dirs:
            dirpath = os.path.join(root, momo)
            old_stat = os.stat(dirpath)
            # directory must have execute bit for directory traversing
            os.chmod(dirpath, old_stat.st_mode | 0o755)
          for momo in files:
            filepath = os.path.join(root, momo)
            old_stat = os.stat(filepath)
            os.chmod(filepath, old_stat.st_mode| 0o764)

    @staticmethod
    def rmdir(dir):
        os.system('rm -rf ' + dir)


    @staticmethod
    def replace_file(file_path, str_ori, str_dst):
        with open(file_path,'r') as f:
             co = f.read()
             new_co = re.sub(str(str_ori), str(str_dst), co)
             with open(file_path,'w') as f:
                  f.write(new_co)

    @staticmethod
    def create_custom_file(file_path, val_list):
        with open(file_path,'w') as f:
             f.write(str(len(val_list))+" REAL;\n")
             for v in val_list:
                f.write(str(v)+"\n")

    @staticmethod
    def get_custom_shocks_options(jobid):

        file_path =  SIMPLEUtil.PRIVATE_JOBS_DIR +"/"+str(jobid)+"/outputs/SIMPLE_G.cmf"

        customs = {'<QLAND_CUSTOM>' : '-cl',
                   '<QNITRO_CUSTOM>': '-cn',
                   '<QWATER_CUSTOM>': '-cw',
                   # baseline custom files
                   '<POP_CUSTOM>': '-bp',
                   '<INCOME_CUSTOM>': '-bi',
                   '<BIOFUEL_CUSTOM>': '-bf',
                   '<CROPPDVT_CUSTOM>': '-bc',
                   '<ANIMALPDVT_CUSTOM>': '-ba'
                   }
        option_string = ""
        with open(file_path,'r') as f:
             co = f.read()

             for key, value in customs.items():
                 if key in co:
                    print(key, value)
                    # return "-cl QLAND_CUSTOM.txt" if <QLAND_CUSTOM> is found
                    option_string += value + " "+  key.strip('<>')+".txt  "
                    print(option_string)
        return option_string

    @staticmethod
    def buildResultList(resultPath):
        # example resultPath is self.jobpath + "/results"

        root = resultPath
        print("root :"+ root)

        SIMPLEUtil.mkdir_p(root)

        resultList = {}

        dirlist = [ item for item in os.listdir(root) if os.path.isdir(os.path.join(root, item)) ]
        print("dirlist: ",dirlist)

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

        # print "resultsList: "
        # debug
        #for k,v in resultList.iteritems():
        #    print k,v

        return resultList