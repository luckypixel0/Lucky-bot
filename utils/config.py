import os

TOKEN = os.getenv("TOKEN")
NAME = "Lucky"
BotName = "Lucky"
server = os.getenv("SUPPORT_SERVER", "https://discord.gg/lucky")
serverLink = server
ch = os.getenv("SUPPORT_CHANNEL", "")

_owner_ids_raw = os.getenv("OWNER_IDS", "")
OWNER_IDS = [int(x.strip()) for x in _owner_ids_raw.split(",") if x.strip().isdigit()]

# Lucky Bot — Rewritten
