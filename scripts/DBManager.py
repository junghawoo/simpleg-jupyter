from scripts.SIMPLEUtil import SIMPLEUtil
import json
import sqlite3
import os, datetime
import sys
from pathlib import Path

class DBManager:


    conn = None
    DB_FILE = None
    dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool"
    #Create the SimpleGTool folder if it doesn't exist
    Path(dbfile).mkdir(parents=True, exist_ok=True)
    
    def __init__(self):
        self.DB_FILE = self.dbfile + '/DatabaseFile(DONOTDELETE).db'
        self.initTable(self.DB_FILE)
        

    def initTable(self, directoryPath):
        
        #create job folder first
        # For shared db, other admins should be able to update database
        # so read,write permissions are given to the simpleggroup
        comment = '''
        if directoryPath == SIMPLEUtil.SHARED_JOBS_DIR:
            try:
                SIMPLEUtil.mkdir_p(directoryPath)
                os.chmod(directoryPath, 0o775 )
            except :
                print ("Unexpected error:", sys.exc_info()[0])
                raise
        else:
            SIMPLEUtil.mkdir_p(directoryPath)

        conn = self.conn
        conn.execute(sql)
        conn.commit()
        conn.close()

        # give simpleggroup read, write permission
        if directoryPath == SIMPLEUtil.SHARED_JOBS_DIR:
            os.chmod(self.DB_FILE, 0o664)
        '''
        conn = sqlite3.connect(self.DB_FILE)
        cursor = conn.cursor()
        # Creating the Table and the DB File
        sql = '''
        CREATE TABLE IF NOT EXISTS SIMPLEJobs (
            jobid INTEGER PRIMARY KEY,
            submitId TEXT,
            submitTime TEXT,
            author TEXT,
            jobstatus TEXT,
            jobname TEXT,
            modeltype TEXT,
            remotejobid INTEGER,
            description TEXT
        );
        '''
        cursor.execute(sql)
        conn.commit()
        conn.close()
        if(len(self.getJobList())==0):
            self.createNewJob("Model Type","Name","Description","Status","Author","0")
        return
    
    def createNewJob(self,model_dd,name,description,status,author,remotejobid):
        
        now = datetime.datetime.now()
        submit_time = now.strftime('%m/%d/%Y %H:%M:%S')
        
        rows = self.getJobList()
        
        con = sqlite3.connect(self.DB_FILE)
        job_id_new = 0
        for row in rows:
            if(int(row[1]) > job_id_new):
                job_id_new = int(row[1])
        job_id_new += 1 
        #conn = self.conn
        conn = con.cursor()
        sql = 'insert into SIMPLEJobs(jobid,submitId,submitTime,author,jobstatus,jobname,modeltype,remotejobid,description) values (?,?,?,?,?,?,?,?,?);'
        conn.execute(sql,(job_id_new,job_id_new,submit_time,author,status,name,model_dd,remotejobid,description))
        con.commit()
        con.close()
        return job_id_new

    def updateJobInfo(self, jobid, params):
        print('IN HERE!')
        sql = 'update SIMPLEJobs set '
        for key in params:
            sql += key + ' = "' + str(params[key])  + '",'
            #print sql,'\n'

        sql = sql[:-1] + ' where jobid = "'+ str(jobid) +'";'
        print(sql,'\n')

        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        conn.execute(sql)
        con.commit()
        con.close()

        return True

    def updateJobStatus(self, jobid, status):
        sql = 'update SIMPLEJobs set jobstatus = ? where jobid = ?;'

        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        conn.execute(sql, (status, str(jobid)))
        con.commit()
        con.close()

        return True

    def updateRemoteID(self,jobid,remote_jobid):
        sql = 'update SIMPLEJobs set remotejobid = ? where jobid = ?;'

        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        conn.execute(sql, (remote_jobid, str(jobid)))
        con.commit()
        con.close()

        return True
        
    def deleteJob(self, jobid):
        conn = sqlite3.connect(self.DB_FILE)
        conn = conn.cursor()
        sql = 'delete from SIMPLEJobs where jobid = ?'
        conn.execute(sql, (str(jobid),))
        con.commit()
        con.close()

        return True

    def getJobList(self):
        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        sql = 'select * from SIMPLEJobs order by jobid desc;'
        cur = conn.execute(sql)
        rows = cur.fetchall()
        con.close()
        return rows

    def getJobInfo(self, jobid):
        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        sql = 'select * from SIMPLEJobs where jobid = ?;'
        #print sql
        cur = conn.execute(sql, (str(jobid),))
        con.close()
        return cur.fetchone()