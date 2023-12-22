import json
import discord
from discord.ext import commands, tasks
import asyncio
import yt_dlp as youtube_dl
import dotenv
import typing
import os
import random
from youtube_search import YoutubeSearch
import sqlite3
import librespot.core as lbc
from librespot.metadata import TrackId
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
import spotipy
import aiohttp
import os
import datetime


version = "1.2.0"
# so that the owner is only notified once
ownerupdated = False
updateversion = version


# load settings

if os.path.isfile("settings.json"):
    with open("settings.json", "r") as settingsfile:
        settings = json.load(settingsfile)
else:
    settings = {
        "globalSpotify": False,
        "updateDM": True,
    }
    with open("settings.json", "w") as settingsfile:
        json.dump(settings, settingsfile)

if settings["globalSpotify"]:
    print("Global Spotify is enabled. Please sign into your premium account.")
    username = input("Username: ")
    password = input("Password: ")
    sign_in = False
    while not sign_in :
        try:
            session = lbc.Session.Builder() \
            .user_pass(username,password) \
            .create()
            sign_in = True
        except:
            print("Invalid credentials. Please try again.")
            username = input("Username: ")
            password = input("Password: ")
    access_token = session.stored()
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("INSERT INTO users VALUES (?,?)", (0,access_token))
    db.commit()
    db.close()
    


# get token 
dotenv.load_dotenv()
try:
    token = os.environ['token']
except:
    token = input("no token provided, Please input it here: ")
    with open('.env', 'w') as envfile:
        envfile.write('token = '+ token)


#setup sqlite3

db = sqlite3.connect("userdata.db")

cursor = db.cursor()

columns = [["id","INTEGER DEFAULT NULL"],["spotify","INTEGER DEFAULT NULL"],["Authorized","BOOL DEFAULT FALSE"],["Playlists","TEXT DEFAULT NULL"]]

entry = "CREATE TABLE IF NOT EXISTS users("
for i in range(len(columns)):
  entry+=columns[i][0] + " " + columns[i][1] + ("," if i!=len(columns)-1 else ")")

cursor.execute(entry)

# update existing table match this format
cursor.execute("PRAGMA table_info(users)")
result = cursor.fetchall()
currentcolumns = [i[1] for i in result]
newcolumns = [i for i in columns if i[0] not in currentcolumns]
if [i[0] for i in columns] != currentcolumns:
    print("Updating database...")
    for column in newcolumns:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column[0]} {column[1]}")
    db.commit()
    print("Database updated.")
db.close()




# set intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# make the bot
bot = commands.Bot(command_prefix = '$',intents=intents, activity=discord.Game(name='Play some music!'))
bot.settings = settings



@tasks.loop(hours=1)
async def updatecheck():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.github.com/repos/jumpers775/Tempo/releases/latest') as resp:
            resp = await resp.json()
            newestversion = resp["tag_name"]
            latestversion = newestversion.split(".")
            currentversion = version.split(".")
            if True in [int(latestversion[i]) > int(currentversion[i]) for i in range(len(currentversion))]:
                print(f"Update Available!\n{version} --> {newestversion}")
                if bot.settings["updateDM"] and (not ownerupdated or updateversion != newestversion):
                    updateversion = newestversion
                    app_info = await bot.application_info()
                    user = bot.get_user(app_info.owner.id)
                    await user.send(f"Update Available!\n{version} --> {newestversion}\n {resp['html_url']}")


# basic setup
@bot.event
async def on_ready():
    await updatecheck()
    print(f"{bot.user} is online.")
    bot.queue = {}
    bot.shuffle = {}
    bot.queueorder = {}
    bot.loopmode = {}
    for guild in bot.guilds:
        bot.queue[guild.id] = []
        bot.shuffle[guild.id] = False
        bot.queueorder[guild.id] = []
        bot.loopmode[guild.id] = 0



