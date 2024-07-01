import os
import sys
import asyncio
import libTempo
import discord
import sqlite3
import discord
from discord.ext import commands, tasks
import typing
import dotenv
import aiohttp
version = "2.0.0"


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
    


backends = libTempo.import_backends("Backends/Music")



# set intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True





# make the bot
bot = commands.Bot(command_prefix = '$',intents=intents, activity=discord.Game(name='Play some music!'))
bot.settings = {
    "updateDM": True,
    "Voice": {}
}


#update checks
ownerupdated = False
@tasks.loop(hours=1)
async def updatecheck():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.github.com/repos/jumpers775/Tempo/releases/latest') as resp:
            resp = await resp.json()
            latestversion = resp["tag_name"] # keep for formatting in message
            newestversion = int("".join(resp["tag_name"].split(".")))
            currentversion = int("".join(version.split("."))) 
            if newestversion > currentversion:
                print(f"Update Available!\n{version} --> {latestversion}")
                if bot.settings["updateDM"] and (not ownerupdated or updateversion != newestversion):
                    updateversion = newestversion
                    app_info = await bot.application_info()
                    user = bot.get_user(app_info.owner.id)
                    await user.send(f"Update Available!\n{version} --> {newestversion}\n {resp['html_url']}")




@bot.event
async def on_ready():
    await updatecheck()
    print(f"{bot.user} is online.")
    bot.players = {}
    for guild in bot.guilds:
        bot.settings["Voice"][guild.id] = True
        bot.players[guild.id] = libTempo.MusicPlayer(backends, bot.settings["Voice"][guild.id])

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
    await interaction.response.send_message("Searching...")
    result = await backends["youtube"].search(song, interaction.user)
    options = []
    for i in range(len(result)):
        options.append(discord.SelectOption(label=f'{i+1}) '+ result[i].title, description=f'By {result[i].author}', emoji='🎧'))
    view = PlaySelectListView(options=options, interaction=interaction,results=result)
    await interaction.edit_original_response(content="Choose a song", view=view)

#view class to select the correct song.
class PlaySelectListView(discord.ui.View):
    def __init__(self, *, timeout = 180, options: dict, interaction: discord.Interaction,results: list):
        super().__init__(timeout=timeout)
        self.add_item(PlaySelectSong(option=options, interaction=interaction,results=results))

class PlaySelectSong(discord.ui.Select):
    def __init__(self,option: dict, interaction: discord.Interaction, results: list):
        #set options to the possibilities for the song
        self.results=results
        #allow access to the original interaction
        self.original_interaction = interaction
        # ask for an option to be selected
        super().__init__(placeholder="Select an option",options=option)
    async def callback(self, interaction: discord.Interaction):
        selection = int(self.values[0].split(") ")[0])-1
        option = self.results[selection]
        if bot.players[interaction.guild.id].active == False:
            try:
                await bot.players[interaction.guild.id].join_channel(self.original_interaction.user.voice.channel) 
            except:
                await self.original_interaction.edit_original_response(content="you are not currently in a voice channel.", view=None)
                return
        bot.players[interaction.guild.id].add_song(option)
        if len(bot.players[interaction.guild.id].playlist) == 1:
            await self.original_interaction.edit_original_response(content=f"Now Playing {option.title}.", view=None)
            bot.players[interaction.guild.id].play()
        else:
            await self.original_interaction.edit_original_response(content=f"{option.title} added to the queue.", view=None)

bot.tree.add_command(play)


@discord.app_commands.command(name='stop', description='Stops the current session')
async def stop(interaction: discord.Interaction):
    if bot.players[interaction.guild.id].active == False:
        await interaction.response.send_message("There is nothing to stop.")
        return
    bot.players[interaction.guild.id].stop()
    await interaction.response.send_message("Session stopped.")

bot.tree.add_command(stop)


