# Tempo
 Rythm clone, a bot for streaming music.

## Info on V2

V2 of this bot is an ambitious (mostly) rewrite, and it will take some time. The following is planned:

- [ ] Modularity (using cogs)
- [X] platform Plugins 
    - This means more platforms can be supported easily
    - There will be a plugin API for custom plugins
- [ ] Speech recognition (allows you to skip/add songs/etc using your voice while the bot is playing)
    - Bot will listen for a keyword, then once it hears it will respond to the user 
    - I plan on doing this with a combo between whisper and an LLM (release will likely use phi3-mini)
    - User will be able to configure which models are in use
    - Fully disableable
    - Must be runnable on a Rasberry pi 5 with 8GB of ram
- [ ] Native playlist support
      - This must include the ability to access playlists on supported platforms
- [ ] Update utility within the bot (will require owner to press a button)
- [ ] Nicer UX

## dependencies
Use python3.11 for now as not all of the dependenccies support 3.12+
to install the dependencies run:
`pip install pynacl git+https://github.com/Rapptz/discord.py.git asyncio youtube_search yt-dlp python-dotenv git+https://github.com/kokarare1212/librespot-python spotipy aiohttp matcha-tts pydub numpy discord-ext-voice-recv SpeechRecognition `
Also install [sqlite3](https://www.sqlite.org/index.html) and [ffmpeg](https://ffmpeg.org/)

## Running the bot

The bot will prompt you for a token, supply your bot token to it, and it will run. run `$sync` to sync the command tree to all servers this bot is in, and then the slash commands should be visible within dicords ui.

## Updating

This bot will be kept runnable, however there may be periods of time where I have less time to work on bug fixes and polish. For now there is no way to auto update, or to notify you when there is an update, however that is planned.

## Features

This bot features the following:

- [X] Slash commands
- [X] Youtube search
- [X] Youtube Playback
- [X] Song queue 
- [X] A way to stop all playback
- [X] A way to manipulate the queue
- [X] Shuffle playback
- [X] yt-dlp (greatly improves audio quality, however as of now randomly drops in connection)
- [X] Spotify support (search, playback, accounts)
- [X] Update notifications
- [X] Pause support
- [X] Loop support
- [ ] Spotify playlists
- [ ] YT playlists
- [ ] inbuilt playlists
