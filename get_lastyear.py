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
    points_per_game TEXT,
    games_played TEXT,
    stat1 TEXT,
    stat2 TEXT,
    stat3 TEXT,
    stat4 TEXT,
    stat5 TEXT,
    stat6 TEXT
    )
    ''')


# QBs
qb_url = requests.get("https://www.cbssports.com/fantasy/football/stats/QB/2023/season/stats/ppr/")
docQB = BeautifulSoup(qb_url.text, "html.parser")
playersQB = docQB.findAll("span", attrs="CellPlayerName--long")
statsQB = docQB.findAll("td", attrs="TableBase-bodyTd")

# format stats
games_played_qb = []
ppgQB = []
stat1_qb = []
stat2_qb = []
stat3_qb = []
stat4_qb = []
stat5_qb = []
stat6_qb = []

j = 1
for stat in statsQB:
    if j % 16 == 0:
        ppgQB.append(stat.text.strip())
    if j == 2:
        games_played_qb.append(stat.text.strip())
    elif (j-2) % 16 == 0:
        games_played_qb.append(stat.text.strip())

    if j == 5:
        stat1_qb.append(stat.text.strip())
    elif (j-5) % 16 == 0:
        stat1_qb.append(stat.text.strip())

    if j == 7:
        stat2_qb.append(stat.text.strip())
    elif(j-7) % 16 == 0:
        stat2_qb.append(stat.text.strip())

    if j == 8:
        stat3_qb.append(stat.text.strip())
    elif(j-8) % 16 == 0:
        stat3_qb.append(stat.text.strip())

    if j == 10:
        stat4_qb.append(stat.text.strip())
    elif(j-10) % 16 == 0:
        stat4_qb.append(stat.text.strip())

    if j == 11:
        stat5_qb.append(stat.text.strip())
    elif (j-11) % 16 == 0:
        stat5_qb.append(stat.text.strip())

    if j == 13:
        stat6_qb.append(stat.text.strip())
    elif (j-13) % 16 == 0:
        stat6_qb.append(stat.text.strip())
    j += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersQB:
        player_name = player.text.strip().split("\n")[0]
        qb_ranking = "QB" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played, stat1, stat2, stat3, stat4, stat5, stat6)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (player_name, qb_ranking, ppgQB[i-1], games_played_qb[i-1], stat1_qb[i-1], stat2_qb[i-1], stat3_qb[i-1], stat4_qb[i-1], stat5_qb[i-1], stat6_qb[i-1]))
        i += 1
    storage.commit()

# add rookies to database (no stats last year)
rookie_qbs = ["Caleb Williams", "Jayden Daniels", "Bo Nix", "Drake Maye", "J.J. McCarthy", "Michael Penix Jr.", "Spencer Rattler"]
with sqlite3.connect('draft_board.db') as storage:
    cursor = storage.cursor()
    for rookie in rookie_qbs:
        qb_ranking = "QB--"
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking)
        VALUES (?, ?)
        ''', (rookie, qb_ranking))
    storage.commit()

print("QB stats have been uploaded")



# RBs
rb_url = requests.get("https://www.cbssports.com/fantasy/football/stats/RB/2023/season/stats/ppr/")
docRB = BeautifulSoup(rb_url.text, "html.parser")
playersRB = docRB.findAll("span", attrs="CellPlayerName--long")
statsRB = docRB.findAll("td", attrs="TableBase-bodyTd")

