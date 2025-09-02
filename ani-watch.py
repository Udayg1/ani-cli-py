import requests as rq
import json
import mpv
import os, sys, multiprocessing, pypresence, threading, time

PATH = os.path.expanduser("~")+"/.local/share/ani-watch/"
ANILIST_URL="https://graphql.anilist.co"
ANILIST_USER = ''
DISCORD_CLIENT = '1408296956266025022'
CLIENT_ID = "28320"
TOKEN = ""
HEADER = {"user-agent":"Mozilla/5.0 Firefox/141.0", "referer":"https://allmanga.to"}
URL = "https://api.allanime.day/api"
OUT = multiprocessing.Manager().dict()
RPC = pypresence.Presence(DISCORD_CLIENT)
ENCRYPTED_SOURCES = ['Default','S-mp4']
SOURCES = ['Mp4']

def mkdir():
    os.system(f"mkdir -p {PATH}")
    os.system(f"touch {PATH+'info.txt'}")
    os.system(f'touch {PATH+'token.txt'}')

def search_anime(query):
    query = "+".join(query.strip().split())
    payload = {"variables":f'{{"search":{{"allowAdult":false,"allowUnknown":false,"query":"{query}"}},"limit":40,"page":1,"translationType":"sub","countryOrigin":"ALL"}}', "query":"query( $search: SearchInput $limit: Int $page: Int $translationType: VaildTranslationTypeEnumType $countryOrigin: VaildCountryOriginEnumType ) { shows( search: $search limit: $limit page: $page translationType: $translationType countryOrigin: $countryOrigin ) { edges { _id name availableEpisodes __typename } } }"}
    r = rq.get(URL, headers = HEADER, params=payload)
    return r.json()

def get_last_ep(_data, _id):
    for i in range(0, len(_data['data']['MediaListCollection']['lists'][0]['entries'])):
        if _data['data']['MediaListCollection']['lists'][0]['entries'][i]['mediaId'] == _id:
            return int(_data['data']['MediaListCollection']['lists'][0]['entries'][i]['progress'])

def getEpsWhenComplete(_data,anime_id):
    for i in range(0, len(_data['data']['MediaListCollection']['lists'][0]['entries'])):
        if _data['data']['MediaListCollection']['lists'][0]['entries'][i]['mediaId'] == anime_id:
            return int(_data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['episodes'])

def get_user_id():
    head = {'Authorization': f'Bearer {TOKEN}'}
    data = {"query" : '''query {
  Viewer {
    id
  }
}'''}
    r = rq.post(ANILIST_URL, headers = head, json = data)
    global ANILIST_USER
    ANILIST_USER = r.json()['data']['Viewer']['id']
    # return r.json()['data']['Viewer']['id']

def modify_data(_data, anime_id, last):
    entry_id = 0
    for i in range(len(_data['data']['MediaListCollection']['lists'][0]['entries'])):
        if _data['data']['MediaListCollection']['lists'][0]['entries'][i]['mediaId'] == anime_id:
            entry_id = _data['data']['MediaListCollection']['lists'][0]['entries'][i]['id']
    print(f"-> Updating progess to {last}\n")
    status = 'CURRENT'
    out = 1
    total = getEpsWhenComplete(_data,anime_id)
    if last >= total:
        last = total
        status = 'COMPLETED'
        out = 0
        score = input("Anime completed. Enter score: ")
        while not score.isdigit() and not 0 <= float(score) <= 10:
            score = input("Enter a valid digit: ")
        data = {"query": """mutation SaveMediaListEntry($saveMediaListEntryId: Int, $progress: Int, $mediaId: Int, $status: MediaListStatus, $score: Float) {
  SaveMediaListEntry(id: $saveMediaListEntryId, progress: $progress, mediaId: $mediaId, status: $status, score: $score) {
    id
    status
        }
}""", "variables":  {"listEntryId" : f"{entry_id}", 'mediaId':f'{anime_id}', 'status' : f"{status}", 'progress': f'{last}', "score": f"{float(score)}"}}
    else:
        data = {"query" : """mutation ($listEntryId: Int, $mediaId: Int, $status: MediaListStatus, $progress: Int) {
    SaveMediaListEntry(id: $listEntryId, mediaId: $mediaId, status: $status, progress: $progress) {
        id
        status
    }
    }""" , "variables": {"listEntryId" : f"{entry_id}", 'mediaId':f'{anime_id}', 'status' : f"{status}", 'progress': f'{last}'}}
    
    head = {'Authorization': f'Bearer {TOKEN}'}
    r = rq.post(ANILIST_URL, json=data, headers = head)
    return out

