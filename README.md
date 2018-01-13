# reddit-notifications
Sends notifications for new reddit posts based on search query. Uses Pushover and reddit.

LANGUAGE:  
Python 3

REQUIREMENTS:  
Pushover for receiving notifications  
Pushover API access for sending notifications  
Reddit API access for retrieving new posts  

HOW TO USE:  
Set up API access, install Pushover on phone  
Set up auth.ini and notification_settings.txt (see below)  
Schedule reddit_notifications.py to run at desired interval  

In notification_settings.txt, each subreddit to search is formatted in 3 lines:  
[subreddit name]  
[keyword 1],[keyword 2],[keyword 3],....  
[title] or [author] depending on what you want to search  
Keywords can either have spaces to search for a phrase, or + in between words to search for individual words.  

For auth.ini, just use the example file and replace with your authentication.  

TO DO:  
1. Support multiple searches for the same subreddit (can't do both author and title searches currently)  
2. Re-format notification_settings.txt input  
3. Support multiple pushover targets and/or multiple users  
4. Add better error handling  
5. Enable permanent/long-term logging  
6. Ignore non-alphanumeric characters
