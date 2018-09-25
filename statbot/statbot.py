import praw
import sqlite3
from nba_scrape import NBA

class StatBot:
    '''Reddit bot to provide NBA stats upon request.

    Usage TBD
    '''

    def __init__(self, reddit_file):
        '''Create praw instance using reddit_file.

        reddit_file (.txt) -- file containing client id, client secret,
                              user agent, username, and password
        '''

        info = []
        with open(reddit_file) as f:
            for line in f:
                info.append(line.split("=")[1].split("\n")[0])
        self.reddit = praw.Reddit(client_id = info[0], client_secret = info[1],
                                  user_agent = info[2], username=info[3],
                                  password =info[4])
        self.sub = self.reddit.subreddit('nba')
        self.league = NBA()
        self.names = [name[0] for name in self.league.get_all_player_names()]
        self.stats = self.league.get_valid_stats()
        self.database = 'logs.db'
        db = sqlite3.connect(self.database)
        cursor = db.cursor()
        cursor.execute('''create table if not exists logs(comment TEXT,
                       url TEXT, response TEXT)''')
        db.close()


    def load_relevant_players(self, limit=5):
        '''Loads players mentioned in recent r/nba comments to database.

        limit (int) -- specifies how many comments to parse for player names
        '''

        info = {*[word.lower() for post in self.sub.new(limit=limit) for word
                in post.title.split(' ')]}
        relevant = set()
        for name in self.names:
            temp = name.split(' ')
            try:
                if temp[0] in info and temp[1] in info:
                    relevant.add(name)
            except IndexError:
                continue
        self.league.load_players(relevant)

    def parse_name(self, words):
        '''Parse a comment's body for a player name and returns it

        words (list) -- list of words from body of praw.Comment object
        '''

        for i, word in enumerate(words[:-1]):
            fullname = word + ' ' + words[i+1]
            if fullname.lower() in self.names:
                return fullname.lower()

    def parse_stats(self, words):
        '''Parse a comment's body for stat queries and returns a list of
           stats requested.

        words (list) -- list of words from body of praw.Comment object
        '''

        # Find a word within the comment containing a stat.
        # Split that word along its forward slashes.
        stat_word = [word for word in words if any([stat in word.upper() for
                     stat in self.stats])][0].split('/')
        return [stat for stat in stat_word if stat.upper() in self.stats]

    def parse_seasons(self, words):
        ''' Parse a comment's body for the season range requested and return it

        words (list) -- list of words from body of praw.Comment object
        '''

        def check(word):
            ''' Checks if a word specifies a year range'''
            if '-' not in word or len(word) != 7:
                return False
            try:
                return (int(word[5:]) > int(word[2:4]) and (int(word[:2]) == 19
                        or int(word[:2]) == 20))
            except ValueError:
                return False

        return [word for word in words if check(word)][0]

    def log(self, comment, response):
        '''Logs comment body, comment url, and response to database.'''

        db = sqlite3.connect(self.database)
        cursor = db.cursor()
        try:
            cursor.execute('''insert into logs (comment, url, response)
                           values (?, ?, ?)''', (comment.body, comment.url,
                           response))
        finally:
            db.close()
        return response

    def process(self, comment):
        '''Takes a comment and posts a reply providing the queried stat(s)

        comment (praw.Comment object) -- comment containing trigger
        '''
        words = comment.body.split(' ')
        name = self.parse_name(words)
        player = self.league.get_player(name)
        stats = self.parse_stats(words)
        year_range = self.parse_seasons(words)
        if '-p' in words or '-playoffs' in words:
            p_results = player.get_stats(stats, year_range, mode='playoffs')
            r_results = []
        elif '-b' in words or '-both' in words:
            p_results = player.get_stats(stats, year_range, mode='playoffs')
            r_results = player.get_stats(stats, year_range)
        else:
            r_results = player.get_stats(stats, year_range) # mode='season'
            p_results = []
        seasons = player.get_year_range(year_range)
        descrip = "%s's stats for %s:\n" % (name.title(), year_range)
        header = '|'.join(['Season'] + [stat.upper() for stat in stats])
        line = '-|' * (len(stats) + 1)
        if r_results:
            r_data = [(pair[0],) + pair[1] for pair in zip(seasons, r_results)]
            string_r = (['Regular Season:\n', header, line] +
                       ['|'.join([str(element) for element in tup]) for tup
                        in r_data])
        else:
            string_r = []
        if p_results:
            p_data = [(pair[0],) + pair[1] for pair in zip(seasons, p_results)]
            string_p = ['Playoffs:\n', header, line] + ['|'.join([str(element)
                        for element in tup]) for tup in p_data]
        else:
            string_p = []
        text = '\n'.join([descrip] + string_p[0:3] + string_p[3:] +
                         string_r[0:3] + string_r[3:])
        return self.log(comment, text)

    def run(self):
        '''Search for comments in r/nba containing "!STAT" and respond to them.

        This functions as the main loop of the program.
        '''
        for comment in self.sub.stream.comments():
            if "!STAT" in comment.body:
                comment.reply(self.process(comment))

class _Comment():
    '''Temporary class for testing purposes'''
    def __init__(self, content):
        self.body = content

if __name__ == "__main__":

    bot = StatBot('reddit.txt')