#sync commands with discord
@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: typing.Optional[typing.Literal["~"]] = None) -> None:
    #Global command sync
    if not guilds:
        if spec == "~":
            bot.tree.copy_global_to(guild=ctx.guild)
            fmt = await bot.tree.sync(guild=ctx.guild)
        else:
            fmt = await bot.tree.sync()
        await ctx.send(
            f"Synced {len(fmt)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return
    # Local command sync
    assert guilds is not None
    fmt = 0
    for guild in guilds:
        try:
            await bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            fmt += 1

    await ctx.send(f"Synced the tree to {fmt}/{len(guilds)} guilds.")@commands.is_owner()

settings = discord.app_commands.Group(name='settings', description='settings related commands.')

@commands.check_any(commands.is_owner())
@settings.command(name='show', description='shows all settings')
async def show(interaction: discord.Interaction):
    
    response = discord.Embed(title="Settings:", description="".join([f"{i}: {'Enabled' if bot.settings[i] else 'Disabled'}\n" for i in bot.settings]), color=0x336EFF)
    await interaction.response.send_message(embed=response)
@show.error
async def show_error(interaction: discord.Interaction, error: Exception):
    await interaction.response.send_message(f'{interaction.user.mention}, You must be the bot owner to use this command',ephemeral=True)

@commands.check_any(commands.is_owner())
@settings.command(name='set', description='sets a setting')
async def set(interaction: discord.Interaction, setting:str, value:bool):
    #set spotify account if global spotify is enabled
    if setting == "globalSpotify":
        if value == True:
            db = sqlite3.connect("userdata.db")
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
            spot_result = cursor.fetchone()
            if spot_result == None:
                await interaction.response.send_message("You have not authenticated a spotify account.", ephemeral=True)
                return
            else:
                cursor.execute("UPDATE users SET spotify = ? WHERE id = ?", (spot_result[1],0))
                db.commit()
                db.close()
        else:
            db = sqlite3.connect("userdata.db")
            cursor = db.cursor()
            cursor.execute("UPDATE users SET spotify = ? WHERE id = ?", (None,0))
            db.commit()
            db.close()
    try:
        bot.settings[setting] = value
    except:
        await interaction.response.send_message("Invalid setting or value.",ephemeral=True)
        return
    with open("settings.json", "w") as settingsfile:
        json.dump(bot.settings, settingsfile)
    await interaction.response.send_message(f"Successfully set {setting} to {value}.")
@set.autocomplete('setting')
async def set_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    settings = [i for i in bot.settings]
    return [
        discord.app_commands.Choice(name=setting, value=setting)
        for setting in settings if current.lower() in setting.lower()
    ]


bot.tree.add_command(settings)

# spotify



spot = discord.app_commands.Group(name='spot', description='Spotify related commands.')


@spot.command(name='auth', description='authenticates a spotify premium account. MAKE SURE YOU TRUST THE BOT OWNER.')
async def auth(interaction: discord.Interaction, email:str, password:str):
    db = sqlite3.connect("userdata.db")

    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    result = cursor.fetchone()
    if result[1] == None:
        try:
            session = lbc.Session.Builder() \
            .user_pass(email,password) \
            .create()

        except:
            await interaction.response.send_message("Invalid credentials.", ephemeral=True)
            return
        access_token = session.stored()
        cursor.execute("UPDATE users SET spotify = ?, Authorized = ? WHERE id = ?", (access_token,False,interaction.user.id))
        db.commit()
        db.close()

        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
        result = cursor.fetchone()
        print(result)
        db.close()

    else:
        await interaction.response.send_message("You have already authenticated a spotify account. Use /spotrm to remove it", ephemeral=True)
        return
    await interaction.response.send_message("Successfully authenticated spotify account.",ephemeral=True)




@spot.command(name='rm', description='removes an authenticated a spotify premium account.')
async def rm(interaction: discord.Interaction):
    db = sqlite3.connect("userdata.db")

    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    result = cursor.fetchone()

    if result == None:
        await interaction.response.send_message("You have not authenticated a spotify account.", ephemeral=True)
        return
    else:
        if result[2] == True:
            view = SelectButtonView(options=["Yes","No"], interaction=interaction)
            await interaction.response.send_message("You are currently authorized to use someone elses spotify account. If you remove your account you will need to be added again by them.", ephemeral=True,view=view)
            return
        cursor.execute("UPDATE users SET spotify = ?, Authorized = ? WHERE id = ?", (None,False,interaction.user.id))
        db.commit()
        db.close()        
    await interaction.response.send_message("Successfully removed spotify account.",ephemeral=True)

class SelectButtonView(discord.ui.View):
    def __init__(self, *, timeout = 180, options: list, interaction: discord.Interaction):
        super().__init__(timeout=timeout)
        for option in options:
            self.add_item(ButtonClass(label=option, interaction=interaction))

class ButtonClass(discord.ui.Button):
    def __init__(self, label: str, interaction: discord.Interaction):
        # Allow access to the original interaction
        self.original_interaction = interaction
        super().__init__(label=label)
    
    async def callback(self, interaction: discord.Interaction):
        if self.label == "Yes":
            db = sqlite3.connect("userdata.db")
            cursor = db.cursor()
            cursor.execute("UPDATE users SET spotify = ?, Authorized = ? WHERE id = ?", (None,False,self.original_interaction.user.id))
            db.commit()
            db.close()
            await self.original_interaction.edit_original_response(content="Successfully removed spotify account.",view=None)
        else:
            await self.original_interaction.edit_original_response(content="Cancelled.",view=None)

@spot.command(name='trustuser', description='authorizes a user to your spotify account.')
async def trustuser(interaction: discord.Interaction,member: discord.Member):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    result = cursor.fetchone()
    db.close()
    if result == None:
        await interaction.response.send_message("You have not authenticated a spotify account.", ephemeral=True)
        return
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    # get users values
    cursor.execute("SELECT * FROM users WHERE id = ?", (member.id,))
    useracc = cursor.fetchone()
    playlists = []
    if useracc != None:
        if useracc[3] != None:
            playlists = json.loads(useracc[3])
    cursor.execute("INSERT INTO users VALUES (?,?,?,?)", (member.id,interaction.user.id,True, json.dumps(playlists)))
    db.commit()
    db.close()
    await interaction.response.send_message(f"Successfully authorized {member.mention} to your spotify account.")


@spot.command(name='rmuser', description='removes a users access to your spotify account.')
async def rmuser(interaction: discord.Interaction,member: discord.Member):
    if member.id == interaction.user.id:
        await interaction.response.send_message("To remove your own accoutn please use /spot rm.", ephemeral=True)
        return
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    spot_auth = cursor.fetchone()
    if spot_auth == None or spot_auth[2] == True:
        await interaction.response.send_message("You have not added a spotify account, or are currently authorized to use someone elses.", ephemeral=True)
        return
    cursor.execute("SELECT * FROM users WHERE id = ?", (member.id,))    
    useracc = cursor.fetchone()
    if useracc[1] == interaction.user.id and useracc[2] == True:
        cursor.execute("INSERT OR REPLACE INTO users (id, spotify, Authorized, Playlists) VALUES (?,?,?,?)", (member.id, None, False, useracc[3]))
        db.commit()
        db.close()
        await interaction.response.send_message(f"Successfully removed {member.mention}'s access to your spotify account.")
    else:
        await interaction.response.send_message(f"This user does not have access to your spotify account.",ephemeral=True)
bot.tree.add_command(spot)


class ByteAudioSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, stream,volume=0.5):
        super().__init__(source,volume)
        self.stream = stream
    @classmethod
    async def get_stream(cls, stream):
        ffmpeg_options = {
            'options': '-vn',
        }
        return cls(discord.FFmpegPCMAudio(stream, **ffmpeg_options, pipe=True), stream=stream)




#youtube streaming
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.url = data.get('url')
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        youtube_dl.utils.bug_reports_message = lambda: ''
        ydl_opts = {
            'format': 'bestaudio/best',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'
        }
        ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        ytdl = youtube_dl.YoutubeDL(ydl_opts)
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.sanitize_info(ytdl.extract_info(url, download=not stream)))
        if 'entries' in data:
            # take first item from a youtube playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
    