# format stats
games_played_rb = []
ppgRB = []
stat1_rb = []
stat2_rb = []
stat3_rb = []
stat4_rb = []
stat5_rb = []
stat6_rb = []
add_stat3_rb = []
j = 1
for stat in statsRB:
    if j % 15 == 0:
        ppgRB.append(stat.text.strip())

    if j == 2:
        games_played_rb.append(stat.text.strip())
    elif (j-2) % 15 == 0:
        games_played_rb.append(stat.text.strip())

    if j == 3:
        stat1_rb.append(stat.text.strip())
    elif (j-3) % 15 == 0:
        stat1_rb.append(stat.text.strip())

    if j == 4:
        stat2_rb.append(stat.text.strip())
    elif(j-4) % 15 == 0:
        stat2_rb.append(stat.text.strip())

    if j == 6:
        stat3_rb.append(stat.text.strip())
    elif(j-6) % 15 == 0:
        stat3_rb.append(stat.text.strip())

    if j == 7:
        stat4_rb.append(stat.text.strip())
    elif(j-7) % 15 == 0:
        stat4_rb.append(stat.text.strip())

    if j == 8:
        stat5_rb.append(stat.text.strip())
    elif (j-8) % 15 == 0:
        stat5_rb.append(stat.text.strip())

    if j == 9:
        stat6_rb.append(stat.text.strip())
    elif (j-9) % 15 == 0:
        stat6_rb.append(stat.text.strip())

    if j == 12:
        add_stat3_rb.append(stat.text.strip())
    elif (j-12) % 15 == 0:
        add_stat3_rb.append(stat.text.strip())
    j += 1

# total tds (receiving and rushing)
for i in range(0, len(stat3_rb)):
    if '—' in stat3_rb[i] or '—' in add_stat3_rb[i]:
        continue
    stat3_rb[i] = str(int(stat3_rb[i]) + int(add_stat3_rb[i]))

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersRB:
        player_name = player.text.strip().split("\n")[0]
        rb_ranking = "RB" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played, stat1, stat2, stat3, stat4, stat5, stat6)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (player_name, rb_ranking, ppgRB[i-1], games_played_rb[i-1], stat1_rb[i-1], stat2_rb[i-1], stat3_rb[i-1], stat4_rb[i-1], stat5_rb[i-1], stat6_rb[i-1]))
        i += 1
    storage.commit()

rookie_rbs = ["Jonathon Brooks", "Trey Benson", "Blake Corum", "Jaylen Wright", "MarShawn Lloyd", "Ray Davis", "Audric Estime", "Bucky Irving", "Braelon Allen", "Will Shipley"]
with sqlite3.connect('draft_board.db') as storage:
    cursor = storage.cursor()
    for rookie in rookie_rbs:
        rb_ranking = "RB--"
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking)
        VALUES (?, ?)
        ''', (rookie, rb_ranking))
    storage.commit()

print("RB stats have been uploaded")
    


# WRs
wr_url = requests.get("https://www.cbssports.com/fantasy/football/stats/WR/2023/season/stats/ppr/")
docWR = BeautifulSoup(wr_url.text, "html.parser")
playersWR = docWR.findAll("span", attrs="CellPlayerName--long")
statsWR = docWR.findAll("td", attrs="TableBase-bodyTd")

# format stats

games_played_wr = []
ppgWR = []
stat1_wr = []
stat2_wr = []
stat3_wr = []
stat4_wr = []
stat5_wr = []
stat6_wr = []
add_stat4_wr = []
j = 1
for stat in statsWR:
    if j % 15 == 0:
        ppgWR.append(stat.text.strip())

    if j == 2:
        games_played_wr.append(stat.text.strip())
    elif (j-2) % 15 == 0:
        games_played_wr.append(stat.text.strip())

    if j == 3:
        stat1_wr.append(stat.text.strip())
    elif (j-3) % 15 == 0:
        stat1_wr.append(stat.text.strip())

    if j == 4:
        stat2_wr.append(stat.text.strip())
    elif(j-4) % 15 == 0:
        stat2_wr.append(stat.text.strip())

    if j == 5:
        stat3_wr.append(stat.text.strip())
    elif(j-5) % 15 == 0:
        stat3_wr.append(stat.text.strip())

    if j == 8:
        stat4_wr.append(stat.text.strip())
    elif(j-8) % 15 == 0:
        stat4_wr.append(stat.text.strip())

    if j == 9:
        stat5_wr.append(stat.text.strip())
    elif (j-9) % 15 == 0:
        stat5_wr.append(stat.text.strip())

    if j == 10:
        stat6_wr.append(stat.text.strip())
    elif (j-10) % 15 == 0:
        stat6_wr.append(stat.text.strip())

    if j == 12:
        add_stat4_wr.append(stat.text.strip())
    elif (j-12) % 15 == 0:
        add_stat4_wr.append(stat.text.strip())
    j += 1

for i in range(0, len(stat4_wr)):
    if '—' in stat4_wr[i] or '—' in add_stat4_wr[i]:
        continue
    stat4_wr[i] = str(int(stat4_wr[i]) + int(add_stat4_wr[i]))

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersWR:
        player_name = player.text.strip().split("\n")[0]
        wr_ranking = "WR" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played, stat1, stat2, stat3, stat4, stat5, stat6)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (player_name, wr_ranking, ppgWR[i-1], games_played_wr[i-1], stat1_wr[i-1], stat2_wr[i-1], stat3_wr[i-1], stat4_wr[i-1], stat5_wr[i-1], stat6_wr[i-1]))
        i += 1
    storage.commit()

rookie_wrs = ["Marvin Harrison Jr.", "Malik Nabers", "Rome Odunze", "Xavier Worthy", "Brian Thomas Jr.", "Ladd McConkey", "Keon Coleman", "Ricky Pearsall", "Adonai Mitchell", "Xavier Legette", "Ja'Lynn Polk", "Roman Wilson", "Malachi Corley"]
with sqlite3.connect('draft_board.db') as storage:
    cursor = storage.cursor()
    for rookie in rookie_wrs:
        wr_ranking = "WR--"
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking)
        VALUES (?, ?)
        ''', (rookie, wr_ranking))
    storage.commit()

