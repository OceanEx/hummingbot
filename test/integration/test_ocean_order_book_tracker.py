#!/usr/bin/env python

import math
import os
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderBookEvent,
    OrderBookTradeEvent,
    TradeType
)
import asyncio
import logging
from typing import (Any, Dict, Optional, List)
import unittest

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.ocean.ocean_order_book_tracker import OceanOrderBookTracker
from hummingbot.market.ocean.ocean_client import OceanClient


class OceanOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[OceanOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "btcusdt",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: OceanOrderBookTracker = OceanOrderBookTracker(
            data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=cls.trading_pairs
        )
        cls.order_book_tracker.start()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    @classmethod
    def print_order_book(cls, book):
        print('bids:')
        for entry in book.bid_entries():
            print(entry)
        print('asks:')
        for entry in book.ask_entries():
            print(entry)

    @classmethod
    def save_order_book(cls, book) -> Dict[str, Any]:
        save = {'bids': [], 'asks': []}
        for entry in book.bid_entries():
            save['bids'].append(entry)
        for entry in book.ask_entries():
            save['asks'].append(entry)
        return save

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Time out running parallel async task in tests.")
            timer += 1
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks, timeout=None):
        return self.ev_loop.run_until_complete(
            self.run_parallel_async(*tasks, timeout=timeout))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    @classmethod
    async def cause_trades(cls, trading_pair: str, trades: int):
        orders = [
            {'market': trading_pair, 'side': 'buy',
             'volume': 1, 'price': 11, 'ord_type': 'limit'},
            {'market': trading_pair, 'side': 'sell',
             'volume': 1, 'price': 9, 'ord_type': 'limit'}
        ]
        async with OceanClient() as client:
            for i in range(trades):
                await asyncio.gather(
                    client.create_order(**orders[0]),
                    client.create_order(**orders[1])
                )

    def test_order_book_trade_event_emission(self):
        """
        Test if order book tracker is able to retrieve order book trade message from exchange and
        emit order book trade events after correctly parsing the trade messages
        """
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent),
                          self.cause_trades('btcusdt', 1),
                          timeout=10)

        for ob_trade_event in self.event_logger.event_log:
            self.assertTrue(type(ob_trade_event) == OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertTrue(type(ob_trade_event.timestamp) in [float, int])
            self.assertTrue(type(ob_trade_event.amount) == float)
            self.assertTrue(type(ob_trade_event.price) == float)
            self.assertTrue(type(ob_trade_event.type) == TradeType)
            self.assertTrue(math.ceil(math.log10(ob_trade_event.timestamp)) == 10)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    @classmethod
    async def create_orders(cls, trading_pair: str):
        orders = [
            {'market': trading_pair, 'side': 'buy',
             'volume': 1, 'price': 9, 'ord_type': 'limit'},
            {'market': trading_pair, 'side': 'buy',
             'volume': 1, 'price': 10, 'ord_type': 'limit'},
            {'market': trading_pair, 'side': 'sell',
             'volume': 1, 'price': 11, 'ord_type': 'limit'},
            {'market': trading_pair, 'side': 'sell',
             'volume': 1, 'price': 12, 'ord_type': 'limit'}
        ]
        async with OceanClient() as client:
            for order in orders:
                await client.create_order(**order)

    def test_tracker_integrity(self):
        trading_pair = 'btcusdt'
        self.ev_loop.run_until_complete(self.create_orders(trading_pair))
        # wait for books
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))

        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        # should have at least 2 levels
        btcusdt_book: OrderBook = order_books[trading_pair]
        save_book = self.save_order_book(btcusdt_book)

        ask_amount = save_book['asks'][0].amount + \
            (save_book['asks'][1].amount / 2)
        self.assertGreater(btcusdt_book.get_price_for_volume(True, ask_amount).result_price,
                           btcusdt_book.get_price(True))
        bid_amount = save_book['bids'][0].amount + \
            (save_book['bids'][1].amount / 2)
        self.assertLess(btcusdt_book.get_price_for_volume(False, bid_amount).result_price,
                        btcusdt_book.get_price(False))

        with OceanClient() as client:
            self.ev_loop.run_until_complete(client.init())
            self.ev_loop.run_until_complete(client.cancel_all_orders())


def main():
    if 'log_level' in os.environ:
        log_level = os.environ['log_level']
    else:
        log_level = 'warning'
    level = getattr(logging, log_level.upper())
    log_format = '%(asctime)s.%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    logging.basicConfig(level=level, format=log_format,
                        datefmt='%H:%M:%S')
    unittest.main()


if __name__ == "__main__":
    main()
