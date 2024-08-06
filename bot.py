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
@bot.tree.command(name='create_draftboard', description='Create your Draft Board')
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

# retrieves player's stats from last season from the database and displays them for a player chosen by the user
@bot.tree.command(name='last_season_stats', description="View a player's fantasy football stats from the 2023-24 season")
@app_commands.describe(player="Enter the player who's stats you'd like to view")
async def last_season_stats(interaction: discord.Interaction, player: str):
    with sqlite3.connect("draft_board.db") as storage:
        query = 'SELECT points_per_game, ranking, games_played FROM last_year_stats where player=?'
        cursor.execute(query, (player,))
        player_info = cursor.fetchall()

    if not player_info:
       await interaction.response.send_message('There are no recorded stats for ' + player + " check your spelling.", ephemeral=True)
    else:
        ppg, rank, games_played = player_info[0]

        stats_embed = discord.Embed(title=player + "'s 2023-24 Stats", color=0x00ffd5)
        # stats_embed.add_field(name='Player', value=player, inline=True)
        stats_embed.add_field(name='Rank', value=rank, inline=False)
        stats_embed.add_field(name='Fantasy Points per Game', value=ppg, inline=False)
        stats_embed.add_field(name='Games Played', value=games_played, inline=False)

        await interaction.response.send_message(embed=stats_embed, ephemeral=True)

# closes the connection when the bot shuts down
@bot.event
async def on_disconnect():
    storage.close()

# runs the bot
bot.run(TOKEN)