def get_anilist_user_data():
    if not ANILIST_USER:
        get_user_id()
    head = {'Authorization': f'Bearer {TOKEN}'}
    data = {"query": '''
query Media($userId: Int, $type: MediaType, $status: MediaListStatus) {
  MediaListCollection(userId: $userId, type: $type, status: $status) {
    lists {
      entries {
        progress
        mediaId
        media {
          episodes
          nextAiringEpisode {
            episode
          }
          title {
            english
          }
          synonyms
        }
        id
      }
    }
  }
}''', "variables" : {"userId": f"{ANILIST_USER}", "type":"ANIME", "status":"CURRENT"}}
    r = rq.post(ANILIST_URL, headers = head, json = data)
    return r.json()


def auth_token_write():
    print("Open this url in browser: ")
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=token"
    print(auth_url)
    print("Auth token here -> ")
    global TOKEN
    TOKEN = input().strip()
    with open(PATH+'token.txt', 'a') as f:
        f.write(TOKEN)

def auth_token_read():
    with open(PATH+"token.txt", 'r') as f:
        global TOKEN
        TOKEN= f.read().strip()
        if not TOKEN:
            auth_token_write()

def get_id_from_file():
    with open(PATH+"info.txt", "r") as f:
        data = f.read()
        # print(data)
        if data:
            return json.loads(data)
        return {}

def update_idfile(file_data):
    with open(PATH+'info.txt', "w") as f:
        f.write(json.dumps(file_data))

def get_url(data):
    payload = {"variables":f'{{"showId":"{data[0]}","translationType":"sub","episodeString":"{data[1]}"}}', "query": """query ($showId: String!, $translationType: VaildTranslationTypeEnumType!, $episodeString: String!) { episode( showId: $showId translationType: $translationType episodeString: $episodeString ) { episodeString sourceUrls }}"""}
    r = rq.get(URL, headers = HEADER, params=payload)
    return r.json()

def get_streamurl(link):
    r = rq.get(f"https://allanime.day{link}", headers = HEADER)
    link = dict(r.json().get('links', None)[0]).get('link', None)
    if link is not None and link.endswith("master.m3u8"):
        nr = rq.get(link, headers = HEADER)
        link = nr.text.split()[2].split('/')[:-1]
        link.pop(2)
        link = '/'.join(link)
    # print(link)
    return link

def decode_link(source):
    hex_map = {
        '79': 'A', '7a': 'B', '7b': 'C', '7c': 'D', '7d': 'E', '7e': 'F', '7f': 'G',
        '70': 'H', '71': 'I', '72': 'J', '73': 'K', '74': 'L', '75': 'M', '76': 'N', '77': 'O',
        '68': 'P', '69': 'Q', '6a': 'R', '6b': 'S', '6c': 'T', '6d': 'U', '6e': 'V', '6f': 'W',
        '60': 'X', '61': 'Y', '62': 'Z',
        '59': 'a', '5a': 'b', '5b': 'c', '5c': 'd', '5d': 'e', '5e': 'f', '5f': 'g',
        '50': 'h', '51': 'i', '52': 'j', '53': 'k', '54': 'l', '55': 'm', '56': 'n', '57': 'o',
        '48': 'p', '49': 'q', '4a': 'r', '4b': 's', '4c': 't', '4d': 'u', '4e': 'v', '4f': 'w',
        '40': 'x', '41': 'y', '42': 'z',
        '08': '0', '09': '1', '0a': '2', '0b': '3', '0c': '4', '0d': '5', '0e': '6', '0f': '7',
        '00': '8', '01': '9',
        '15': '-', '16': '.', '67': '_', '46': '~', '02': ':', '17': '/', '07': '?', '1b': '#',
        '63': '[', '65': ']', '78': '@', '19': '!', '1c': '$', '1e': '&', '10': '(', '11': ')',
        '12': '*', '13': '+', '14': ',', '03': ';', '05': '=', '1d': '%',
    }
    source = source[2:]
    decoded = []
    for i in range(0,len(source), 2):
        decoded.append(hex_map.get(source[i:i+2] , ''))
    return "clock.json".join("".join(decoded).strip().split('clock'))

