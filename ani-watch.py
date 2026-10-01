import json
import multiprocessing
import os
import re
import tempfile
import threading
import time
from urllib.parse import urljoin

import mpv
import pypresence
import requests

rq = requests.session()


def get_cookie():
    r = rq.post(
        URL + "api/watch/session",
        json={"token": ""},
        headers={
            "User-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0",
            "Referer": REFR,
        },
    )
    return r.headers["Set-Cookie"].split(";")[0]


rq.max_redirects = 100
PATH = os.path.expanduser("~") + "/.local/share/ani-watch/"
ANILIST_URL = "https://graphql.anilist.co"
ANILIST_USER = ""
DISCORD_CLIENT = "1408296956266025022"
URL = "https://anichan.to/"
REFR = URL
CLIENT_ID = "28320"
TOKEN = ""
HEADER = {
    "User-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0",
    "Referer": REFR,
    "Cookie": get_cookie(),
}
FALLBACK_SOURCE = "https://anikuro.to/api/v1/sources/"
FALLBACK_MAIN = "https://anikuro.to/"
OUT = None
RPC = pypresence.Presence(DISCORD_CLIENT)


def mkdir():
    os.system(f"mkdir -p {PATH}")
    os.system(f"touch {PATH}info.txt")
    os.system(f"touch {PATH}token.txt")


def search_anime(query):
    r = rq.get(URL + "api/suggest?q=" + "%20".join(query.split()), headers=HEADER)
    data = r.json()

    results = data["results"]  # {results: [{}, {}, ...]}
    out = []
    for item in results:
        title = item["title"]  # {"title": str}
        url = str(item["id"])  # {"id": int}
        out.append({"title": title, "id": url})

    return results


def get_slug(id) -> str:
    html = rq.get(f"https://anichan.to/anime/{id}", headers=HEADER).text

    m = re.search(rf'/anime/{id}/([a-z0-9-]+?)(?:/\d+)?["\'\s]', html)
    slug = m.group(1) if m else ""
    return slug


def get_last_ep(_data, _id):
    for i in range(len(_data["data"]["MediaListCollection"]["lists"][0]["entries"])):
        if (
            _data["data"]["MediaListCollection"]["lists"][0]["entries"][i]["mediaId"]
            == _id
        ):
            return int(
                _data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                    "progress"
                ]
            )


def getEpsWhenComplete(_data, anime_id):
    for i in range(len(_data["data"]["MediaListCollection"]["lists"][0]["entries"])):
        if (
            _data["data"]["MediaListCollection"]["lists"][0]["entries"][i]["mediaId"]
            == anime_id
        ):
            if (
                _data["data"]["MediaListCollection"]["lists"][0]["entries"][i]["media"][
                    "episodes"
                ]
                is not None
            ):
                return int(
                    _data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                        "media"
                    ]["episodes"]
                )
            return None


def get_user_id():
    head = {"Authorization": f"Bearer {TOKEN}"}
    data = {
        "query": """query {
  Viewer {
    id
  }
}"""
    }
    r = rq.post(ANILIST_URL, headers=head, json=data)
    global ANILIST_USER
    ANILIST_USER = r.json()["data"]["Viewer"]["id"]


