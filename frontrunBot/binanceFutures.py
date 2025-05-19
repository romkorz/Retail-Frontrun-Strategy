import random, string
from typing import Literal
from time import sleep

BASE_ID = "x-40PTWbMI"
STOP, TP = "STOP_MARKET", "TAKE_PROFIT"
Side = Literal["Buy", "Sell"]

def _uid() -> str:
    return BASE_ID + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))


class Bot:
    def __init__(self, exchange):
        self.ex = exchange            # ccxt instance

    def _market_entry(self, symbol: str, side: Side, qty: float):
        return self.ex.create_order(symbol, "Market", side, qty, params={
            "newClientOrderId": _uid(),
            "reduceOnly": False,
        })

    def _bracket(self, symbol: str, entry_side: Side, size: float,
                 stop: float, take: float):
        exit_side: Side = "Sell" if entry_side == "Buy" else "Buy"
        for typ, price in ((STOP, stop), (TP, take)):
            self.ex.create_order(symbol, typ, exit_side, size, params={
                "newClientOrderId": _uid(),
                "reduceOnly": True,
                "stopPrice": price,
            })

    def trade(self, symbol: str, long: bool, balance: float, pct: float):
        side: Side = "Buy" if long else "Sell"
        mkt_price  = self.ex.fetch_ticker(symbol)["last"]
        qty        = balance * 0.999 / mkt_price      # fee buffer

        self._market_entry(symbol, side, qty)

        delta = mkt_price * pct / 100
        stop  = mkt_price - delta if long else mkt_price + delta
        take  = mkt_price + delta if long else mkt_price - delta
        self._bracket(symbol, side, qty, stop, take)


    def finwhale (self, s, long, bal):  self.trade(s, long, bal, 0.66)
    def friedman (self, s, long, bal):  self.trade(s, long, bal, 0.42)
    def alwayswin(self, s, long, bal):  self.trade(s, long, bal, 1.66)


    def run(self, data: dict):
        if data.get("close_position") == "True":
            return self.close_position(**data)        # type: ignore

        if data.get("cancel_orders"):
            self.ex.cancel_all_orders(symbol=data["symbol"])

        if "type" not in data:
            return {"status": "error", "message": "Order type missing"}

        pct  = float(data["take_profit_percent"])
        long = data["side"] == "Buy"
        self.trade(data["symbol"], long, data.get("balance", 0), pct)
