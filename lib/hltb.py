"""
Retrieves info from howlongtobeat.com - well, actually it retrieves what I've uploaded
most recently to a VPS of mine of the info from HLTB. The issue is the dynamically generated pages
on HLTB that make it difficult to scrape with just something like urllib2 and BeautifulSoup.
I'll perhaps try scrapy when I get a chance.

"""


import urllib2
import utils
import logging
import re
import specialcases
import utils
from config import *
from datastore.models import *
from time import sleep
from bs3.BeautifulSoup import BeautifulSoup
from google.appengine.api import urlfetch
from datetime import datetime
from decimal import Decimal


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

def open_morpheus(num):
    url = "http://74.63.212.37/hltb/%s.html" % num
    try:
        return urllib2.urlopen(url)
    except urllib2.URLError as e:
        print 'URLError = ' + str(e.reason)
    except urllib2.HTTPError as e:
        print 'HTTPError = ' + str(e.code)
        return retry(self, url, 5, 5)
    except ValueError as e:
        print 'Not a proper URL'
    except:
        return retry(url, 10, 3)

def validate_hours(hours_str):
    hours_str = hours_str.replace(u'\xbd', '.5') # Replace the unicode 1/2 with .5
    mins = False
    if "Mins" in hours_str:
        mins = True
    hours_search = re.search(r'([\d]*\.?[\d]*)', hours_str)
    if hours_search and mins:
        return float(hours_search.group(1))/60
        return round_decimal(Decimal(hours_search.group(1))/60)
    elif hours_search:
        return float(hours_search.group(1))
    else:
        return None


tidbit_re = re.compile("gamelist_tidbit.*")
def get_hltb():
    stats = utils.retrieve_stats()

    total_main_with_hours = 0
    total_main = 0.0
    total_completion_with_hours = 0
    total_with_hours = 0
    total_completion = 0.0


    num_url = urllib2.urlopen("http://74.63.212.37/hltb/num.html").read()

    file_range = range(1,int(num_url))
    for i in file_range:
    #for i in range(1,2): # Use for testing
        curr_games = []
        soup = BeautifulSoup(open_morpheus(i))
        search_results = soup.find("div", {"class": "search_results"})
        games = search_results.findAll("li", {"class": "backwhite radius shadow_box"})

        for game in games:

            title = game.find("a", {"class": "textwhite"})
            
            try:
                url = title['href']
            except KeyError:
                url = None
            title = title.text      
            main = None
            completion = None
            combined = None
            tidbits = game.findAll("div",  {'class': tidbit_re})

            if len(tidbits) > 1:
                total_with_hours += 1
                main_recorded = False
                for i in range(len(tidbits)):
                    if tidbits[i].text == "Main Story":
                        main_recorded = True
                        main = tidbits[i+1].text
                        main = validate_hours(main)
                        if main is not None:
                            total_main += main
                            total_main_with_hours += 1
                    elif tidbits[i].text == "Completionist":
                        completion = tidbits[i+1].text
                        completion = validate_hours(completion)
                        if completion is not None:
                            total_completion += completion
                            total_completion_with_hours += 1
                    elif tidbits[i].text == "Combined":
                        combined = tidbits[i+1].text
                        combined = validate_hours(combined)
                    if main_recorded is False:
                        if combined is not None:
                            main = combined

            this_game = {'title': title, 'url': url, 'main': main, 'completion': completion}
            curr_games.append(this_game)
        update_hltb(curr_games)

    average_main = total_main / total_main_with_hours
    average_completion = total_completion / total_completion_with_hours
    stats.total_with_hours = total_with_hours
    stats.average_main = average_main - 2
    stats.average_completion = average_completion - 2
    stats.hltb_last_updated = datetime.now()
    stats.put()
    return None, None


def update_hltb(games):

    to_put = []
    not_in_steam = []
    for game in games:
        title = game['title']
        title = title.lower()
        title = title.replace('amp;', '')
        title = utils.remove_specials(title)


        if title in specialcases.hltb_names:
            title = specialcases.hltb_names[title]

        curr_game = utils.find_item(title)

        if curr_game is not None:
            curr_game.hltburl = game['url']
            curr_game.main = game['main']
            curr_game.completion = game['completion']
            to_put.append(curr_game)
        else:            
            pass

    ndb.put_multi(to_put)


