import praw
import pushover
from datetime import datetime, timedelta
from dateutil import tz
from time import strftime
from collections import namedtuple
import sys,os
import re
import configparser
import logging

##To-fix:
##(1) can't search one subreddit using multiple search types
##(2) change notification input into config format


#structure of reddit post
#author not mandatory
class reddit_post:
	def __init__(self,post_id,post_title,post_time,post_author=None):
		self.post_id = post_id
		self.post_title = post_title
		self.post_time = post_time
		self.post_author = post_author

	def __eq__(self,other):
		return self.post_id == other.post_id

	def __str__(self):
		return "Submission ID: {}\nSubmission Title: {}\nSubmission Time: {}".format(self.post_id,self.post_title,self.post_time.strftime('%Y-%m-%d %H:%M:%S'))

#this isn't necessary, yet
#class notification_entry:
#	def __init__(self,subreddit,search_term_list,search_type):
#		self.subreddit = subreddit
#		self.search_term_list = search_term_list
#		self.search_type = search_type
#	def __eq__(self,other):
#		return self.subreddit == other.subreddit

#converts a UTC timestamp to a readable time in PST
#not actually used at any point lol
def get_time_pst(timestamp_utc):
	from_zone = tz.gettz('UTC')
	to_zone = tz.gettz('America/Los_Angeles')
	time_utc = datetime.fromtimestamp(timestamp_utc)
	time_utc = time_utc.replace(tzinfo = from_zone)
	time_pst = time_utc.astimezone(to_zone)
	return time_pst

#converts UTC timestamp to a readable time (still in UTC)
def get_time_from_stamp(timestamp_utc):
	return datetime.fromtimestamp(timestamp_utc)

#gets parsed submissions stored in parsed_submissions.txt
#submissions must be stored as id, title, time with 3 lines per submission
#ignores author.
def read_parsed_submissions():
	parsed_submissions = []
	try:
		with open('parsed_submissions.txt') as submissions_file:
			submissions_list = submissions_file.read().splitlines()
			for i in range(0,len(submissions_list),3):
				post_id = submissions_list[i]
				post_title = submissions_list[i+1]
				post_time = datetime.strptime(submissions_list[i+2],'%Y-%m-%d %H:%M:%S')
				current_post = reddit_post(post_id=post_id,post_title=post_title,post_time=post_time)
				parsed_submissions.append(current_post)
	except OSError:
		print("No parsed submissions yet.")
		return []
	return parsed_submissions

#assumes that newly_parsed does not contain any old posts or posts in current submissions
def write_parsed_submissions(newly_parsed,parsed_submissions=None,cutoff_time=(datetime.utcnow()-timedelta(hours=6))):
	if parsed_submissions is None:
		parsed_submissions = read_parsed_submissions()
	parsed_submissions = [current_post for current_post in parsed_submissions if not current_post.post_time < cutoff_time]
	parsed_submissions.extend(newly_parsed)
	try:
		with open('parsed_submissions.txt','w') as submissions_file:
			for current_post in parsed_submissions:
				submissions_file.write("{}\n{}\n{}\n".format(current_post.post_id,current_post.post_title,current_post.post_time.strftime('%Y-%m-%d %H:%M:%S')))
	except OSError:
		print("Something went wrong while writing submissions...")

#reads reddit auth into dictionary with keys corresponding to praw values
def read_reddit_auth():
	AUTH_FILE = "auth.ini"
	config = configparser.ConfigParser()
	auth_dict = {}
	try:
		config.read(AUTH_FILE)
		auth_dict["client_id"] = config["reddit"]["client_id"]
		auth_dict["client_secret"] = config["reddit"]["client_secret"]
		auth_dict["username"] = config["reddit"]["username"]
		auth_dict["password"] = config["reddit"]["password"]
		auth_dict["user_agent"] = config["reddit"]["user_agent"]
		if None in auth_dict.values():
			raise ValueError("Some value is missing from your reddit auth.")
	except Exception:
		print("Reddit auth didn't work, check your {}".format(AUTH_FILE))
		raise
	return auth_dict

