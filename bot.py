import os
import discord
import sqlite3
import requests
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

# load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))

# initialize the bot with required intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='/', intents=intents)

# create or connect to the SQLite database
storage = sqlite3.connect('draft_board.db', check_same_thread=False)
cursor = storage.cursor()

# ensure the necessary tables exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        date TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS draft_board (
        user_id INTEGER,
        ranking INTEGER,
        player TEXT,
        PRIMARY KEY (user_id, ranking),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')
storage.commit()

# read starting draft board
async def load_starting():
    global players
    starting_storage = sqlite3.connect('starting_draftboard.db')
    cursor = starting_storage.cursor()
    query = "SELECT player FROM players"
    cursor.execute(query)
    players = cursor.fetchall()
    starting_storage.close()
    return players

# load existing draftboard
async def load_existing(discord_id):
    user_id = str(discord_id)
    cursor = storage.cursor()
    query = "SELECT player FROM draft_board WHERE user_id=?"
    cursor.execute(query, (user_id,))
    old_players = cursor.fetchall()
    return old_players

# check if user already has a custom draft board
async def check_exists(discord_id):
    old_players = await load_existing(discord_id)
    hasDraftboard = False
    if len(old_players) == 150:
        hasDraftboard = True
    return hasDraftboard

# on bot startup connect to guild and print confirmation
@bot.event
async def on_ready():
    await load_starting()
    for guild in bot.guilds:
        if guild.id == GUILD_ID:
            break

    print(f'{bot.user} is connected to {guild.name}')
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")

