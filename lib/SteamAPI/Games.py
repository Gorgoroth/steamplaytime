"""
Hm....this is an old, crappy version for getting game details from the Steam store that I wrote.
The version in lib/games and steamgames.py is much better. 
Not sure why this is still here. Will need to check if I'm still using this somewhere.
I may be using a method or two from here somewhere.

"""

import json
import re
import math
import logging
from time import sleep
from SteamBase import SteamAPI
from bs3.BeautifulSoup import BeautifulSoup

class BadGame(Exception):
	"""Raised if info is called on a game that doesn't exist"""
	pass

class Games(SteamAPI):
	"""
	Usage: all_games = Retrieve_Games.get_games()
	Creates a 'Games' object that includes all games currently
	in the store.			

	"""

	def __init__(self):
		"""The Store list does not require an API key or SteamID"""
		self.store_url = "http://api.steampowered.com/ISteamApps/GetAppList/v2" 
		self.sleep_time = 1.5 # Time to sleep between requests to Steam. Steam gets grouchy when you
							  # hit them too many times. Wouldn't have to do it so much if they had
							  # a better API...

		# Packs are category 996, games are category 998
		packs = "996"
		packs_url = "sub"
		games = "998"
		games_url = "app"
		
		#packs_dict = self._get_games(packs, packs_url)
		#games_dict = self._get_games(games, games_url)

		#self.games = dict(packs_dict.items() + games_dict.items())


	def get_games_from(self, url, url_property):
		url_info = self._open_url(url)
	
		all_games = []
		if url_info is not None:
			soup = BeautifulSoup(url_info)
			# Finds all of the sections containing game info
			games = soup.findAll("a", "search_result_row")
			appid_re = r"http://store.steampowered.com/%s/([0-9]*).*" % url_property
			
			for game in games:
				price = 0
				# If the price is in "<strike>" tags, it's on sale, and we have to get it with another method
				price_text = game.find('div', {'class': 'col search_price'})
				sale = price_text.find('strike')
	
				name = game.find("h4").text
				if name:
					formatted_game = name.replace("&reg;", '') # Replace the (R) symbol
					formatted_game = formatted_game.replace('&trade;', '') # Replace the (TM) symbol
				else:
					name = ""
	
				if sale:
					try:
						price = float(sale.text[5:])
					except ValueError:
						price = 0.00
				else:
					try:
						price = float(price_text.text[5:])
					except ValueError:
						price = 0.00
					
				appid = re.search(appid_re, game['href'])
				if appid:
				    appid = appid.group(1)
				try:
					appid = int(appid)
				except:
					appid = -1
	
				store_url = "http://store.steampowered.com/%s/%s" % (url_property, appid)
	
				#logging.error("appid: %s store: %s" % (appid, store_url))
	
				image_url = self._image_url(appid, url_property)
	
				current_game = {'name': formatted_game, 'appid': appid, 'price': price, 'store_url': store_url, 'image_url': image_url}
				all_games.append(current_game)
			return all_games
		else:
			return None
			

	def _store_url(self, appid):
		return "http://store.steampowered.com/app/%s" % appid

	def _image_url(self, appid, url_property):
		if url_property == "sub":
			return "http://cdn2.steampowered.com/v/gfx/subs/%s/header_292x136.jpg" % appid
		else:
			return "http://cdn.steampowered.com/v/gfx/apps/%s/header_292x136.jpg" % appid

	def get_all(self):
		"""Return all info about Steam games"""
		return self.games

	def get_names(self):
		"""Return just the names of all Steam games"""
		return self.games.keys()

	def get_ids(self):
		all_ids = []
		for game in self.games:
			all_ids.append(self.games[game]['appid'])	
		return all_ids

	def get_id(self, game_name):
		if game_name not in self.games:
			raise BadGame("%s does not exist in the Steam Store." % game_name)
		else:
			return self.games[game_name]['appid']

	def get_game_info(self, game_name):
		"""Given a game name, return the games store url, image url, and appid"""
		if game_name not in self.games:
			raise BadGame("%s does not exist in the Steam Store." % game_name)
		else:
			return self.games[game_name]

	def get_store_url(self, game_name):
		"""Given a game, return its store url"""
		if game_name not in self.games:
			raise BadGame("%s does not exist in the Steam Store." % game_name)
		else:
			return self.games[game_name]['store_url']

	def get_image_url(self, game_name):
		"""Given a game, return it's image url"""
		if game_name not in self.games:
			raise BadGame("%s does not exist in the Steam Store." % game_name)
		else:
			return self.games[game_name]['image_url']