print("WR stats have been uploaded")
    



# TEs
te_url = requests.get("https://www.cbssports.com/fantasy/football/stats/TE/2023/season/stats/ppr/")
docTE = BeautifulSoup(te_url.text, "html.parser")
playersTE = docTE.findAll("span", attrs="CellPlayerName--long")
statsTE = docTE.findAll("td", attrs="TableBase-bodyTd")

# format stats

games_played_te = []
ppgTE = []
stat1_te = []
stat2_te = []
stat3_te = []
stat4_te = []
j = 1
for stat in statsTE:
    if j % 11 == 0:
        ppgTE.append(stat.text.strip())

    if j == 2:
        games_played_te.append(stat.text.strip())
    elif (j-2) % 11 == 0:
        games_played_te.append(stat.text.strip())

    if j == 3:
        stat1_te.append(stat.text.strip())
    elif (j-3) % 11 == 0:
        stat1_te.append(stat.text.strip())

    if j == 4:
        stat2_te.append(stat.text.strip())
    elif(j-4) % 11 == 0:
        stat2_te.append(stat.text.strip())

    if j == 5:
        stat3_te.append(stat.text.strip())
    elif(j-5) % 11 == 0:
        stat3_te.append(stat.text.strip())

    if j == 8:
        stat4_te.append(stat.text.strip())
    elif(j-8) % 11 == 0:
        stat4_te.append(stat.text.strip())
    j += 1

# upload info to database
with sqlite3.connect('draft_board.db') as storage:
    i = 1
    cursor = storage.cursor()
    for player in playersTE:
        player_name = player.text.strip().split("\n")[0]
        te_ranking = "TE" + str(i)
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking, points_per_game, games_played, stat1, stat2, stat3, stat4)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (player_name, te_ranking, ppgTE[i-1], games_played_te[i-1], stat1_te[i-1], stat2_te[i-1], stat3_te[i-1], stat4_te[i-1]))
        i += 1
    storage.commit()

rookie_tes = ["Brock Bowers", "Ben Sinnott", "Ja'Tavion Sanders", "Theo Johnson", "Cade Stover", "Erick All Jr."]
with sqlite3.connect('draft_board.db') as storage:
    cursor = storage.cursor()
    for rookie in rookie_tes:
        te_ranking = "TE--"
        cursor.execute('''
        INSERT INTO last_year_stats (player, ranking)
        VALUES (?, ?)
        ''', (rookie, te_ranking))
    storage.commit()

print("TE stats have been uploaded")