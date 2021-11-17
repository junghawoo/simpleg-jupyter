import sqlite3
import os

class Sqlitedatabase:
    
    def Database(self):
        #Creating a folder in the user's home directory if it doesn't exist
        os.popen("mkdir -p ~/SimpleGTool")
        #Create the database file if not already created
        dbfile =os.popen("echo $HOME").read().rstrip('\n') + "/SimpleGTool/DatabaseFile(DONOTDELETE).db"
        conn = sqlite3.connect(dbfile)
        cursor = conn.cursor()
        #Make the table in the database if does not exist
        cursor.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY NOT NULL, model_type TEXT,name TEXT,description TEXT, status TEXT)")
        cursor.execute("SELECT * from jobs")
        rows = cursor.fetchall()
        #If the table is blank
        if len(rows) == 0:
            #Adding the first line just to make it like the column names, easier to read for the user
            cursor.execute("INSERT INTO jobs (job_id,model_type,name,description,status) VALUES('Job ID','Model Type','Name','Description','STATUS')")
            #Commit is important to save the data in the table
            conn.commit()
            cursor.execute("SELECT * FROM jobs")
            rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return None