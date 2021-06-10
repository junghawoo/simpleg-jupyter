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
    
    def __init__(self, directoryPath):
        self.DB_FILE = directoryPath + '/DatabaseFile(DONOTDELETE).db'
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
            jobid INTEGER PRIMARY KEY AUTOINCREMENT,
            submitId TEXT,
            submitTime TEXT,
            author TEXT,
            jobstatus TEXT,
            jobname TEXT,
            modeltype TEXT,
            published INTEGER,
            description TEXT
        );
        '''
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return
    
    def createNewJob(self):
        
        now = datetime.datetime.now()
        submit_time = now.strftime('%m/%d/%Y %H:%M:%S')
        
        con = sqlite3.connect(self.DB_FILE)
        #conn = self.conn
        conn = con.cursor()
        sql = 'insert into SIMPLEJobs(submitTime,jobstatus) values (?,?);'
        conn.execute(sql, (submit_time ,'None'))
        con.commit()

        sql = 'select jobid from SIMPLEJobs order by jobid desc limit 1;'
        cur = conn.execute(sql)
        jobid = cur.fetchone()[0]
        con.commit()
        
        sql = 'SELECT jobid from SIMPLEJobs order by jobid desc limit 1;'
        cur=conn.execute(sql)
        print("CUR")
        #conn.commit()
        
        print("JOBID IN CNJ")
        print(jobid)
        con.commit()
        con.close()
        return str(jobid)

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

    def updateJobStatus(self, jobid, status, submit_id):
        sql = 'update SIMPLEJobs set jobstatus = ? where jobid = ?;'

        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        conn.execute(sql, (status, str(jobid)))
        con.commit()
        con.close()
        param = {}
        param['submitId'] = submit_id

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
        con.close()
        return cur.fetchall()

    def getJobInfo(self, jobid):
        con = sqlite3.connect(self.DB_FILE)
        conn = con.cursor()
        sql = 'select * from SIMPLEJobs where jobid = ?;'
        #print sql
        cur = conn.execute(sql, (str(jobid),))
        con.close()
        return cur.fetchone()