#! /usr/bin/env python

import asyncio
import logging
import os
import sys; sys.path.insert(0, os.path.realpath(os.path.join(__file__, '../../../')))
import time
import unittest

from collections import namedtuple
from decimal import Decimal
from typing import (Any, Dict, List,)

import pandas as pd

from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderType, TradeType,
    MarketEvent, MarketOrderFailureEvent,
    OrderFilledEvent, OrderCancelledEvent,
    BuyOrderCompletedEvent, SellOrderCompletedEvent)
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.core.utils.market_mid_price import ocean_mid_price
from hummingbot.market.ocean.ocean_api_order_book_data_source \
    import OceanAPIOrderBookDataSource
from hummingbot.market.ocean.ocean_in_flight_order import OceanInFlightOrder
from hummingbot.market.ocean.ocean_market import OceanMarket
from hummingbot.market.ocean.ocean_client import OceanClient
from hummingbot.market.ocean.ocean_order_book import OceanOrderBook
from hummingbot.market.trading_rule import TradingRule


g_ev_loop = asyncio.get_event_loop()
g_debug: bool = True if 'debug' in os.environ else False


class TestOceanInFlightOrder(unittest.TestCase):
    def test_apply_fee_bid(self):
        fee_rate = Decimal(0.01)

        price = Decimal(10)
        amount = Decimal(2)
        order = OceanInFlightOrder(
            '1', '1', 'btcusdt', OrderType.LIMIT, TradeType.BUY,
            price, amount)
        order.executed_amount_base = amount
        order.executed_amount_quote = price * amount
        fee = fee_rate * order.executed_amount_base

        order.apply_fee(fee_rate)

        self.assertEqual('btc', order.fee_asset)
        self.assertEqual(fee, order.fee_paid)

    def test_apply_fee_ask(self):
        fee_rate = Decimal(0.01)

        price = Decimal(10)
        amount = Decimal(2)
        order = OceanInFlightOrder(
            '1', '1', 'btcusdt', OrderType.LIMIT, TradeType.SELL,
            price, amount)
        order.executed_amount_base = amount
        order.executed_amount_quote = price * amount
        fee = fee_rate * order.executed_amount_quote

        order.apply_fee(fee_rate)

        self.assertEqual('usdt', order.fee_asset)
        self.assertEqual(fee, order.fee_paid)


class TestOceanAPIOrderBookDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_gets_active_exchange_markets(self):
        coro = OceanAPIOrderBookDataSource.get_active_exchange_markets()
        markets: pd.DataFrame = g_ev_loop.run_until_complete(coro)
        if g_debug:
            print('markets:\n', markets)

        got_columns = set(markets.columns)
        exp_columns = set(['baseAsset', 'quoteAsset', 'USDVolume'])
        self.assertTrue(exp_columns.issubset(got_columns))
        self.assertGreater(len(markets), 10)
        markets_with_volume = markets[markets['volume'] > 0]
        volumes_are_valid = markets_with_volume['USDVolume'] > 0
        self.assertTrue(volumes_are_valid.all())

    def test_gets_trading_pairs(self):
        source = OceanAPIOrderBookDataSource()
        coro = source.get_trading_pairs()
        pairs: List[str] = g_ev_loop.run_until_complete(coro)
        self.assertGreater(len(pairs), 10)
        self.assertIn('btcusdt', pairs)

    def test_gets_snapshot(self):
        symbol = 'btcusdt'
        snap: Dict[str, Any] = None
        with OceanClient() as client:
            g_ev_loop.run_until_complete(client.init())
            coro = OceanAPIOrderBookDataSource.get_snapshot(client, symbol)
            snap = g_ev_loop.run_until_complete(coro)
        self.assertIn('timestamp', snap)
        self.assertIn('bids', snap)
        self.assertIn('asks', snap)

    def test_gets_tracking_pairs(self):
        source = OceanAPIOrderBookDataSource()
        coro = source.get_tracking_pairs()
        trackers: Dict[str, Any] = g_ev_loop.run_until_complete(coro)
        self.assertGreater(len(trackers), 10)
        self.assertIn('btcusdt', trackers)

    async def _collect_messages(self, queue: asyncio.Queue,
                                required_msgs: int,
                                timeout: int) -> int:
        got_msgs = 0
        while got_msgs < required_msgs:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
                if g_debug:
                    print(msg)
            except asyncio.TimeoutError:
                break
            got_msgs += 1
        return got_msgs

    def test_listens_for_order_book_snapshots(self):
        queue = asyncio.Queue()
        source = OceanAPIOrderBookDataSource()
        coro_listen = source.listen_for_order_book_snapshots(g_ev_loop, queue)
        g_ev_loop.create_task(coro_listen)
        exp_msgs = 2
        timeout = 10
        coro_consume = self._collect_messages(queue, exp_msgs, timeout)
        got_msgs = g_ev_loop.run_until_complete(coro_consume)
        self.assertEqual(exp_msgs, got_msgs)

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

    def test_listens_for_trades(self):
        queue = asyncio.Queue()
        source = OceanAPIOrderBookDataSource()
        coro_listen = source.listen_for_trades(g_ev_loop, queue)
        g_ev_loop.create_task(coro_listen)
        exp_msgs = 2
        g_ev_loop.create_task(self.cause_trades('btcusdt', exp_msgs))
        timeout = 5
        coro_consume = self._collect_messages(queue, exp_msgs, timeout)
        got_msgs = g_ev_loop.run_until_complete(coro_consume)
        self.assertEqual(exp_msgs, got_msgs)


