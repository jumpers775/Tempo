import os
import importlib
import sys
import asyncio
import sqlite3

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
    2 - Valid, Playlists supported
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


class Result:
    def __init__(self, user, title, backend, length, result, playlist=None):
        self.user = user
        self.title = title
        self.backend = backend
        self.length = length
        self.result = result
        self.playlist = playlist

class Playlist:
    def __init__(self, title, entries):
        self.title = title
        self.entries = entries

    def delete(self, index):
        self.entries.pop(index)

    def add(self, entry):
        self.entries.append(entry)

    def move(self, index, newindex):
        self.entries.insert(newindex, self.entries.pop(index))
