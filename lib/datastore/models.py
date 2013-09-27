from google.appengine.ext import db, ndb

class Games_DB(ndb.Model):
	appid = ndb.IntegerProperty()
	game_name = ndb.StringProperty()
	image_url = ndb.StringProperty()
	store_url = ndb.StringProperty()
	price = ndb.FloatProperty()
	hltburl = ndb.StringProperty()
	main = ndb.FloatProperty()
	completion = ndb.FloatProperty()
	search_name = ndb.StringProperty()
	multiplayer_only = ndb.BooleanProperty(default=False)

class Stats(ndb.Model):
	total_steam = ndb.IntegerProperty(default = 0)
	total_with_hours = ndb.IntegerProperty(default = 0)
	average_main = ndb.FloatProperty()
	average_completion = ndb.FloatProperty()
	steam_ids = ndb.IntegerProperty(default = 0)
	number_of_queries = ndb.IntegerProperty(default = 0)
	games_last_updated = ndb.DateTimeProperty()
	hltb_last_updated = ndb.DateTimeProperty()
	updating = ndb.BooleanProperty(default=False)

class SteamIds(ndb.Model):
	steam_id = ndb.StringProperty()
	visibility = ndb.BooleanProperty()
	username = ndb.StringProperty()
	profileurl = ndb.StringProperty()
	avatar = ndb.StringProperty()
	games = ndb.IntegerProperty(repeated=True)
	last_updated = ndb.DateTimeProperty()
	steam_account_worth = ndb.FloatProperty()
	hours_played = ndb.FloatProperty()
	hours_needed_main = ndb.FloatProperty()
	hours_needed_completion = ndb.FloatProperty()
	hours = ndb.FloatProperty(repeated=True)
	hours_without_mp = ndb.FloatProperty()
	needed_main_nmp = ndb.FloatProperty()
	needed_complete_nmp = ndb.FloatProperty()

class RegUsers(ndb.Model):
	steam_id_obj = ndb.KeyProperty()
	games = ndb.TextProperty()
	date_created = ndb.DateTimeProperty()
	curr_session = ndb.IntegerProperty()

class LostIds(ndb.Model):
	appids = ndb.IntegerProperty(repeated=True)

class Counters(ndb.Model):
    """Shards for the counter"""
    query_count = ndb.IntegerProperty(default=0)
    id_count = ndb.IntegerProperty(default=0)

class Bad_IDS(ndb.Model):
	appid = ndb.IntegerProperty()
	count = ndb.IntegerProperty(default=0)
	hltb_exists = ndb.IntegerProperty(default=0)
	nasty_numbers = ndb.IntegerProperty(default=0)
	mp_only = ndb.IntegerProperty(default=0)
	other_issues = ndb.IntegerProperty(default=0)