def modify_data(_data, anime_id, last):
    entry_id = 0
    for i in range(len(_data["data"]["MediaListCollection"]["lists"][0]["entries"])):
        if (
            _data["data"]["MediaListCollection"]["lists"][0]["entries"][i]["mediaId"]
            == anime_id
        ):
            entry_id = _data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                "id"
            ]
    print(f"-> Updating progess to {last}\n")
    status = "CURRENT"
    out = 1
    total = getEpsWhenComplete(_data, anime_id)
    if total is not None and last >= total:
        last = total
        status = "COMPLETED"
        out = 0
        score = input("Anime completed. Enter score: ")
        while not score.isdigit() and not 0 <= float(score) <= 10:
            score = input("Enter a valid digit: ")
        data = {
            "query": """mutation SaveMediaListEntry($saveMediaListEntryId: Int, $progress: Int, $mediaId: Int, $status: MediaListStatus, $score: Float) {
  SaveMediaListEntry(id: $saveMediaListEntryId, progress: $progress, mediaId: $mediaId, status: $status, score: $score) {
    id
    status
        }
}""",
            "variables": {
                "listEntryId": f"{entry_id}",
                "mediaId": f"{anime_id}",
                "status": f"{status}",
                "progress": f"{last}",
                "score": f"{float(score)}",
            },
        }
    else:
        data = {
            "query": """mutation ($listEntryId: Int, $mediaId: Int, $status: MediaListStatus, $progress: Int) {
    SaveMediaListEntry(id: $listEntryId, mediaId: $mediaId, status: $status, progress: $progress) {
        id
        status
    }
    }""",
            "variables": {
                "listEntryId": f"{entry_id}",
                "mediaId": f"{anime_id}",
                "status": f"{status}",
                "progress": f"{last}",
            },
        }

    head = {"Authorization": f"Bearer {TOKEN}"}
    _ = rq.post(ANILIST_URL, json=data, headers=head)
    return out


def get_anilist_user_data():
    if not ANILIST_USER:
        get_user_id()
    head = {"Authorization": f"Bearer {TOKEN}"}
    data = {
        "query": """
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
                    romaji
                  }
                }
                id
              }
            }
          }
        }""",
        "variables": {
            "userId": f"{ANILIST_USER}",
            "type": "ANIME",
            "status": "CURRENT",
        },
    }
    r = rq.post(ANILIST_URL, headers=head, json=data)
    return r.json()


def auth_token_write():
    print("Open this url in browser: ")
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=token"
    print(auth_url)
    print("Auth token here -> ")
    global TOKEN
    TOKEN = input().strip()
    with open(PATH + "token.txt", "a") as f:
        f.write(TOKEN)


def auth_token_read():
    with open(PATH + "token.txt", "r") as f:
        global TOKEN
        TOKEN = f.read().strip()
        if not TOKEN:
            auth_token_write()


def get_id_from_file():
    with open(PATH + "info.txt", "r") as f:
        data = f.read()
        if data:
            return json.loads(data)
        return {}


def update_idfile(file_data):
    with open(PATH + "info.txt", "w") as f:
        f.write(json.dumps(file_data))


def get_url(data):
    """
    index 0 has ep id and index 1 has episode number. returns response json
    """
    id = data[0]
    episode = data[1]
    numeric_id = id
    api_url = (
        URL
        + "api/watch/servers?anilistId="
        + str(numeric_id)
        + "&ep="
        + str(episode)
        + "&cagtegory=sub"
    )
    cookie = {HEADER["Cookie"].split("=")[0]: HEADER["Cookie"].split("=")[1]}
    r = rq.get(api_url, headers=HEADER, cookies=cookie)
    first_json = r.json()

    result = first_json["servers"]
    links = []

    for item in result:
        if not item.get("stream", None):
            continue
        sub_obj = item.get("subtitles")
        sub = None
        if sub_obj:
            for i in sub_obj:
                if i.get("lang", None) == "English":
                    sub = i.get("url", None)
        links.append(
            {
                "stream": item["stream"],
                "sub": sub,
                "rank": item["rank"],
            }
        )

    return sorted(links, key=lambda x: float(x["rank"]))


def select_best(playlist: str) -> dict:
    streams = []

    lines = playlist.splitlines()

    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            attrs = line.split(":", 1)[1]

            bandwidth = int(re.search(r"BANDWIDTH=(\d+)", attrs).group(1))

            resolution_match = re.search(r"RESOLUTION=(\d+x\d+)", attrs)
            resolution = resolution_match.group(1) if resolution_match else None

            url = lines[i + 1].strip()

            streams.append(
                {"bandwidth": bandwidth, "resolution": resolution, "url": url}
            )

    best = max(streams, key=lambda x: x["bandwidth"])
    return best