# class for creating the draft board
class DraftBoardViewWithSelect(View):
    def __init__(self, draft_board):
        super().__init__(timeout=None)
        self.draft_board = draft_board
        self.selected_player_index = None
        self.currently_moving_player = None
        self.page = 0
        self.items_per_page = 12

        self.select_menu = Select(
            placeholder='Select a player to move',
            options=[
                discord.SelectOption(label=player[0], value=str(index))
                for index, player in enumerate(self.draft_board[:self.items_per_page])
            ]
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

        move_up_button = Button(label='Move Up', style=discord.ButtonStyle.primary)
        move_up_button.callback = self.move_up_callback
        self.add_item(move_up_button)

        move_down_button = Button(label='Move Down', style=discord.ButtonStyle.primary)
        move_down_button.callback = self.move_down_callback
        self.add_item(move_down_button)

        move_to_position_button = Button(label='Move to specific position', style=discord.ButtonStyle.secondary)
        move_to_position_button.callback = self.move_to_position_callback
        self.add_item(move_to_position_button)

        swap_button = Button(label='Swap with specific position', style=discord.ButtonStyle.secondary)
        swap_button.callback = self.swap_button_callback
        self.add_item(swap_button)

        save_button = Button(label='Save order', style=discord.ButtonStyle.success)
        save_button.callback = self.save_callback
        self.add_item(save_button)

        previous_page_button = Button(label='Previous', style=discord.ButtonStyle.secondary)
        previous_page_button.callback = self.previous_page
        self.add_item(previous_page_button)

        next_page_button = Button(label='Next', style=discord.ButtonStyle.secondary)
        next_page_button.callback = self.next_page
        self.add_item(next_page_button)

        self.update_options()

    # selecting player drop down
    async def select_callback(self, interaction: discord.Interaction):
        self.selected_player_index = self.page * 12 + int(self.select_menu.values[0])
        self.currently_moving_player = self.draft_board[self.selected_player_index]
        await interaction.response.edit_message(
            content=self.create_draft_board_message(), view=self
        )

    # updates select menu and buttons
    def update_options(self):
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        self.select_menu.options = [
            discord.SelectOption(label=player[0], value=str(index))
            for index, player in enumerate(self.draft_board[start_index:end_index])
        ]

        self.children[-2].disabled = self.page == 0
        self.children[-1].disabled = end_index >= len(self.draft_board)

    # creates and updates the draft board message
    def create_draft_board_message(self):
        current_player = self.currently_moving_player[0] if self.currently_moving_player else None
        moving_status = f"Currently moving: {current_player}" if current_player else "No player currently selected"
        start_index = self.page * 12
        end_index = start_index + 12
        displayed_players = self.draft_board[start_index:end_index]
        draft_board_status = "\n".join(
            f"{start_index + i + 1}. {player[0]}" for i, player in enumerate(displayed_players)
        )

        total_content = f"{moving_status}\n\nUpdated Draft Board:\n{draft_board_status}"

        return total_content

    # adds functionality to 'move up' button
    async def move_up_callback(self, interaction: discord.Interaction):
        if self.currently_moving_player is not None and self.selected_player_index is not None and self.selected_player_index > 0:
            self.draft_board[self.selected_player_index], self.draft_board[self.selected_player_index - 1] = \
                self.draft_board[self.selected_player_index - 1], self.draft_board[self.selected_player_index]
            self.selected_player_index -= 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "No player selected or player is already at the top.",
                ephemeral=True
            )

    # adds functionality to 'move down' button
    async def move_down_callback(self, interaction: discord.Interaction):
        if self.currently_moving_player is not None and self.selected_player_index is not None and self.selected_player_index < len(self.draft_board) - 1:
            self.draft_board[self.selected_player_index], self.draft_board[self.selected_player_index + 1] = \
                self.draft_board[self.selected_player_index + 1], self.draft_board[self.selected_player_index]
            self.selected_player_index += 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "No player selected or player is already at the bottom.",
                ephemeral=True
            )

    # adds functionality to 'swap with specific position' button
    async def swap_button_callback(self, interaction: discord.Interaction):
        if self.selected_player_index is not None:
            await interaction.response.send_modal(SwapWithPositionModal(self))
        else:
            await interaction.response.send_message(
                "No player selected to swap.",
                ephemeral=True
            )

    # adds functionality to 'move to specific position' button
    async def move_to_position_callback(self, interaction: discord.Interaction):
        if self.selected_player_index is not None:
            await interaction.response.send_modal(MoveToPositionModal(self))
        else:
            await interaction.response.send_message(
                "No player selected to move.",
                ephemeral=True
            )

    # saves user information, time, and draft board in database
    async def save_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        username = interaction.user.name
        now = datetime.now()
        time_saved = now.strftime("%m/%d/%Y %H:%M:%S")
        i = 1
        with sqlite3.connect('draft_board.db') as storage:
            cursor = storage.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, date)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, date = excluded.date
            ''', (user_id, username, time_saved))
            cursor.execute('DELETE FROM draft_board WHERE user_id=?', (user_id,))
            for player in self.draft_board:
                cursor.execute('''
                    INSERT INTO draft_board (user_id, ranking, player)
                    VALUES (?, ?, ?)
                ''', (user_id, i, player[0]))
                i += 1
            storage.commit()
            await interaction.response.send_message("Draft board saved successfully.", ephemeral=True)

    # shows previous 12 players when 'previous' button is selected
    async def previous_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "You are already on the first page.", ephemeral=True
            )

    # shows next 12 players when 'next' button is selected
    async def next_page(self, interaction: discord.Interaction):
        if (self.page + 1) * self.items_per_page < len(self.draft_board):
            self.page += 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "You are already on the last page.", ephemeral=True
            )

# class for swap position modal where user can enter a desired position to swap with
class SwapWithPositionModal(Modal):
    def __init__(self, view: DraftBoardViewWithSelect):
        super().__init__(title="Swap Player with Position")
        self.view = view
        self.add_item(TextInput(label="Target Position (1-150)", placeholder="Enter a number between 1 and 150"))

    async def on_submit(self, interaction: discord.Interaction):
        target_position = int(self.children[0].value) - 1
        if 0 <= target_position < len(self.view.draft_board):
            selected_player_index = self.view.selected_player_index
            self.view.draft_board[selected_player_index], self.view.draft_board[target_position] = \
                self.view.draft_board[target_position], self.view.draft_board[selected_player_index]
            self.view.selected_player_index = target_position
            self.view.update_options()
            await interaction.response.edit_message(
                content=self.view.create_draft_board_message(), view=self.view
            )
        else:
            await interaction.response.send_message(
                "Invalid position. Please enter a number between 1 and 150.",
                ephemeral=True
            )

# class for move to position modal where user can enter a desired position to move to
class MoveToPositionModal(Modal):
    def __init__(self, view: DraftBoardViewWithSelect):
        super().__init__(title="Move Player to Position")
        self.view = view
        self.add_item(TextInput(label="Target Position (1-150)", placeholder="Enter a number between 1 and 150"))

    async def on_submit(self, interaction: discord.Interaction):
        target_position = int(self.children[0].value) - 1
        if 0 <= target_position < len(self.view.draft_board):
            selected_player_index = self.view.selected_player_index
            selected_player = self.view.draft_board.pop(selected_player_index)
            self.view.draft_board.insert(target_position, selected_player)
            self.view.selected_player_index = target_position
            self.view.update_options()
            await interaction.response.edit_message(
                content=self.view.create_draft_board_message(), view=self.view
            )
        else:
            await interaction.response.send_message(
                "Invalid position. Please enter a number between 1 and 150.",
                ephemeral=True
            )

# class for existing custom draft board
class DraftBoardViewWithoutSelect(View):
    def __init__(self, draft_board):
        super().__init__(timeout=None)
        self.draft_board = draft_board
        self.page = 0
        self.items_per_page = 12

        edit_button = Button(label='Edit', style=discord.ButtonStyle.primary)
        edit_button.callback = self.edit_callback
        self.add_item(edit_button)

        delete_button = Button(label='Delete', style=discord.ButtonStyle.danger)
        delete_button.callback = self.delete_callback
        self.add_item(delete_button)

        previous_page_button = Button(label='Previous', style=discord.ButtonStyle.secondary)
        previous_page_button.callback = self.previous_page
        self.add_item(previous_page_button)

        next_page_button = Button(label='Next', style=discord.ButtonStyle.secondary)
        next_page_button.callback = self.next_page
        self.add_item(next_page_button)

        self.update_options()

    def update_options(self):
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page

        self.children[-2].disabled = self.page == 0
        self.children[-1].disabled = end_index >= len(self.draft_board)

    def create_draft_board_message(self):
        start_index = self.page * 12
        end_index = start_index + 12
        displayed_players = self.draft_board[start_index:end_index]
        draft_board_status = "\n".join(
            f"{start_index + i + 1}. {player[0]}" for i, player in enumerate(displayed_players)
        )

        total_content = f"Draft Board:\n{draft_board_status}"
        if len(total_content) > 2000:
            max_lines = 2000 - 23
            truncated_draft_board_status = draft_board_status[:max_lines].rsplit('\n', 1)[0]
            total_content = f"Draft Board:\n{truncated_draft_board_status}\n... (truncated)"

        return total_content

    # reuses DraftBoardViewWithSelect class but with existing draft board for edit functionality
    async def edit_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        existing_players = await load_existing(user_id)
        view = DraftBoardViewWithSelect(existing_players[:])
        await interaction.response.edit_message(
            content="Editing your Draft Board:\n" + "\n".join(f"{i + 1}. {player[0]}" for i, player in enumerate(existing_players[:12])),
            view=view
        )

    # deletes existing draft board from database
    async def delete_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        old_storage = sqlite3.connect('draft_board.db')
        cursor = old_storage.cursor()
        query1 = "DELETE FROM draft_board WHERE user_id=?"
        cursor.execute(query1, (user_id,))
        query2 = "DELETE FROM users WHERE user_id=?"
        cursor.execute(query2, (user_id,))
        old_storage.commit()
        old_storage.close()
        await interaction.response.send_message("Draft Board Deleted Successfully!", ephemeral=True)


    async def previous_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "You are already on the first page.", ephemeral=True
            )

    async def next_page(self, interaction: discord.Interaction):
        if (self.page + 1) * self.items_per_page < len(self.draft_board):
            self.page += 1
            self.update_options()
            await interaction.response.edit_message(
                content=self.create_draft_board_message(), view=self
            )
        else:
            await interaction.response.send_message(
                "You are already on the last page.", ephemeral=True
            )

# 'create_draftboard' command to create draft board if user does not have an existing one
@bot.tree.command(name='create_draftboard', description="Plan out your custom Draft Board, so you're prepared when draft day comes")
async def create_draftboard(interaction: discord.Interaction):
    user_id = interaction.user.id
    check = await check_exists(user_id)
    if not check:
        initial_players = await load_starting()
        view = DraftBoardViewWithSelect(initial_players[:])
        await interaction.response.send_message(
            content="Current Draft Board:\n" + "\n".join(f"{i + 1}. {player[0]}" for i, player in enumerate(initial_players[:12])), view=view
        )
    else:
        await interaction.response.send_message(
            content="You've already created a draft board. Try /manage_draftboard", ephemeral=True
        )

# view, edit, or delete draft board if user already has a created one
@bot.tree.command(name='manage_draftboard', description='View, Edit, or Delete your Personal Fantasy Football Draft Board')
async def manage_draftboard(interaction: discord.Interaction):
    user_id = interaction.user.id
    check = await check_exists(user_id)
    if check:
        existing_players = await load_existing(user_id)
        view = DraftBoardViewWithoutSelect(existing_players)

        await interaction.response.send_message(
            content=view.create_draft_board_message(), view=view
        )
    else:
        await interaction.response.send_message(
            content="You do not have a draft board saved under this account. Try /create_draftboard", ephemeral=True
        )

# autocomplete function for players' names
async def player_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    storage = sqlite3.connect('draft_board.db')
    cursor = storage.cursor()
    parts = current.split()
    if len(parts) == 1:
        query = "SELECT player FROM last_year_stats WHERE player LIKE ? OR player LIKE ? LIMIT 20"
        cursor.execute(query, (f'{parts[0]}%', f'% {parts[0]}%'))
    elif len(parts) > 1:
        query = "SELECT player FROM last_year_stats WHERE player LIKE ? LIMIT 20"
        cursor.execute(query, (f'{parts[0]}% {parts[1]}%',))

    results = cursor.fetchall()
    storage.close()

    choices = [discord.app_commands.Choice(name=player[0], value=player[0]) for player in results]
    return choices

# retrieves player's stats from last season from the database and displays them for a player chosen by the user
@bot.tree.command(name='last_season_stats', description="View a player's fantasy football stats from the 2023-24 season")
@app_commands.describe(player="Enter the player whose stats you'd like to view")
async def last_season_stats(interaction: discord.Interaction, player: str):
    with sqlite3.connect("draft_board.db") as storage:
        cursor = storage.cursor()
        query = 'SELECT points_per_game, ranking, games_played FROM last_year_stats WHERE player=?'
        cursor.execute(query, (player,))
        player_info = cursor.fetchall()

    if not player_info:
        await interaction.response.send_message(f'There are no recorded stats for {player}. Check your spelling.', ephemeral=True)
    else:
        ppg, rank, games_played = player_info[0]

        stats_embed = discord.Embed(title=f"{player}'s 2023-24 Stats", color=0x00ffd5)
        stats_embed.add_field(name='Rank', value=rank, inline=False)
        stats_embed.add_field(name='Fantasy Points per Game', value=ppg, inline=False)
        stats_embed.add_field(name='Games Played', value=games_played, inline=False)

        await interaction.response.send_message(embed=stats_embed, ephemeral=True)

# adds autocompletion for last_season_stats 'player' field
@last_season_stats.autocomplete('player')
async def last_season_stats_player_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return await player_autocomplete(interaction, current)

# user can compare two players projected fantasy football stats for a given week
@bot.tree.command(name='start_or_sit', description="Compare two players' projected fantasy performance for a given week")
@app_commands.describe(player1="Enter the first player you'd like to compare")
@app_commands.describe(player2="Enter the second player you'd like to compare")
@app_commands.describe(week="Enter the week you'd like to compare stats in")
async def start_or_sit(interaction: discord.Interaction, player1: str, player2: str, week: str):
    await interaction.response.send_message("Gathering information, please wait...", ephemeral=True)
    initial_message = await interaction.original_response()
    # get ranking (just need position) from database of players
    with sqlite3.connect('draft_board.db') as storage:
        cursor = storage.cursor()
        query = "SELECT ranking FROM last_year_stats WHERE player=?"
        cursor.execute(query, (player1,))
        pos1 = cursor.fetchall()
        cursor.execute(query, (player2,))
        pos2 = cursor.fetchall()

    # format position ranking to be position ex: QB1 -> qb
    if pos1:
        position1 = pos1[0][0][:2].lower()
    elif not pos2:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {player1} or {player2} in our database. Try selecting a player from the drop down menu.")
        return
    else:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {player1} in our database. Try selecting a player from the drop down menu.")
        return
    if pos2:
        position2 = pos2[0][0][:2].lower()
    else:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {player2} in our database. Try selecting a player from the drop down menu.")
        return

    if int(week) > 17 or int(week) < 1:
        await interaction.followup.edit_message(initial_message.id, content=f"Please enter a week from 1-17. You entered: {week}")
        return
    else:
        # get consensus player projections for user chosen players and week
        url1 = requests.get(f"https://www.fantasypros.com/nfl/projections/{position1}.php?week={week}&scoring=PPR")
        url2 = requests.get(f"https://www.fantasypros.com/nfl/projections/{position2}.php?week={week}&scoring=PPR")
        doc1 = BeautifulSoup(url1.text, "html.parser")
        doc2 = BeautifulSoup(url2.text, "html.parser")
        player1_info = doc1.findAll("td")
        player2_info = doc2.findAll("td")

        # formatting for data scrape
        pos1_offset = 0
        if position1 == "qb":
            pos1_offset = 10
        elif position1 == "wr":
            pos1_offset = 8
        elif position1 == "rb":
            pos1_offset = 8
        elif position1 == "te":
            pos1_offset = 5

        found1 = False
        team1 = ''
        projection1 = ''

        for i in range(len(player1_info)):
            if found1:
                break
            if player1 in player1_info[i].text:
                team1 = player1_info[i].text
                team1 = team1[-3:].strip()
                found1 = True
                projection1 = player1_info[i + pos1_offset].text

        pos2_offset = 0
        if position2 == "qb":
            pos2_offset = 10
        elif position2 == "wr":
            pos2_offset = 8
        elif position2 == "rb":
            pos2_offset = 8
        elif position2 == "te":
            pos2_offset = 5

        found2 = False
        team2 = ''
        projection2 = ''

        for i in range(len(player2_info)):
            if found2:
                break
            if player2 in player2_info[i].text:
                team2 = player2_info[i].text
                team2 = team2[-3:].strip()
                found2 = True
                projection2 = player2_info[i + pos2_offset].text

        if not projection1:
            if not projection1:
                await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find any projections for {player1} or {player2} :(")
                return
            await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find any projections for {player1} :(")
            return
        if not projection2:
            await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find any projections for {player2} :(")
            return

        # get game information (time, date, home team, away team, week) from database for relevant games
        with sqlite3.connect("draft_board.db") as schedule_storage:
            if 'JAC' in team1:
                team1 = "JAX"
            if 'JAC' in team2:
                team2 = "JAX"
            formatted_week = f"Week {week}"
            cursor1 = schedule_storage.cursor()
            query1 = "SELECT * FROM schedules WHERE (home_team = ? OR away_team = ?) AND week=?"
            cursor1.execute(query1,(team1, team1, formatted_week))
            info1 = cursor1.fetchall()
            cursor1.execute(query1,(team2, team2, formatted_week))
            info2 = cursor1.fetchall()

        if not info1:
            if not info2:
                await interaction.followup.edit_message(initial_message.id, content=f"{player1} and {player2} Don't have a scheduled matches this week!")
                return
            await interaction.followup.edit_message(initial_message.id, content=f"{player1} Doesn't have a scheduled match this week!")
            return
        elif not info2:
            await interaction.followup.edit_message(initial_message.id, content=f"{player2} Doesn't have a scheduled match this week!")
            return

        # unpack tuple with game info
        home1, away1, time1, date1, week1, trash1 = info1[0]
        home2, away2, time2, date2, week2, trash2 = info2[0]

        # display information to user in an embed
        compare_embed = discord.Embed(title=f"{formatted_week} Player Comparison", color=discord.Color.orange())
        compare_embed.add_field(name=player1, value='', inline=False)
        compare_embed.add_field(name="Game Info", value=f"{away1} @ {home1} \n{date1} at {time1}", inline=False)
        compare_embed.add_field(name="Projected Points", value=projection1, inline=False)
        compare_embed.add_field(name=player2, value='', inline=False)
        compare_embed.add_field(name="Game Info", value=f"{away2} @ {home2} \n{date2} at {time2}", inline=False)
        compare_embed.add_field(name="Projected Points", value=projection2, inline=False)

        await interaction.followup.edit_message(initial_message.id, content=None, embed=compare_embed)

# adds autocompletion for the players in the start_or_sit command
@start_or_sit.autocomplete('player1')
async def start_or_sit_player1_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return await player_autocomplete(interaction, current)

@start_or_sit.autocomplete('player2')
async def start_or_sit_player2_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return await player_autocomplete(interaction, current)

# adds autocompletion for the week in the start_or_sit command
@start_or_sit.autocomplete('week')
async def start_or_sit_week_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    weeks = [f"{i}" for i in range(1, 18)]
    if current.isdigit():
        filtered_weeks = [week for week in weeks if current in week]
    else:
        filtered_weeks = [week for week in weeks if current.lower() in week.lower()]

    choices = [discord.app_commands.Choice(name=week, value=week) for week in filtered_weeks]
    return choices

@bot.tree.command(name='trade_analyzer', description="Enter a proposed trade to see if our projections think it's to your benefit or not")
@app_commands.describe(giving1='Enter a player you are trading away')
@app_commands.describe(giving2='Enter a player you are trading away')
@app_commands.describe(giving3='Enter a player you are trading away')
@app_commands.describe(giving4='Enter a player you are trading away')
@app_commands.describe(giving5='Enter a player you are trading away')
@app_commands.describe(receiving1='Enter a player you are trading for')
@app_commands.describe(receiving2='Enter a player you are trading for')
@app_commands.describe(receiving3='Enter a player you are trading for')
@app_commands.describe(receiving4='Enter a player you are trading for')
@app_commands.describe(receiving5='Enter a player you are trading for')
async def trade_analyzer(interaction: discord.Interaction, giving1: str = None, giving2: str = None, giving3: str = None, giving4: str = None, giving5: str = None, receiving1: str = None, receiving2: str = None, receiving3: str = None, receiving4: str = None, receiving5: str = None):
    await interaction.response.send_message("Gathering information, please wait...", ephemeral=True)
    initial_message = await interaction.original_response()

    # store user input in a list
    giving_player = []
    receiving_player = []
    giving_count = 0
    receiving_count = 0

    if giving1:
        giving_count += 1
        giving_player.append(giving1)
    if giving2:
        giving_count += 1
        giving_player.append(giving2)
    if giving3:
        giving_count += 1
        giving_player.append(giving3)
    if giving4:
        giving_count += 1
        giving_player.append(giving4)
    if giving5:
        giving_count += 1
        giving_player.append(giving5)

    if receiving1:
        receiving_count += 1
        receiving_player.append(receiving1)
    if receiving2:
        receiving_count += 1
        receiving_player.append(receiving2)
    if receiving3:
        receiving_count += 1
        receiving_player.append(receiving3)
    if receiving4:
        receiving_count += 1
        receiving_player.append(receiving4)
    if receiving5:
        receiving_count += 1
        receiving_player.append(receiving5)

    if len(giving_player) == 0 or len(receiving_player) == 0:
        await interaction.followup.edit_message(initial_message.id, content=f"Please enter at least one player that you are trading away (giving) as well as trading for (recieving)")
        return
    # get ranking (just need position) from database of players
    giving_pos = []
    receiving_pos = []

    for i in range(0, len(giving_player)):
        with sqlite3.connect('draft_board.db') as storage:
            cursor = storage.cursor()
            query = "SELECT ranking FROM last_year_stats WHERE player=?"
            cursor.execute(query, (giving_player[i],))
            temp = cursor.fetchall()
            if temp:
                temp = temp[0][0][:2]
                giving_pos.append(temp)
            else:
                await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {giving_player[i]} in our database. Try selecting a player from the drop down menu.")
                return

    for i in range(0, len(receiving_player)):
        with sqlite3.connect('draft_board.db') as storage:
            cursor = storage.cursor()
            query = "SELECT ranking FROM last_year_stats WHERE player=?"
            cursor.execute(query, (receiving_player[i],))
            temp = cursor.fetchall()
            if temp:
                temp = temp[0][0][:2]
                receiving_pos.append(temp)
            else:
                await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {receiving_player[i]} in our database. Try selecting a player from the drop down menu.")
                return

    giving_score = []
    receiving_score = []

    for i in range(0, len(giving_player)):
        giving_score.append(await calculate_trade_value(giving_player[i], giving_pos[i]))
        if giving_score[i] == -1:
            await interaction.followup.edit_message(initial_message.id, content=f"Unfortunately we couldn't find {giving_player[i]} in our database.")
            return

    for i in range(0, len(receiving_player)):
        receiving_score.append(await calculate_trade_value(receiving_player[i], receiving_pos[i]))
        if receiving_score[i] == -1:
            await interaction.followup.edit_message(initial_message.id, content=f"Unfortunately we couldn't find {receiving_player[i]} in our database.")
            return

    giving_score_string = ''
    receiving_score_string = ''
    giving_player_string = ''
    receiving_player_string = ''
    giving_sum = 0.0
    receiving_sum = 0.0

    for i in range(0, len(giving_score)):
        giving_sum += giving_score[i]
        giving_player_string += giving_player[i] + '\n'
        giving_score_string += str(round(giving_score[i], 2)) + '\n'

    for i in range(0, len(receiving_score)):
        receiving_sum += receiving_score[i]
        receiving_player_string += receiving_player[i] + '\n'
        receiving_score_string += str(round(receiving_score[i], 2)) + '\n'

        difference = giving_sum - receiving_sum
        outcome = ''

        if difference > 4:
            if difference < 12:
                outcome = "It's close, but the trade doesn't favor your team"
            else:
                outcome = "Based on our projections, you shouldn't make this trade"
        elif difference < -4:
            if difference > -12:
                outcome = "The trade favors your team, but not by a lot"
            else:
                outcome = "Great trade, we think you should do it"
        else:
            outcome = "This one's a toss up, go with team needs"

        # display information to user in an embed
        trade_embed = discord.Embed(title=outcome, color=discord.Color.brand_red())
        trade_embed.add_field(name="Trading Away", value=giving_player_string, inline=True)
        trade_embed.add_field(name=f"{giving_sum:.2f}", value=giving_score_string, inline=True)
        trade_embed.add_field(name="\u200b", value="\u200b", inline=False)
        trade_embed.add_field(name="Trading For", value=receiving_player_string, inline=True)
        trade_embed.add_field(name=f"{receiving_sum:.2f}", value=receiving_score_string, inline=True)


        await interaction.followup.edit_message(initial_message.id, content=None, embed=trade_embed)

async def calculate_trade_value(player1, position):
    url = requests.get("https://www.numberfire.com/nfl/fantasy/remaining-projections")
    doc = BeautifulSoup(url.text, "html.parser")
    player_name = doc.findAll("span", attrs="full")
    positions = doc.findAll("td", attrs="player")
    fpts = doc.findAll("td", attrs="nf_fp active")
    receptions = doc.findAll("td", attrs='rec')

    proj = ''
    recs = ''
    i = 0
    j = 1
    posCount = 0
    posSum = 0.0
    posRank = 0
    posRange = 12
    if position == 'WR' or position == 'RB':
        posRange = 24

    # hotfix for issue inconsistency in database
    if player1 == 'Michael Pittman':
        player1 = 'Michael Pittman Jr.'

    for player in player_name:
        if player1 in player:
            recs = receptions[i].text.strip()
            proj = fpts[i].text.strip()
            posRank = j
        if position in positions[i].text:
            if posCount < posRange:
                posSum += (float(fpts[i].text.strip())) + (float(receptions[i].text.strip()))
                posCount += 1
            j += 1
        i += 1
    if proj == '':
        return -1

    if recs == '':
        return -1

    proj = (float(proj) + float(recs))
    posAvg = posSum / posRange
    offset = 0

    # top 3 qbs and tes, top 6 wrs and rbs
    if posRank <= (posRange / 4):
        offset = (proj - posAvg) + (((posRange / 2) - posRank) * 10)
    # top 8 qbs and tes, top 16 wrs and rbs
    elif posRank <= (posRange * (2 / 3)):
        offset = (proj - posAvg) + ((posRange / 2) - posRank)
    # top 18 qbs and tes, top 36 wrs and rbs
    elif posRank < (posRange * 1.5):
        offset += ((proj - posAvg) * 0.8) + (((posRange / 2) - posRank) * 4)
    # bench players
    else:
        offset += ((proj - posAvg) * 0.8) + (((posRange / 2) - posRank) * 2)

    value = (proj + float(recs) + offset) / 15

    if position == 'QB':
        value = value * 0.75
    if value < 1:
        value = 1.00
    value = round(value, 2)
    if value:
        return value
    else:
        return -1


# autocomplete for trade_analyzer command
@trade_analyzer.autocomplete('giving1')
@trade_analyzer.autocomplete('giving2')
@trade_analyzer.autocomplete('giving3')
@trade_analyzer.autocomplete('giving4')
@trade_analyzer.autocomplete('giving5')
@trade_analyzer.autocomplete('receiving1')
@trade_analyzer.autocomplete('receiving2')
@trade_analyzer.autocomplete('receiving3')
@trade_analyzer.autocomplete('receiving4')
@trade_analyzer.autocomplete('receiving5')
async def trade_analyzer_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return await player_autocomplete(interaction, current)


# closes the connection when the bot shuts down
@bot.event
async def on_disconnect():
    storage.close()

# runs the bot
bot.run(TOKEN)