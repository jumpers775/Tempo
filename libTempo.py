import os
import importlib
import sys
import asyncio
import sqlite3
import discord
import time
import threading
import random
import numpy as np
from tts import generate
from discord.ext import voice_recv
import torch
import torchaudio
from pydub import AudioSegment
import math
from faster_whisper import WhisperModel
import struct
import io
from typing import BinaryIO, Union, Optional, List, Tuple, Iterable
import wave
import array
from collections import defaultdict


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
            backendtype = _verify_backend(module)
            if backendtype != 0:
                backends[module_name] = module
                backends[module_name].type = backendtype
            else:
                print(f"Failed to import backend {module_name}: Backend is missing 1 or more required functions.")
                continue
        except ImportError as e:
            print(f"Failed to import backend {module_name}: {e}")

    return backends

def _verify_backend(backend):
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
    def __init__(self, backends, voice:bool = False):
        self.playlist = Playlist("queue", [])
        self.vc = None
        self.active = False
        self.backends = backends

        self.mixer = Mixer()

        self._voice = voice            
        self._skip = False
        self._paused = False 
        self._stop = False
    async def listen(self):
        if self.vc != None :
            if self.active == False:
                asyncio.create_task(self._listen())
            else:
                raise RuntimeError("MusicPlayer.listen() cannot be run twice concurrently.")
        else:
            raise RuntimeError("MusicPlayer must be bound to a vc to listen.")
    async def _listen(self):
        if self._voice:
            sink = WhisperSink()
            self.vc.listen(sink)
    async def _play(self):
        self.active = True
        while len(self.playlist) > 0:
            song = self.playlist.GetCurrentEntry()
            stream = await self.backends[song.backend].getstream(song.url, song.user.id)

            speech = generate(f"now playing {song.title} by {song.author}")
            
            source2 = discord.FFmpegPCMAudio(speech, pipe=True)

            self.mixer.set_source1(stream)
            self.mixer.set_source2(source2)
            self.vc.play(self.mixer)
            while self.vc.is_playing() or self.mixer.is_paused():
                if self._stop:
                    self.mixer.stop()
                    self._stop = False
                if self._skip == True:
                    self.mixer.stop()
                    self._skip = False
                if self._paused == True:
                    if not self.mixer.is_paused():
                        self.mixer.pause()
                else:
                    if self.mixer.is_paused():
                        self.mixer.resume()
                await asyncio.sleep(0.1)
            self.playlist.next()
        await self.leave_channel()
        self.active = False
    async def join_channel(self, vc:discord.VoiceChannel):
        self.vc = await vc.connect(cls=voice_recv.VoiceRecvClient)
        await self.listen()
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



class Mixer(discord.AudioSource):
    def __init__(self, source1: discord.AudioSource = None, source2: discord.AudioSource = None):
        self.source1 = source1
        self.source2 = source2
        self._paused = False

    def overlay_audio(self, audio1_bytes, audio2_bytes, sample_width=2, num_channels=2, sample_rate=48000, volume:int = 0.3):
        # Number of samples per 20ms for stereo audio
        num_samples = int(0.02 * sample_rate * num_channels)
        
        # Convert bytes-like objects to numpy arrays
        audio1 = np.frombuffer(audio1_bytes, dtype=np.int16).reshape(-1, num_channels).copy().astype(float)
        audio2 = np.frombuffer(audio2_bytes, dtype=np.int16).reshape(-1, num_channels)

        #lower audio so you can hear the DJ
        audio1 *= volume

        # Ensure both audio samples have the same length
        min_length = min(len(audio1), len(audio2))
        audio1 = audio1[:min_length]
        audio2 = audio2[:min_length]
        
        # Overlay the audio by summing the samples
        combined_audio = audio1 + audio2
        
        # Prevent clipping by scaling the combined audio
        max_val = np.iinfo(np.int16).max
        min_val = np.iinfo(np.int16).min
        combined_audio = np.clip(combined_audio, min_val, max_val)
        
        # Convert the combined audio back to bytes
        combined_audio_bytes = combined_audio.astype(np.int16).tobytes()
        
        return combined_audio_bytes

    def read(self):
        if self.source1 is not None and self._paused == False:
            a = self.source1.read()
        else:
            a = None
            
        if self.source2 is not None:
            b = self.source2.read()
        else:
            b = None
        
        if a and b:  
            return self.overlay_audio(a, b)
        elif a:  
            return a
        elif b:  
            return b
        else:  
            return b''
    
    def pause(self):
        self._paused = True
    
    def resume(self):
        self._paused = False
    
    def stop(self):
        self.source1 = None

    def is_paused(self):
        return self._paused

    def set_source1(self, new_source: discord.AudioSource):
        # Set the new source1
        self.source1 = new_source
    def set_source2(self, new_source: discord.AudioSource):
        # Set the new source1
        self.source2 = new_source

class BytesAudioSource(discord.AudioSource):
    def __init__(self, byte_io):
        self.byte_io = byte_io

    def read(self):
        # Read 20ms worth of audio (3840 bytes)
        return self.byte_io.read(3840)

    def cleanup(self):
        # Cleanup when the source is no longer needed
        self.byte_io.close()




class WhisperSink(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.user_packets = defaultdict(lambda: array.array("B"))
        model = "base" # hardcoded, should be configurable
        self.whisper = WhisperModel(model, device="auto", compute_type="int8")

    def wants_opus(self) -> bool:
        return False

    def write(self, user: discord.User | discord.Member | None, data: voice_recv.VoiceData):
        if isinstance(data.packet, voice_recv.rtp.SilencePacket):
            return

        if user is None:
            return
        
        user_id = user.id
        self.user_packets[user_id].extend(data.pcm)

        speaking_length = len(self.user_packets[user_id]) / (48000 * 2 * 2)  # assuming PCM format with 48kHz, stereo, 16-bit audio

        if math.floor(speaking_length) == 5:
            self._transcribe(user_id)
            self.user_packets[user_id] = array.array("B")

    def _transcribe(self, user_id):
        pcm_data = self.user_packets[user_id]
        audio_data = np.array(pcm_data, dtype="B")

        # Save audio data in an in-memory buffer
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(48000)  # 48 kHz
            wav_file.writeframes(audio_data.tobytes())

        # Reset the buffer position to the beginning
        audio_buffer.seek(0)

        # Transcribe audio from the in-memory buffer
        segments, info = self.whisper.transcribe(audio_buffer, beam_size=5)
        
        # Print or return the transcription results
        print(f"Transcribed: " + "".join([segment.text for segment in segments]))


    def cleanup(self):
        return

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: discord.Member):
        self.user_packets[member.id] = array.array("B")

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: discord.Member):
        self._transcribe(member.id)
        self.user_packets[member.id] = array.array("B")
