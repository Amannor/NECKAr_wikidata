# /usr/bin/env python3

from datetime import datetime
import bz2
import json
import pymongo
from pymongo import errors
import configparser
import sys

'''
TODO
1) Change the config file s.t. the inout json file is the stdin (/dev/stdin).
After that run the program like Nick wrote (bzcat dump.json.bz2 | python3 WD2DB.py)

This is what nick wrote in our meeting:
/dev/stdin 
bzcat dump.json.bz2 | python3 WD2DB.py
 
 
2) Nick also suggested that if needed,  I can make it parallel:
bzcat dump.json.bz2 | parallel --jobs 2 --round-robin python3 
WD2DB.py

3) Also one can create a small dump:

bzcat dump.json.bz2 | sed -n 1,10000p | bzcat -z > minidump.json.bz2 
OR
ll
'''



###read configuration file
config = configparser.ConfigParser()
config.read('../NECKAr.cfg')
host = config.get('Database', 'host') # -> "Python is fun!"
port = config.getint('Database', 'port') # -> "%(bar)s is %(baz)s!"
db = config.get('Database', 'db_dump')
collection = config.get('Database', 'collection_dump')
# json_file = config.get('Dump', 'json_file')
archive_file = config.get('Dump', 'sample_archive_file_100')

#connection to db
print(datetime.now(), "NECKAR: WD2DB: connecting to MongoDB")
try:
    client = pymongo.MongoClient(host,port)
except errors.ConnectionFailure:
        print(datetime.now(), "Connection to the database cannot be made. Please check the config file")

db = client[db]
collection = db[collection]


print(datetime.now(), "NECKAR: WD2DB: inserting WD items")
# with open(json_file) as input_file:
with bz2.open(archive_file, 'rt') as gf:
     for i, line in enumerate(gf):
         if len(line) > 2 and not line.startswith("["):
             line = line.strip(",\n")
         else:
             continue

         json_data = json.loads(line)
         collection.insert_one(json_data)
         if i % 10**4 == 0:
             print(datetime.now(), i)

print(datetime.now(), "NECKAR: WD2DB: creating indices")
collection.create_index([('claims.P31.mainsnak.datavalue.value.numeric-id', pymongo.ASCENDING)])
collection.create_index([('en_sitelink', pymongo.ASCENDING)])
collection.create_index([('de_sitelink', pymongo.ASCENDING)])
collection.create_index([('type', pymongo.ASCENDING)])
collection.create_index([('id', pymongo.ASCENDING)])

print(datetime.now(), "NECKAR: WD2DB: DONE")