@discord.app_commands.command(name='play', description='plays a song')
async def play(interaction: discord.Interaction, song:str, platform:str = None):
    try:
        channel = interaction.user.voice.channel
    except:
        await interaction.response.send_message("you are not currently in a voice channel.")
        return
    permissions = channel.permissions_for(interaction.guild.me)
    if not permissions.connect or not permissions.speak:
        await interaction.response.send_message("I do not have permission to play music in that voice channel.")
        return
    message = await interaction.response.send_message("searching...")
    spot_authenticated = False
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id if not bot.settings["globalSpotify"] else 0,))
    spot_result = cursor.fetchone()
    if spot_result != None:
        if spot_result[3] != None and spot_result[3] != "{}":
            spot = True
    if platform != None:
        if platform.lower() == "spotify":
            spot = True
        elif platform.lower() == "youtube":
            spot = False
        else:
            await interaction.edit_original_response(content="Invalid platform. Please use either 'spotify' or 'youtube'.")
            return
    results = None
    if not spot:
        # search for the song on youtube
        results = YoutubeSearch(song, max_results=10).to_json()
        results = json.loads(results)
        results = results['videos']
    else:
        if spot_result[2] == True:
            cursor.execute("SELECT * FROM users WHERE id = ?", (spot_result[1],))
            spot_result = cursor.fetchone()
            if spot_result == None:
                #error youtube if spotify acc is removed
                await interaction.edit_original_response(content="The user who Authorized your spotify account has removed their spotify account. Youtube is now the default provider.")
                cursor.execute("DELETE FROM users WHERE id = ?", (interaction.user.id,))
                return
        # search for the song on spotify
        try:
            session = lbc.Session.Builder().stored(spot_result[1]).create()
        except:
            await interaction.edit_original_response(content="An error occured, please try again.")
            return
        oauth_token = session.tokens().get("playlist-read")
        sp = spotipy.Spotify(auth=oauth_token)
        results = sp.search(q=song, type='track', limit=10)["tracks"]["items"]
        results = [result | {"user_id": interaction.user.id} for result in results]
        spot_authenticated = True
    db.close()
    #build an option for each song
    options = []
    num = 1
    for result in results:
        if not spot:
            options.append(discord.SelectOption(label=f'{num}) '+ result['title'], description=f'By {result["channel"]}', emoji='🎧'))
        else:
            options.append(discord.SelectOption(label=f'{num}) '+ result["name"], description=f'By {", ".join([result["artists"][i]["name"] for i in range(len(result["artists"]))])}', emoji='🎧'))
        num+=1

    #build a view to choose the option
    view = SelectListView(options=options, interaction=interaction,results=results)

    #select a song
    try:
        messsage = "The user who authenticated your account has removed their account. They will need to re-authenticate and re-add you for you to use their account.\nUsing Youtube\n" if spot and not spot_authenticated else "" + "Select a song to play:"
        await interaction.edit_original_response(content=message,view=view)
    except:
        await interaction.edit_original_response(content='An error occured. Please Try again.')
