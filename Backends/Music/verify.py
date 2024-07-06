def verify(backend):
    """
    Verifies that a backend has all the required functions. Also returns the backend type.
    Backend types:
    0 - Invalid, missing required functions
    1 - Valid
    2 - Valid, Platform Playlists supported
    """
    # Presume maximum support
    req = False
    playlist = False

    fns = dir(backend)

    required_functions = ["search","getstream", "auth"]
    playlist_functions = ["getplaylist"]

    if False not in [i in fns for i in required_functions]:
        req = True
    
    if False not in [i in fns for i in playlist_functions]:
        playlist = True

    if req == True and playlist == True:
        return 2
    
    if req == True and playlist == False:
        return 1
    
    return 0