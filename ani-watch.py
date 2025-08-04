import requests as rq
import json
import mpv
import os, sys, multiprocessing

PATH = os.path.expanduser("~")+"/.local/share/ani-watch/"
ANILIST_URL="https://graphql.anilist.co"
ANILIST_USER = ''
CLIENT_ID = "28320"
CLIENT_SECRET = "jC9CMYQtj9iy9LoySHVc0MYbSI5N0MNVbVUrbvlW"
TOKEN = ""
HEADER = {"user-agent":"Mozilla/5.0 Firefox/141.0", "referer":"https://allmanga.to"}
URL = "https://api.allanime.day/api"
OUT = multiprocessing.Manager().dict()

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
    status = 'CURRENT'
    total = getEpsWhenComplete(_data,anime_id)
    if last >= total:
        last = total
        status = 'COMPLETED'
    print(f"-> Updating progess to {last}\n")
    entry_id = 0
    for i in range(len(_data['data']['MediaListCollection']['lists'][0]['entries'])):
        if _data['data']['MediaListCollection']['lists'][0]['entries'][i]['mediaId'] == anime_id:
            entry_id = _data['data']['MediaListCollection']['lists'][0]['entries'][i]['id']
    head = {'Authorization': f'Bearer {TOKEN}'}
    data = {"query" : """mutation ($listEntryId: Int, $mediaId: Int, $status: MediaListStatus, $progress: Int) {
  SaveMediaListEntry(id: $listEntryId, mediaId: $mediaId, status: $status, progress: $progress) {
    id
    status
  }
}""" , "variables": {"listEntryId" : f"{entry_id}", 'mediaId':f'{anime_id}', 'status' : f"{status}", 'progress': f'{last}'}}
    r = rq.post(ANILIST_URL, json=data, headers = head)

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
    # print(r.text)
    return r.json()['links'][0]['link']

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
        if links['data']['episode']['sourceUrls'][i]['sourceName'] in ['S-mp4','Default']:
            decoded_links.append([decode_link(links['data']['episode']['sourceUrls'][i]['sourceUrl']), links['data']['episode']['sourceUrls'][i]['priority']])
    return sorted(decoded_links, key=lambda x: x[1], reverse = True)


def mpv_player(link):
    player = mpv.MPV(ytdl=True,input_default_bindings=True, input_vo_keyboard=True,osc=True)
    player.play(link)
    player.wait_until_playing()
    global OUT
    OUT['dur'] = player.duration
    @player.property_observer('time-pos')
    def get_time(_name,value):
        if value:
            OUT['time'] = value
    player.wait_for_playback()

def main():
    last_option = ''
    epAvailableForlast = False
    while True:
        data = get_anilist_user_data()
        if not epAvailableForlast:
            print()
            ep_behind = 0
            for i in range(0, len(data['data']['MediaListCollection']['lists'][0]['entries'])):
                prog = data['data']['MediaListCollection']['lists'][0]['entries'][i]['progress']
                if not data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['nextAiringEpisode']:
                    total_ep = data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['episodes']
                else:
                    total_ep = int(data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['nextAiringEpisode']['episode']) - 1
                ep_behind = int(total_ep) - int(prog)
                if ep_behind:
                    if ep_behind > 1:
                        print(str(i+1)+'.', data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english'], f'**({ep_behind} episodes behind)')
                    else:
                        print(str(i+1)+'.', data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english'], f'**({ep_behind} episode behind)')
                else:
                    print(str(i+1)+'.', data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english'])
            valid = [str(x) for x in range(0, len(data['data']['MediaListCollection']['lists'][0]['entries'])+1)]
            print("\nEnter anime number (0 - exit): ")
            query = input(">>> ")
            while query not in valid:
                query = input(">>> ")
            if int(query) == 0:
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
                total_ep = int(data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['episodes'])+1
            else:
                total_ep = data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['nextAiringEpisode']['episode']
            if last < int(total_ep)-1:
                link = get_url([choice["_id"], last+1])
                print(f'-> Playing Episode {last+1}')
                # print(link)
                final_link = get_real_link(link)
                # print(final_link)
                play_link = get_streamurl(final_link)
                thr = multiprocessing.Process(target = mpv_player, args = (play_link, ))
                thr.start()
                thr.join()
                thr.terminate()
                if OUT['time']/OUT['dur'] >= 0.9:
                    modify_data(data,data['data']['MediaListCollection']['lists'][0]['entries'][query]['mediaId'],last +1)
                    if last +1 < int(total_ep)-1:
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

auth_token_read()
main()
