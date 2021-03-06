# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 grandizzy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import uuid
from pprint import pformat

from kucoin.client import Client
from pyexchange.api import PyexAPI
from pymaker import Wad
from typing import List, Optional


class Order:
    def __init__(self,
                 order_id: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount*self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(item: list, pair: str, sell: bool):
        return Order(order_id=item[5],
                     pair=pair,
                     is_sell=sell,
                     price=Wad.from_number(item[2]),
                     amount=Wad.from_number(item[3]))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 order_id: Optional[str],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int) or (trade_id is None))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(order_id, str) or (order_id is None))

        self.trade_id = trade_id
        self.order_id = order_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.order_id == other.order_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.order_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_dict(pair, trade):
        return Trade(trade_id=trade['id'],
                     order_id=trade['orderOid'],
                     timestamp=int(float(trade['createdAt'])) // 1000,
                     pair=pair,
                     is_sell=trade['direction'] == 'SELL',
                     price=Wad.from_number(trade['dealPrice']),
                     amount=Wad.from_number(trade['amount']))

    @staticmethod
    def from_list(pair, trade):
        # [1544564526000, 'SELL', 25.0005, 0.0614088, 1.5352507, '5c102f2d335e7e08134edd77']
        return Trade(trade_id=None,
                     order_id=trade[5],
                     timestamp=int(float(trade[0])) // 1000,
                     pair=pair,
                     is_sell=trade[1] == 'SELL',
                     price=Wad.from_number(trade[2]),
                     amount=Wad.from_number(trade[3]))

class KucoinApi(PyexAPI):
    """kucoin API interface.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, timeout: float, requests_params=None):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.client = Client(api_key, secret_key)

    def get_markets(self):
        return self.client.get_trading_markets()

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self.client.get_tick(pair);

    def get_balances(self):
        return self.client.get_all_balances()

    def get_fiat_balance(self, fiat : str):
        assert(isinstance(fiat, str))
        return self.client.get_total_balance(fiat)

    def get_balance(self, coin : str):
        assert(isinstance(coin, str))
        return self.client.get_coin_balance(coin)

    def get_user_info(self):
        return self.client.get_user()

    def order_book(self, pair: str, limit=None):
        assert(isinstance(pair, str))
        return self.client.get_order_book(pair, limit)

    def get_orders(self, pair: str)  -> List[Order]:
        assert(isinstance(pair, str))

        orders = self.client.get_active_orders(pair)

        sell_orders = list(map(lambda item: Order.from_list(item, pair, True), orders[self.client.SIDE_SELL]))
        buy_orders = list(map(lambda item: Order.from_list(item, pair, False), orders[self.client.SIDE_BUY]))

        return sell_orders + buy_orders

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad) -> str:
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        side = self.client.SIDE_SELL if is_sell else self.client.SIDE_BUY

        coins = pair.split("-")

        price = self._get_precision(coins[1]) % float(price)
        amount = self._get_precision(coins[0]) % float(amount)

        self.logger.info(f"Placing order ({side}, amount {amount} of {pair},"
                         f" price {price})...")

        result = self.client.create_order(pair, side, price, amount)

        order_id = result['orderOid']

        self.logger.info(f"Placed order as #{order_id}")

        return order_id

    def cancel_order(self, order_id: str, is_sell: bool, pair: str):
        assert(isinstance(order_id, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(pair, str))

        side = self.client.SIDE_SELL if is_sell else self.client.SIDE_BUY

        self.logger.info(f"Cancelling order #{order_id} of type {side}...")

        try:
            self.client.cancel_order(order_id, side, pair)
            self.logger.info(f"Canceled order #{order_id}...")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel order #{order_id}... {e}")
            return False

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        page_number = page_number - 1
        limit = 100

        result = self.client.get_symbol_dealt_orders(pair, page_number, limit)

        return list(map(lambda item: Trade.from_dict(pair, item), result['datas']))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(page_number == 1)

        result = self.client.get_recent_orders(pair, 50)

        return list(map(lambda item: Trade.from_list(pair, item), result))

    @staticmethod
    def _get_precision(coin):
        return {
            'ETH': "%.7f",
            'USDT': "%.6f",
            'MKR': "%.4f",
            'BTC': "%.7f",
            'DAI': "%.4f",
        }[coin]





