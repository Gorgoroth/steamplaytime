import os
import webapp2
import jinja2
import time
import logging
import urllib
import json
from lib import utils
from lib import hltb
from lib import users
from lib.config import *
from google.appengine.api import users as appengine_users
from google.appengine.api import taskqueue
from google.appengine.api import mail
from datetime import datetime, timedelta
from lib import counters
from google.appengine.api import capabilities
from lib import games
from lib.datastore.models import *
import collections
import operator



jinja_environment = jinja2.Environment(autoescape=True,
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
jinja_environment.globals['len'] = len
jinja_environment.filters['tojson'] = json.dumps

class Handler(webapp2.RequestHandler):
    """Base class that handles writing and rendering (from Steve Huffman, CS 253)"""
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, ** params):
        t = jinja_environment.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))



"""
Page handlers

"""

provider = "http://steamcommunity.com/openid"
log_in_url = '<a href="%s"><img src="/images/sits_small.png" alt="Sign in through Steam"></a>' % appengine_users.create_login_url(federated_identity=provider)
log_out_url = '<a href="%s">Log Out</a>' % appengine_users.create_logout_url("/")

class MainHandler(Handler):
    def get(self):
        """
        Return codes for get_user():
        1 - New user succesfully added
        2 - User update succeeded
        3 - New user was private, not added
        4 - Current user, no need for update, sucesfully returned
        5 - Update failed - private profile
        6 - Update failed - too soon since last update
        7 - Bad Steam ID

        """

        counters.pingpong_incr(main_counter)
        steam_id = self.request.get('steamid')
        p = self.request.get('p')
        p = True if p == 'y' else False
        mp = self.request.get('mp')
        mp = True if mp == 'y' else False
        stats = utils.retrieve_stats()

        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())


        if stats.updating: # If we're performing maintanence
            self.render('updating.html', logged_in=False)

        else:
            if steam_id:
                user, rc = users.get_user(steam_id, stats)
                have_error = False
                error_msg = ""
                success_msg = ""
                if rc == 1:
                    # User succesfully returned
                    pass
                elif rc == 2:
                    # User update succeeded
                    success_msg = """
                    There was some recent updates to the Steam Database or <a href='http://howlongtobeat.com'>
                    HowLongToBeat.com</a>. We've updated %s's details to match the new info.
                    """  % user.username
                elif rc == 3:
                    # New user was private, not added
                    have_error = True
                    error_msg = "The profile for %s is private." % steam_id
                elif rc == 5:
                    # Update failed - private profile
                    success_msg = """
                    There have been some recent updates to the Steam Database or <a href='http://howlongtobeat.com'>
                    HowLongToBeat.com</a>. We've updated the counts for this Steam ID accordingly, but we noticed
                    it was changed to private since last we looked. If this is your Steam ID and you have bought any
                    new items recently and would like your counts to be accurate, please set your Steam Profile to public
                    temporarily, and then <a href="/update?steam_id=%s">update</a>.
                    """ % steam_id
                elif rc == 6:
                    # Update failed - too soon since last update
                    have_error = False
                    success_msg = "You can only update a Steam ID once per minute. Try again soon."
                elif rc == 7:
                    # Bad Steam ID
                    have_error = True
                    error_msg = "I couldn't find a Steam account with the URL or ID of %s. Please try to enter either your Steam Community ID, or the full URL to your profile. <p class='center'><a href='/'>Try again?</a></p>" % steam_id

                if have_error:
                    self.render('error.html', error_message=error_msg, user_logged_url=user_logged_url,logged_in=logged_in)

                else:
                    # Dict with info to be sent to the Jinja2 template
                    user_hour_info = {}
                    if mp:
                        # TODO - May run into some division by zero errors here for empty profiles/those that haven't played
                        # any games
                        percent_main = "%.2f" % ((user.hours_played / user.hours_needed_main) * 100)
                        percent_complete = "%.2f" % ((user.hours_played / user.hours_needed_completion) * 100)
                        days = "%.2f" % (user.hours_needed_main/24)
                        user_hour_info = {'played': "%.2f" % (user.hours_played), 'main_needed': "%.2f" % user.hours_needed_main,\
                        'completion_needed': "%.2f" % user.hours_needed_completion, 'per_main': percent_main, 'per_complete': percent_complete,'days': days}
                    else:
                        days = "%.2f" % ((user.hours_needed_main - user.needed_main_nmp)/24)
                        percent_main = "%.2f" % ((user.hours_without_mp  / (user.hours_needed_main - user.needed_main_nmp)) * 100)
                        percent_complete = "%.2f" % ((user.hours_without_mp  / (user.hours_needed_completion - user.needed_complete_nmp)) * 100)
                        user_hour_info = {'played': "%.2f" % user.hours_without_mp, 'main_needed': "%.2f" % (user.hours_needed_main - user.needed_main_nmp), 'completion_needed':\
                        "%.2f" % (user.hours_needed_main - user.needed_complete_nmp), 'per_main':percent_main, 'per_complete': percent_complete,'days': days}

                    self.render('details.html', user=user, notice=success_msg, stats=stats,
                        mp=mp,user_hour_info=user_hour_info, user_logged_url=user_logged_url,logged_in=logged_in)
    
            else:
                total_hits = utils.retrieve_hit_count()
                total_queries, total_ids = utils.retrieve_counts()
                if private:
                    self.redirect(appengine_users.create_logout_url("/?p=y"))
                self.render('index.html', total=total_hits,queries=total_queries,ids=total_ids, user_logged_url=user_logged_url,
                    logged_in=logged_in, private=p)



