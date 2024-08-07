import sqlite3
import requests
from bs4 import BeautifulSoup

# create table if it doesnt exist
with sqlite3.connect("draft_board.db") as storage:
    cursor = storage.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS last_year_stats (
    player TEXT,
    ranking TEXT,
    points_per_game INTEGER,
    games_played INTEGER,
    )
    ''')


# QBs
qb_url = requests.get("https://www.cbssports.com/fantasy/football/stats/QB/2023/season/stats/ppr/")
docQB = BeautifulSoup(qb_url.text, "html.parser")
playersQB = docQB.findAll("span", attrs="CellPlayerName--long")
statsQB = docQB.findAll("td", attrs="TableBase-bodyTd")

# get games played
games_played_qb = []
j = 1
for stat in statsQB:
    if j == 2:
        games_played_qb.append(stat.text)
    elif (j-2) % 16 == 0:
        games_played_qb.append(stat.text)
    j += 1

# get points per game
ppgQB = []
k = 1
for stat in statsQB:
    if k % 16 == 0:
        ppgQB.append(stat.text)
    k += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersQB:
        player_name = player.text.strip().split("\n")[0]
        qb_ranking = "QB" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played)
        VALUES (?, ?, ?, ?)
        ''', (player_name, qb_ranking, ppgQB[i-1], games_played_qb[i-1]))
        i += 1
    storage.commit()
    print("QB stats have been uploaded")
    

# RBs
rb_url = requests.get("https://www.cbssports.com/fantasy/football/stats/RB/2023/season/stats/ppr/")
docRB = BeautifulSoup(rb_url.text, "html.parser")
playersRB = docRB.findAll("span", attrs="CellPlayerName--long")
statsRB = docRB.findAll("td", attrs="TableBase-bodyTd")

# get games played
games_played_rb = []
j = 1
for stat in statsRB:
    if j == 2:
        games_played_rb.append(stat.text)
    elif (j-2) % 15 == 0:
        games_played_rb.append(stat.text)
    j += 1

# get points per game
ppgRB = []
k = 1
for stat in statsRB:
    if k % 15 == 0:
        ppgRB.append(stat.text)
    k += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersRB:
        player_name = player.text.strip().split("\n")[0]
        rb_ranking = "RB" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played)
        VALUES (?, ?, ?, ?)
        ''', (player_name, rb_ranking, ppgRB[i-1], games_played_rb[i-1]))
        i += 1
    storage.commit()
    print("RB stats have been uploaded")
    


# WRs
wr_url = requests.get("https://www.cbssports.com/fantasy/football/stats/WR/2023/season/stats/ppr/")
docWR = BeautifulSoup(wr_url.text, "html.parser")
playersWR = docWR.findAll("span", attrs="CellPlayerName--long")
statsWR = docWR.findAll("td", attrs="TableBase-bodyTd")

# get games played
games_played_wr = []
j = 1
for stat in statsWR:
    if j == 2:
        games_played_wr.append(stat.text)
    elif (j-2) % 15 == 0:
        games_played_wr.append(stat.text)
    j += 1

# get points per game
ppgWR = []
k = 1
for stat in statsWR:
    if k % 15 == 0:
        ppgWR.append(stat.text)
    k += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersWR:
        player_name = player.text.strip().split("\n")[0]
        wr_ranking = "WR" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played)
        VALUES (?, ?, ?, ?)
        ''', (player_name, wr_ranking, ppgWR[i-1], games_played_wr[i-1]))
        i += 1
    storage.commit()
    print("WR stats have been uploaded")
    



# TEs
te_url = requests.get("https://www.cbssports.com/fantasy/football/stats/TE/2023/season/stats/ppr/")
docTE = BeautifulSoup(te_url.text, "html.parser")
playersTE = docTE.findAll("span", attrs="CellPlayerName--long")
statsTE = docTE.findAll("td", attrs="TableBase-bodyTd")

# get games played
games_played_te = []
j = 1
for stat in statsTE:
    if j == 2:
        games_played_te.append(stat.text)
    elif (j-2) % 11 == 0:
        games_played_te.append(stat.text)
    j += 1

# get points per game
ppgTE = []
k = 1
for stat in statsTE:
    if k % 11 == 0:
        ppgTE.append(stat.text)
    k += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersTE:
        player_name = player.text.strip().split("\n")[0]
        te_ranking = "TE" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played)
        VALUES (?, ?, ?, ?)
        ''', (player_name, te_ranking, ppgTE[i-1], games_played_te[i-1]))
        i += 1
    storage.commit()
    print("TE stats have been uploaded")