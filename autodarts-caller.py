import os
from os import path
import time
import json
import ssl
import platform
import random
import argparse
import rel

from keycloak import KeycloakOpenID
import requests

import _thread
# import threading

import websocket



AUTODART_URL = 'https://autodarts.io'
AUTODART_AUTH_URL = 'https://login.autodarts.io/auth/'
AUTODART_AUTH_TICKET_URL = 'https://api.autodarts.io/ms/v0/ticket'
AUTODART_CLIENT_ID = 'autodarts-app'
AUTODART_REALM_NAME = 'autodarts'
AUTODART_MATCHES_URL = 'https://api.autodarts.io/gs/v0/matches'
AUTODART_BOARDS_URL = 'https://api.autodarts.io/bs/v0/boards/'
AUTODART_WEBSOCKET_URL = 'wss://api.autodarts.io/ms/v0/subscribe?ticket='

SUPPORTED_GAME_VARIANTS = ['X01']
VERSION = '0.1.0'
DEBUG = True




def ppjson(js):
    if DEBUG:
        print(json.dumps(js, indent=4, sort_keys=True))

def setup_caller():
    global caller
    if TTS == True:
        import pyttsx3
        engine = pyttsx3.init()
        print('>>> Your current caller: TTS-Engine')
    else:
        choose_caller()
        print(">>> Your current caller: " + str(caller))


def choose_caller():
    global caller

    if RANDOM_CALLER == False:
        caller = AUDIO_MEDIA_PATH
    else:
        callerSubDirs = os.listdir(AUDIO_MEDIA_PATH)
        if len(callerSubDirs) == 0:
            print('WARNING: You chose "RANDOM_CALLER", but there are no subfolders that identify your caller-media-files. Please correct this. Fallback to caller-media-files in Media-main-directory.\r\n')
            caller = AUDIO_MEDIA_PATH
        else:
            caller = AUDIO_MEDIA_PATH + random.choice([ name for name in callerSubDirs if os.path.isdir(os.path.join(AUDIO_MEDIA_PATH, name)) ])


def play_sound_effect(fileName):
    global caller

    if TTS == True:
        engine.say(fileName)
        engine.runAndWait()
        return

    if osType != 'Linux' and osType != 'Osx' and osType != 'Windows': 
        print('Can not play sound for OS: ' + osType + " . Please contact developer for support") 
        return

    fileToPlay = caller + '/' + fileName 

    if path.isfile(fileToPlay + '.wav'):
        if osType == 'Linux' or osType == 'Osx':
            from pygame import mixer
            mixer.init()
            mixer.music.load(fileToPlay + '.wav')
            mixer.music.play()
        elif osType == 'Windows':
            import winsound
            winsound.PlaySound(fileToPlay + '.wav', winsound.SND_ASYNC | winsound.SND_NODEFAULT)

    elif path.isfile(fileToPlay + '.mp3'):
        if osType == 'Linux' or osType == 'Osx':
            from pygame import mixer
            mixer.init()
            mixer.music.load(fileToPlay + '.mp3')
            mixer.music.play()
        elif osType == 'Windows':
            from pygame import mixer
            mixer.init()
            mixer.music.load(fileToPlay + '.mp3')
            mixer.music.play()

    else:
        print('XXX Could not find a playable sound-file for: ' + fileName)

def listen_to_newest_match(m, ws):
    global currentMatch

    # look for newest supported match that match my board-id and take it as ongoing match
    newMatch = None
    if m['variant'] in SUPPORTED_GAME_VARIANTS and m['finished'] == False:
        for p in m['players']:
            if p['boardId'] == AUTODART_USER_BOARD_ID:
                newMatch = m['id']   
                break

    if currentMatch == None or (currentMatch != None and newMatch != None and currentMatch != newMatch):
        print('\r\n>>> Listen to match: ' + newMatch)

        if currentMatch != None:
            paramsUnsubscribeMatchEvents = {
                "type": "unsubscribe",
                "channel": "autodarts.matches",
                "topic": str(currentMatch) + ".state"
            }
            ws.send(json.dumps(paramsUnsubscribeMatchEvents))

        paramsSubscribeMatchEvents = {
            "type": "subscribe",
            "channel": "autodarts.matches",
            "topic": newMatch + ".state"
        }
        ws.send(json.dumps(paramsSubscribeMatchEvents))
        currentMatch = newMatch

  