def make_usable_playlist(url: str) -> str:
    r = rq.get(url)
    r.raise_for_status()

    best = select_best(r.text)

    variant_url = urljoin(url, best["url"])

    host = url.split("/", maxsplit=3)
    host.pop()
    host = "/".join(host)

    r = rq.get(variant_url)
    r.raise_for_status()

    directory = os.path.join(tempfile.gettempdir(), "aniwatch")
    os.makedirs(directory, exist_ok=True)

    path = os.path.join(directory, "playlist.m3u8")

    playlist = []

    for line in r.text.splitlines():
        if line.startswith("#") or not line.strip():
            playlist.append(line)
        else:
            # make ffmpeg recognize extensionless segments
            playlist.append(host + line + "?ts")

    with open(path, "w") as f:
        f.write("\n".join(playlist))

    return path


def mpv_player(link, title, out):
    header_args = [f"{k.lower()}: {v}" for k, v in link["headers"].items()]
    formatted_headers = ",".join([f"'{h}'" for h in header_args])
    player = mpv.MPV(
        ytdl=True,
        hr_seek="yes",
        input_default_bindings=True,
        input_vo_keyboard=True,
        osc=True,
        http_header_fields=formatted_headers,
        referrer=link.get("headers", {}).get("Referer", ""),
        hwdec="vaapi",
        title=title,
        demuxer_lavf_o="protocol_whitelist=[hls,tcp,tls,file,crypto,http,https]",
        cache="yes",
        demuxer_max_bytes=500000000,
        demuxer_max_back_bytes=100000000,
    )
    player.play(link.get("url", ""))
    player.wait_until_playing()
    if link.get("sub", None):
        player.command("sub-add", link.get("sub"), "select")

    @player.property_observer("time-pos")
    def get_time(_name, value):
        if value:
            out["time"] = value

    @player.property_observer("duration")
    def get_dur(_name, value):
        if value:
            out["dur"] = player.duration

    player.wait_for_playback()


def discord_connector(thread_exitflag, lock):
    global RPC
    with lock:
        while not thread_exitflag.is_set():
            try:
                RPC.connect()
                return
            except:
                time.sleep(1)


def discord_updator(thread_exitflag, lock, message):
    global RPC
    discord_connector(thread_exitflag, lock)
    with lock:
        while not thread_exitflag.is_set():
            try:
                RPC.update(state=message)
                return
            except (pypresence.exceptions.PipeClosed, BrokenPipeError):
                discord_connector(thread_exitflag, lock)


def fallback_api(
    series_id,
    ep_num,
):
    lists = ["allanime", "animepahe", "anikoto"]
    for i in lists:
        r = rq.get(FALLBACK_SOURCE + f"{i}/{series_id}:{ep_num}")
        if r.status_code != 200:
            continue
        jsn = r.json()
        try:
            if (
                rq.get(
                    jsn["data"]["raw"]["sub"]["originalUrl"],
                    headers=jsn["data"]["raw"]["sub"]["headers"],
                ).status_code
                != 200
            ):
                continue
            return {
                "url": jsn["data"]["raw"]["sub"]["originalUrl"],
                "headers": jsn["data"]["raw"]["sub"]["headers"],
            }
        except:
            continue


def migrate_cache():
    """
    Convert old cache formats here.
    """

    # Example old format:
    # {
    #   "173533": "KskTkSCsQHiGkYgAZ"
    # }
    CACHE_VERSION = 1.11

    new_cache = {"version": CACHE_VERSION, "data": {}}
    old_cache = get_id_from_file()
    if old_cache.get("version", None) and old_cache["version"] > 1:
        return
    for key, value in old_cache.items():
        if key == "version":
            continue

        if isinstance(value, str):
            new_cache["data"][key] = {"allanime": value}

        elif isinstance(value, dict):
            new_cache["data"][key] = value

    update_idfile(new_cache)


