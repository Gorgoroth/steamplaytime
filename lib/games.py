"""
Retrieves information about Steam games from the Steam API

TODO: Create an update method that just updates the games, rather then readding them.
The problem currently is that it overwrites the HLTB scores, which means I have to update
HLTB whenever I update the games. This is why the cron that updates the games once a week
puts the site in a maintanence mode while updating (otherwise people will get bad scores).

"""

import urllib2
import urllib
import utils
import logging
import re
import json
from SteamAPI.Games import *
from datastore.models import *
from SteamAPI.steamgames import Games
from time import sleep
from config import *
from bs3.BeautifulSoup import BeautifulSoup
from datetime import datetime
from google.appengine.api import urlfetch
from google.appengine.api.urlfetch_errors import DeadlineExceededError
urlfetch.set_default_fetch_deadline(60)


def retry(url, time, retries):
	"""Retries a certain number of times to open a url"""
	logging.error("%s was unreachable, retrying %s number of times" % (url, retries))
	for num in range(retries):
		try:
			return urlfetch.fetch(url)
		except:
			sleep(time)
	logging.error("Couldn't reach %s after %s number of tries. Moving to next" % (url, retries))
	return None

def open_url(url):
	try:
		return urlfetch.fetch(url)
	except DeadlineExceededError as e:
		"""Retry a certain amount of times if needed"""
		return retry(url, 10, 3)

def create_url(params):
	"""Creates a steam api url to fetch info for up to 200 appids"""
	appids = ','.join(params)
	data = {'appids': appids, 'cc': 'US', 'l': 'english', 'v': '1'}
	url_vals = urllib.urlencode(data)
	return "http://store.steampowered.com/api/appdetails/?" + url_vals

def create_store_url(appid):
	return "http://store.steampowered.com/app/%s" % str(appid)

def get_ids():
	"""Gets all current appids using the Steam API"""
	ids = []
	url = "http://api.steampowered.com/ISteamApps/GetAppList/v2"
	url_info = open_url(url)
	if url_info is not None:
		json_info = json.loads(url_info.content)
		for id in json_info['applist']['apps']:
			ids.append(str(id['appid']))
		return ids

def fetch_urls():
	"""Creates all the urls from our list of ids, broken into slices of 200"""
	amount = open_url("http://74.63.212.37/steam/amount.html")
	amount = int(amount.content)
	all_urls = []
	for num in range(amount):
		curr_url = "http://74.63.212.37/steam/%s.json" % str(num)
		all_urls.append(curr_url)
	return all_urls

def chunks(ids, number):
	"""Generator that cuts a list into chunks of 'number' size"""
	for i in xrange(0, len(ids), number):
		yield ids[i:i+number]


def get_games():
	"""Actually retrieves the games and adds them to the datastore"""
	stats = utils.retrieve_stats()
	total_games = 0

	games = Games()
	all_games = games.get_all('us')
	current_stack = []
	for game in all_games:
		if game.type == 'game':
			name = game.name.encode('ascii', 'ignore')
			store_url = create_store_url(game.appid)
			search_name = utils.remove_specials(name.lower().replace('amp;', ''))
			new_game = Games_DB(id=game.appid,appid=int(game.appid),game_name=name,image_url=game.header_image,
				store_url=store_url,price=game.price,search_name=search_name)
			if int(game.appid) not in mp_games:
				new_game.multiplayer_only = False
			else:
				new_game.multiplayer_only = True
			current_stack.append(new_game)
			if len(current_stack) > 250:
				ndb.put_multi(current_stack)
				current_stack = []

			total_games += 1

	stats.total_steam = total_games
	stats.games_last_updated = datetime.now()
	stats.put()