class UserGamesHandler(Handler):
    def get(self):

        counters.pingpong_incr(main_counter)
        stats = utils.retrieve_stats()

        if stats.updating: # If we're performing maintanence
            self.render('updating.html', logged_in=False)

        else:
            steam_id = self.request.get('steamid')
    
            reg_user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
            logged_in = (False, None) if reg_user is None or private else (True, reg_user.key.id())

            if logged_in[0] is False:
                self.redirect('/')
            else:
                user, rc = users.get_user(steam_id, stats)
        
                mp = self.request.get('mp')
                mp = True if mp == 'y' else False
                games = utils.find_games_by_id(user.games)
                games = [x for x in games if x is not None] # Just in case an appid in their list doesn't seem to exist
                
                # Filter out multiplayer only games if needed
                if mp is False:
                    games = [x for x in games if x.multiplayer_only is False]    

                # Users games and hours are kept in parallel dictionaries in the datastore
                hours_and_games = dict(zip(user.games, user.hours))

                games_and_cat = utils.sort_games(json.loads(reg_user.games), games, hours_and_games, stats)
                s = utils.get_secret()
                reg_user.curr_session = s
                reg_user.put()

                self.render('games.html',user=user,beaten=games_and_cat['beaten'],unbeaten=games_and_cat['unbeaten'],
                    not_interested=games_and_cat['not_interested'], playing=games_and_cat['playing'],
                    user_logged_url=user_logged_url,logged_in=logged_in,
                    stats=stats,mp=mp,s=s)


class SaveChangesHandler(Handler):
    def post(self):
        post_data = json.loads(self.request.body)
        saved, error = utils.save_data(post_data)
        if saved:
            self.write(json.dumps({'success': True}))
        else:
            self.write(json.dumps({'success': False, 'error': error}))
        

