import os
import sys
import asyncio
import libTempo
import discord
import sqlite3

version = "2.0.0b1"


# create the database if it doesnt already exist
with sqlite3.connect("tempo.db") as db:
    cursor = db.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, data TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS DBInfo (version TEXT)")
    # set version if databse was just created (first run)
    cursor.execute("SELECT * FROM DBInfo")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO DBInfo(version) VALUES (?)", (version,))
    db.commit()
    


backends = libTempo.import_backends()


result = asyncio.run(backends["youtube"].search("test", 1))

print(result[0].title)