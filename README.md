# Fantasy Football Discord Bot
## About this project
The Fantasy Football Discord Bot was created to help fantasy football players plan, manage, and improve their teams with commands that allow the user to create their own draft board rankings, view players' stats from the current or previous season, get an in depth analysis on potential trades, get reccomendations on who to start and who to keep on their bench on a week by week basis, see up to date news, and more! This project was built using Python, SQL, Discord.py, and the Beautiful Soup python and uses information from a sqlite database, webscraping, and its own calculations and analysis to turn hours worth of football research into the ease of a few button clicks. The project is hosted on a dedicated server that is always running so using the application is as simple as inviting the bot to a discord server and allowing permissions.
<img width="1124" alt="commands" src="https://github.com/user-attachments/assets/5964dcea-692a-487b-98f7-a324691531d9">
<img width="1119" alt="managedraftboard" src="https://github.com/user-attachments/assets/3bef37fc-06b2-49e3-be23-aa07470e0d48">
<img width="1119" alt="lastseason" src="https://github.com/user-attachments/assets/4a56aec0-3a26-42f4-b9b9-441e0e592609">
<img width="1128" alt="start_sit" src="https://github.com/user-attachments/assets/041ab612-1933-48c9-876a-8869627c1f9a">
<img width="1126" alt="tradeanalyzer" src="https://github.com/user-attachments/assets/e7aabb92-08b7-4fed-90bc-7c6e92ce26eb">
<img width="1125" alt="breakingnews" src="https://github.com/user-attachments/assets/10f7df0d-439d-4e55-a68c-dba89de4a8e8">


## Getting started
### Using the application through its dedicated server
1. Create or choose an already created discord server to invite the Fantasy Football Discord Bot to.
2. Click the invite link (or alternatively post it in a discord channel of the server you want to invite it to) https://discord.com/oauth2/authorize?client_id=1266541364657786900&permissions=8&integration_type=0&scope=bot+applications.commands and log into your discord account. Select the server you want to invite the Fantasy Football Bot to and press continue. Allow the required permissions for the bot and authorize access.
3. Congratulations, the Fantasy Football Bot is now setup in your server and can be used at any time! Type '/' in any text channel and click the Fantasy Football Bot's icon (white background brown football) to view all commands

### Hosting the application locally
#### Python Version
Python 3.12

#### Installing required packages
pip install -r /path/to/your/requirements.txt

#### Creating the application through Discord's Developer Portal
1. Click the link https://discord.com/developers/applications
2. At the top right click 'New Application' and name it as you please
3. On the left under settings select 'Bot'. Ensure public bot is enabled. Copy the token (reset token if there is no copy option) and save it somewhere safe. This token should not be shared with anyone as it is essentially the password to your bot.
4. Navigate to 'OAuth2' under settings. Under 'Scopes' tick the boxes for applications.commands and bot. On the same screen under 'Bot Permissions' tick the box for Administrator. Copy the 'Generated URL' and save it somewhere. This is the link people will use to invite your bot to their server.

#### Creating Necessary Files
1. In the directory for this project, create a new file and name it '.env'
2. Inside of this file paste this line "DISCORD_TOKEN=YOUR_DISCORD_TOKEN" and replace 'YOUR_DISCORD_TOKEN' with the token copied from earlier.
3. Run get_lastyear.py and get_schedule.py  \
   In your terminal type: \
     ```python get_lastyear.py``` \
   Followed by \
    ```python get_schedule.py``` \

#### Running the Bot
1. Setup is complete now it's time to run the application!
2. In your terminal type: \
     ```python bot.py```
3. The application is now running, refer to "Using the application through it's dedicated server" for more instructions on how to use the Fantasy Football Discord Bot and enjoy!