class UpdateHandler(Handler):
    def get(self):
        """
        Update users return codes:
        2 - Full, sucessful update
        5 - private profile, user removed
        6 - Update failed. Too soon since last update.
        8 - Huh? That user doesn't exist.

        """

        stats = utils.retrieve_stats()
        counters.pingpong_incr(update_counter)

        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())

        if stats.updating:
            self.render('updating.html', logged_in=False)
        else:
            steam_id = self.request.get('steamid')
            if steam_id:
                user, rc = users.update_user(steam_id)
                have_error = False
                error_msg = ''
                success_msg = '%s has been sucesfully updated.' % steam_id
                if rc == 2:
                    # Succesful update
                    pass
                elif rc == 5:
                    # Priavte profile
                    success_msg = """
                    This user's account is currently set to private. It has been removed from our database. If you would
                    like it re-added, set your profile to public and then enter it again.
    
                    """
                elif rc == 6:
                    # Update failed - too soon since last update
                    have_error = True
                    error_msg = "Please wait at least one minute between updates.<p><a href='/?steamid=%s'>Return</a>" % steam_id
                elif rc == 8:
                    # That user doesn't exist
                    have_error = True
                    error_msg = "%s doesn't exist in our database. Perhaps you meant to <a href='/?steamid=%s'>add it?</a>" % (steam_id, steam_id)
    
                if have_error:
                    self.render('update.html',error=error_msg,steam_id=steam_id,user_logged_url=user_logged_url,
                        logged_in=logged_in)
                else:
                    self.render('update.html',success=success_msg,user=user,steam_id=steam_id,
                        user_logged_url=user_logged_url,logged_in=logged_in)
    
            else:
                self.redirect('/')



class StatsHandler(Handler):
    def get(self):
        counters.pingpong_incr(stats_counter)
        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())

        stats = utils.retrieve_stats()
        queries, ids = utils.retrieve_counts()
        self.render('stats.html',queries=queries,ids=ids,stats=stats, user_logged_url=user_logged_url,
            logged_in=logged_in)

class AboutHandler(Handler):
    def get(self):
        counters.pingpong_incr(about_counter)
        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())

        self.render('about.html', user_logged_url=user_logged_url,logged_in=logged_in)

class UnlistedHandler(Handler):
    def get(self):
        counters.pingpong_incr(unlisted_counter)
        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())
        self.render('unlisted.html', user_logged_url=user_logged_url,logged_in=logged_in)

class GoogleHandler(Handler):
    """For the google analytics confirmation page"""
    def get(self):
        self.render('googlea179e97b99c3d427.html')


class Report(Handler):
    """Page to report inaccurate numbers"""
    def get(self):
        self.redirect('/')

    def post(self):
        counters.pingpong_incr(report_counter)
        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())

        games = self.request.get_all('a')
        games = utils.find_games_by_id(games)
        steam_id = self.request.get('id')
        games = [x for x in games if x is not None]

        self.render('report.html',games=games,steam_id=steam_id,user_logged_url=user_logged_url,logged_in=logged_in)

class Reported(Handler):
    def get(self):
        self.redirect('/')

    def post(self):
        id = self.request.get('id')
        args = self.request.arguments()
        user, user_logged_url, private = utils.confirm_user(appengine_users.get_current_user())
        logged_in = (False, None) if user is None or private else (True, user.key.id())
        reasons = {}
        for arg in args:
            if arg != 'id':
                reason = int(self.request.get(arg))
                reasons[arg] = int(self.request.get(arg))
                bad_id = Bad_IDS.get_by_id(arg)
                if bad_id is None:
                    utils.create_bad_id((arg, reason))
                else:
                    utils.update_bad_id((arg, reason), bad_id)
        self.render('reported.html',id=id,user_logged_url=user_logged_url,logged_in=logged_in)


"""
The following are a set of administrative handlers for updating games and HLTB scores
They add tasks to the taskqueue with the AdminTaskHandler

"""


class HLTBHandler(Handler):
    def get(self):
        #not_found = hltb.get_hltb() # Use for testing
        taskqueue.add(url='/admintaskhandler', params={'hltb': 'y'})
        self.response.write('Getting them there times!')

class UpdateGamesHandler(Handler):
    def get(self):
        #games.update_games() # Use for testing
        taskqueue.add(url='/admintaskhandler', params={'gamesupdate': 'y'})
        self.response.write('Updated them there games!')

class UpdateBothHandler(Handler):
    def get(self):
        taskqueue.add(url='/admintaskhandler', params={'updateall': 'y'})
        self.response.write('Updated them there both!')