class TestOceanMarket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        self._trading_pair = 'btcusdt'
        self._market = OceanMarket('', '')
        g_ev_loop.run_until_complete(self._market.init())
        self._market.order_book_tracker.order_books[self._trading_pair] = OrderBook()

    def tearDown(self):
        self._market.close()

    def test_quantizes_order_amount(self):
        market = self._market
        rule = TradingRule(trading_pair='vthousdt',
                           min_price_increment=Decimal('1e-6'),
                           min_base_amount_increment=Decimal('1e-2'),
                           min_notional_size=Decimal(1))
        market.trading_rules[rule.trading_pair] = rule

        raw_books = {"asks": [["0.0006", "10"]], "bids": [["0.0004", "10"]]}
        msg: OrderBookMessage = OceanOrderBook.snapshot_message_from_exchange(
            raw_books, 111, metadata={"trading_pair": rule.trading_pair})
        book = OrderBook()
        book.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        market.order_books[rule.trading_pair] = book

        amount = Decimal(2)
        quantized_amount: Decimal = market.quantize_order_amount(
            rule.trading_pair, amount)
        self.assertEqual(amount, quantized_amount)

        price = Decimal('0.0005')
        quantized_price: Decimal = market.quantize_order_price(
            rule.trading_pair, price)
        self.assertEqual(price, quantized_price)

    def _test_executes(self, coro, params):
        g_ev_loop.run_until_complete(coro)

        orders = self._market.in_flight_orders
        self.assertEqual(1, len(orders))
        self.assertIn(params['order_id'], orders)
        order = orders[params['order_id']]
        self.assertEqual(params['order_id'], order.client_order_id)
        self.assertEqual(params['trading_pair'], order.trading_pair)
        self.assertEqual(params['order_type'], order.order_type)
        self.assertEqual(params['price'], order.price)
        self.assertEqual(params['amount'], order.amount)

        with OceanClient() as client:
            g_ev_loop.run_until_complete(client.init())
            time.sleep(1)
            g_ev_loop.run_until_complete(client.cancel_order(order.exchange_order_id))

    def test_executes_buy(self):
        params = {
            'order_id': '1',
            'trading_pair': self._trading_pair,
            'amount': 1,
            'order_type': OrderType.LIMIT,
            'price': Decimal(10)
        }
        g_ev_loop.run_until_complete(self._market._update_trading_rules())
        coro = self._market.execute_buy(**params)
        self._test_executes(coro, params)

    def test_executes_sell(self):
        params = {
            'order_id': '2',
            'trading_pair': self._trading_pair,
            'amount': 1,
            'order_type': OrderType.LIMIT,
            'price': Decimal(10)
        }
        g_ev_loop.run_until_complete(self._market._update_trading_rules())
        coro = self._market.execute_sell(**params)
        self._test_executes(coro, params)

    def test_execute_buy_and_sell_checks_min_size(self):
        g_ev_loop.run_until_complete(self._market._update_trading_rules())
        min_order_size = Decimal(10)
        self._market.trading_rules[self._trading_pair].min_order_size = min_order_size
        order_size = min_order_size - Decimal(0.1)

        params = {'order_id': '1', 'trading_pair': self._trading_pair,
                  'amount': order_size,
                  'order_type': OrderType.LIMIT, 'price': Decimal(10)}

        with self.assertRaisesRegex(ValueError,
                                    'Buy order amount 0 is lower than the minimum order size 10'):
            g_ev_loop.run_until_complete(self._market.execute_buy(**params))

        with self.assertRaisesRegex(ValueError,
                                    'Sell order amount 0 is lower than the minimum order size 10'):
            g_ev_loop.run_until_complete(self._market.execute_sell(**params))

    def test_executes_cancel(self):
        params = {
            'order_id': '3',
            'trading_pair': self._trading_pair,
            'amount': 1,
            'order_type': OrderType.LIMIT,
            'price': Decimal(10)
        }
        g_ev_loop.run_until_complete(self._market._update_trading_rules())
        g_ev_loop.run_until_complete(self._market.execute_buy(**params))
        g_ev_loop.run_until_complete(
            self._market.execute_cancel(self._trading_pair, params['order_id']))

        orders = self._market.in_flight_orders
        self.assertEqual(0, len(orders))

    def test_executes_cancel_invalid_order(self):
        params = {
            'order_id': '1',
            'trading_pair': self._trading_pair,
            'amount': 1,
            'order_type': OrderType.LIMIT,
            'price': Decimal(10)
        }

        # an order not in exchange but still tracked
        exchange_order_id = '11111'
        orders = self._market.in_flight_orders
        orders[params['order_id']] = OceanInFlightOrder(
            client_order_id=params['order_id'],
            exchange_order_id=exchange_order_id,
            trading_pair=params['trading_pair'],
            order_type=params['order_type'],
            trade_type=TradeType.BUY,
            price=params['price'],
            amount=params['amount']
        )

        g_ev_loop.run_until_complete(
            self._market.execute_cancel(self._trading_pair, params['order_id']))
        self.assertEqual(1, len(orders))

    def test_updates_balances(self):
        g_ev_loop.run_until_complete(self._test_updates_balances())

    async def _test_updates_balances(self):
        Balance = namedtuple('Balance', 'total avail')
        market = self._market
        btc_balances = []
        usdt_balances = []
        await market._update_balances()
        btc_balances.append(Balance(market.get_balance('btc'),
                                    market.get_available_balance('btc')))
        usdt_balances.append(Balance(market.get_balance('usdt'),
                                     market.get_available_balance('usdt')))

        orders = [
            {'market': 'btcusdt', 'side': 'buy',
             'volume': 10, 'price': 100, 'ord_type': 'limit'},
            {'market': 'btcusdt', 'side': 'sell',
             'volume': 10, 'price': 101, 'ord_type': 'limit'}
        ]
        async with OceanClient() as client:
            for order in orders:
                await client.create_order(**order)
                await self._market._update_balances()
                btc_balances.append(Balance(market.get_balance('btc'),
                                            market.get_available_balance('btc')))
                usdt_balances.append(Balance(market.get_balance('usdt'),
                                             market.get_available_balance('usdt')))
            await client.cancel_all_orders()

        self.assertEqual(btc_balances[0].total, btc_balances[1].total)
        self.assertEqual(btc_balances[0].avail, btc_balances[1].avail)
        self.assertEqual(usdt_balances[0].total, usdt_balances[1].total)
        exp_usdt_avail = usdt_balances[0].avail - (orders[0]['volume'] * orders[0]['price'])
        self.assertEqual(exp_usdt_avail, usdt_balances[1].avail)

        self.assertEqual(btc_balances[1].total, btc_balances[2].total)
        exp_btc_avail = btc_balances[1].avail - orders[1]['volume']
        self.assertEqual(exp_btc_avail, btc_balances[2].avail)
        self.assertEqual(usdt_balances[1].total, usdt_balances[2].total)
        self.assertEqual(usdt_balances[1].avail, usdt_balances[2].avail)

    @staticmethod
    async def schedule_in_order(*coros):
        tasks = []
        for coro in coros:
            task = asyncio.ensure_future(coro)
            tasks.append(task)
        for task in tasks:
            await task

    def test_update_order_status_not_in_exchange(self):
        '''
        tracked order not in exchange should be removed
        '''
        market = self._market
        listener = EventLogger()
        market.add_listener(MarketEvent.OrderFailure, listener)
        tracked_orders = market.in_flight_orders
        order = OceanInFlightOrder(client_order_id='buy-btcusdt-1',
                                   exchange_order_id='100000', trading_pair='btcusdt',
                                   order_type='OrderType.LIMIT',
                                   trade_type=TradeType.BUY, price=10, amount=1)
        tracked_orders[order.client_order_id] = order
        self.assertEqual(1, len(tracked_orders))

        g_ev_loop.run_until_complete(TestOceanMarket.schedule_in_order(
            listener.wait_for(MarketOrderFailureEvent, timeout_seconds=5),
            market._update_order_status_now()
        ))
        self.assertEqual(0, len(tracked_orders))

    def test_update_order_status_complete_fill(self):
        market = self._market
        listener = EventLogger()
        for ev in (MarketEvent.OrderFilled, MarketEvent.BuyOrderCompleted):
            market.add_listener(ev, listener)
        tracked_orders = market.in_flight_orders
        order = OceanInFlightOrder(client_order_id='buy-btcusdt-1',
                                   exchange_order_id='1', trading_pair='btcusdt',
                                   order_type='OrderType.LIMIT',
                                   trade_type=TradeType.BUY, price=10, amount=1)
        tracked_orders[order.client_order_id] = order
        self.assertEqual(1, len(tracked_orders))
        order_update = {'id': 1, 'side': 'buy', 'ord_type': 'limit',
                        'market': 'btcusdt', 'price': '10.0', 'avg_price': '10.0',
                        'state': 'done',
                        'volume': '1', 'remaining_volume': '0',
                        'executed_volume': '1', 'trades_count': 0}

        g_ev_loop.run_until_complete(TestOceanMarket.schedule_in_order(
            listener.wait_for(OrderFilledEvent, timeout_seconds=5),
            listener.wait_for(BuyOrderCompletedEvent, timeout_seconds=5),
            market._update_an_order_status(order, order_update),
        ))
        self.assertEqual(0, len(tracked_orders))

    def test_update_order_status_complete_fill_ask(self):
        market = self._market
        listener = EventLogger()
        for ev in (MarketEvent.OrderFilled, MarketEvent.SellOrderCompleted):
            market.add_listener(ev, listener)
        tracked_orders = market.in_flight_orders
        order = OceanInFlightOrder(client_order_id='sell-btcusdt-1',
                                   exchange_order_id='1', trading_pair='btcusdt',
                                   order_type='OrderType.LIMIT',
                                   trade_type=TradeType.SELL, price=10, amount=1)
        tracked_orders[order.client_order_id] = order
        self.assertEqual(1, len(tracked_orders))
        order_update = {'id': 1, 'side': 'sell', 'ord_type': 'limit',
                        'market': 'btcusdt', 'price': '10.0', 'avg_price': '10.0',
                        'state': 'done',
                        'volume': '1', 'remaining_volume': '0',
                        'executed_volume': '1', 'trades_count': 0}

        g_ev_loop.run_until_complete(TestOceanMarket.schedule_in_order(
            listener.wait_for(OrderFilledEvent, timeout_seconds=5),
            listener.wait_for(SellOrderCompletedEvent, timeout_seconds=5),
            market._update_an_order_status(order, order_update),
        ))
        self.assertEqual(0, len(tracked_orders))

    def test_update_order_status_partial_fill(self):
        market = self._market
        listener = EventLogger()
        for ev in (MarketEvent.OrderFilled, MarketEvent.BuyOrderCompleted):
            market.add_listener(ev, listener)
        tracked_orders = market.in_flight_orders
        order = OceanInFlightOrder(client_order_id='buy-btcusdt-1',
                                   exchange_order_id='1', trading_pair='btcusdt',
                                   order_type='OrderType.LIMIT',
                                   trade_type=TradeType.BUY, price=10, amount=2)
        tracked_orders[order.client_order_id] = order
        self.assertEqual(1, len(tracked_orders))

        # first fill
        order_update = {'id': 1, 'side': 'buy', 'ord_type': 'limit',
                        'market': 'btcusdt', 'price': '10.0', 'avg_price': '10.0',
                        'state': 'wait',
                        'volume': '2', 'remaining_volume': '1',
                        'executed_volume': '1', 'trades_count': 0}

        g_ev_loop.run_until_complete(TestOceanMarket.schedule_in_order(
            listener.wait_for(OrderFilledEvent, timeout_seconds=5),
            market._update_an_order_status(order, order_update),
        ))
        self.assertEqual(1, len(tracked_orders))

        # second fill
        order_update['remaining_volume'] = '0'
        order_update['executed_volume'] = order_update['volume']
        order_update['state'] = 'done'

        g_ev_loop.run_until_complete(TestOceanMarket.schedule_in_order(
            listener.wait_for(OrderFilledEvent, timeout_seconds=5),
            listener.wait_for(BuyOrderCompletedEvent, timeout_seconds=5),
            market._update_an_order_status(order, order_update),
        ))
        self.assertEqual(0, len(tracked_orders))

    def test_update_order_status_cancel(self):
        market = self._market
        listener = EventLogger()
        market.add_listener(MarketEvent.OrderCancelled, listener)
        tracked_orders = market.in_flight_orders
        order = OceanInFlightOrder(client_order_id='buy-btcusdt-1',
                                   exchange_order_id='1', trading_pair='btcusdt',
                                   order_type='OrderType.LIMIT',
                                   trade_type=TradeType.BUY, price=10, amount=1)
        tracked_orders[order.client_order_id] = order
        self.assertEqual(1, len(tracked_orders))
        order_update = {'id': 1, 'side': 'buy', 'ord_type': 'limit',
                        'market': 'btcusdt', 'price': '10.0', 'avg_price': '0',
                        'state': 'cancel',
                        'volume': '1', 'remaining_volume': '1',
                        'executed_volume': '0', 'trades_count': 0}

        g_ev_loop.run_until_complete(self.schedule_in_order(
            listener.wait_for(OrderCancelledEvent, timeout_seconds=6),
            market._update_an_order_status(order, order_update),
        ))
        self.assertEqual(0, len(tracked_orders))

    def test_cancel_all_no_fails(self):
        orders = (
            OceanInFlightOrder('a', '1', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'wait'),
            OceanInFlightOrder('b', '2', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'wait'),
            OceanInFlightOrder('c', '3', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'done'),
            OceanInFlightOrder('d', '4', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'cancel'),
        )
        for o in orders:
            self._market.in_flight_orders[o.client_order_id] = o

        updates = (
            {'id': 1, 'state': 'cancelling'},
            {'id': 2, 'state': 'cancelling'}
        )
        results = self._market._calc_cancel_all_result(updates)

        exp_results = [
            CancellationResult('a', True),
            CancellationResult('b', True)
        ]
        self.assertEqual(exp_results, results)

    def test_cancel_all_with_fails(self):
        orders = [
            OceanInFlightOrder('a', '1', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'wait'),
            OceanInFlightOrder('b', '2', 'btcusdt',
                               OrderType.LIMIT, TradeType.BUY, 10, 1, 'wait')
        ]
        for o in orders:
            self._market.in_flight_orders[o.client_order_id] = o

        updates = [
            {'id': 1, 'state': 'cancelling'},
        ]
        results = self._market._calc_cancel_all_result(updates)

        exp_results = [
            CancellationResult('a', True),
            CancellationResult('b', False)
        ]
        self.assertEqual(exp_results, results)


class TestRelated(unittest.TestCase):
    def test_TradingPairFetcher_fetch_ocean_trading_pairs(self):
        g_ev_loop.run_until_complete(
            self._test_TradingPairFetcher_fetch_ocean_trading_pairs())

    async def _test_TradingPairFetcher_fetch_ocean_trading_pairs(self):
        fetcher = TradingPairFetcher()
        pairs: List[str] = await fetcher.fetch_ocean_trading_pairs()
        sep = '-'
        for name in pairs:
            sep_index = name.find(sep)
            msg = f"no separator({sep}) in {name}"
            self.assertTrue(sep_index > 0, msg)
            self.assertTrue(sep_index < len(name) - 1, msg)

    def test_ocean_mid_price(self):
        sym = 'BTC-USDT'
        mid_price = ocean_mid_price(sym)
        self.assertIsNotNone(mid_price)


if __name__ == '__main__':
    if 'log_level' in os.environ:
        log_level = os.environ['log_level']
    else:
        log_level = 'warning'
    level = getattr(logging, log_level.upper())
    log_format = '%(asctime)s.%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    logging.basicConfig(level=level, format=log_format,
                        datefmt='%H:%M:%S')

    unittest.main()