@play.autocomplete('platform')
async def create_autocomplete2(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    spotify = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            results=json.loads(result[3])
            spotify = result[1] != None
    db.close()

    platforms = ["youtube"]
    if spotify or bot.settings["globalSpotify"]:
        platforms.append("spotify")
    return [
        discord.app_commands.Choice(name=platform, value=platform)
        for platform in platforms if current.lower() in platform.lower()
    ]

#view class to select the correct song.
class SelectListView(discord.ui.View):
    def __init__(self, *, timeout = 180, options: dict, interaction: discord.Interaction,results: list):
        super().__init__(timeout=timeout)
        self.add_item(SelectSong(option=options, interaction=interaction,results=results))

class SelectSong(discord.ui.Select):
    def __init__(self,option: dict, interaction: discord.Interaction, results: list):
        #set options to the possibilities for the song
        self.music_options=results
        #allow access to the original interaction
        self.original_interaction = interaction
        # ask for an option to be selected
        super().__init__(placeholder="Select an option",options=option)
    async def callback(self, interaction: discord.Interaction):
        #check the selection against the list
        option = self.music_options[int(self.values[0][0])-1]
        # uri is not in the yt dict, so if it is present it is a spotify song
        spotify = "uri" in option
        #build entry
        if spotify:
            # set the url
            url = option['uri']
            # set the title
            title = option['name']
            artists = ", ".join([option["artists"][i]["name"] for i in range(len(option["artists"]))])
            # make queue entry
            entry = {"url": url,"title": title, "artist": artists, "platform": "spotify","auth": option["user_id"], "length": option["duration_ms"]}
        else: # youtube
            #song length
            duration = option['duration'].split(":")
            duration = (int(duration[0])*60 + int(duration[1]))*1000
            # set the url
            url = 'https://www.youtube.com' + option['url_suffix']
            # set the title
            title = option['title']
            # make queue entry
            entry = {"url": url,"title": title, "artist": option["channel"], "platform": "youtube","auth": None, "length": duration}
        #insert in a random spot non-current if shuffle is enabled, at the end if disabled
        if bot.shuffle[interaction.guild.id] and len(bot.queue[interaction.guild.id]) > 1:
            spot = random.randint(1,len(bot.queue[interaction.guild.id]))
        else:
            spot = len(bot.queue[interaction.guild.id])
        bot.queue[interaction.guild.id].insert(spot, entry)
        #record the location of this item in case shuffle is turned off
        bot.queueorder[interaction.guild.id].append(entry)
        #check if the new url is the first in the list
        if not bot.queue[interaction.guild.id][0]["url"] is url:
            #if the new url isnt first, reply that it has been added to the queue
            await self.original_interaction.edit_original_response(content=f"{str(self.values[0])[3:]} has been added to the queue!",view=None)
            return
        else:
            #if it is, reply that it is playing
            await self.original_interaction.edit_original_response(content=f"Now playing {str(self.values[0])[3:]}!",view=None)
            #connect to the vc
            vc = await interaction.user.voice.channel.connect()
            #wait for the queue to be empty
            while len(bot.queue[interaction.guild.id]) > 0:
                if spotify:
                    db = sqlite3.connect("userdata.db")
                    cursor = db.cursor()
                    cursor.execute("SELECT * FROM users WHERE id = ?", (bot.queue[interaction.guild.id][0]["auth"] if not bot.settings["globalSpotify"] else 0,))
                    spot_result = cursor.fetchone()
                    if spot_result[2] == True:
                        cursor.execute("SELECT * FROM users WHERE id = ?", (spot_result[1],))
                        spot_result = cursor.fetchone()
                    db.close()
                    try:
                        session = lbc.Session.Builder().stored(spot_result[1]).create()
                    except:
                        continue
                    track_id = TrackId.from_uri(bot.queue[interaction.guild.id][0]["url"])
                    stream = session.content_feeder().load(track_id, VorbisOnlyAudioQuality(AudioQuality.VERY_HIGH), False, None)
                    audio = stream.input_stream
                    song = await ByteAudioSource.get_stream(stream=audio.stream())
                    songname = bot.queue[interaction.guild.id][0]
                    
                else:
                    #record what will be played
                    songname = bot.queue[interaction.guild.id][0]
                    #get a stream
                    song = await YTDLSource.from_url(url=bot.queue[interaction.guild.id][0]["url"], loop=bot.loop, stream=True)
                #play the stream
                vc.play(song)
                #wait for the current song to end or get skipped
                while vc.is_playing() or vc.is_paused():
                    if not songname == bot.queue[interaction.guild.id][0]:
                        vc.stop()
                    await asyncio.sleep(0.1)
                #remove the first entry in the queue if not skipped
                if len(bot.queue[interaction.guild.id]) > 0 and bot.loopmode[interaction.guild.id] in [0,2]:
                    if songname == bot.queue[interaction.guild.id][0]:
                        if bot.loopmode[interaction.guild.id] == 2:
                            bot.queue[interaction.guild.id].append(bot.queue[interaction.guild.id][0])
                            bot.queueorder[interaction.guild.id].append(bot.queueorder[interaction.guild.id][0])
                        #remove from queue
                        bot.queue[interaction.guild.id].pop(0)
                        # if shuffle is enable iterate over ordered list to find song and remove it
                        if bot.shuffle[interaction.guild.id]:
                            spot = 0
                            for song in bot.queueorder[interaction.guild.id]:
                                if song == songname:
                                    bot.queueorder[interaction.guild.id].pop(spot)
                                    break
                                else:
                                    spot+=1
                        else:
                            bot.queueorder[interaction.guild.id].pop(0)
            #disconnect once the list is empty
            await vc.disconnect()
#add the play command to the bots command tree
bot.tree.add_command(play)

#stop all playing audio
@discord.app_commands.command(name='stop', description='stops the music')
async def stop(interaction: discord.Interaction):
    #get the voice channel the bot is in from the current server
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    #check if the bot is in a voice channel
    if vc != None:
        #if it is in a voice channel disconnect, and flush the queue
        bot.queue[interaction.guild.id] = []
        bot.queueorder[interaction.guild.id] = []
        bot.loopmode[interaction.guild.id] = 0
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Stopped the music.")
    else:
        # if not, inform the user that there is no music playing.
        await interaction.response.send_message("There is no music playing.", ephemeral=True)
# add the stop command to the commands tree
bot.tree.add_command(stop)

#build the queue object - behaves as its own nested tree
queue = discord.app_commands.Group(name='queue', description='queue related commands.')

# show the current queue
@queue.command(name="view", description='shows the current queue')
async def view(interaction: discord.Interaction):
    # build a list of songs
    # each song is stored as a url, so iterate over them and get info, add it to an embed.
    response = discord.Embed(title="Queue:", description=f"Shuffle is {'on' if bot.shuffle[interaction.guild.id] else 'off'}", color=0x336EFF)
    i = 1
    total = 0
    if len(bot.queue[interaction.guild.id]) == 0:
        response.add_field(name="Nothing is playing.", value="", inline=False)
        await interaction.response.send_message(embed=response)
        return
    for song in bot.queue[interaction.guild.id]:
        if i <= 25:
            response.add_field(name=str(i) + f".{' **(Current song)**' if i == 1 else ''}", value=f"Title: {song['title']}\nArtist: {song['artist']}\nLength: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))} seconds", inline=False)
        i += 1
        total += song['length']
    response.set_footer(text=f"Total Queue Length: {str(datetime.timedelta(milliseconds=(total-(total%1000))))} seconds")
    # send response
    view = SelectButtonView2(options=["Previous","Next"], interaction=interaction, embed=response)
    await interaction.response.send_message(embed=response,view=view)

class SelectButtonView2(discord.ui.View):
    def __init__(self, *, timeout = 180, options: list, interaction: discord.Interaction, embed: discord.Embed):
        super().__init__(timeout=timeout)
        for option in options:
            self.add_item(ButtonClass2(label=option, interaction=interaction, embed=embed))

class ButtonClass2(discord.ui.Button):
    def __init__(self, label: str, interaction: discord.Interaction, embed: discord.Embed):
        # Allow access to the original interaction
        self.original_interaction = interaction
        self.embed = embed
        super().__init__(label=label)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.label == "Next":
            last_field = self.embed.fields[-1]
            num = int(last_field.name.split(".")[0])
            if num == len(bot.queue[interaction.guild.id]):
                return
            self.embed.clear_fields()
            for i in range(25):
                if num+i < len(bot.queue[interaction.guild.id]):
                    song = bot.queue[interaction.guild.id][num+i]
                    self.embed.add_field(name=str(num+i+1) + f".{' **(Current song)**' if num+i+1 == 1 else ''}", value=f"Title: {song['title']}\nArtist: {song['artist']}\nLength: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))} seconds", inline=False)
            view = SelectButtonView2(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed)
        else:
            first_field = self.embed.fields[0]
            num = int(first_field.name.split(".")[0])-1
            if num-25 < 0:
                return
            self.embed.clear_fields()
            for i in range(25):
                if num-25+i >= 0:
                    song = bot.queue[interaction.guild.id][num-25+i]
                    self.embed.add_field(name=str(num-24+i) + f".{' **(Current song)**' if num-24+i == 1 else ''}", value=f"Title: {song['title']}\nArtist: {song['artist']}\nLength: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))} seconds", inline=False)
            view = SelectButtonView2(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed)

#remove a song from the queue
@queue.command(name="del", description='removes a song from the queue')
async def delete(interaction: discord.Interaction, spot: int):
    #1 is subtracted as 1 is added when the queue is veiwed to avoid starting at 0.
    spot-=1
    # make sure songs are playing
    if len(bot.queue[interaction.guild.id]) > 0:
        #make sure the int provided is valid. 
        if len(bot.queue[interaction.guild.id]) >= spot and spot > 0:
            # record title to tell user
            title = bot.queue[interaction.guild.id][spot]
            #skip the selected song. 
            bot.queue[interaction.guild.id].pop(spot)
            staticspot = 0
            for song in bot.queueorder[interaction.guild.id]:
                if song == title:
                    bot.queueorder[interaction.guild.id].pop(staticspot)
                    break
                else:
                    staticspot+=1
            await interaction.response.send_message(f"Removed song #{spot+1} ({title['title']}) from the queue.")
        else:
            await interaction.response.send_message(f"spot {spot} is invalid. Spot cannot be lower than 0 or higher than the number of songs in the queue.")
    else:
        await interaction.response.send_message("No songs playing.")

# move in queue
@queue.command(name="move", description='moves a song to a new spot int the queue')
async def move(interaction: discord.Interaction, initial_song_spot: int, new_song_spot: int):
    initial_song_spot-=1
    new_song_spot-=1
    #catch bad input
    if initial_song_spot > len(bot.queue[interaction.guild.id]) or initial_song_spot < 1 or new_song_spot > len(bot.queue[interaction.guild.id]):
        await interaction.response.send_message("Unfortunately the provided info is invalid. The initial song spot must be a valid spot in the queue, and cannot be 1 as that is the current playing song. The new song spot must also be a valid location in the queue, it however can be 1.",ephemeral=True)
    #catch current song replacements     
    else:
        if new_song_spot == 0:
            currentsong = bot.queue[interaction.guild.id][0]
            bot.queue[interaction.guild.id].pop(0)
            spot = 0
            for song in bot.queueorder[interaction.guild.id]:
                if song == currentsong:
                    bot.queueorder[interaction.guild.id].pop(spot)
                    break
                else:
                    spot+=1
        selectedsong = bot.queue[interaction.guild.id][initial_song_spot]
        bot.queue[interaction.guild.id].insert(new_song_spot,bot.queue[interaction.guild.id].pop(initial_song_spot))
        spot = 0
        for song in bot.queueorder[interaction.guild.id]:
            if song == selectedsong:
                bot.queueorder[interaction.guild.id].pop(spot)
            else:
                spot+=1
        await interaction.response.send_message(f"Successfully moved {selectedsong['title']} to spot {new_song_spot+1}.")



#shuffle
@queue.command(name="shuffle", description='enables or disables shuffle')
async def shuffle(interaction: discord.Interaction, mode: str):
    #set shuffle on
    if mode == 'on':
        bot.shuffle[interaction.guild.id] = True
        #preserve current song, while randomizing the queue
        currentsong = bot.queue[interaction.guild.id][0]
        oldqueue = bot.queue[interaction.guild.id]
        oldqueue.pop(0)
        random.shuffle(oldqueue)
        oldqueue.insert(0,currentsong)
        bot.queue[interaction.guild.id] = oldqueue
    #set shuffle off
    elif mode == 'off':
        bot.shuffle[interaction.guild.id] = False
        # set queue back to non-shuffled form.
        currentsong = bot.queue[interaction.guild.id][0]
        spot = 0
        for song in bot.queueorder[interaction.guild.id]:
            if song == currentsong:
                bot.queueorder[interaction.guild.id].insert(0,bot.queueorder[interaction.guild.id].pop(spot))
                break
            else:
                spot+=1
        bot.queue[interaction.guild.id] = bot.queueorder[interaction.guild.id]
    #if neither on or off error
    else:
        await interaction.response.send_message("Mode not recognized. Please use either 'on' or 'off'.")
        return
    # tell user what has been done.
    await interaction.response.send_message(f"Shuffle has been turned {mode}.")
        
@shuffle.autocomplete('mode')
async def shuffle_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    statuses = ['on', 'off']
    return [
        discord.app_commands.Choice(name=status, value=status)
        for status in statuses if current.lower() in status.lower()
    ]

# add queue to commands tree
bot.tree.add_command(queue)

@discord.app_commands.command(name="skip", description='skips the current song.')
async def skip(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc != None:
        if bot.loopmode[interaction.guild.id] == 2:
            bot.queue[interaction.guild.id].append(bot.queue[interaction.guild.id][0])
            bot.queueorder[interaction.guild.id].append(bot.queueorder[interaction.guild.id][0])
            bot.queue[interaction.guild.id].pop(0)
            bot.queueorder[interaction.guild.id].pop(0)            
        vc.stop()
        if bot.queue[interaction.guild.id] == []:
            await vc.disconnect()
            await interaction.response.send_message("Skipped, no songs left in queue. Stopping.")
            return
        await interaction.response.send_message("Skipped.")
    else:
        await interaction.response.send_message("Nothing is playing.")

bot.tree.add_command(skip)

@discord.app_commands.command(name="pause", description='pauses the current song.')
async def pause(interaction: discord.Interaction):
    # make sure there is a song playing
    if len(bot.queue[interaction.guild.id]) > 0:
        # get the vc
        vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        # pause the song
        vc.pause()
        # tell the user it was done
        await interaction.response.send_message("Paused.")
    # if not, tell the user
    else:
        await interaction.response.send_message("Nothing is playing.")
bot.tree.add_command(pause)

@discord.app_commands.command(name="resume", description='resumes the current song.')
async def resume(interaction: discord.Interaction):
    # make sure there is a song playing
    if len(bot.queue[interaction.guild.id]) > 0:
        # get the vc
        vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        # resume the song
        vc.resume()
        # tell the user it was done
        await interaction.response.send_message("Resumed.")
    # if not, tell the user
    else:
        await interaction.response.send_message("Nothing is playing.")
bot.tree.add_command(resume)


@discord.app_commands.command(name="loop", description='sets the loop mode.')
async def loop(interaction: discord.Interaction, mode: str):
    # make sure there is a song playing
    if len(bot.queue[interaction.guild.id]) > 0:
        # make sure the mode is valid
        if mode == "off":
            bot.loopmode[interaction.guild.id] = 0
        elif mode == "song":
            bot.loopmode[interaction.guild.id] = 1
        elif mode == "queue":
            bot.loopmode[interaction.guild.id] = 2
        else:
            await interaction.response.send_message("Invalid mode. Please use either 'off', 'one', or 'all'.")
            return
        # tell the user it was done
        await interaction.response.send_message(f"Loop mode set to {mode}.")
    # if not, tell the user
    else:
        await interaction.response.send_message("Nothing is playing.")
@loop.autocomplete('mode')
async def shuffle_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    statuses = ['off', 'song',"queue"]
    return [
        discord.app_commands.Choice(name=status, value=status)
        for status in statuses if current.lower() in status.lower()
    ]


bot.tree.add_command(loop)


playlists = discord.app_commands.Group(name='playlist', description='playlist related commands.')

@playlists.command(name="create", description='creates a new playlist.')
async def create(interaction: discord.Interaction, name: str):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    if name in playlists:
        await interaction.response.send_message("You already have a playlist with that name.")
        return
    playlists[name] = []
    cursor.execute("UPDATE users SET Playlists = ? WHERE id = ?", (json.dumps(playlists),interaction.user.id))
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO users (id, Playlists) VALUES (?, ?)", (interaction.user.id, json.dumps(playlists)))
    db.commit()
    db.close()
    await interaction.response.send_message(f"Successfully created playlist {name}. add to it with /playlist add {name} <song>")

@playlists.command(name="add", description='adds a song to a playlist.')
async def add(interaction: discord.Interaction, playlist:str, song: str, platform: str):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    if playlist not in playlists:
        await interaction.response.send_message("You do not have a playlist with that name.")
        return
    selections = []
    if platform == "youtube":
        results = YoutubeSearch(song, max_results=10).to_json()
        results = json.loads(results)
        results = results['videos']
    elif platform == "spotify":
        try:
            session = lbc.Session.Builder().stored(result[1]).create()
        except:
            await interaction.response.send_message("An error occured, please try again.")
            return
        oauth_token = session.tokens().get("playlist-read")
        sp = spotipy.Spotify(auth=oauth_token)
        results = sp.search(q=song, type='track', limit=10)["tracks"]["items"]
        results = [result | {"user_id": interaction.user.id} for result in results]
    else:
        await interaction.response.send_message("Invalid platform. Please use either 'youtube' or 'spotify'.")
        return
    options = []
    for i in range(5):
        if platform == "youtube":
            title = results[i]['title'][:80]
            channel = results[i]['channel'][:80]
            options.append(discord.SelectOption(label=str(i+1) + ") " + title, description=f'By {channel}', emoji='🎧'))
        else:
            name = results[i]["name"][:80]
            artists = ", ".join([artist["name"] for artist in results[i]["artists"]])[:80]
            options.append(discord.SelectOption(label=str(i+1) + ") " + name, description=f'By {artists}', emoji='🎧'))
    view = SelectListView2(options=options, interaction=interaction,results=results,playlist=playlist,platform=platform)
    try:
        await interaction.response.send_message(f"select a song to add to {playlist}:",view=view)
    except:
        await interaction.response.send_message(content='An error occured. Please Try again.')
@add.autocomplete('playlist')
async def create_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    db.close()
    print(result[3])
    playlists = [i for i in json.loads(result[3])]
    return [
        discord.app_commands.Choice(name=playlist, value=playlist)
        for playlist in playlists if current.lower() in playlist.lower()
    ]
@add.autocomplete('platform')
async def create_autocomplete2(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    spotify = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            results=json.loads(result[3])
            spotify = result[1] != None
    db.close()

    platforms = ["youtube"]
    if spotify or bot.settings["globalSpotify"]:
        platforms.append("spotify")
    return [
        discord.app_commands.Choice(name=platform, value=platform)
        for platform in platforms if current.lower() in platform.lower()
    ]


class SelectListView2(discord.ui.View):
    def __init__(self, *, timeout = 180, options: dict, interaction: discord.Interaction,results: list, playlist: str, platform: str):
        super().__init__(timeout=timeout)
        self.add_item(SelectSong2(option=options, interaction=interaction,results=results,playlist=playlist,platform=platform))

class SelectSong2(discord.ui.Select):
    def __init__(self,option: dict, interaction: discord.Interaction, results: list,playlist: str,platform: str):
        #set options to the possibilities for the song
        self.music_options=results
        #allow access to the original interaction
        self.original_interaction = interaction
        # add playlist and platform
        self.playlist = playlist
        self.platform = platform
        # ask for an option to be selected
        super().__init__(placeholder="Select an option",options=option)
    async def callback(self, interaction: discord.Interaction):
        #check the selection against the list
        option = self.music_options[int(self.values[0][0])-1]
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (self.original_interaction.user.id,))
        result = cursor.fetchone()
        playlists = {}
        if result != None:
            playlists=json.loads(result[3])
        if self.platform == "youtube":
            url = 'https://www.youtube.com' + option['url_suffix']
            title = option['title']
            duration = option['duration'].split(":")
            duration = (int(duration[0])*60 + int(duration[1]))*1000
            entry = {"url": url,"title": title, "artist": option["channel"], "platform": "youtube","auth": None, "length": duration}
        elif self.platform == "spotify":
            url = option['uri']
            title = option['name']
            artists = ", ".join([option["artists"][i]["name"] for i in range(len(option["artists"]))])
            entry = {"url": url,"title": title,"artist": artists, "platform": "spotify","auth": option["user_id"], "length": option["duration_ms"]}
        playlists[self.playlist].append(entry)
        cursor.execute("UPDATE users SET Playlists = ? WHERE id = ?", (json.dumps(playlists),self.original_interaction.user.id))
        db.commit()
        db.close()
        await self.original_interaction.edit_original_response(content=f"Successfully added {title} to {self.playlist}.",view=None)

@playlists.command(name="remove", description='removes a song from a playlist.')
async def remove(interaction: discord.Interaction, playlist:str):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = []
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    if playlist not in playlists:
        await interaction.response.send_message("You do not have a playlist with that name.")
        return
    if playlists[playlist] == []:
        await interaction.response.send_message("You do not have any songs in that playlist.")
        return
    selections = []
    for song in playlists[playlist]:
        selections.append(discord.SelectOption(label=song['title'], emoji='🎧'))
    selections.append(discord.SelectOption(label="Cancel", emoji='❌'))
    view = SelectListView3(options=selections, interaction=interaction,playlist=playlist)
    try:
        await interaction.response.send_message(f"select a song to remove from {playlist}:",view=view)
    except:
        await interaction.response.send_message(content='An error occured. Please Try again.')

@remove.autocomplete('playlist')
async def mute_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    settings = [i for i in playlists]
    return [
        discord.app_commands.Choice(name=setting, value=setting)
        for setting in settings if current.lower() in setting.lower()
    ]

    

class SelectListView3(discord.ui.View):
    def __init__(self, *, timeout = 180, options: dict, interaction: discord.Interaction,playlist: str):
        super().__init__(timeout=timeout)
        self.add_item(SelectSong3(option=options, interaction=interaction,playlist=playlist))

class SelectSong3(discord.ui.Select):
    def __init__(self,option: dict, interaction: discord.Interaction,playlist: str):
        #set options to the possibilities for the song
        #allow access to the original interaction
        self.original_interaction = interaction
        # add playlist
        self.playlist = playlist
        # ask for an option to be selected
        super().__init__(placeholder="Select an option",options=option)
    async def callback(self, interaction: discord.Interaction):
        #check the selection against the list
        option = [option.label for option in self.options if option.label == self.values[0]][0]
        if option == "Cancel":
            await self.original_interaction.edit_original_response(content=f"OK, Cancelled.",view=None)
            return
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (self.original_interaction.user.id,))
        result = cursor.fetchone()
        # can assume playlist exists as it is checked before this is called
        playlists=json.loads(result[3])
        for song in playlists[self.playlist]:
            if song['title'] == option:
                playlists[self.playlist].remove(song)
                # update database
                cursor.execute("UPDATE users SET Playlists = ? WHERE id = ?", (json.dumps(playlists),self.original_interaction.user.id))
                db.commit()
                db.close()
        await self.original_interaction.edit_original_response(content=f"Successfully removed {option} from {self.playlist}.",view=None)


@playlists.command(name="list", description='lists playlists or songs in a playlist.')
async def list_em(interaction: discord.Interaction, playlist:str = None):
    if playlist == None:
        # create embed with all playlists, and their lengths, then send it
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
        result = cursor.fetchone()
        playlists = {}
        if result != None:
            if result[3] != None and result[3] != "{}":
                playlists=json.loads(result[3])
        if playlists == {}:
            await interaction.response.send_message("You do not have any playlists.")
            return
        response = discord.Embed(title="Playlists:", color=0x336EFF)
        num = 0
        for playlist in playlists:
            total = 0
            for song in playlists[playlist]:
                total += song["length"]
            num+=1
            if num <= 25:
                response.add_field(name=str(num) + ". " + playlist, value=f"""{len(playlists[playlist])} song{"s" if len(playlists[playlist]) > 1 else ""}\nTotal Time: {str(datetime.timedelta(milliseconds=(total-(total%1000))))}""", inline=False)
        view = SelectButtonView3(options=["Previous","Next"], interaction=interaction, embed=response)
        await interaction.response.send_message(embed=response,view=view)
    else:
        # create embed with all songs in playlist, and the total length of it, then send it
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
        result = cursor.fetchone()
        playlists = []
        if result != None:
            if result[3] != None and result[3] != "{}":
                playlists=json.loads(result[3])
        if playlist not in playlists:
            await interaction.response.send_message("You do not have a playlist with that name.")
            return
        if playlists[playlist] == []:
            await interaction.response.send_message("You do not have any songs in that playlist.")
            return
        response = discord.Embed(title=playlist + ":", color=0x336EFF)
        total = 0
        num = 0
        for song in playlists[playlist]:
            total += song["length"]
            num+=1
            if num <= 25:
                response.add_field(name=str(num) + ". " + song["title"], value=f"by {song['artist']}\nDuration: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))}", inline=False)
            response.set_footer(text=f"Total Time: {str(datetime.timedelta(milliseconds=(total-(total%1000))))}")
            view = SelectButtonView4(options=["Previous","Next"], interaction=interaction, embed=response)
        await interaction.response.send_message(embed=response,view=view)
@list_em.autocomplete('playlist')
async def list_em_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    settings = [i for i in playlists]
    return [
        discord.app_commands.Choice(name=setting, value=setting)
        for setting in settings if current.lower() in setting.lower()
    ]


class SelectButtonView4(discord.ui.View):
    def __init__(self, *, timeout = 180, options: list, interaction: discord.Interaction, embed: discord.Embed):
        super().__init__(timeout=timeout)
        for option in options:
            self.add_item(ButtonClass4(label=option, interaction=interaction, embed=embed))

class ButtonClass4(discord.ui.Button):
    def __init__(self, label: str, interaction: discord.Interaction, embed: discord.Embed):
        # Allow access to the original interaction
        self.original_interaction = interaction
        self.embed = embed
        super().__init__(label=label)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        title = self.embed.title.split(":")[0]
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
        result = cursor.fetchone()
        playlists = {}
        if result != None:
            if result[3] != None and result[3] != "{}":
                playlists=json.loads(result[3])
        db.close()
        if self.label == "Next":
            last_field = self.embed.fields[-1]
            num = int(last_field.name.split(".")[0])
            if num == len(playlists[title]):
                return
            self.embed.clear_fields()
            for i in range(25):
                if num+i < len(playlists[title]):
                    song = playlists[title][num+i]
                    self.embed.add_field(name=str(num+i+1) + f".{' **(Current song)**' if num+i+1 == 1 else ''}", value=f"Title: {song['title']}\nArtist: {song['artist']}\nLength: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))} seconds", inline=False)
            view = SelectButtonView2(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed)
        else:
            first_field = self.embed.fields[0]
            num = int(first_field.name.split(".")[0])-1
            if num-25 < 0:
                return
            self.embed.clear_fields()
            for i in range(25):
                if num-25+i >= 0:
                    song = playlists[title][num-25+i]
                    self.embed.add_field(name=str(num-24+i) + f".{' **(Current song)**' if num-24+i == 1 else ''}", value=f"Title: {song['title']}\nArtist: {song['artist']}\nLength: {str(datetime.timedelta(milliseconds=(song['length']-(song['length']%1000))))} seconds", inline=False)
            view = SelectButtonView2(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed)




class SelectButtonView3(discord.ui.View):
    def __init__(self, *, timeout = 180, options: list, interaction: discord.Interaction, embed: discord.Embed):
        super().__init__(timeout=timeout)
        for option in options:
            self.add_item(ButtonClass3(label=option, interaction=interaction, embed=embed))

class ButtonClass3(discord.ui.Button):
    def __init__(self, label: str, interaction: discord.Interaction, embed: discord.Embed):
        # Allow access to the original interaction
        self.original_interaction = interaction
        self.embed = embed
        super().__init__(label=label)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
        result = cursor.fetchone()
        playlists = []
        if result != None:
            if result[3] != None and result[3] != "{}":
                playlists=json.loads(result[3])

        if self.label == "Next":
            last_field = self.embed.fields[-1]
            num = int(last_field.name.split(".")[0])
            if num == len(list(playlists.keys())):
                return
            self.embed.clear_fields()
            for i in range(25):
                if num+i < len(playlists):
                    playlist = list(playlists.keys())[num+i]
                    # get total length of playlist
                    total = 0
                    for song in playlists[playlist]:
                        total += song["length"]
                    self.embed.add_field(name=str(num+i+1) + ". " + playlist, value=f"{len(playlists[playlist])} song{'s' if len(playlists[playlist]) > 1 else ''}\nTotal Time: {str(datetime.timedelta(milliseconds=(total-(total%1000))))}", inline=False)
            view = SelectButtonView3(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed,view=view)
        else:
            first_field = self.embed.fields[0]
            num = int(first_field.name.split(".")[0])
            if num-25 < 0:
                return
            self.embed.clear_fields()
            for i in range(25):
                playlist = list(playlists.keys())[num-25+i]
                if num-25+i >= 0:
                    total = 0
                    for song in playlists[playlist]:
                        total += song["length"]
                    self.embed.add_field(name=str(num-25+i) + ". " + playlist, value=f"{len(playlists[playlist])} song{'s' if len(playlists[playlist]) > 1 else ''}\nTotal Time: {str(datetime.timedelta(milliseconds=(total-(total%1000))))}", inline=False)
            view = SelectButtonView3(options=["Previous", "Next"], interaction=interaction, embed=self.embed)
            await self.original_interaction.edit_original_response(embed=self.embed,view=view)





@playlists.command(name="delete", description='deletes a playlist.')
async def delete(interaction: discord.Interaction, playlist:str):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    if playlist not in playlists:
        await interaction.response.send_message("You do not have a playlist with that name.")
        return
    playlists.pop(playlist)
    cursor.execute("UPDATE users SET Playlists = ? WHERE id = ?", (json.dumps(playlists),interaction.user.id))
    db.commit()
    db.close()
    await interaction.response.send_message(f"Successfully deleted {playlist}.")
@delete.autocomplete('playlist')
async def mute_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    settings = [i for i in playlists]
    return [
        discord.app_commands.Choice(name=setting, value=setting)
        for setting in settings if current.lower() in setting.lower()
    ]


@playlists.command(name="play", description='plays a playlist.')
async def play(interaction: discord.Interaction, playlist:str):
    playhere = True if len(bot.queue[interaction.guild.id]) == 0 else False
    if interaction.user.voice == None:
        await interaction.response.send_message("You are not in a voice channel.")
        return
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    db.close()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    if playlist not in playlists:
        await interaction.response.send_message("You do not have a playlist with that name.")
        return
    if playlists[playlist] == []:
        await interaction.response.send_message("You do not have any songs in that playlist.")
        return
    for song in playlists[playlist]:
        bot.queue[interaction.guild.id].append(song)
        bot.queueorder[interaction.guild.id].append(song)
    if playhere:
        await interaction.response.send_message(f"Now playing {playlist}.")
        vc = await interaction.user.voice.channel.connect()
        while len(bot.queue[interaction.guild.id]) > 0:
            if bot.queue[interaction.guild.id][0]["platform"] == "spotify":
                db = sqlite3.connect("userdata.db")
                cursor = db.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (bot.queue[interaction.guild.id][0]["auth"] if not bot.settings["globalSpotify"] else 0,))
                spot_result = cursor.fetchone()
                if spot_result[2] == True:
                    cursor.execute("SELECT * FROM users WHERE id = ?", (spot_result[1],))
                    spot_result = cursor.fetchone()
                db.close()
                try:
                    session = lbc.Session.Builder().stored(spot_result[1]).create()
                except:
                    await asyncio.sleep(1)
                    try:
                        session = lbc.Session.Builder().stored(spot_result[1]).create()
                    except:
                        await response.edit_original_response(content="Failed to connect to spotify.")
                        await vc.disconnect()
                        return
                track_id = TrackId.from_uri(bot.queue[interaction.guild.id][0]["url"])
                stream = session.content_feeder().load(track_id, VorbisOnlyAudioQuality(AudioQuality.VERY_HIGH), False, None)
                audio = stream.input_stream
                song = await ByteAudioSource.get_stream(stream=audio.stream())
                songname = bot.queue[interaction.guild.id][0]
                
            else:
                #record what will be played
                songname = bot.queue[interaction.guild.id][0]
                #get a stream
                song = await YTDLSource.from_url(url=bot.queue[interaction.guild.id][0]["url"], loop=bot.loop, stream=True)
            #play the stream
            vc.play(song)
            #wait for the current song to end or get skipped
            while vc.is_playing() or vc.is_paused():
                if not songname == bot.queue[interaction.guild.id][0]:
                    vc.stop()
                await asyncio.sleep(0.1)
            #remove the first entry in the queue if not skipped
            if len(bot.queue[interaction.guild.id]) > 0 and bot.loopmode[interaction.guild.id] in [0,2]:
                if songname == bot.queue[interaction.guild.id][0]:
                    if bot.loopmode[interaction.guild.id] == 2:
                        bot.queue[interaction.guild.id].append(bot.queue[interaction.guild.id][0])
                        bot.queueorder[interaction.guild.id].append(bot.queueorder[interaction.guild.id][0])
                    #remove from queue
                    bot.queue[interaction.guild.id].pop(0)
                    # if shuffle is enable iterate over ordered list to
        await vc.disconnect()
    else:
        await interaction.response.send_message(f"Added {playlist} to the queue.")