def process_match_x01(m):
    players = m['players'][0]
    turns = m['turns'][0]
    currentPlayer = m['players'][turns['player']]['index']
    # print(currentPlayer)

    # Check for game start 
    if players['boardStatus'] != 'Takeout in progress' and m['stats'][0]['average'] == 0:
        play_sound_effect('gameon')
        print('>>> Match: Leg started')

    # Check for game end
    elif m['winner'] != -1:
        play_sound_effect('gameshot')
        setup_caller()
        print('>>> Match: Gameshot and match')

    # Check for leg end
    elif m['gameWinner'] != -1:
        play_sound_effect('gameshot')
        if RANDOM_CALLER_EACH_LEG:
            setup_caller()
        print('>>> Match: Gameshot and match')
    
    # Check for busted turn
    elif players['boardStatus'] != 'Takeout in progress' and turns['busted'] == True:
        play_sound_effect('busted')
        print('>>> Match: Busted')

    # Check for possible checkout
    elif m['player'] == currentPlayer and m['gameScores'][0] <= 170 and turns != None and turns['throws'] == None:
        play_sound_effect(str(m['gameScores'][currentPlayer]))
        print('>>> Match: Checkout possible')

    # Check for points call
    elif players['boardStatus'] != 'Takeout in progress' and turns != None and turns['throws'] != None and len(turns['throws']) == 3:
        play_sound_effect(str(turns['points']))
        print(">>> Match: Turn ended")

def process_match_cricket(m):
    players = m['players'][0]
    turns = m['turns'][0]

    # TODO: implement logic





if __name__ == "__main__":

    ap = argparse.ArgumentParser()
    ap.add_argument("-U", "--autodarts_email", required=True, help="Registered email address at " + AUTODART_URL)
    ap.add_argument("-P", "--autodarts_password", required=True, help="Registered password address at " + AUTODART_URL)
    ap.add_argument("-B", "--autodarts_board_id", required=True, help="Registered board-id at " + AUTODART_URL)
    ap.add_argument("-M", "--media_path", required=True, help="Absolute path to your media folder. You can download free sounds at https://freesound.org/")
    ap.add_argument("-R", "--random_caller", type=int, choices=range(0, 2), default=0, required=False, help="If '1', the application will randomly choose a caller each game. It only works when your base-media-folder has subfolders with its files")
    ap.add_argument("-L", "--random_caller_each_leg", type=int, choices=range(0, 2), default=0, required=False, help="If '1', the application will randomly choose a caller each leg instead of each game. It only works when 'random_caller=1'")
    args = vars(ap.parse_args())

    AUTODART_USER_EMAIL = args['autodarts_email']                          
    AUTODART_USER_PASSWORD = args['autodarts_password']              
    AUTODART_USER_BOARD_ID = args['autodarts_board_id']        
    AUDIO_MEDIA_PATH = args['media_path']
    RANDOM_CALLER = args['random_caller']   
    RANDOM_CALLER_EACH_LEG = args['random_caller_each_leg']   

    TTS = False     

    osType = platform.system()
    osName = os.name
    osRelease = platform.release()
    print('\r\n')
    print('##########################################')
    print('       WELCOME TO AUTODARTS-CALLER')
    print('##########################################')
    print('VERSION: ' + VERSION)
    print('SUPPORTED GAME-VARIANTS: ' + " ".join(str(x) for x in SUPPORTED_GAME_VARIANTS) )
    print('RUNNING OS: ' + osType + ' | ' + osName + ' | ' + osRelease)
    print('\r\n')
    
    global currentMatch
    currentMatch = None

    global caller
    caller = None

    # Configure client
    keycloak_openid = KeycloakOpenID(server_url=AUTODART_AUTH_URL,
                        client_id=AUTODART_CLIENT_ID,
                        realm_name=AUTODART_REALM_NAME,
                        verify=True)

    # Get Token
    token = keycloak_openid.token(AUTODART_USER_EMAIL, AUTODART_USER_PASSWORD)
    # print(token)


    # Get Ticket
    ticket = requests.post(AUTODART_AUTH_TICKET_URL, headers={'Authorization': 'Bearer ' + token['access_token']})
    # print(ticket.text)



    rel.safe_read()

    def on_message(ws, message):
        m = json.loads(message)
        # ppjson(m)

        if m['channel'] == 'autodarts.matches':

            global currentMatch
            data = m['data']
            listen_to_newest_match(data, ws)
            
            if currentMatch != None and data['id'] == currentMatch:
                if data['variant'] == 'X01':
                    # ppjson(data)
                    process_match_x01(data)
                elif data['variant'] == 'Cricket':
                    process_match_cricket(data)


    def on_error(ws, error):
        print(error)

    def on_close(ws, close_status_code, close_msg):
        print("### Websocket closed ###")
        print("### " + close_msg + "###")
        print("### " + close_status_code + "###")

    def on_open(ws):
        caller = setup_caller()

        print('>>> Receiving live information from ' + AUTODART_URL)

        paramsSubscribeMatchesEvents = {
            "channel": "autodarts.matches",
            "type": "subscribe",
            "topic": "*.state"
        }
        ws.send(json.dumps(paramsSubscribeMatchesEvents))

        



    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(AUTODART_WEBSOCKET_URL + ticket.text,
                            on_open=on_open,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)


    ws.run_forever(dispatcher=rel)  # Set dispatcher to automatic reconnection
    rel.signal(2, rel.abort)        # Keyboard interrupt
    rel.dispatch()
   
