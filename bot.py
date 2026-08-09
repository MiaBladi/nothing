# bot.py
import discord
import asyncio
import os
from aiohttp import web
from dotenv import load_dotenv

load_dotenv("config.env")

# ── Config loader ─────────────────────────────────────────────────────────────

def load_bot_configs():
    configs = []
    i = 1
    while True:
        token = os.getenv(f"BOT_{i}_TOKEN")
        if not token:
            break
        configs.append({
            "token":      token,
            "guild_id":   int(os.getenv(f"BOT_{i}_GUILD_ID")),
            "channel_id": int(os.getenv(f"BOT_{i}_CHANNEL_ID")),
            "self_mute":  os.getenv(f"BOT_{i}_SELF_MUTE", "TRUE").upper() == "TRUE",
            "self_deaf":  os.getenv(f"BOT_{i}_SELF_DEAF", "TRUE").upper() == "TRUE",
        })
        i += 1
    return configs

# ── Keep-alive HTTP server (required for Render free web service) ─────────────

async def handle_ping(request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[HTTP] Keep-alive server running on port {port}")

# ── Bot factory ───────────────────────────────────────────────────────────────

def make_client(cfg):
    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True
    client = discord.Client(intents=intents)

    async def join_channel():
        guild   = client.get_guild(cfg["guild_id"])
        channel = guild.get_channel(cfg["channel_id"])
        vc      = discord.utils.get(client.voice_clients, guild=guild)

        if vc and vc.is_connected():
            return

        await channel.connect(
            self_mute=cfg["self_mute"],
            self_deaf=cfg["self_deaf"]
        )
        print(f"[BOT {client.user}] Joined #{channel.name} "
              f"(mute={cfg['self_mute']}, deaf={cfg['self_deaf']})")

    @client.event
    async def on_ready():
        print(f"[BOT] Online as {client.user}")
        await join_channel()

    @client.event
    async def on_voice_state_update(member, before, after):
        guild = client.get_guild(cfg["guild_id"])
        vc    = discord.utils.get(client.voice_clients, guild=guild)

        if not vc or not vc.is_connected():
            print(f"[BOT {client.user}] Disconnected — rejoining in 5s...")
            await asyncio.sleep(5)
            await join_channel()

    return client

# ── Per-bot runner with crash recovery ────────────────────────────────────────

async def run_bot(cfg):
    client = make_client(cfg)
    while True:
        try:
            await client.start(cfg["token"])
        except Exception as e:
            print(f"[BOT] Crashed: {e} — restarting in 10s...")
            await asyncio.sleep(10)

# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    configs = load_bot_configs()
    if not configs:
        print("No bots found in config.env. Add BOT_1_TOKEN, BOT_1_GUILD_ID, etc.")
        return

    print(f"Starting {len(configs)} bot(s) + HTTP keep-alive...")
    await asyncio.gather(
        start_http_server(),
        *(run_bot(cfg) for cfg in configs)
    )

if __name__ == "__main__":
    asyncio.run(main())
