import utils
import logging
import json
import re
import urllib
import random
import counters
from SteamAPI.Users import *
from datastore.models import *
from datetime import datetime, timedelta
from google.appengine.api import mail
from config import *
from bs3.BeautifulSoup import BeautifulSoup
from google.appengine.api import memcache
from specialcases import *


# TODO: We should be mapping the return codes to variable names...it's nasty to return stuff like "4"

steam_re = r'[\d]{17}'
def get_user(steam_id, stats=None):
    """
    Return codes for get_user():
    1 - New user succesfully added
    2 - User update succeeded
    3 - New user was private, not added
    4 - Current user, no need for update, sucesfully returned
    5 - Update succeeded, but private profile
    6 - Update failed - too soon since last update
    7 - Bad Steam ID

    """

    # If the user inputs a URL that doesn't have the 64 bit id, then we have to retrieve that
    # with a call to Steam to see if it's valid. Since we don't always want to do that,
    # we store the "orig_id" (the full url) in memcache, mapped to the actual id if needed.
    # Cuts down on the amount of Steam API calls needed per user lookup.
    if stats is None:
        stats = utils.retrieve_stats()
    orig_id = steam_id
    id_retrieved = False
    cached_id = memcache.get(orig_id)
    if cached_id is not None:
        id_retrieved = True
        steam_id = cached_id

    if id_retrieved is False:
        steam_match = re.match(steam_re, steam_id)
        if steam_match:
            steam_id = steam_match.string
        else:
            if re.match(r'https?://steamcommunity.com/.*', steam_id):
                try:
                    profile = urllib2.urlopen(steam_id)
                except:
                    return None, 7
                soup = BeautifulSoup(profile)
                scripts = soup.findAll('script')
                found = False
                for script in scripts:
                    text = script.text.strip()
                    if text[:15] == 'g_rgProfileData':
                        json_info = json.loads(text[18:-1])
                        steam_id = json_info['steamid']
                        found = True
                if found is False:
                    return None, 7
            else:
                try:
                    profile = urllib2.urlopen("http://steamcommunity.com/id/%s" % steam_id)
                except:
                    return None, 7
    
                soup = BeautifulSoup(profile)
                scripts = soup.findAll('script')
                found = False
                for script in scripts:
                    text = script.text.strip()
                    if text[:15] == 'g_rgProfileData':
                        json_info = json.loads(text[18:-1])
                        steam_id = json_info['steamid']
                        found = True
                if found is False:
                    return None, 7
        memcache.add(orig_id, steam_id)

    user = SteamIds.get_by_id(steam_id)
    counters.pingpong_incr(queries_counter)
    # User already exists, decide what to do
    if user:
        # If this is true, there have been updates to the db. Update the user, if possible.
        if stats.games_last_updated > user.last_updated or stats.hltb_last_updated > user.last_updated:
            info_to_update = SteamUsers(steam_id, api_key)
            # User profile is invisible. Still update what we have on record, but warn the user
            # to update w/public profile.
            if info_to_update.visibility is False:
                user, rc = _update_user(user, info_to_update, stats)
                return user, rc
            #User's profile was visible, fully sucessful update.
            else:
                user, rc = _update_user(user, info_to_update, stats)
                return user, rc
        # Current user, no need for update, just return for display.
        else:
            return user, 4

    else:
        user_info = SteamUsers(steam_id, api_key)
        # This is not a Steam ID
        if user_info.good_id is False:
            return None, 7
        # This is not a public profile. Can't view.
        elif user_info.visibility is False:
            return None, 3
        # New user was succesfully added. FTW!
        else:
            user = add_user_to_ndb(user_info, stats)
            #increment_steamids()
            counters.pingpong_incr(steamids_counter)
            return user, 1


def add_user_to_ndb(user_info,stats):
    games = user_info.get_games()
    total_hours, hours_without_mp, hours = calc_hours(games)
    hours_needed_main, hours_needed_complete, game_objs, mp_main, mp_complete = calc_needed(games,stats)
    price = utils.calc_value(game_objs)
    new_steam_id = SteamIds(visibility=user_info.visibility,steam_id=user_info.get_steam(),
        username=user_info.get_username(),profileurl=user_info.get_profileurl(),avatar=user_info.get_avatar(),
        games=games.keys(),last_updated=datetime.now(),steam_account_worth=price,
        hours_played=total_hours,hours_needed_main=hours_needed_main,
        hours_needed_completion=hours_needed_complete,hours=hours,id=user_info.steam_id,hours_without_mp=hours_without_mp,
        needed_main_nmp=mp_main,needed_complete_nmp=mp_complete)
    new_steam_id.put()
    return new_steam_id


