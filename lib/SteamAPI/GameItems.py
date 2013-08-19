"""
This is a leftover from a previous project that I'm not using here...anyway, retrieves
information for items from Steam (for games like Dota 2 and TF2).
"""

import json
from SteamBase import SteamAPI

class BadGameException(Exception):
	"""Raised when the game passed in is not TF2 or Dota2 (or in a bad format)"""
	pass

class BadItemException(Exception):
	"""Raised when an incorrect item is passed in"""
	pass

class GameItems(SteamAPI):
	"""
	Returns all of the current items in the TF2 or Dota2 store.
	See http://wiki.teamfortress.com/wiki/WebAPI/GetPlayerItems for more
	info on the various fields.

	We could probably use json.loads to do this a lot simpler, but I don't
	like the way it maps things out from Valve's json.

	"""

	def __init__(self, game, api_key):
		"""
		We don't need a SteamID, only an api key here.
		Pass in either 'Dota2' or 'TF2' for 'game'
		"""
		SteamAPI.__init__(self, "", api_key)
		self.game = ''
		if game == "TF2" or game == "tf2":
			self.game = "440"
		elif game == "Dota2" or game == "dota2":
			self.game = "570"
		else:
			raise BadGameException("Please enter either TF2 or Dota12")

		self.items = self._get_items()


	def _get_items(self):

		url = "http://api.steampowered.com/IEconItems_%s/GetSchema/v0001/?key=%s" % (self.game, self.api_key)
		json_data = self._get_json(url)

		all_items = {}
		for item in json_data["result"]["items"]:
			values = {}
			values['defindex'] = item.get('defindex')
			values['item_class'] = item.get('item_class')
			values['item_type_name'] = item.get('item_type_name')
			values['proper_name'] = item.get('proper_name')
			values['item_slot'] = item.get('item_slot')
			values['item_quality'] = item.get('item_quality')
			values['image_url'] = item.get('image_url')
			values['image_url_large'] = item.get('image_url_large')
			values['craft_class'] = item.get('craft_class')

			if item.get('capabilities') is not None:
				capable = item.get('capabilities')
				capabilities = {}
				capabilities['nameable'] = capable.get('nameable')
				capabilities['can_gift_wrap'] = capable.get('can_gift_wrap')
				capabilities['can_craft_mark'] = capable.get('can_craft_mark')
				capabilities['can_be_restored'] = capable.get('can_be_restored')
				capabilities['strange_parts'] = capable.get('strange_parts')
				capabilities['can_card_upgrade'] = capable.get('can_card_upgrade')
				values['capabilities'] = capabilities
			if item.get('used_by_classes') is not None:
				game_classes = []
				for character_class in item.get('used_by_classes'):
					game_classes.append(character_class)
				values['used_by_classes'] = game_classes

			all_items[item.get('name')] = values

		return all_items

	def get_all(self):
		"""Retrieve all info about all items"""
		return self.items

	def get_names(self):
		"""Return names of all items"""
		return self.items.keys()

	def get_defindex(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['defindex']

	def get_item_class(self, item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['item_class']

	def get_item_type_name(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['item_type_name']

	def get_proper_name(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['proper_name']

	def get_slot(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['item_slot']

	def get_quality(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['item_quality']

	def get_image_url(self,item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['image_url']

	def get_image_url_large(self, item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['image_url_large']

	def get_craft_class(self, item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['craft_class']

	def get_capabilities(self, item):
		if item not in self.items:
			raise BadItemException('Item %s does not exist' % item)
		return self.items[item]['capabilities']