@discord.app_commands.command(name='pause', description='Pauses the current song')
async def pause(interaction: discord.Interaction):
    if bot.players[interaction.guild.id].active == False:
        await interaction.response.send_message("There is nothing to pause.")
        return
    bot.players[interaction.guild.id].pause()
    await interaction.response.send_message(f"Paused {bot.players[interaction.guild.id].playlist.GetCurrentEntry().title}.")

bot.tree.add_command(pause)

@discord.app_commands.command(name='resume', description='Resumes the current song')
async def resume(interaction: discord.Interaction):
    if bot.players[interaction.guild.id].active == False:
        await interaction.response.send_message("There is nothing to resume.")
        return
    bot.players[interaction.guild.id].resume()
    await interaction.response.send_message(f"Resumed {bot.players[interaction.guild.id].playlist.GetCurrentEntry().title}.")

bot.tree.add_command(resume)

@discord.app_commands.command(name='skip', description='Skips the current song')
async def skip(interaction: discord.Interaction):
    if bot.players[interaction.guild.id].active == False:
        await interaction.response.send_message("There is nothing to skip.")
        return
    title = bot.players[interaction.guild.id].playlist.GetCurrentEntry().title
    bot.players[interaction.guild.id].skip()
    await interaction.response.send_message(f"Skipped {title}.")

bot.tree.add_command(skip)


@discord.app_commands.command(name='queue', description='Shows the Queue')
async def queue(interaction: discord.Interaction):
    if len(bot.players[interaction.guild.id].playlist) == 0:
        await interaction.response.send_message("There is no music playing.")
        return
    
    entries = bot.players[interaction.guild.id].getQueue()
    embed = discord.Embed(title="Current Song Queue", color=0x00ff00)
    
    # Calculate total duration
    total_duration = 0
    for song in entries:
        total_duration += song[2]

    # Convert total duration to mm:ss format
    total_minutes, total_seconds = divmod(total_duration, 60)
    total_duration_str = f"{total_minutes}:{total_seconds:02d}"

    # Add song details to the embed
    for index, (title, author, duration) in enumerate(entries):
        if index == 0:
            embed.add_field(name=f"**{index + 1}. {title} [Now Playing]**", value=f"By {author}.", inline=False)
        else:
            embed.add_field(name=f"**{index + 1}. {title}**", value=f" By {author}", inline=False)
    embed.add_field(name="Shuffle", value='On' if bot.players[interaction.guild.id].playlist.shuffle != False else 'Off', inline=True)
    embed.add_field(name="Loop", value=["Off","Queue","Song"][bot.players[interaction.guild.id].playlist.loop], inline=True)

    # Add total duration at the bottom
    embed.add_field(name="Total Duration", value=total_duration_str, inline=False)
    await interaction.response.send_message(embed=embed)



bot.tree.add_command(queue)



@discord.app_commands.command(name='shuffle', description='sets shuffle mode.')
async def shuffle(interaction: discord.Interaction, mode:bool):
    bot.players[interaction.guild.id].playlist.SetShuffle(mode)
    await interaction.response.send_message(f"Shuffle {'enabled' if mode else 'disabled'}.")
bot.tree.add_command(shuffle)

@discord.app_commands.command(name='loop', description='sets loop mode.')
async def loop(interaction: discord.Interaction, mode:str):
    if mode not in ["off", "queue", "song"]:
        await interaction.response.send_message("Invalid mode.")
        return
    bot.players[interaction.guild.id].playlist.SetLoop(["off", "queue", "song"].index(mode))
    await interaction.response.send_message(f"Loop set to {mode}.")
bot.tree.add_command(loop)
@loop.autocomplete('mode')
async def shuffle_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[discord.app_commands.Choice[str]]:
    statuses = ['off', 'song','queue']
    return [
        discord.app_commands.Choice(name=status, value=status)
        for status in statuses if current.lower() in status.lower()
    ]









dotenv.load_dotenv()
try:
    token = os.environ['token']
except:
    token = input("no token provided, Please input it here: ")
    with open('.env', 'w') as envfile:
        envfile.write('token = '+ token)


bot.run(token)