def _update_user(user, info_to_update, stats):
    if info_to_update.visibility is False:
        user.key.delete()
        return user, 5
    else:

        # This section ONLY tries to recalculate the beaten/unbeaten lists for NEW games since the last update
        # (so we don't overwrite what the user might have custom set other games as.)
        reg_user = RegUsers.get_by_id(user.steam_id)
        if reg_user:

            reg_games = json.loads(reg_user.games)
            new = [x for x in user.games if str(x) not in reg_games.keys()]
            new = utils.find_games_by_id(new)
            new = utils.users_games_beaten(user, stats, new)
            
            all_games = dict(reg_games.items() + new.items())
            reg_user.games = json.dumps(all_games)

            reg_user.put()

        games = info_to_update.get_games()
        total_hours, hours_without_mp, hours = calc_hours(games)
        hours_needed_main, hours_needed_complete, game_objs, mp_main, mp_complete = calc_needed(info_to_update.get_games(),stats)
        price = utils.calc_value(game_objs)
        user.games = games.keys()
        user.steam_account_worth = price
        user.hours_played = total_hours
        user.hours_needed_main = hours_needed_main
        user.hours_needed_complete = hours_needed_complete
        user.needed_main_nmp=mp_main
        user.needed_complete_nmp=mp_complete
        user.hours = hours
        user.hours_without_mp = hours_without_mp
        user.last_updated = datetime.now()
        user.put()


        return user, 2

def update_user(steam_id):
    """
    Update users return codes:
    2 - Full, sucessful update
    5 - Private profile, user removed
    6 - Update failed. Too soon since last update.
    8 - Huh? That user doesn't exist.

    """

    stats = utils.retrieve_stats()
    user = SteamIds.get_by_id(steam_id)
    if user:
        if user.last_updated > datetime.now() - timedelta(minutes=1):
            return user, 6
        else:
            info_to_update = SteamUsers(steam_id, api_key)
            user, rc = _update_user(user, info_to_update, stats)
            return user, rc
    else:
        return None, 8


def calc_hours(games):
    total_hours = 0.0
    hours_without_mp = 0.0
    hours = []
    for game in games:
        total_hours += games[game]['hours']
        if game not in specialcases.mp_games:
            hours_without_mp += games[game]['hours']
        hours.append(float(games[game]['hours']))
    return total_hours, hours_without_mp, hours
    
# Refactor the following two methods into one
def calc_needed_update(games,stats):
    total_need_main = 0.0
    total_need_complete = 0.0
    mp_main = 0.0
    mp_complete = 0.0
    all_games = get_game_objects(games)

    for game_info in all_games:

        if game_info is not None:
            if game_info.appid in specialcases.mp_games:
                try:
                    mp_main += game_info.main
                except:
                    mp_main += stats.average_main
                try:
                    mp_complete += game_info.complete
                except:
                    mp_complete += stats.average_completion
            if game_info.main is not None:
                total_need_main += game_info.main
            else:
                total_need_main += stats.average_completion
            if game_info.completion is not None:
                total_need_complete += game_info.completion
            else:
                total_need_complete += stats.average_completion
    return total_need_main, total_need_complete, all_games, mp_main, mp_complete


def calc_needed(games, stats):
    total_need_main = 0.0
    total_need_complete = 0.0
    mp_main = 0.0
    mp_complete = 0.0
    not_found = []
    all_games = get_game_objects(games.keys())

    for game_info in all_games:

        if game_info is not None:
            if game_info.appid in mp_games:
                try:
                    mp_main += game_info.main
                except:
                    mp_main += stats.average_main
                try:
                    mp_complete += game_info.complete
                except:
                    mp_complete += stats.average_completion
            if game_info.main is not None:
                total_need_main += game_info.main
            else:
                total_need_main += stats.average_main
            if game_info.completion is not None:
                total_need_complete += game_info.completion
            else:
                total_need_complete += stats.average_completion
    
    return total_need_main, total_need_complete, all_games, mp_main, mp_complete


def get_game_objects(games):
    all_keys = []
    for game in games:
        all_keys.append(ndb.Key('Games_DB', str(game)))
    return ndb.get_multi(all_keys)
