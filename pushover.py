from datetime import datetime,timedelta
from time import strftime
import requests
import http.client, urllib
import json
import configparser

#class representing a single pushover notification
class pushover_push:
	def __init__(self,message,title=None,url=None,url_title=None,priority=0,
			push_time=datetime.utcnow(),push_response=None,token=None,user=None): #push_response=None corresponds to an unsent push
		self.message = message
		self.title = title
		self.url = url
		self.url_title = url_title
		self.priority = priority
		self.push_time = push_time
		self.push_response = push_response
		if user is None or token is None: #if user and token are not passed in
			self.__read_pushover_auth()
		else:
			self.user = user
			self.token = token

	#two pushes are equal if they were sent at the same time and they had the same response code
	def __eq__(self,other):
		return (self.push_time == other.push_time and self.push_response == other.push_response)

	def __read_pushover_auth(self):
		AUTH_FILE = "auth.ini"
		config = configparser.ConfigParser()
		try:
			config.read(AUTH_FILE)
			self.token = config['pushover']['token']
			self.user = config['pushover']['user']
		except (ValueError, OSError) as e:
			print("Pushover auth didn't work, check your {}".format(AUTH_FILE))
			raise

	def __load_pushover_data(self):
		self.pushover_data = {'token' : self.token, 'user' : self.user, 'message' : self.message, 'priority' : self.priority}
		if self.title is not None:
			self.pushover_data['title'] = self.title
		if self.url is not None and self.url_title is not None:
			self.pushover_data['url'] = self.url
			self.pushover_data['url_title'] = self.url_title
		if self.priority == 2:
			self.pushover_data['retry'] = 300 #default values of 5 minutes and 1 hour
			self.pushover_data['expire'] = 3600

	def send_push(self):
		self.__load_pushover_data()
		conn = http.client.HTTPSConnection("api.pushover.net:443")
		conn.request("POST", "/1/messages.json",urllib.parse.urlencode(self.pushover_data), { "Content-type": "application/x-www-form-urlencoded" })
		push_response_data = conn.getresponse().read()
		self.push_response = json.loads(push_response_data.decode())['status']
		write_push_history(self)
		self.print_status()

	def print_status(self):
		if self.push_response is None:
			print("No response when sending push: {}".format(self.title))
		elif self.push_response == 1:
			print("Successfully sent push: {}".format(self.title))
		else:
			print("Push failed to send: {}".format(self.title))

#pushes are contained in 3 lines containing message, response and timestamp
def read_push_history():
	push_history = []
	try:
		with open('push_history.txt') as push_file:
			push_list  = push_file.read().splitlines()
			for i in range(0,len(push_list),3):
				push_message = push_list[i]
				try:
					push_response = int(push_list[i+1])
				except ValueError as e:
					push_response = None
				push_time = datetime.strptime(push_list[i+2],'%Y-%m-%d %H:%M:%S')
				current_push = pushover_push(message=push_message,push_time=push_time,push_response=push_response)
				push_history.append(current_push)
	except OSError:
		return []
	return push_history

#writes push history, deleting ones that are older than cutoff_time (default 4 weeks)
def write_push_history(new_push,cutoff_time=(datetime.utcnow()-timedelta(weeks=4))):
	push_history = read_push_history()
	push_history = [current_push for current_push in push_history if not current_push.push_time < cutoff_time]
	if new_push is not None:
		push_history.append(new_push)
	try:
		with open('push_history.txt','w') as push_file:
			for current_push in push_history:
				push_file.write("{}\n{}\n{}\n".format(current_push.message,current_push.push_response,current_push.push_time.strftime('%Y-%m-%d %H:%M:%S')))
	except OSError:
		print("Something went wrong while writing pushes...")

#checks for a previous push matching the given values
#values are represented as T/F in order [message,response,timestamp]
#response matches if and only if it is 1
def check_matching_push(new_push,match_message=True,match_response=True,match_timestamp=True,cutoff_time=(datetime.utcnow()-timedelta(hours=2))):
	push_history = read_push_history()
	if not push_history:
		return False
	for old_push in push_history:
		if ((old_push.message == new_push.message or not match_message) and (old_push.push_response == 1 or not match_response)
				and ((old_push.push_time < new_push.push_time + timedelta(seconds=1) and old_push.push_time > new_push.push_time - timedelta(seconds=1)) or not match_timestamp)
				and old_push.push_time > cutoff_time):
			return True
	return False