#returns new posts in /r/subreddit_name posted after cutoff_time
#requires reddit to be defined globally!
def get_reddit_posts(subreddit_name,cutoff_time=(datetime.utcnow()-timedelta(hours=6))):
	subreddit = reddit.subreddit(subreddit_name)

	parsed_submissions = read_parsed_submissions()
	newly_parsed = []

	for submission in subreddit.new(limit=NUMBER_NEW_TO_GET):
		post_time = get_time_from_stamp(submission.created) #submission.created returns timestamp in utc(!)
		post_title = submission.title
		post_id = submission.fullname
		post_author = submission.author
		current_post = reddit_post(post_id=post_id,post_title=post_title,post_time=post_time,post_author=post_author)
		if (post_time < cutoff_time or current_post in parsed_submissions): #doesn't bother parsing if submission has been parsed or if submission is too old
			continue
		else:
			newly_parsed.append(current_post)

	write_parsed_submissions(newly_parsed,parsed_submissions)

	return newly_parsed

#converts a search query into a list of bounded words
def parse_search_term(search_term):
	search_term.strip()
	search_word_list = search_term.split('+')
	result = []
	for word in search_word_list:
		result.append(r'(?<!\w)' + word + r'(?!\w)') #lookbehind and lookahead to make sure word is not surrounded by any alphanumeric characters
	return result

#given a list of regex-compatible strings, searches word and returns true if all strings are matched
#ALWAYS IGNORES CASE, even when trying to search user
def match_string(vals_to_search,word):
	for val in vals_to_search:
		pattern = re.compile(val,re.IGNORECASE)
		if pattern.search(word) is None:
			return False
	return True

#read the list of notifications that you want to get
#notifications are grouped by subreddit in 3 lines: subreddit name, what to match (not supported yet), comma-separated matches
def read_notification_settings():
	all_notifications = []
	notification_entry = namedtuple('notification_entry', ['subreddit','search_term_list','search_type'])
	try:
		with open('notification_settings.txt') as notifications_file:
			notifications_list = notifications_file.read().splitlines()
			for i in range(2,len(notifications_list),3):
				subreddit = notifications_list[i-2]
				search_term_list = map(str.strip,notifications_list[i-1].split(','))
				search_type = notifications_list[i]
				new_notification = notification_entry(subreddit=subreddit,search_term_list=search_term_list,search_type=search_type)
				all_notifications.append(new_notification)
	except OSError:
		print("No notification_settings.txt, script can't run.")
		raise ValueError("No notification_settings.txt, script can't run.")
		return []
	return all_notifications

#checks search terms in one subreddit, sends notifications for matching posts
def check_one_subreddit(notification):
	#print("Checking subreddit {}, searching by {}".format(notification.subreddit,notification.search_type))
	try:
		new_posts = get_reddit_posts(notification.subreddit)
	except Exception:
		print("Failed to get reddit posts.")
		raise
	for post in new_posts:
		if notification.search_type == 'title':
			post_val_to_search = post.post_title
		elif notification.search_type == 'author':
			post_val_to_search = post.post_author.name
		else:
			raise ValueError("Invalid search type for subreddit {}".format(notification.subreddit))
		if any([match_string(parse_search_term(search_term),post_val_to_search) for search_term in notification.search_term_list]):
			print("Found match in subreddit {}, sending push...".format(notification.subreddit))
			new_push = pushover.pushover_push(message=post.post_title,title="New post of interest in /r/{} by /u/{}".format(notification.subreddit,post.post_author))
			new_push.send_push()

#checks every subreddit using notification_settings.txt
#runs ONE TIME and exits
if __name__ == '__main__':
#global values
NUMBER_NEW_TO_GET = 10

	print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
	try:
		reddit = praw.Reddit(**read_reddit_auth())
		all_notifications = read_notification_settings()
		for notification in all_notifications:
			check_one_subreddit(notification)
	except Exception as e:
		print("Error caught, trying to log to file.")
		LOG_FILENAME = "tmp/error_log.txt"
		logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)
		logging.exception("Error occurred, program exiting, printing error message.")
		error_push = pushover.pushover_push(message='Unknown error occurred; please check script.',title='Reddit Notifications Error')
		if not pushover.check_matching_push(error_push,match_timestamp=False):
			error_push.send_push()
			error_push.print_status()
		else:
			print("Unknown error occurred. Sent a push recently, didn't bother sending another.")
		raise
	print("Finished checking, exiting program.")
