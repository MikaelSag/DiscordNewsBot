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

async def get_logo(team):

    team_logos = {
        'ARI': 'https://loodibee.com/wp-content/uploads/nfl-arizona-cardinals-team-logo-2-768x768.png',
        'ATL': 'https://loodibee.com/wp-content/uploads/nfl-atlanta-falcons-team-logo-2-768x768.png',
        'BAL': 'https://loodibee.com/wp-content/uploads/nfl-baltimore-ravens-team-logo-2-768x768.png',
        'BUF': 'https://loodibee.com/wp-content/uploads/nfl-buffalo-bills-team-logo-2-768x768.png',
        'CAR': 'https://loodibee.com/wp-content/uploads/nfl-carolina-panthers-team-logo-2-768x768.png',
        'CHI': 'https://loodibee.com/wp-content/uploads/nfl-chicago-bears-team-logo-2-768x768.png',
        'CIN': 'https://loodibee.com/wp-content/uploads/nfl-cincinnati-bengals-team-logo-768x768.png',
        'CLE': 'https://loodibee.com/wp-content/uploads/nfl-cleveland-browns-team-logo-2-768x768.png',
        'DAL': 'https://loodibee.com/wp-content/uploads/nfl-dallas-cowboys-team-logo-2-768x768.png',
        'DEN': 'https://loodibee.com/wp-content/uploads/nfl-denver-broncos-team-logo-2-768x768.png',
        'DET': 'https://loodibee.com/wp-content/uploads/nfl-detroit-lions-team-logo-2-768x768.png',
        'GB': 'https://loodibee.com/wp-content/uploads/nfl-green-bay-packers-team-logo-2-768x768.png',
        'HOU': 'https://loodibee.com/wp-content/uploads/nfl-houston-texans-team-logo-2-768x768.png',
        'IND': 'https://loodibee.com/wp-content/uploads/nfl-indianapolis-colts-team-logo-2-768x768.png',
        'JAC': 'https://loodibee.com/wp-content/uploads/nfl-jacksonville-jaguars-team-logo-2-768x768.png',
        'KC': 'https://loodibee.com/wp-content/uploads/nfl-kansas-city-chiefs-team-logo-2-768x768.png',
        'LV': 'https://loodibee.com/wp-content/uploads/nfl-oakland-raiders-team-logo-768x768.png',
        'LAC': 'https://loodibee.com/wp-content/uploads/nfl-los-angeles-chargers-team-logo-2-768x768.png',
        'LAR': 'https://loodibee.com/wp-content/uploads/los-angeles-rams-2020-logo-300x300.png',
        'MIA': 'https://loodibee.com/wp-content/uploads/Miami-Dolphins-Logo-480x480.png',
        'MIN': 'https://loodibee.com/wp-content/uploads/nfl-minnesota-vikings-team-logo-2-768x768.png',
        'NE': 'https://loodibee.com/wp-content/uploads/nfl-new-england-patriots-team-logo-2-768x768.png',
        'NO': 'https://loodibee.com/wp-content/uploads/nfl-new-orleans-saints-team-logo-2-768x768.png',
        'NYG': 'https://loodibee.com/wp-content/uploads/nfl-new-york-giants-team-logo-2-768x768.png',
        'NYJ': 'https://loodibee.com/wp-content/uploads/nfl-new-york-jets-team-logo-768x768.png',
        'PHI': 'https://loodibee.com/wp-content/uploads/nfl-philadelphia-eagles-team-logo-2-768x768.png',
        'PIT': 'https://loodibee.com/wp-content/uploads/nfl-pittsburgh-steelers-team-logo-2-768x768.png',
        'SF': 'https://loodibee.com/wp-content/uploads/nfl-san-francisco-49ers-team-logo-2-768x768.png',
        'SEA': 'https://loodibee.com/wp-content/uploads/nfl-seattle-seahawks-team-logo-2-768x768.png',
        'TB': 'https://loodibee.com/wp-content/uploads/tampa-bay-buccaneers-2020-logo-480x480.png',
        'TEN': 'https://loodibee.com/wp-content/uploads/nfl-tennessee-titans-team-logo-2-768x768.png',
        'WAS': 'https://loodibee.com/wp-content/uploads/washington-commanders-logo-480x480.png'
    }

    logo = team_logos.get(team, "")
    return logo

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
        query = 'SELECT points_per_game, ranking, games_played, stat1, stat2, stat3, stat4, stat5, stat6 FROM last_year_stats WHERE player=?'
        cursor.execute(query, (player,))
        player_info = cursor.fetchall()

    if not player_info:
        await interaction.response.send_message(f'There are no recorded stats for {player}. Check your spelling.', ephemeral=True)
    else:
        ppg, rank, games_played, stat1, stat2, stat3, stat4, stat5, stat6 = player_info[0]

        if 'QB' in rank:
            stat1_name = 'Passing Yards'
            stat2_name = 'Passing TDs'
            stat3_name = 'Interceptions'
            stat4_name = 'Rushing Attempts'
            stat5_name = 'Rushing Yards'
            stat6_name = 'Rushing TDs'
        elif 'RB' in rank:
            stat1_name = 'Rushing Attempts'
            stat2_name = 'Rushing Yards'
            stat3_name = 'Total TDs'
            stat4_name = 'Targets'
            stat5_name = 'Receptions'
            stat6_name = 'Receiving Yards'
        elif 'WR' in rank:
            stat1_name = 'Targets'
            stat2_name = 'Receptions'
            stat3_name = 'Receiving Yards'
            stat4_name = 'Total TDs'
            stat5_name = 'Rushing Attempts'
            stat6_name = 'Rushing Yards'
        elif 'TE' in rank:
            stat1_name = 'Targets'
            stat2_name = 'Catches'
            stat3_name = 'Receiving Yards'
            stat4_name = 'Receiving TDs'
            stat5_name = 'null'
            stat6_name = 'null'

        position = rank[:2]
        url = requests.get(f"https://www.cbssports.com/fantasy/football/stats/{position}/2023/season/stats/ppr/")
        doc = BeautifulSoup(url.text, "html.parser")
        player_names = doc.findAll("span", attrs="CellPlayerName--long")

        for name in player_names:
            if player in name.text:
                playerStr = name.text
                break
        playerStr = playerStr.strip()
        team = playerStr[-3:].strip()

        logo = await get_logo(team)
        if not logo:
            logo = "https://seeklogo.com/images/N/nfl-logo-B2C95E8E88-seeklogo.com.png"

        stats_embed = discord.Embed(title=f"{player}'s 2023-24 Stats", color=0x00ffd5)
        stats_embed.set_author(name="Fantasy Football Bot", icon_url=logo)
        stats_embed.add_field(name='Rank', value=rank, inline=True)
        stats_embed.add_field(name='Fantasy PPG', value=ppg, inline=True)
        stats_embed.add_field(name='Games Played', value=games_played, inline=True)
        stats_embed.add_field(name='', value='', inline=False)
        if 'null' not in stat5_name:
            stats_embed.add_field(name=stat1_name, value=stat1, inline=True)
            stats_embed.add_field(name=stat4_name, value=stat4, inline=True)
            stats_embed.add_field(name='', value='', inline=False)
            stats_embed.add_field(name=stat2_name, value=stat2, inline=True)
            stats_embed.add_field(name=stat5_name, value=stat5, inline=True)
            stats_embed.add_field(name='', value='', inline=False)
            stats_embed.add_field(name=stat3_name, value=stat3, inline=True)
            stats_embed.add_field(name=stat6_name, value=stat6, inline=True)
        else:
            stats_embed.add_field(name=stat1_name, value=stat1, inline=True)
            stats_embed.add_field(name=stat3_name, value=stat3, inline=True)
            stats_embed.add_field(name='', value='', inline=False)
            stats_embed.add_field(name=stat2_name, value=stat2, inline=True)
            stats_embed.add_field(name=stat4_name, value=stat4, inline=True)

        stats_embed.add_field(name='', value='', inline=False)
        stats_embed.timestamp = datetime.now()
        stats_embed.set_footer(text='Last Season Stats')

        await interaction.response.send_message(embed=stats_embed, ephemeral=True)

