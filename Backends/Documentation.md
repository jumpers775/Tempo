# Documentation for Tempo Backends

Tempo's backends must includea few functions to work at all, and can, optionally, support more features if implemented. 

All functions are expected to be async.

## Required Functions

### search(song_name, user_id) -> list
song_name: str -> The search term

user_id: int -> The ID of the user who ran the command

Returns a list of results each as a Result object. It is highly recommended that this contains 5 objects for consistency

### getstream(result) -> discord.FFmpegPCMAudio
result: any -> whatever data structure you decided to use when building your Result object

Returns a discord FFmpegPCMAudio or other [discord audio object](https://discordpy.readthedocs.io/en/stable/api.html?highlight=audio#voice-related) which can be used for streaming


## Non-Required Functions

### searchplaylists(query) -> list
query: str -> The search query for playlists

Returns a list of playlists each as a Playlist object. It is highly recommended that this contains 5 objects for consistency


## Required libTempo docs

I have only provided info that is stable about these, as for now they change per what would be useful to the main project. 

### Result(user, title, backend, length, result, playlist = None)
**Creation Params:**

user: int -> User who created

title: str -> the title of the song

backend: str -> The name of the backend its from

length: int -> song length in ms

result: any -> this can be whatever you want, it will only ever be stored then passed back to your stream function

playlist: str -> Name of the playlist its from (None if not from a playlist)

### Playlist(title, entries)
**Creation Params:**

title: str -> Playlist title

entries: list -> a list of Result objects corresponding to each song in the playlist

**attributes:**

title: str -> Playlist title

entries: list -> a list of Result objects corresponding to each song in the playlist

**Methods:**

delete(index) -> removes a song from the playlist

add(index=-1) -> adds a song to the playlist (defaults to the end)

move(index,newindex) -> moves a song from one place to another


