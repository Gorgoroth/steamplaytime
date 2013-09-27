import re
import logging
import math
import json
import urllib2
import counters
import config
import os
import users
import random
import sys
from bs3.BeautifulSoup import BeautifulSoup
from datastore.models import *
from datetime import datetime, timedelta
from random import choice
from google.appengine.api import mail
from google.appengine.api import datastore_errors
from google.appengine.api import users as appengine_users
from config import *


ID_RE = r'http://steamcommunity.com/openid/id/([0-9]+)'
def get_steam_id(federated_identity):
    """Used to extract a SteamID from the OpenID identifier"""
    steam_id = re.search(ID_RE, federated_identity)
    if steam_id:
        return steam_id.group(1)
    else:
        return None


provider = "http://steamcommunity.com/openid"
log_in_url = '<a href="%s"><img src="/images/sits_small.png" alt="Sign in through Steam"></a>' % appengine_users.create_login_url(federated_identity=provider)
log_out_url = '<a href="%s">Log Out</a>' % appengine_users.create_logout_url("/")

def confirm_user(user):
    if user is None:
        return (None, log_in_url, False)
    else:
        steam_id = get_steam_id(user.nickname())
        if os.environ.get('SERVER_SOFTWARE','').startswith('Development'):
            steam_id = "76561197990319574" # SenseiJinx
            # steam_id = "76561198077101159" # Naiyt
        if steam_id:
            user, log_url, private = get_registered_user(steam_id, True)
            return user, log_url, private


# Checks to see if we have a registered user with that name
def get_registered_user(steam_id, add_if_none=False):
    user = RegUsers.get_by_id(steam_id)
    if user:
        return user, log_out_url, False
    else:
        # The next few lines try and confirm if the user was logged in (only possible if a correct
        # steamid was passed in).
        stats = retrieve_stats()
        flat_steam_id = get_user(steam_id)
        if flat_steam_id and add_if_none:
            new_user = add_user(flat_steam_id, stats)
            return new_user, log_out_url, False
        else:
            flat_steam_id, rc = users.get_user(steam_id, stats)
            if flat_steam_id and add_if_none:
                new_user = add_user(flat_steam_id, stats)
                return new_user, log_out_url, False
            else:
                return None, log_in_url, True


def save_data(post_data):
    reg_user, throw_away, throw_away2 = get_registered_user(post_data['steam_id'])
    if reg_user:
        if reg_user.curr_session != post_data['s']:
            return False, 'Bad session data'
        else:
            #game_info = json.loads(reg_user.games)
            game_info = {}
            for game in post_data['beaten']:
                game_info[game['appid']] = {'user_defined': True, 'category': 'beaten'}
            for game in post_data['unbeaten']:
                game_info[game['appid']] = {'user_defined': True, 'category': 'unbeaten'}
            for game in post_data['playing']:
                game_info[game['appid']] = {'user_defined': True, 'category': 'playing'}
            for game in post_data['not_interested']:
                logging.error(game['game_name'])
                game_info[game['appid']] = {'user_defined': True, 'category': 'not_interested'}
    
            reg_user.games = json.dumps(game_info)
            reg_user.put()
    
            return True, None
    else:
        return False, 'Error finding user'


def get_secret():
    random.seed()
    return random.randrange(sys.maxint)

def sort_games(games_and_categories, games, hours_and_games, stats):
    beaten = []
    unbeaten = []
    not_interested = []
    playing = []

    for game in games:
        appid = game.appid
        game_and_cat = games_and_categories[str(appid)]
        game_and_cat['game_name'] = game.game_name
        game_and_cat['store_url'] = game.store_url
        game_and_cat['image_url'] = game.image_url
        game_and_cat['played'] = hours_and_games[appid]
        game_and_cat['appid'] = appid

        if game.main is None:
            game_and_cat['hours'] = "%.2f" % stats.average_main
        else:
            game_and_cat['hours'] = game.main

        if game_and_cat['category'] == 'beaten':
            beaten.append(game_and_cat)
        elif game_and_cat['category'] == 'unbeaten':
            unbeaten.append(game_and_cat)
        elif game_and_cat['category'] == 'not_interested':
            not_interested.append(game_and_cat)
        elif game_and_cat['category'] == 'playing':
            playing.append(game_and_cat)

    return {'beaten': beaten, 'unbeaten': unbeaten, 'not_interested': not_interested, 'playing': playing}
        

def add_user(user, stats):
    users_games = users_games_beaten(user, stats)
    users_games = json.dumps(users_games)
    new_user = RegUsers(id=user.steam_id, steam_id_obj=user.key, date_created=datetime.now(), games=users_games)
    new_user.put()
    return new_user

