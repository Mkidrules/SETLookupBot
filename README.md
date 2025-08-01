# SETLookup Bot

A Discord bot that lets users search through PDF documents and view results as embeds with image previews.

## Features
- Slash command `/lookup` to search through PDF contents
- Interactive pagination of search results
- Dropdown selection when multiple PDFs match
- Automatic inactivity sleep after 10 minutes

## Setup

1. Clone the repo:
        git clone https://github.com/Mkidrules/SETLookup.git
        cd SETLookup

2. Install dependencies:

        pip install -r requirements.txt

3. Add your PDFs to the pdfs/ folder (excluded from Git)

4. Set your Discord bot token in an .env file or in config.py

5. Run the bot:
        python bot.py

## Requirements:

Python 3.10+

Nextcord
