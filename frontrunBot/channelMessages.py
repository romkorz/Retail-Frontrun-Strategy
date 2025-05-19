import asyncio, configparser, os, re
from threading import Timer

from flask import Flask
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
import ccxt

from binance_futures import Bot


_cfg = configparser.ConfigParser()
_cfg.read("config.ini")

API_ID   = _cfg["Telegram"]["api_id"]
API_HASH = _cfg["Telegram"]["api_hash"]
PHONE    = _cfg["Telegram"]["phone"]
SESSION  = _cfg["Telegram"]["username"]

BIN_KEY  = os.getenv("BINANCE_KEY", "")
BIN_SEC  = os.getenv("BINANCE_SECRET", "")

exchange = ccxt.binance({
    "apiKey": BIN_KEY,
    "secret": BIN_SEC,
    "options": {"defaultType": "future"},
})

_balance = 0.0
def _refresh_balance():
    global _balance
    _balance = exchange.fetch_balance()["total"]["USDT"]
    print(f"[BAL] {_balance:.2f} USDT")
    Timer(30, _refresh_balance).start()
_refresh_balance()


client = TelegramClient(SESSION, API_ID, API_HASH)
bot    = Bot(exchange)

BAN = {"BTC/USDT", "ETH/USDT", "DOGE/USDT", "SOL/USDT"}

PATTERNS = {
    "finwhale":  re.compile(r"#(\w+)/?USDT?.*?\((Long|Short|Sell)\).*Take-Profit Targets", re.S),
    "friedman":  re.compile(r"🪙\s*(\w+/USDT).*?\((Long|Short|Sell)\).*TP:", re.S),
    "alwayswin": re.compile(r"#AlwaysWinTrades.*?\n.*? (\w+)/USDT", re.S),
}

@client.on(events.NewMessage())
async def on_signal(evt):
    global _balance
    txt = evt.raw_text

    if getattr(on_signal, "_last", None) == evt.id:
        return
    on_signal._last = evt.id

    for name, rx in PATTERNS.items():
        m = rx.search(txt)
        if not m:
            continue

        pair = (m.group(1).upper()
                if "/" in m.group(1) else f"{m.group(1).upper()}/USDT")

        if pair in BAN:
            print(f"🚫   {pair} is on the ban-list")
            return

        long = m.group(2).lower().startswith("long") if name != "alwayswin" else True
        print(f"→  {name} | {pair} | {'LONG' if long else 'SHORT'}")
        getattr(bot, name)(pair, long, _balance)
        return

    print("…not a recognised signal")


app = Flask(__name__)
@app.route("/")
def health(): return {"status": "ok"}


async def ensure_login():
    await client.start()
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        try:
            await client.sign_in(PHONE, input("Code: "))
        except SessionPasswordNeededError:
            await client.sign_in(password=input("2FA Password: "))

async def main():
    await ensure_login()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().create_task(main())
    app.run(host="0.0.0.0", port=8000, debug=False)