def main():
    global OUT
    OUT = multiprocessing.Manager().dict()
    thread_exitflag = threading.Event()
    preloaded_link = ""
    last_option = ""
    lock = threading.Lock()
    discord_msgThr = None
    epAvailableForlast = False
    source = "anichan"
    cached = False
    thr = None
    migrate_cache()
    while True:
        thread_exitflag.clear()
        valid = []
        data = get_anilist_user_data()
        if not epAvailableForlast:
            preloaded_link = ""
            cached = False
            print()
            ep_behind = 0
            anilist_entries = len(
                data["data"]["MediaListCollection"]["lists"][0]["entries"]
            )
            if not anilist_entries:
                print(
                    "No anime entry found in the anilist account. Please add some before proceeding."
                )
                if discord_msgThr and discord_msgThr.is_alive():
                    thread_exitflag.set()
                return
            for i in range(anilist_entries):
                prog = data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                    "progress"
                ]
                if not data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                    "media"
                ]["nextAiringEpisode"]:
                    total_ep = data["data"]["MediaListCollection"]["lists"][0][
                        "entries"
                    ][i]["media"]["episodes"]
                else:
                    total_ep = (
                        int(
                            data["data"]["MediaListCollection"]["lists"][0]["entries"][
                                i
                            ]["media"]["nextAiringEpisode"]["episode"]
                        )
                        - 1
                    )
                ep_behind = int(total_ep) - int(prog)
                if ep_behind:
                    if ep_behind > 1:
                        print(
                            str(i + 1) + ".",
                            f"\033[32m{data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english']}",
                            f"**({ep_behind} episodes behind)\033[0m",
                        )
                    else:
                        print(
                            str(i + 1) + ".",
                            f"\033[32m{data['data']['MediaListCollection']['lists'][0]['entries'][i]['media']['title']['english']}",
                            f"**({ep_behind} episode behind)\033[0m",
                        )
                else:
                    print(
                        str(i + 1) + ".",
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][i][
                            "media"
                        ]["title"]["english"],
                    )
                valid.append(str(i))
            valid.append(str(anilist_entries))
            print("\nEnter anime number (0 - exit): ")
            query = input(">>> ")
            while query not in valid:
                query = input(">>> ")
            if int(query) == 0:
                if discord_msgThr and discord_msgThr.is_alive():
                    thread_exitflag.set()
                return
            last_option = query
            query = int(query) - 1
            print()
        else:
            query = int(last_option) - 1
        file_write_flag = False
        file_data = get_id_from_file()
        shows = file_data.get(
            str(
                data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                    "mediaId"
                ]
            ),
            {},
        ).get(source, "")
        if not shows:
            shows = search_anime(
                data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                    "media"
                ]["title"]["english"]
            )
            file_write_flag = True
        if not shows:
            shows = search_anime(
                data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                    "media"
                ]["title"]["romaji"]
            )
            file_write_flag = True
        if not shows:
            print("-> No result found for the query.")
        else:
            if file_write_flag:
                for i in range(len(shows)):
                    print(
                        str(i + 1) + ".",
                        shows[i]["title"],
                    )
                if len(shows) == 1:
                    print("Enter 1 to play, 0 - exit")
                else:
                    print(f"Enter (1-{len(shows)}, 0 - exit)")
                valid = [str(x) for x in range(len(shows) + 1)]
                choice = input(">>> ").strip()
                while choice not in valid:
                    choice = input(">>> ").strip()
                if choice == "0":
                    if discord_msgThr and discord_msgThr.is_alive():
                        thr.join()
                        thread_exitflag.set()
                    return
                choice = shows[int(choice) - 1]
            else:
                choice = {}
                choice["id"] = shows
            last = get_last_ep(
                data,
                data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                    "mediaId"
                ],
            )
            if file_write_flag:
                if file_data.get(
                    data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                        "mediaId"
                    ]
                ):
                    file_data[
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["mediaId"]
                    ][source] = choice["id"]
                else:
                    file_data[
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["mediaId"]
                    ] = {}
                    file_data[
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["mediaId"]
                    ][source] = choice["id"]
                update_idfile(file_data)
            total_ep = data["data"]["MediaListCollection"]["lists"][0]["entries"][
                query
            ]["media"]["nextAiringEpisode"]
            if not total_ep:
                total_ep = int(
                    data["data"]["MediaListCollection"]["lists"][0]["entries"][query][
                        "media"
                    ]["episodes"]
                )
            else:
                total_ep = (
                    int(
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["media"]["nextAiringEpisode"]["episode"]
                    )
                    - 1
                )
            if last < total_ep:
                if not cached:
                    # link = fallback_api(data['data']["MediaListCollection"]["lists"][0]["entries"][query]["mediaId"], last + 1)
                    link = get_url(
                        [choice["id"], last + 1]
                    )  # {stream: url, sub: url | None} sorted according to rank
                else:
                    link = preloaded_link
                    preloaded_link = ""
                    cached = False
                finLink = None
                sub = None

                if link:
                    finLink = link[0]["stream"]
                    sub = link[0]["sub"]
                if finLink:
                    print(f"-> Playing episode {last + 1}")
                    thr = multiprocessing.Process(
                        target=mpv_player,
                        args=(
                            {
                                "url": finLink,
                                "sub": sub,
                                "headers": {
                                    "Referer": URL
                                    if finLink[0][0].find("mp4upload") == -1
                                    else ""
                                },
                            },
                            f"{data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} - Episode {last + 1}",
                            OUT,
                        ),
                    )
                    thr.start()
                    discord_msgThr = threading.Thread(
                        target=discord_updator,
                        args=(
                            thread_exitflag,
                            lock,
                            f"Watching {data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} -- Episode {last + 1}",
                        ),
                    )
                    discord_msgThr.start()
                    if last + 1 < total_ep:
                        preloaded_link = get_url([choice["id"], last + 2])
                        if preloaded_link:
                            cached = True
                        else:
                            preloaded_link = fallback_api(
                                data["data"]["MediaListCollection"]["lists"][0][
                                    "entries"
                                ][query]["mediaId"],
                                last + 2,
                            )
                            if preloaded_link:
                                cached = True
                    thr.join()
                    thr.terminate()
                else:
                    print("===> Trying fallback sources")
                    link = fallback_api(
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["mediaId"],
                        last + 1,
                    )
                    if link:
                        print(f"-> Playing episode {last + 1}")
                        thr = multiprocessing.Process(
                            target=mpv_player,
                            args=(
                                link,
                                f"{data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} - Episode {last + 1}",
                                OUT,
                            ),
                        )
                        thr.start()
                        discord_msgThr = threading.Thread(
                            target=discord_updator,
                            args=(
                                thread_exitflag,
                                lock,
                                f"Watching {data['data']['MediaListCollection']['lists'][0]['entries'][query]['media']['title']['english']} -- Episode {last + 1}",
                            ),
                        )
                        discord_msgThr.start()
                        if last + 1 < total_ep:
                            preloaded_link = get_url([choice["id"], last + 2])
                            if preloaded_link:
                                cached = True
                            else:
                                preloaded_link = fallback_api(
                                    data["data"]["MediaListCollection"]["lists"][0][
                                        "entries"
                                    ][query]["mediaId"],
                                    last + 2,
                                )
                                if preloaded_link:
                                    cached = True
                        thr.join()
                        thr.terminate()
                    else:
                        print("==> Episode released but no sources available....")
                        continue
                if (
                    OUT.get("time", 0)
                    / OUT.get("dur", 10000000000000000000000000000000000000000)
                    >= 0.9
                ):
                    result = modify_data(
                        data,
                        data["data"]["MediaListCollection"]["lists"][0]["entries"][
                            query
                        ]["mediaId"],
                        last + 1,
                    )
                    if not result:
                        epAvailableForlast = False
                    elif last + 1 < total_ep:
                        epAvailableForlast = True
                    else:
                        epAvailableForlast = False
                        print("-> No new episodes available.")
                else:
                    epAvailableForlast = False
                    print("-> Skipping to update the episode.")
                if not discord_msgThr.is_alive():
                    RPC.close()
            else:
                epAvailableForlast = False
                print("-> No new episodes available.")
        if discord_msgThr and discord_msgThr.is_alive():
            thread_exitflag.set()


if __name__ == "__main__":
    mkdir()
    auth_token_read()
    try:
        main()
    except KeyboardInterrupt:
        pass
