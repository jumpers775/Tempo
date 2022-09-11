import json
import discord
from discord.ext import commands
import asyncio
import youtube_dl
import dotenv
import typing
import os 
from youtube_search import YoutubeSearch

# get token 
dotenv.load_dotenv()
try:
    token = os.environ['token']
except:
    token = input("no token provided, Please input it here: ")
    with open('.env', 'w') as envfile:
        envfile.write('token = '+ token)

# set intents
intents = discord.Intents.default()
intents.message_content = True

# make the bot
bot = commands.Bot(command_prefix = '$',intents=intents, activity=discord.Game(name='Play some music!'))

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

# basic setup
@bot.event
async def on_ready():
    bot.queue = {}
    for guild in bot.guilds:
        bot.queue[guild.id] = []

#youtube streaming
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        youtube_dl.utils.bug_reports_message = lambda: ''
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
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
            # take first item from a playlist
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
    # search for the song on youtube
    results = YoutubeSearch(song, max_results=10).to_json()
    results = json.loads(results)
    results = results['videos']
    #build an option for each song
    options = []
    num = 1
    for result in results:
        options.append(discord.SelectOption(label=f'{num}) '+ result['title'], description=f'By {result["channel"]}', emoji='🎧'))
        num+=1

    #build a view to choose the option
    view = SelectView(options=options, interaction=interaction,results=results)

    #select a song
    await interaction.edit_original_response(content='Select a song to play:',view=view)

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
        for option in self.music_options:
            if option['title'] == self.values[0][3:]:
                # set the url
                url = 'https://www.youtube.com' + option['url_suffix']
                bot.queue[interaction.guild.id].append(url)
                #check if the new url is the first in the list
                if not bot.queue[interaction.guild.id][0] is url:
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
                        #get a stream
                        song = await YTDLSource.from_url(url=bot.queue[interaction.guild.id][0], loop=bot.loop, stream=True)
                        #play the stream
                        vc.play(song)
                        #wait for the current song to end
                        while vc.is_playing():
                            await asyncio.sleep(0.1)
                        #remove the first entry in the queue
                        bot.queue[interaction.guild.id].pop(0)
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
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Stopped the music.")
    else:
        # if not, inform the user that there is no music playing.
        await interaction.response.send_message("There is no music playing.", ephemeral=True)
# add the stop command to the commands tree
bot.tree.add_command(stop)



bot.run(token)