from scripts.SIMPLEUtil import SIMPLEUtil
import json
import sqlite3
import os, datetime
import sys


class DBManager:


    conn = None
    DB_FILE = None
    dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool"
    def __init__(self, directoryPath):
        self.DB_FILE = directoryPath + '/DatabaseFile(DONOTDELETE).db'
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
        conn.close()

    def initTable(self, directoryPath):

        #create job folder first
        # For shared db, other admins should be able to update database
        # so read,write permissions are given to the simpleggroup
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


    def createNewJob(self):
        
        now = datetime.datetime.now()
        submit_time = now.strftime('%m/%d/%Y %H:%M:%S')

        conn = self.conn
        sql = 'insert into SIMPLEJobs(submitTime,jobstatus) values (?,?);'
        conn.execute(sql, (submit_time ,'None'))
        conn.commit()

        sql = 'select jobid from SIMPLEJobs order by jobid desc limit 1;'
        cur = conn.execute(sql)
        jobid = cur.fetchone()[0]
        conn.commit()
        
        sql = 'SELECT jobid from SIMPLEJobs order by jobid desc limit 1;'
        cur=conn.execute(sql)
        print("CUR")
        #conn.commit()
        
        print("JOBID IN CNJ")
        print(jobid)
        conn.commit()
        #conn.close()
        return str(jobid)

    def updateJobInfo(self, jobid, params):
        print('IN HERE!')
        sql = 'update SIMPLEJobs set '
        for key in params:
            sql += key + ' = "' + str(params[key])  + '",'
            #print sql,'\n'

        sql = sql[:-1] + ' where jobid = "'+ str(jobid) +'";'
        print(sql,'\n')

        conn = self.conn
        conn.execute(sql)
        conn.commit()
        #conn.close()

        return True

    def updateJobStatus(self, jobid, status, submit_id):
        sql = 'update SIMPLEJobs set jobstatus = ? where jobid = ?;'

        conn = self.conn
        conn.execute(sql, (status, str(jobid)))
        conn.commit()
        #conn.close()
        param = {}
        param['submitId'] = submit_id

        return True


    def deleteJob(self, jobid):
        conn = self.conn
        sql = 'delete from SIMPLEJobs where jobid = ?'
        conn.execute(sql, (str(jobid),))
        conn.commit()
        #conn.close()

        return True

    def getJobList(self):
        conn = self.conn
        sql = 'select * from SIMPLEJobs order by jobid desc;'
        cur = conn.execute(sql)
        return cur.fetchall()

    def getJobInfo(self, jobid):
        conn = self.conn
        sql = 'select * from SIMPLEJobs where jobid = ?;'
        #print sql
        cur = conn.execute(sql, (str(jobid),))
        return cur.fetchone()