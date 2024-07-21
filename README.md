# Tempo
 Rythm clone, a bot for streaming music.

## Info on V2

V2 of this bot is an ambitious (mostly) rewrite, and it will take some time. The following is planned:

- [ ] Modularity (using cogs)
- [ ] Plugins
    - Each platform will be a plugin
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

## Useage
To use this bot, first install [miniconda](https://docs.anaconda.com/miniconda/), then run the following commands:

```sh
$ conda env create -f /path/to/Tempo/environment.yml
$ conda activate Tempo
$ python bot.py
```
The bot will then prompt you for a token. Supply your bot token to it and it will run. Add it to your servers, then run `$sync` to enable the slash commands within discords UI.

## Updating

The bot will notify you if there is an update available. It is recommended that git is used to keep the bot up to date with the latest release on github. The bot will give you the update command when it discovers an update.

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


known issues:
 - doesnt always pick up wake word
 - freeze on youtube search
