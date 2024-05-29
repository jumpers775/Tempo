import os
import importlib
import sys
import asyncio
import sqlite3
import discord
import multiprocessing
import time
import threading
import random

def import_backends():
    """Imports all valid backends from the Backends folder and returns a dictionary of them."""
    backends_folder = "Backends"
    backends = {}

    sys.path.append(backends_folder)

    backend_files = [file for file in os.listdir(backends_folder) if file.endswith(".py")]

    for file in backend_files:
        module_name = os.path.splitext(file)[0]  
        module_path = os.path.join(backends_folder, file) 

        try:
            module = importlib.import_module(module_name)
            backendtype = verify_backend(module)
            if backendtype != 0:
                backends[module_name] = module
                backends[module_name].type = backendtype
            else:
                print(f"Failed to import backend {module_name}: Backend is missing 1 or more required functions.")
                continue
        except ImportError as e:
            print(f"Failed to import backend {module_name}: {e}")

    return backends

def verify_backend(backend):
    """
    Verifies that a backend has all the required functions. Also returns the backend type.
    Backend types:
    0 - Invalid, missing required functions
    1 - Valid
    2 - Valid, Platform Playlists supported
    """
    # Presume maximum support
    backendtype = 2

    required_functions = ["search","getstream"]
    playlist_functions = ["getplaylist"]

    for function_name in required_functions:
        if not hasattr(backend, function_name):
            # If the backend doesnt have the required functions we can exit early as it's invalid
            return 0
    
    # If the backend doesn't support playlists, set the backend type to 1
    for function_name in playlist_functions:
        if not hasattr(backend, function_name):
            backendtype = 1
    return backendtype

# get userdata from database
def get_userdata(user_id):
    with sqlite3.connect('userdata.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM userdata WHERE users = ?", (user_id,))
        userdata = cursor.fetchone()
        return userdata


class Song:
    def __init__(self, user, title, author, backend, length, url):
        self.user = user
        self.title = title
        self.author = author
        self.backend = backend
        self.length = length
        self.url = url
        
class Playlist:
    def __init__(self, title:str, entries:list):
        self.title = title
        self.entries = [[i,entry] for i,entry in enumerate(entries)]
        self.shuffle = False
        self.loop = 0 # 0 is off, 1 is full queue, 2 is song

    def __len__(self):
        return len(self.entries)
    
    def delete(self, index):
        self.entries.pop(index)

    def add(self, entry):
        self.entries.append([max([i[0] for i in self.entries])+1 if len(self.entries) > 0 else 0, entry])

    def move(self, index, newindex):
        self.entries.insert(newindex, self.entries.pop(index))

    def GetCurrentEntry(self):
        return self.entries[0][1]
    
    def next(self):
        if self.loop == 1:
            self.entries.append(self.entries[0])
        if len(self.entries) > 0 and self.loop!=2:
            self.entries.pop(0)

    def getAll(self):
        return [entry[1] for entry in self.entries]
    def SetShuffle(self, mode: bool):
        if not self.shuffle and mode == True:
            currentsong = self.entries.pop(0)
            random.shuffle(self.entries)
            self.entries.insert(0,currentsong)
        if mode == False:
            currentsong = self.entries.pop(0)
            self.entries.sort()
            self.entries.insert(0,currentsong)
    def SetLoop(self, mode:int):
        if mode not in [0,1,2]:
            raise ValueError("Loop mode must be [0,1,2]")
        self.loop = mode

class MusicPlayer:
    def __init__(self, backends):
        self.playlist = Playlist("queue", [])
        self.vc = None
        self.active = False
        self.backends = backends

        self._skip = False
        self._paused = False 
        self._stop = False
    async def _play(self):
        self.active = True
        while len(self.playlist) > 0:
            song = self.playlist.GetCurrentEntry()
            stream = await self.backends[song.backend].getstream(song.url)
            self.vc.play(stream)
            while self.vc.is_playing() or self.vc.is_paused():
                if self._stop:
                    self.vc.stop()
                    self._stop = False
                if self._skip == True:
                    self.vc.stop()
                    self._skip = False
                if self._paused == True:
                    if not self.vc.is_paused():
                        self.vc.pause()
                else:
                    if self.vc.is_paused():
                        self.vc.resume()
                await asyncio.sleep(0.1)
            self.playlist.next()
        await self.leave_channel()
        self.active = False
    async def join_channel(self, vc:discord.VoiceChannel):
        self.vc = await vc.connect()
    async def leave_channel(self):
        await self.vc.disconnect()
        self.vc = None
    def add_song(self, song:Song):
        self.playlist.add(song)
    def play(self):
        if self.vc != None :
            if self.active == False:
                asyncio.create_task(self._play())
            else:
                raise RuntimeError("MusicPlayer.play() cannot be run twice concurrently.")
        else:
            raise RuntimeError("MusicPlayer must be bound to a vc to play.")
    def pause(self):
        if self.active:
            self._paused = True
        else:
            raise RuntimeError("Nothing is playing.")
    def resume(self):
        if self.active:
            self._paused = False
        else:
            raise RuntimeError("Nothing is playing.")
    def stop(self):
        self.playlist = Playlist("queue", [])
        self._stop = True
    def getQueue(self):
        entries = self.playlist.getAll()
        return [[entry.title, entry.author, entry.length] for entry in entries]
    def skip(self):
        self._skip = True