@play.autocomplete('playlist')
async def mute_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    db.close()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    settings = [i for i in playlists]
    return [
        discord.app_commands.Choice(name=setting, value=setting)
        for setting in settings if current.lower() in setting.lower()
    ]

#import playlists from spotify
@playlists.command(name="import", description='imports a spotify playlist.')
async def import_playlist(interaction: discord.Interaction, playlist:str):
    await interaction.response.send_message("searching...")
    name = playlist # i accidentally overwrote playlist and am too lazy to fix it.
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    db.close()
    if not result[1]:
        await interaction.edit_original_response(content="You do not have spotify linked.")
        return
    try:
        session = lbc.Session.Builder().stored(result[1]).create()
    except:
        await interaction.edit_original_response(content="An error occured, please try again.")
        return
    oauth_token = session.tokens().get("playlist-read")
    sp = spotipy.Spotify(auth=oauth_token)
    playlists = sp.current_user_playlists()
    playlists = playlists["items"]
    playlists = [playlist1 for playlist1 in playlists if playlist1["name"].lower() == playlist.lower()]
    if playlist == []:
        await interaction.edit_original_response(content="You do not have a playlist with that name.")
        return
    playlist = playlists[0]
    tracks = sp.playlist_tracks(playlist["id"])
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    playlists = {}
    if result != None:
        if result[3] != None and result[3] != "{}":
            playlists=json.loads(result[3])
    num = 1
    while playlist["name"] in playlists:
        playlist["name"] = playlist["name"][:-len(str(num-1))] + str(num+1)
        num+=1
    playlists[playlist["name"]] = []
    for i in range(len(tracks["items"])):
        track = tracks["items"][i]["track"]
        artists = ", ".join([artist["name"] for artist in track["artists"]])
        playlists[playlist["name"]].append({"url": track["uri"],"title": track["name"],"artist": artists, "platform": "spotify","auth": interaction.user.id, "length": track["duration_ms"]})
    cursor.execute("UPDATE users SET Playlists = ? WHERE id = ?", (json.dumps(playlists),interaction.user.id))
    db.commit()
    db.close()
    await interaction.edit_original_response(content=f"""Successfully imported {name}{f" as {playlist['name']}" if playlist['name'] != name else ''}.""")
@import_playlist.autocomplete('playlist')
async def import_playlist_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    db.close()
    playlists = {}
    if result[1] != None:
        session = lbc.Session.Builder().stored(result[1]).create()
        oauth_token = session.tokens().get("playlist-read")
        sp = spotipy.Spotify(auth=oauth_token)
        playlists = sp.current_user_playlists()
        playlists = playlists["items"]
        playlists = [playlist["name"] for playlist in playlists]
        return [
            discord.app_commands.Choice(name=playlist, value=playlist)
            for playlist in playlists if current.lower() in playlist.lower()
        ]
bot.tree.add_command(playlists)


bot.run(token)
