#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

import asyncio
import contextlib
from decimal import Decimal
import os
import time
from typing import (
    List,
    Optional
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.ocean.ocean_market import OceanMarket
from hummingbot.market.ocean.ocean_client import OceanClient
from hummingbot.market.market_base import OrderType
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map

# logging.basicConfig(level=METRICS_LOG_LEVEL)


class OceanMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: OceanMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: OceanMarket = OceanMarket(
            os.environ['ocean_uid'],
            os.environ['ocean_private_key_file'],
            trading_pairs=["btcusdt"]
        )
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.ev_loop.run_until_complete(cls.market.init())
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    async def async_create_order_book(cls, wait):
        symbol = 'btcusdt'
        orders = [
            {'side': 'buy', 'volume': 2, 'price': 8},
            {'side': 'buy', 'volume': 2, 'price': 9},
            {'side': 'sell', 'volume': 2, 'price': 11},
            {'side': 'sell', 'volume': 2, 'price': 12},
        ]
        async with OceanClient() as client:
            await client.cancel_all_orders()
            await client.create_multiple_orders(symbol, orders)
            # wait for client to get update
            await asyncio.sleep(wait)

    @classmethod
    def create_order_book(cls, wait):
        cls.ev_loop.run_until_complete(cls.async_create_order_book(wait))

    @classmethod
    def clear_order_book(cls):
        with OceanClient() as client:
            cls.ev_loop.run_until_complete(client.init())
            cls.ev_loop.run_until_complete(client.cancel_all_orders())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.market.close()
        cls.stack.close()
        cls.clear_order_book()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../ocean_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: TradeFee = self.market.get_fee("btc", "usdt", OrderType.LIMIT, TradeType.BUY, 1, 10)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)

        market_fee: TradeFee = self.market.get_fee("btc", "usdt", OrderType.MARKET, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

        sell_trade_fee = self.market.get_fee("btc", "usdt", OrderType.LIMIT, TradeType.SELL, 1, 10)
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

        self.assertEqual(limit_fee.percent, market_fee.percent)
        self.assertEqual(limit_fee.percent, sell_trade_fee.percent)

        bid_fee = self.market.get_fee("btc", "vet", OrderType.LIMIT, TradeType.BUY, 1, 1)
        ask_fee = self.market.get_fee("btc", "vet", OrderType.LIMIT, TradeType.SELL, 1, 1)
        self.assertAlmostEqual(bid_fee.percent, Decimal(0.001))
        self.assertAlmostEqual(ask_fee.percent, Decimal(0.001))

    def test_fee_overrides_config(self):
        configs_before_test = {
            "ocean_taker_fee": fee_overrides_config_map["ocean_taker_fee"].value,
            "ocean_maker_fee": fee_overrides_config_map["ocean_maker_fee"].value
        }

        fee_overrides_config_map["ocean_taker_fee"].value = None
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)

        fee_overrides_config_map["ocean_taker_fee"].value = Decimal('0.2')
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)

        fee_overrides_config_map["ocean_maker_fee"].value = None
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), maker_fee.percent)

        fee_overrides_config_map["ocean_maker_fee"].value = Decimal('0.4')
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.004"), maker_fee.percent)

        fee_overrides_config_map["ocean_taker_fee"].value = configs_before_test["ocean_taker_fee"]
        fee_overrides_config_map["ocean_maker_fee"].value = configs_before_test["ocean_maker_fee"]

    def test_limit_buy(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        self.assertFalse(current_bid_price.is_nan())

        amount: Decimal = Decimal("1")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        bid_price: Decimal = current_bid_price + Decimal("0.05") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        [order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCompletedEvent, 10))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("btc", order_completed_event.base_asset)
        self.assertEqual("usdt", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()
        self.clear_order_book()

    def test_limit_sell(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        self.assertFalse(current_ask_price.is_nan())

        amount: Decimal = Decimal("1")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        ask_price: Decimal = current_ask_price - Decimal("0.05") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price)
        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT, quantize_ask_price)

        [order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCompletedEvent, 10))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("btc", order_completed_event.base_asset)
        self.assertEqual("usdt", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()
        self.clear_order_book()

    def test_market_buy(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        amount: Decimal = Decimal("1")  # in quote currency
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        order_id = self.market.buy(trading_pair, quantized_amount, OrderType.MARKET)

        [buy_order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCompletedEvent, 10))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("btc", buy_order_completed_event.base_asset)
        self.assertEqual("usdt", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, buy_order_completed_event.base_asset_amount, places=4)
        self.assertAlmostEqual(quote_amount_traded, buy_order_completed_event.quote_asset_amount, places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()
        self.clear_order_book()

    def test_market_sell(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        amount: Decimal = Decimal("1")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        order_id = self.market.sell(trading_pair, amount, OrderType.MARKET, 0)

        [sell_order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCompletedEvent, 10))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, sell_order_completed_event.base_asset_amount)
        self.assertEqual("btc", sell_order_completed_event.base_asset)
        self.assertEqual("usdt", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, sell_order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, sell_order_completed_event.quote_asset_amount)
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()
        self.clear_order_book()

    def test_cancel_order(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        self.assertFalse(current_bid_price.is_nan())
        amount: Decimal = Decimal("1")

        bid_price: Decimal = current_bid_price - Decimal("0.1") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        client_order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_created_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCreatedEvent, 10))
        self.market.cancel(trading_pair, client_order_id)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent, 10))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, client_order_id)

        self.clear_order_book()

    def test_cancel_all(self):
        self.create_order_book(2)
        trading_pair = "btcusdt"
        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal("0.5")
        self.assertFalse(bid_price.is_nan())
        ask_price: Decimal = self.market.get_price(trading_pair, False) * 2
        self.assertFalse(ask_price.is_nan())
        amount: Decimal = Decimal("1")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

        self.clear_order_book()

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "btcusdt"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()
        self.create_order_book(2)

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to limit buy order and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            self.assertFalse(current_bid_price.is_nan())
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal("1")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
            [order_created_event] = self.run_parallel(
                self.market_logger.wait_for(BuyOrderCreatedEvent, 10))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: OceanMarket = OceanMarket(
                os.environ['ocean_uid'],
                os.environ['ocean_private_key_file'],
                trading_pairs=["btcusdt"]
            )
            self.ev_loop.run_until_complete(self.market.init())

            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(
                self.market_logger.wait_for(OrderCancelledEvent, 10))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(
                    self.market_logger.wait_for(OrderCancelledEvent, 10))

            self.market.close()
            recorder.stop()
            os.unlink(self.db_path)
            self.clear_order_book()

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "btcusdt"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()
        self.create_order_book(2)

        try:
            # Try to buy from the exchange, and watch for completion event.
            amount: Decimal = Decimal("1")
            order_id = self.market.buy(trading_pair, amount)
            [buy_order_completed_event] = self.run_parallel(
                self.market_logger.wait_for(BuyOrderCompletedEvent, 10))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount to the exchange, and watch for completion event.
            amount = buy_order_completed_event.base_asset_amount
            order_id = self.market.sell(trading_pair, amount)
            [sell_order_completed_event] = self.run_parallel(
                self.market_logger.wait_for(SellOrderCompletedEvent, 10))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertEqual(2, len(trade_fills))
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertEqual(1, len(buy_fills))
            self.assertEqual(1, len(sell_fills))

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(
                    self.market_logger.wait_for(OrderCancelledEvent, 10))

            recorder.stop()
            os.unlink(self.db_path)
            self.clear_order_book()


if __name__ == "__main__":
    if 'log_level' in os.environ:
        log_level = os.environ['log_level']
        level = getattr(logging, log_level.upper())
    else:
        level = METRICS_LOG_LEVEL
    log_format = '%(asctime)s.%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    logging.basicConfig(level=level, format=log_format,
                        datefmt='%H:%M:%S')
    unittest.main()
