<<<<<<< HEAD
GET /pis-gateway/api/v3/routes?modes=BUS&locale=ka HTTP/1.1
Accept: application/json, text/plain, */*
Accept-Encoding: gzip, deflate, br, zstd
Accept-Language: en-US,en;q=0.9
Cache-Control: no-cache
Connection: keep-alive
Cookie: cookiesession1=678A3E12E7455809ACBF5D3F6007D885
Host: transit.ttc.com.ge
Pragma: no-cache
Referer: https://transit.ttc.com.ge/
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
Sec-GPC: 1
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
X-api-key: c0a2f304-551a-4d08-b8df-2c53ecd57f9f
sec-ch-ua: "Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "Windows"
=======

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

```discord.py>=2.0.0
python-dotenv
requests
discord-py-interactions
PyNaCl
```
Refer to the requirements.txt file for more details.

Contributing
If you would like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.
>>>>>>> origin/main