# Make an educated guess as to whether or not a user has beaten a game
def users_games_beaten(user, stats, games=None):

    games_list = {}
    if games is None:
        games = find_games_by_id(user.games)
    games = [x for x in games if x is not None] # Just in case an appid in their list doesn't seem to exist
    hours_and_games = dict(zip(user.games, user.hours))

    for game in games:
        played = hours_and_games[game.appid]
        new_game = {'user_defined': False}
        if game.main is None:
            game.main = stats.average_main
        if played < game.main:
            new_game['category'] = 'unbeaten'
        else:
            new_game['category'] = 'beaten'
        games_list[game.appid] = new_game

    return games_list



def remove_specials(str):
    """
    Removes everything but letters from a string. This is used to create "search names" for games
    in the datastore. This makes it easier to compare the names on HLTB with Steam, and reduces
    the number of games incorrectly reported as not existing on HTLB.

    e.g. - Chivalry: Medieval Warfare -> chivalrymedievalwarfare 

    """

    special = r'[^0-9A-Za-z]'
    str = str.lower()
    return re.sub(special, '', str)

def get_user(steam_id):
    return SteamIds.get_by_id(steam_id)

def users_games(games):
    """Given a list of game appids, returns a SteamGames object"""
    games_list = []
    for game in games:
        new_game = SteamGames.find_game_by_appid(game)
        if new_game:
            games_list.append(new_game)
    return games_list

def calc_value(games):
    """Takes a list of appids, and determines the worth of all the games"""
    price = 0.0
    for game in games:
        if game:
            price += game.price
    return price

def find_games_by_id(games):
    all_games = []
    for game in games:
        all_games.append(ndb.Key('Games_DB', str(game)))
    return ndb.get_multi(all_games)

def all_games():
    """Retrieves ALL the games! Ordered by name. Not using this currently."""
    q = Games_DB.query()
    q.order(-Games_DB.game_name)
    return q

def convert_to_utc(date, time_zone):
    """Given an integer offset, converts date to UTC for easier comparisons"""
    return date - timedelta(hours=time_zone)

def validate_format_date(date, time_zone):
    """Makes sure that a date is in the correct format"""
    curr_time = datetime.utcnow()
    try:
        date = datetime.strptime(date, "%m/%d/%Y %I %p")
        date = convert_to_utc(date, time_zone)      
        if date <= curr_time: # Don't allow dates before the current time
            return None
        elif date > curr_time + timedelta(days=14): # Don't allow dates greater
                                                         # than two weeks away
            return None
        return date
    except ValueError:
        return None

def validate_date(date):
    try:
        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        return date
    except:
        return None

def create_json(json_str):
    """Grabs a json string and returns a dictionary you can use"""
    try:
        json_obj = json.loads(json_str)
        return json_obj
    except:
        return None

def find_item(name, find_by_name=True):
    """Finds an item by either name or appidw"""
    if find_by_name:
        item = Games_DB.query(Games_DB.search_name == name)
        if item:
            return item.get()
    else:
        item = Games_DB.get_by_id(str(name))
        if item:
            return item

def retrieve_stats():
    stats = Stats.get_by_id('1')
    if stats is None:
        stats = Stats(id='1',games_last_updated=datetime.now(),hltb_last_updated=datetime.now())
        stats.put()
    return stats

def retrieve_counts():
    total_queries = counters.SimpleCounter.get_by_id(queries_counter)
    total_ids = counters.SimpleCounter.get_by_id(steamids_counter)
    if total_queries and total_ids:
        return total_queries.count, total_ids.count
    else:
        return 0, 0

def retrieve_hit_count():
    ent_keys = []
    for thing in hit_counters:
        ent_keys.append(ndb.Key(counters.SimpleCounter, thing))
    all_entities = ndb.get_multi(ent_keys)
    count = 0
    for ent in all_entities:
        try:
            count += ent.count
        except AttributeError:
            pass
    return count

def retrieve_lost():
    lost = LostIds.get_by_id('1')
    if lost is None:
        lost = LostIds(id='1')
        lost.put()
    return lost

def create_bad_id(reasons):
    """Used for specifiying bad ids when reporting"""
    bad_id = None
    if reasons[1] == 1:
        bad_id = Bad_IDS(id=reasons[0],appid=int(reasons[0]),count=1,hltb_exists=1)
    elif reasons[1] == 2:
        bad_id = Bad_IDS(id=reasons[0],appid=int(reasons[0]),count=1,nasty_numbers=1)
    elif reasons[1] == 3:
        bad_id = Bad_IDS(id=reasons[0],appid=int(reasons[0]),count=1,mp_only=1)
    elif reasons[1] == 4:
        bad_id = Bad_IDS(id=reasons[0],appid=int(reasons[0]),count=1,other_issues=1)
    bad_id.put()

def update_bad_id(reasons, bad_id):
    bad_id.count += 1
    if reasons[1] == 1:
        bad_id.hltb_exists += 1
    elif reasons[1] == 2:
        bad_id.nasty_numbers += 1
    elif reasons[1] == 3:
        bad_id.mp_only += 1
    elif reasons[1] == 4:
        bad_id.other_issues += 1
    bad_id.put()