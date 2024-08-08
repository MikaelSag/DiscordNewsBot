import sqlite3
import requests
import datetime
from bs4 import BeautifulSoup

with sqlite3.connect("draft_board.db") as storage:
    cursor = storage.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedules (
    home_team TEXT,
    away_team TEXT,
    time TEXT,
    date TEXT,
    week TEXT,
    id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    ''')
storage.commit()

# get weeks and days of matches in order
url = requests.get("https://theredzone.org/schedule/Week-by-Week-NFL-Schedule")
doc = BeautifulSoup(url.text, "html.parser")
schedules = doc.findAll("strong")

weeks = []
days = []
for schedule in schedules:
    scheduleStr = schedule.text
    if "Week " in scheduleStr:
        weeks.append(scheduleStr)
    elif scheduleStr != "NFL Weekly Schedule 2024":
        days.append(scheduleStr)

times_to_dupe_weeks = [16, 16, 16, 16, 14, 14, 15, 16, 15, 14, 14, 13, 16, 13, 16, 16, 16, 16]
times_to_dupe_days = [1, 1, 13, 1, 1, 14, 1, 1, 13, 2, 1, 13, 2, 1, 12, 1, 1, 12, 1, 1, 12, 2, 1, 14, 1, 1, 13, 1, 1, 12, 1, 1, 12, 1, 1, 11, 1, 3, 1, 11, 1, 1, 11, 1, 1, 13, 2, 1, 2, 12, 1, 2, 1, 5, 7, 1, 16]

duplicated_weeks = [week for week, count in zip(weeks, times_to_dupe_weeks) for _ in range(count)]
duplicated_days = [day for day, count in zip(days, times_to_dupe_days) for _ in range(count)]

duplicated_days = duplicated_days[:-16]
duplicated_weeks = duplicated_weeks[:-16]

# get home and away teams and times
games = doc.findAll("br")
game_text = []
for game in games:
    game_text.append(game.parent.text)

game_info = [line for i in game_text for line in i.splitlines()]

home_teams = []
away_teams = []
times = []

# will replace team names with abbreviations
team_abbreviations = {
    'Arizona Cardinals': 'ARI',
    'Atlanta Falcons': 'ATL',
    'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR',
    'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN',
    'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN',
    'Detroit Lions': 'DET',
    'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU',
    'Indianapolis Colts': 'IND',
    'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC',
    'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE',
    'New Orleans Saints': 'NO',
    'New York Giants': 'NYG',
    'New York Jets': 'NYJ',
    'Las Vegas Raiders': 'LV',
    'Philadelphia Eagles': 'PHI',
    'Pittsburgh Steelers': 'PIT',
    'Los Angeles Chargers': 'LAC',
    'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA',
    'Los Angeles Rams': 'LAR',
    'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN',
    'Washington Commanders': 'WAS'
}

seen = set()
unique_games = []
days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# remove duplicates and dates, should only be teams and time
for game in game_info:
    if any(day not in game for day in days_of_week):
        if game not in seen:
            unique_games.append(game)
            seen.add(game)

# split string into time, home_team, away_team variables
for game in unique_games:
    halves = game.split(' -- ')

    if len(halves) < 2:
        continue

    teams_section = halves[0]
    time_section = halves[1].split(',')[0]

    teams = teams_section.split(' at ')
    if (' at ') not in teams_section:
        teams = teams_section.split(' vs ')
    if len(teams) < 2:
        continue

    away_teams.append(teams[0].strip())
    home_teams.append(teams[1].strip())
    times.append(time_section.strip())

# convert to central time
central_times = []
for time in times:
    if time == '9:30 a.m.':
        central_times.append('8:30 a.m.')
    elif time == '12:30 p.m.':
        central_times.append('11:30 p.m.')
    elif time == '1 p.m.':
        central_times.append('12:00 p.m.')
    elif time == '3 p.m.':
        central_times.append('2:00 p.m.')
    elif time == '4:05 p.m.':
        central_times.append('3:05 p.m.')
    elif time == '4:25 p.m.':
        central_times.append('3:25 p.m.')
    elif time == '4:30 p.m.':
        central_times.append('3:30 p.m.')
    elif time == '8 p.m.':
        central_times.append('7 p.m.')
    elif time == '8:15 p.m.':
        central_times.append('7:15 p.m.')
    elif time == '8:20 p.m.':
        central_times.append('7:20 p.m.')
    else:
        central_times.append(time)

# replace team names with abbreviations from dict
abbr_home = [team_abbreviations.get(team_name, team_name) for team_name in home_teams]
abbr_away = [team_abbreviations.get(team_name, team_name) for team_name in away_teams]

# add elements to the following to offset issue with parsing (doesn't matter week 18 will be omitted)

duplicated_weeks.append("trash")
duplicated_weeks.append("trash")
duplicated_weeks.append("trash")
duplicated_weeks.append("trash")
duplicated_weeks.append("trash")
duplicated_weeks.append("trash")

duplicated_days.append("trash")
duplicated_days.append("trash")
duplicated_days.append("trash")
duplicated_days.append("trash")
duplicated_days.append("trash")
duplicated_days.append("trash")

times.append("trash")
times.append("trash")
times.append("trash")
times.append("trash")
times.append("trash")
times.append("trash")

# upload to database
with sqlite3.connect("draft_board.db") as storage:
    i = 0
    cursor = storage.cursor()
    for days in duplicated_days:
        cursor.execute('''
        INSERT INTO schedules (home_team, away_team, time, date, week)
        VALUES (?, ?, ?, ?, ?)
        ''', (abbr_home[i], abbr_away[i], central_times[i], days, duplicated_weeks[i]))
        i += 1
    storage.commit()
    print("Schedules have been uploaded")










