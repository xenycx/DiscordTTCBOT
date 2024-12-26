# DiscordTTCBOT

DiscordTTCBOT is a bot designed for Discord, written in Python. It leverages the discord.py library and Tbilisi Transport Company API to show you the statistics of the journey of different transports in the cities. This also shows you bus stop information and when the buses arrive.

## Setup

To set up the project locally, follow these steps:

**Clone the repository**:
```sh
git clone https://github.com/xenyc1337/DiscordTTCBOT.git
cd DiscordTTCBOT
```
Create a virtual environment:

```sh
python3 -m venv venv
```

```sh
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```
Install the dependencies:

```sh
pip install -r requirements.txt
```
Set up environment variables:
Create a .env file in the root directory of the project and add your Discord bot token and any other necessary environment variables. Example:

```env
DISCORD_TOKEN=your_discord_token_here
API_KEY=ttc_api_key
```
Usage
To run the bot, execute the main script:
```python
python main.py
```
> Make sure your bot is added to a Discord server and has the appropriate permissions to operate.

Dependencies
The project requires the following Python libraries:

```
discord.py>=2.0.0
python-dotenv
requests
asyncio
discord-py-interactions
PyNaCl
```
Refer to the requirements.txt file for more details.


# you can also use docker package but i dont have a documentation for now because im too lazy
## notes for me to build the docker


```
docker build -t ghcr.io/xenyc1337/discordttcbot:latest .
```

```
echo $GITHUB_TOKEN | docker login ghcr.io -u xenyc1337 --password-stdin
```

```
docker push ghcr.io/xenyc1337/discordttcbot:latest
```

# just use my image and you will be fine heres docker-compose.yml config

```yml
version: '3.8'

services:
  discordttcbot:
    image: ghcr.io/xenyc1337/discordttcbot:latest
    container_name: discordttcbot
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - API_KEY=${API_KEY}
    restart: always
```




Contributing
If you would like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.
>>>>>>> origin/main