def get_real_link(links):
    decoded_links = []
    for i in range(len(links['data']['episode']['sourceUrls'])):
        real_final_link = []
        if links['data']['episode']['sourceUrls'][i]['sourceName'] == 'Yt-mp4':
            real_final_link = [decode_link(links['data']['episode']['sourceUrls'][i]['sourceUrl']),9]
        elif links['data']['episode']['sourceUrls'][i]['sourceName'] in ENCRYPTED_SOURCES:
            real_final_link = [get_streamurl(decode_link(links['data']['episode']['sourceUrls'][i]['sourceUrl'])), links['data']['episode']['sourceUrls'][i]['priority']]
        elif links['data']['episode']['sourceUrls'][i]['sourceName'] in SOURCES:
            real_final_link = [links['data']['episode']['sourceUrls'][i]['sourceUrl'],links['data']['episode']['sourceUrls'][i]['priority']]
        if len(real_final_link) == 2 and real_final_link[0] is not None:
            decoded_links.append(real_final_link)
    return sorted(decoded_links, key=lambda x: x[1], reverse = True)


def mpv_player(link,title):
    player = mpv.MPV(ytdl=True,input_default_bindings=True, input_vo_keyboard=True,osc=True,http_header_fields='Referer: https://allmanga.to/',hwdec='vaapi', title=title)
    player.play(link)
    player.wait_until_playing()
    global OUT
    OUT['dur'] = player.duration
    @player.property_observer('time-pos')
    def get_time(_name,value):
        if value:
            OUT['time'] = value
    player.wait_for_playback()

def discord_connector(thread_exitflag,lock):
    global RPC
    with lock:
        while not thread_exitflag.is_set():
            try:
                # print(len(list(RPC)))
                RPC.connect()
                break
            except:
                time.sleep(1)

def discord_updator(thread_exitflag, lock, message):
    global RPC
    with lock:
        RPC.update(state = message)