# adds autocompletion for last_season_stats 'player' field
@last_season_stats.autocomplete('player')
async def last_season_stats_player_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return await player_autocomplete(interaction, current)

# retrieves player's stats from last season from the database and displays them for a player chosen by the user
@bot.tree.command(name='current_stats', description="View a player's fantasy football stats from this season (2024-25)")
@app_commands.describe(player="Enter the player whose stats you'd like to view")
async def current_stats(interaction: discord.Interaction, player: str):
    await interaction.response.send_message("Gathering information, please wait...", ephemeral=True)
    initial_message = await interaction.original_response()
    with sqlite3.connect("draft_board.db") as storage:
        cursor = storage.cursor()
        query = 'SELECT ranking FROM last_year_stats WHERE player=?'
        cursor.execute(query, (player,))
        player_info = cursor.fetchall()

    if not player_info:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find {player} in our database :(")
        return
    else:
        position = player_info[0][0][:2]
    if 'QB' in position:
        stat1_name = 'Passing Yards'
        stat2_name = 'Passing TDs'
        stat3_name = 'Interceptions'
        stat4_name = 'Rushing Attempts'
        stat5_name = 'Rushing Yards'
        stat6_name = 'Rushing TDs'
    elif 'RB' in position:
        stat1_name = 'Rushing Attempts'
        stat2_name = 'Rushing Yards'
        stat3_name = 'Total TDs'
        stat4_name = 'Targets'
        stat5_name = 'Receptions'
        stat6_name = 'Receiving Yards'
    elif 'WR' in position:
        stat1_name = 'Targets'
        stat2_name = 'Receptions'
        stat3_name = 'Receiving Yards'
        stat4_name = 'Total TDs'
        stat5_name = 'Rushing Attempts'
        stat6_name = 'Rushing Yards'
    elif 'TE' in position:
        stat1_name = 'Targets'
        stat2_name = 'Catches'
        stat3_name = 'Receiving Yards'
        stat4_name = 'Receiving TDs'
        stat5_name = 'null'
        stat6_name = 'null'
    else:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find any stats for {player}")
        return

    url = requests.get(f"https://www.cbssports.com/fantasy/football/stats/{position}/2024/season/stats/ppr/")
    doc = BeautifulSoup(url.text, "html.parser")
    player_names = doc.findAll("span", attrs="CellPlayerName--long")
    stats = doc.findAll("td", attrs="TableBase-bodyTd")
    playerStr = ''
    # get player index
    i = 0
    for name in player_names:
        if player in name.text:
            playerStr = name.text
            break
        i += 1

    if not playerStr:
        await interaction.followup.edit_message(initial_message.id, content=f"We couldn't find any stats for {player}")
        return

    playerStr = playerStr.strip()
    team = playerStr[-3:].strip()

    rank = position + str(i + 1)

    # offsets based on position
    if 'QB' in position:
        pos_multi = 16
        offset1 = 1
        offset2 = 4
        offset3 = 6
        offset4 = 7
        offset5 = 9
        offset6 = 10
        offset7 = 12
        offset8 = 15
    elif 'RB' in position:
        pos_multi = 15
        offset1 = 1
        offset2 = 2
        offset3 = 3
        offset4 = 5
        offset5 = 6
        offset6 = 7
        offset7 = 8
        offset8 = 11
        offset9 = 14
    elif 'WR' in position:
        pos_multi = 15
        offset1 = 1
        offset2 = 2
        offset3 = 3
        offset4 = 4
        offset5 = 7
        offset6 = 8
        offset7 = 9
        offset8 = 11
        offset9 = 14
    elif 'TE' in position:
        pos_multi = 11
        offset1 = 1
        offset2 = 2
        offset3 = 3
        offset4 = 4
        offset5 = 7
        offset6 = 10

    # get stats
    games_played = stats[i * pos_multi + offset1].text.strip()
    stat1 = stats[i * pos_multi + offset2].text.strip()
    stat2 = stats[i * pos_multi + offset3].text.strip()
    stat3 = stats[i * pos_multi + offset4].text.strip()
    stat4 = stats[i * pos_multi + offset5].text.strip()
    if 'TE' in position:
        ppg = stats[i * pos_multi + offset6].text.strip()
    else:
        stat5 = stats[i * pos_multi + offset6].text.strip()
        stat6 = stats[i * pos_multi + offset7].text.strip()
        if 'QB' in position:
            ppg = stats[i * pos_multi + offset8].text.strip()
        elif 'RB' in position or 'WR' in position:
            stat_add = stats[i * pos_multi + offset8].text.strip()
            ppg = stats[i * pos_multi + offset9].text.strip()

    if 'RB' in position:
        if '—' not in stat3 or '—' not in stat_add:
            stat3 = str(int(stat3) + int(stat_add))

    if 'WR' in position:
        if '—' not in stat4 or '—' not in stat_add:
            stat4 = str(int(stat4) + int(stat_add))

    logo = await get_logo(team)
    if not logo:
        logo = "https://seeklogo.com/images/N/nfl-logo-B2C95E8E88-seeklogo.com.png"

    stats_embed = discord.Embed(title=f"{player}'s 2024-25 Stats", color=discord.Color.brand_green())
    stats_embed.set_author(name="Fantasy Football Bot", icon_url=logo)
    stats_embed.add_field(name='Rank', value=rank, inline=True)
    stats_embed.add_field(name='Fantasy PPG', value=ppg, inline=True)
    stats_embed.add_field(name='Games Played', value=games_played, inline=True)
    stats_embed.add_field(name='', value='', inline=False)
    if 'null' not in stat5_name:
        stats_embed.add_field(name=stat1_name, value=stat1, inline=True)
        stats_embed.add_field(name=stat4_name, value=stat4, inline=True)
        stats_embed.add_field(name='', value='', inline=False)
        stats_embed.add_field(name=stat2_name, value=stat2, inline=True)
        stats_embed.add_field(name=stat5_name, value=stat5, inline=True)
        stats_embed.add_field(name='', value='', inline=False)
        stats_embed.add_field(name=stat3_name, value=stat3, inline=True)
        stats_embed.add_field(name=stat6_name, value=stat6, inline=True)
    else:
        stats_embed.add_field(name=stat1_name, value=stat1, inline=True)
        stats_embed.add_field(name=stat3_name, value=stat3, inline=True)
        stats_embed.add_field(name='', value='', inline=False)
        stats_embed.add_field(name=stat2_name, value=stat2, inline=True)
        stats_embed.add_field(name=stat4_name, value=stat4, inline=True)

    stats_embed.add_field(name='', value='', inline=False)
    stats_embed.timestamp = datetime.now()
    stats_embed.set_footer(text='Current Stats')

    await interaction.followup.edit_message(initial_message.id, content=None, embed=stats_embed)

@current_stats.autocomplete('player')
async def current_stats_player_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
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

        if position1 == 'qb':
            url3 = requests.get(f"https://www.fantasypros.com/nfl/reports/boom-bust-qb.php")
        else:
            url3 = requests.get(f"https://www.fantasypros.com/nfl/reports/ppr-boom-bust-{position1}.php")
        if position2 == 'qb':
            url4 = requests.get(f"https://www.fantasypros.com/nfl/reports/boom-bust-qb.php")
        else:
            url4 = requests.get(f"https://www.fantasypros.com/nfl/reports/ppr-boom-bust-{position2}.php")

        doc1 = BeautifulSoup(url1.text, "html.parser")
        doc2 = BeautifulSoup(url2.text, "html.parser")
        doc3 = BeautifulSoup(url3.text, "html.parser")
        doc4 = BeautifulSoup(url4.text, "html.parser")

        player1_info = doc1.findAll("td")
        player2_info = doc2.findAll("td")
        player1_bust = doc3.findAll("td")
        player2_bust = doc4.findAll("td")

        # get boom and bust percentages
        check1 = False
        check2 = False
        boom1 = ''
        bust1 = ''
        i = 0
        for player in player1_bust:
            if check2 and '%' not in player.text:
                bust1 = player1_bust[i - 2].text
                break
            if check1 and '%' in player.text and not check2:
                check2 = True
                boom1 = player.text
            if player1 in player.text:
                check1 = True
            i += 1

        check1 = False
        check2 = False
        boom2 = ''
        bust2 = ''
        i = 0
        for player in player2_bust:
            if check2 and '%' not in player.text:
                bust2 = player2_bust[i - 2].text
                break
            if check1 and '%' in player.text and not check2:
                check2 = True
                boom2 = player.text
            if player2 in player.text:
                check1 = True
            i += 1

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

        position1 = position1.upper()
        position2 = position2.upper()

        url5 = requests.get(f"https://www.cbssports.com/fantasy/football/stats/{position1}/2024/season/stats/ppr/")
        doc5 = BeautifulSoup(url5.text, "html.parser")
        player_names1 = doc5.findAll("span", attrs="CellPlayerName--long")

        url6 = requests.get(f"https://www.cbssports.com/fantasy/football/stats/{position2}/2024/season/stats/ppr/")
        doc6 = BeautifulSoup(url6.text, "html.parser")
        player_names2 = doc6.findAll("span", attrs="CellPlayerName--long")

        x = 0
        found1 = False
        for name in player_names1:
            if player1 in name.text:
                found1 = True
                break
            x += 1

        y = 0
        found2 = False
        for name in player_names2:
            if player2 in name.text:
                found2 = True
                break
            y += 1

        if found1:
            rank1 = position1 + str(x+1)
        else:
            rank1 = position1 + '--'
        if found2:
            rank2 = position2 + str(y+1)
        else:
            rank2 = position2 + '--'

        # unpack tuple with game info
        home1, away1, time1, date1, week1, trash1 = info1[0]
        home2, away2, time2, date2, week2, trash2 = info2[0]
        if not boom1:
            boom1 = '—'
        if not bust1:
            bust1 = '—'
        if not boom2:
            boom2 = '—'
        if not bust2:
            bust2 = '—'

        # display information to user in an embed
        compare_embed = discord.Embed(title=f"{formatted_week} Player Comparison", color=discord.Color.orange())
        compare_embed.set_author(name="Fantasy Football Bot", icon_url="https://seeklogo.com/images/N/nfl-logo-B2C95E8E88-seeklogo.com.png")
        compare_embed.add_field(name=f"**{player1}**", value="", inline=True)
        compare_embed.add_field(name=f"{position1.upper()} • {team1}", value='', inline=True)
        compare_embed.add_field(name="Game Info", value=f"{away1} @ {home1} \n{date1} at {time1}", inline=False)
        compare_embed.add_field(name="Projected Points", value=projection1, inline=True)
        compare_embed.add_field(name="Current Rank", value=rank1, inline=True)
        compare_embed.add_field(name='', value='', inline=False)
        compare_embed.add_field(name="Boom Chance", value=boom1, inline=True)
        compare_embed.add_field(name="Bust Chance", value=bust1, inline=True)
        compare_embed.add_field(name="", value="----------------------------------", inline=False)
        compare_embed.add_field(name=f"**{player2}**", value='', inline=True)
        compare_embed.add_field(name=f"{position2.upper()} • {team2}", value='', inline=True)
        compare_embed.add_field(name="Game Info", value=f"{away2} @ {home2} \n{date2} at {time2}", inline=False)
        compare_embed.add_field(name="Projected Points", value=projection2, inline=True)
        compare_embed.add_field(name="Current Rank", value=rank2, inline=True)
        compare_embed.add_field(name="", value="", inline=False)
        compare_embed.add_field(name="Boom Chance", value=boom2, inline=True)
        compare_embed.add_field(name="Bust Chance", value=bust2, inline=True)
        compare_embed.add_field(name='', value='', inline=False)
        compare_embed.timestamp = datetime.now()
        compare_embed.set_footer(text='Start or Sit')

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
    giving_team = []
    giving_rank = []
    receiving_score = []
    receiving_team = []
    receiving_rank = []

    for i in range(0, len(giving_player)):
        giving_score.append(await calculate_trade_value(giving_player[i], giving_pos[i], giving_team, giving_rank))
        if giving_score[i] == -1:
            await interaction.followup.edit_message(initial_message.id, content=f"Unfortunately we couldn't find {giving_player[i]} in our database.")
            return

    for i in range(0, len(receiving_player)):
        receiving_score.append(await calculate_trade_value(receiving_player[i], receiving_pos[i], receiving_team, receiving_rank))
        if receiving_score[i] == -1:
            await interaction.followup.edit_message(initial_message.id, content=f"Unfortunately we couldn't find {receiving_player[i]} in our database.")
            return

    giving_score_string = ''
    receiving_score_string = ''
    giving_player_string = ''
    receiving_player_string = ''
    giving_rank_string = ''
    receiving_rank_string = ''
    giving_sum = 0.0
    receiving_sum = 0.0

    for i in range(0, len(giving_score)):
        temp = giving_score[i]
        giving_sum += giving_score[i]
        giving_player_string += f"{giving_player[i]}  ({giving_team[i]})\n"
        giving_score_string += f"{temp:.2f} \n"
        giving_rank_string += giving_rank[i] + '\n'

    if len(giving_player) > 1:
        giving_score_string += f"**{giving_sum:.2f}**"

    for i in range(0, len(receiving_score)):
        temp = receiving_score[i]
        receiving_sum += receiving_score[i]
        receiving_player_string += f"{receiving_player[i]}  ({receiving_team[i]})\n"
        receiving_score_string += f"{temp:.2f} \n"
        receiving_rank_string += receiving_rank[i] + '\n'

    if len(receiving_player) > 1:
        receiving_score_string += f"**{receiving_sum:.2f}**"

    difference = giving_sum - receiving_sum
    outcome = ''

    if difference > 3:
        if difference < 7.5:
            outcome = "It's close, but the trade doesn't favor your team"
        else:
            outcome = "We wouldn't recommend this trade"
    elif difference < -3:
        if difference > -7.5:
            outcome = "The trade favors your team, but not by a lot"
        else:
            outcome = "Great trade, we think you should do it"
    else:
        outcome = "This one's a toss up, go with team needs"

    multi = int(1.2 * len(outcome))
    linebreak = multi * '-'

    # display information to user in an embed
    trade_embed = discord.Embed(title=outcome, color=discord.Color.brand_red())
    trade_embed.set_author(name="Fantasy Football Bot", icon_url="https://seeklogo.com/images/N/nfl-logo-B2C95E8E88-seeklogo.com.png")
    trade_embed.add_field(name=f"Trading Away", value=giving_player_string, inline=True)
    trade_embed.add_field(name="ROS Ranking", value=giving_rank_string, inline=True)
    trade_embed.add_field(name=f"Trade Value", value=giving_score_string, inline=True)
    trade_embed.add_field(name='', value=linebreak, inline=False)
    trade_embed.add_field(name=f"Trading For", value=receiving_player_string, inline=True)
    trade_embed.add_field(name="ROS Ranking", value=receiving_rank_string, inline=True)
    trade_embed.add_field(name=f"Trade Value", value=receiving_score_string, inline=True)
    trade_embed.add_field(name="", value="", inline=False)
    trade_embed.timestamp = datetime.now()
    trade_embed.set_footer(text='Trade Analyzer')
    await interaction.followup.edit_message(initial_message.id, content=None, embed=trade_embed)

async def calculate_trade_value(player1, position, team1, rank1):
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

    index = -1
    for player in player_name:
        if player1 in player:
            recs = receptions[i].text.strip()
            proj = fpts[i].text.strip()
            posRank = j
            index = i
        if position in positions[i].text:
            if posCount < posRange:
                posSum += (float(fpts[i].text.strip())) + (float(receptions[i].text.strip()))
                posCount += 1
            j += 1
        i += 1

    rank1.append(position + str(posRank))

    if index != -1:
        start_idx = positions[index].text.rfind('(')
        end_idx = positions[index].text.rfind(')')
        content = positions[index].text[start_idx + 1:end_idx]
        parts = content.split(',')
        team = parts[1].strip()
        team1.append(team)

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