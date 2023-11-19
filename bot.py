import json
import discord
from discord.ext import commands
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
import pydub
import opuslib



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

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER,
    spotify INTEGER
)""")

db.close()




# set intents
intents = discord.Intents.default()
intents.message_content = True

# make the bot
bot = commands.Bot(command_prefix = '$',intents=intents, activity=discord.Game(name='Play some music!'))



# basic setup
@bot.event
async def on_ready():
    print(f"{bot.user} is online.")
    bot.queue = {0:[]}
    bot.shuffle = {0:False}
    bot.queueorder = {0:[]}
    for guild in bot.guilds:
        bot.queue[guild.id] = []
        bot.shuffle[guild.id] = False
        bot.queueorder[guild.id] = []



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


# spotify


async def is_spotify(id:int):
    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    result = cursor.fetchone()
    db.close()
    return result != None



@discord.app_commands.command(name='spotauth', description='authenticates a spotify premium account. MAKE SURE YOU TRUST THE BOT OWNER.')
async def spotauth(interaction: discord.Interaction, email:str, passwd:str):
    
    db = sqlite3.connect("userdata.db")

    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    result = cursor.fetchone()
    db.close()
    if result == None:
        try:
            session = lbc.Session.Builder() \
            .user_pass(email,passwd) \
            .create()

        except:
            await interaction.response.send_message("Invalid credentials.", ephemeral=True)
            return
        access_token = session.stored()
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("INSERT INTO users VALUES (?,?)", (interaction.user.id,access_token))
        db.commit()
        db.close()
    else:
        await interaction.response.send_message("You have already authenticated a spotify account. Use /spotrm to remove it", ephemeral=True)
        return
    await interaction.response.send_message("Successfully authenticated spotify account.",ephemeral=True)

bot.tree.add_command(spotauth)



@discord.app_commands.command(name='spotrm', description='removes an authenticated a spotify premium account.')
async def spotrm(interaction: discord.Interaction):
    db = sqlite3.connect("userdata.db")

    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))    
    result = cursor.fetchone()

    db.close()
    if result == None:
        await interaction.response.send_message("You have not authenticated a spotify account.", ephemeral=True)
        return
    else:
        db = sqlite3.connect("userdata.db")
        cursor = db.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (interaction.user.id,))
        db.commit()
        db.close()
    await interaction.response.send_message("Successfully removed spotify account.",ephemeral=True)
bot.tree.add_command(spotrm)




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
        }
        ytdl = youtube_dl.YoutubeDL(ydl_opts)
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a youtube playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

#add a song to the servers queue, and play the queue
@discord.app_commands.command(name='play', description='plays a song')
async def play(interaction: discord.Interaction, song:str):
    try:
        channel = interaction.user.voice.channel
    except:
        await interaction.response.send_message("you are not currently in a voice channel.")
        return
    message = await interaction.response.send_message("searching...")

    db = sqlite3.connect("userdata.db")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (interaction.user.id,))
    spot_result = cursor.fetchone()
    db.close()
    if spot_result == None:
        # search for the song on youtube
        results = YoutubeSearch(song, max_results=10).to_json()
        results = json.loads(results)
        results = results['videos']
    else:
        # search for the song on spotify
        try:
            session = lbc.Session.Builder().stored(spot_result[1]).create()
        except:
            await interaction.response.send_message("An error occured, please try again.")
            return
        oauth_token = session.tokens().get("playlist-read")
        sp = spotipy.Spotify(auth=oauth_token)
        results = sp.search(q=song, type='track', limit=10)["tracks"]["items"]
        results = [result | {"user_id": interaction.user.id} for result in results]
    #build an option for each song
    options = []
    num = 1
    for result in results:
        if spot_result == None:
            options.append(discord.SelectOption(label=f'{num}) '+ result['title'], description=f'By {result["channel"]}', emoji='🎧'))
        else:
            options.append(discord.SelectOption(label=f'{num}) '+ result["name"], description=f'By {result["artists"][0]["name"]}', emoji='🎧'))
        num+=1

    #build a view to choose the option
    view = SelectView(options=options, interaction=interaction,results=results)

    #select a song
    try:
        await interaction.edit_original_response(content='Select a song to play:',view=view)
    except:
        await interaction.edit_original_response(content='An error occured. Please Try again.')

#view class to select the correct song.
class SelectView(discord.ui.View):
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
            # make queue entry
            entry = {"url": url,"title": title,"platform": "spotify","auth": option["user_id"]}
        else:
            # set the url
            url = 'https://www.youtube.com' + option['url_suffix']
            # set the title
            title = option['title']
            # make queue entry
            entry = {"url": url,"title": title,"platform": "youtube","auth": None}
        #insert in a random spot non-current if shuffle is enabled, at the end if disabled
        if bot.shuffle[interaction.guild.id] and len(bot.queue[interaction.guild.id]) > 1:
            spot = random.randint(1,len(bot.queue[interaction.guild.id]))
        else:
            spot = len(bot.queue[interaction.guild.id])
        bot.queue[interaction.guild.id].insert(spot, entry)
        #record the location of this item in case shuffle is turned off
        print(type(bot.queueorder),bot.queueorder)
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
                    cursor.execute("SELECT * FROM users WHERE id = ?", (bot.queue[interaction.guild.id][0]["auth"],))
                    spot_result = cursor.fetchone()
                    db.close()
                    session = lbc.Session.Builder().stored(spot_result[1]).create()

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
                while vc.is_playing():
                    if not songname == bot.queue[interaction.guild.id][0]:
                        vc.stop()
                    await asyncio.sleep(0.1)
                #remove the first entry in the queue if not skipped
                if len(bot.queue[interaction.guild.id]) > 0:
                    if songname == bot.queue[interaction.guild.id][0]:
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
    #build a list of songs
    #each song is stored as a url, so iterate over them and get info, add it to an embed.
    response = discord.Embed(title="Queue:", description=f"Shuffle is {'on' if bot.shuffle[interaction.guild.id] else 'off'}", color=0x336EFF)
    i = 1
    for song in bot.queue[interaction.guild.id]:
        response.add_field(name=str(i) + f".{' **(Current song)**' if i == 1 else ''}", value=song["title"], inline=False)
        i+=1
    # send response
    await interaction.response.send_message(embed=response)

#remove a song from the queue
@queue.command(name="del", description='removes a song from the queue')
async def view(interaction: discord.Interaction, spot: int):
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


# skip command
@discord.app_commands.command(name="skip", description='skips the current song.')
async def skip(interaction: discord.Interaction):
    # make sure there is a second song to play after this one
    if len(bot.queue[interaction.guild.id]) > 1:
        #record title to inform what was skipped
        title = bot.queue[interaction.guild.id][0]
        # skip the current song
        bot.queue[interaction.guild.id].pop(0)
        spot = 0
        for song in bot.queueorder[interaction.guild.id]:
            if song == title:
                bot.queueorder[interaction.guild.id].pop(spot)
                break
            else:
                spot+=1
        # tell the user that it was done
        await interaction.response.send_message(f"Skipped {title['title']}")
    # if only one song, stop playback altogether
    elif discord.utils.get(bot.voice_clients, guild=interaction.guild) != None:
        bot.queue[interaction.guild.id] = []
        bot.queueorder[interaction.guild.id] = []
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Only one song in queue, stopping.")
    # if neither, no songs are playing
    else:
        await interaction.response.send_message("Nothing is playing.")
bot.tree.add_command(skip)


bot.run(token)
