# Tempo
 Rythm clone, a bot for streaming music.

## dependencies
to install the dependencies run:
`pip install pynacl discord asyncio youtube_search yt-dlp python-dotenv git+https://github.com/kokarare1212/librespot-python spotipy aiohttp`
Also [install sqlite3](https://www.sqlite.org/index.html)

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
- [X] Spotify
- [ ] Auto updates or update notifications