class AdminTaskHandler(Handler):
    def post(self):
        games_req = self.request.get('games')
        hltb_request = self.request.get('hltb')
        games_update_req = self.request.get('gamesupdate')
        update_all = self.request.get('updateall')
        stats = utils.retrieve_stats()

        if games_req or hltb_request or games_update_req or update_all:
            stats.updating = True
            stats.put()

        if update_all:
            games.get_games()

            not_found, both_none = hltb.get_hltb()
            content = '\n'.join(not_found)
            mail_subject = "Games not found in Steam"
            mail.send_mail('nate@natecollings.com','nate@natecollings.com',mail_subject,content)    

            content = '\n'.join(both_none)
            mail_subject = "Games with no playtimes"
            mail.send_mail('nate@natecollings.com','nate@natecollings.com',mail_subject,content)

        if games_req:
            games.get_games()

        if hltb_request:
            not_found, both_none = hltb.get_hltb()
            stats.updating = False
            stats.put()         
            """content = '\n'.join(not_found)
            mail_subject = "Games not found in Steam"
            mail.send_mail('nate@natecollings.com','nate@natecollings.com',mail_subject,content)    

            content = '\n'.join(both_none)
            mail_subject = "Games with no playtimes"
            mail.send_mail('nate@natecollings.com','nate@natecollings.com',mail_subject,content)    
            elapsed = time.clock() - start
            logging.info("Took %s seconds to retrieve hltb" % elapsed)"""

        if games_update_req:
            games.get_games()

        new_imag = self.request.get('newimgs')
        if new_imag:
            games = Games_DB.query()
            changed_games = []
            for game in games.iter():
                appid = game.appid
                new_image_url = "http://cdn.steampowered.com/v/gfx/apps/{}/capsule_184x69.jpg".format(appid)
                game.image_url = new_image_url
                changed_games.append(game)
            ndb.put_multi(changed_games)



class TestBed(Handler):
    """
    This handler is used to test various features, or debugging or whatnot.
    Admin login required.

    """
    def get(self):
        taskqueue.add(url='/admintaskhandler', params={'newimgs': 'y'})
        self.write("Done")



class UpdateStatsCron(Handler):
    """
    Thanks to http://blog.yjl.im/2011/02/simple-counter-for-google-app-engine.html
    for this method. Called in a cron that runs every 10 minutes to save the current
    counts in memcache to the datastore.

    """

    def update_counter(self, key_name):
        # Checking memcache
        count = counters.pingpong_get(key_name, from_ping=False)
        if not count:
          return    
        counter = counters.SimpleCounter.get_by_id(key_name)
        if not counter:
          counter = counters.SimpleCounter(id=key_name, name=key_name, count=count)
        else:
          counter.count += count
        counter.put()
        counters.pingpong_delete(key_name)

    def get(self):

      if capabilities.CapabilitySet('datastore_v3', capabilities=['write']).is_enabled() \
          and capabilities.CapabilitySet('memcache').is_enabled():
        self.update_counter(main_counter)
        self.update_counter(stats_counter)
        self.update_counter(unlisted_counter)
        self.update_counter(queries_counter)
        self.update_counter(steamids_counter)
        self.update_counter(report_counter)


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/games/?', UserGamesHandler),
    ('/savechanges/?', SaveChangesHandler),
    ('/update/?', UpdateHandler),
    ('/gamesupdate/?', UpdateGamesHandler),
    ('/updateboth/?', UpdateBothHandler),
    ('/hltb/?', HLTBHandler),
    ('/testbed/?', TestBed),
    ('/stats/?', StatsHandler),
    ('/about/?', AboutHandler),
    ('/unlistedgames', UnlistedHandler),
    ('/admintaskhandler/?', AdminTaskHandler),
    ('/stats-update', UpdateStatsCron),
    ('/report', Report),
    ('/reported', Reported),
    ('/googlea179e97b99c3d427.html', GoogleHandler),
], debug=False)