def main():
    connected = False
    thread_exitflag = threading.Event()
    preloaded_link = ''
    last_option = ''
    lock = threading.Lock()
    epAvailableForlast = False
    cached = False
    while True:
        thread_exitflag.clear()
        valid = []
        discord_thread = threading.Thread(target = discord_connector, args = (thread_exitflag,lock, ))
        discord_thread.start()
        data = get_anilist_user_data()
        if not epAvailableForlast:
            preloaded_link = ''
            cached = False
            print()
            ep_behind = 0
            anilist_entries = len(data['data']['MediaListCollection']['lists'][0]['entries'])
            if not anilist_entries:
                print("No anime entry found in the anilist account. Please add some before proceeding.")
                if discord_thread.is_alive():
                    thread_exitflag.set()
                sys.exit()
            for i in range(0, anilist_entries):
                prog = data['data']['MediaListCollection']['lists'][0]['entries'][i]['progress']
                if not data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['nextAiringEpisode']:
                    total_ep = data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['episodes']
                else:
                    total_ep = int(data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['nextAiringEpisode']['episode']) - 1
                ep_behind = int(total_ep) - int(prog)
                if ep_behind:
                    if ep_behind > 1:
                        print(str(i+1)+'.', f'\033[32m{data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english']}', f'**({ep_behind} episodes behind)\033[0m')
                    else:
                        print(str(i+1)+'.', f"\033[32m{data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english']}", f'**({ep_behind} episode behind)\033[0m')
                else:
                    print(str(i+1)+'.', data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english'])
                valid.append(str(i))
            valid.append(str(anilist_entries))
            print("\nEnter anime number (0 - exit): ")
            query = input(">>> ")
            while query not in valid:
                query = input(">>> ")
            if int(query) == 0:
                if discord_thread.is_alive():
                    thread_exitflag.set()
                sys.exit()
            last_option = query
            query = int(query) -1
            print()
        else:
            query = int(last_option) - 1
        file_write_flag = False
        file_data = get_id_from_file()
        shows = file_data.get(str(data['data']['MediaListCollection']['lists'][0]['entries'][query]['mediaId']), "")
        # print()
        if not shows:
            shows = search_anime(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english'])["data"]["shows"]["edges"]
            file_write_flag = True
        if not shows:
            shows = search_anime(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['synonyms'][0])["data"]["shows"]["edges"]
            file_write_flag = True
        if not shows:
            # print(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['synonyms'])
            print("-> No result found for the query.")
        else:
            if file_write_flag:
                for i in range(len(shows)):
                    print(str(i+1)+".", shows[i]["name"], "(Episodes:", str(shows[i]['availableEpisodes']["sub"])+')')
                if len(shows) == 1:
                    print("Enter 1 to play, 0 - exit")
                else:
                    print(f"Enter (1-{len(shows)}, 0 - exit)")
                valid = [str(x) for x in range(0,len(shows)+1)]
                choice = input(">>> ").strip()
                while choice not in valid:
                    choice = input(">>> ").strip()
                if choice == "0":
                    if discord_thread.is_alive():
                        thread_exitflag.is_set()
                    sys.exit()
                choice = shows[int(choice)-1]
            else:
                choice = {}
                choice['_id'] = shows
            last = get_last_ep(data,data['data']['MediaListCollection']['lists'][0]['entries'][query]['mediaId'])
            if file_write_flag:
                file_data[data['data']['MediaListCollection']['lists'][0]['entries'][query]['mediaId']] = choice['_id']
                update_idfile(file_data)
            # print(choice['availableEpisodes']['sub'])
            total_ep = data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['nextAiringEpisode']
            if not total_ep:
                total_ep = int(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['episodes'])
            else:
                total_ep = int(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['nextAiringEpisode']['episode'])-1
            if last < total_ep:
                if not cached:
                    link = get_url([choice["_id"], last+1])
                else : 
                    link = preloaded_link
                    print("==> Using prefetched episode link.")
                    preloaded_link = ''
                    cached = False
                    # link = get_url([choice["_id"], last+1])
                # print(link)
                if not link['data']['episode']:
                    print("==> Episode released but no source available.", flush=True)
                else:
                    final_link = get_real_link(link)
                    # print(final_link)
                    if not final_link:
                        print("==> Episode released but no source available.", flush=True)
                    else:
                        link = ''
                        # play_link = get_streamurl(final_link[0][0])
                        print(f'-> Playing Episode {last+1}')
                        thr = multiprocessing.Process(target = mpv_player, args = (final_link[0][0], f'{data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} - Episode {last+1}',))
                        thr.start()
                        if not discord_thread.is_alive():
                            discord_updator(thread_exitflag, lock, f'Watching {data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} -- Episode {last+1}')
                        if last +1 < total_ep:
                            preloaded_link = get_url([choice["_id"], last+2])
                            cached = True
                        thr.join()
                        thr.terminate()
                        if OUT['time']/OUT['dur'] >= 0.9:
                            result = modify_data(data,data['data']['MediaListCollection']['lists'][0]['entries'][query]['mediaId'],last +1)
                            if not result:
                                epAvailableForlast = False
                            elif last +1 < total_ep:
                                epAvailableForlast = True
                            else:
                                epAvailableForlast = False
                                print("-> No new episodes available.")
                        else:
                            epAvailableForlast = False
                            print('-> Skipping to update the episode.')
            else:
                epAvailableForlast = False
                print("-> No new episodes available.")

        if not discord_thread.is_alive():
            RPC.close()
        else:
            thread_exitflag.set()

auth_token_read()
try:
    main()
except KeyboardInterrupt:
    pass
