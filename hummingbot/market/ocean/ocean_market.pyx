import aiohttp
from aiohttp.test_utils import TestClient
import asyncio
from async_timeout import timeout
import conf
from datetime import datetime
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import pandas as pd
import re
import time
from typing import (
    Any,
    AsyncIterable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple
)
import traceback
import ujson
import json

import hummingbot
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    MarketEvent,
    MarketWithdrawAssetEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.market.ocean.ocean_api_order_book_data_source import OceanAPIOrderBookDataSource
from hummingbot.market.ocean.ocean_in_flight_order import OceanInFlightOrder
from hummingbot.market.ocean.ocean_order_book_tracker import OceanOrderBookTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.market_base import (
    MarketBase,
    NaN,
    s_decimal_NaN)
from hummingbot.market.ocean.ocean_client import OceanClient
from hummingbot.core.utils.estimate_fee import estimate_fee


hm_logger = None
s_decimal_0 = Decimal(0)
TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(btc|eth|usd|usdt|vet)$")


cdef class OceanMarketTransactionTracker(TransactionTracker):
    cdef:
        OceanMarket _owner

    def __init__(self, owner: OceanMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class OceanMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 ocean_uid: str,
                 ocean_private_key_file: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._trading_required = trading_required
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._ocean_client = OceanClient(ocean_uid,
                                         ocean_private_key_file)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = OceanOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            trading_pairs=trading_pairs
        )
        self._tx_tracker = OceanMarketTransactionTracker(self)

        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._order_tracker_task = None
        self._status_polling_task = None

        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (bid_fee:Decimal, ask_fee:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._trading_rules_polling_task = None

    async def init(self):
        await self._ocean_client.init()

    def close(self):
        self._ocean_client.close()

    @staticmethod
    def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
        try:
            m = TRADING_PAIR_SPLITTER.match(trading_pair)
            return m.group(1), m.group(2)
        # Exceptions are now logged as warnings in trading pair fetcher
        except Exception as e:
            return None

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        pair = OceanMarket.split_trading_pair(exchange_trading_pair)
        if pair is None:
            return None
        # Ocean uses lowercase base and quote asset (btcusdt)
        return f"{pair[0].upper()}-{pair[1].upper()}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        # Ocean uses lowercase (btcusdt)
        return hb_trading_pair.replace("-", "").lower()

    @property
    def name(self) -> str:
        return "ocean"

    @property
    def order_book_tracker(self) -> OceanOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, OceanInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: OceanInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await OceanAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        MarketBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._order_tracker_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._ocean_client.get_server_time()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)
        MarketBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _update_balances(self):
        cdef:
            dict data
            list balances
            set local_assets = set(self._account_balances.keys())
            set remote_assets = set()
            str asset

        resp = await self._ocean_client.get_account_info()
        if 0 != resp['code']:
            self.logger().error(f"ocean failed to get account info: "
                                f"code={resp['code']}, message={resp['message']}")
            return

        data = resp['data']
        balances = data['accounts']

        for entry in balances:
            asset = entry['currency']
            remote_assets.add(asset)
            exch_balance = Decimal(entry['balance'])
            self._account_available_balances[asset] = exch_balance
            self._account_balances[asset] = exch_balance + Decimal(entry['locked'])

        lost_assets = local_assets.difference(remote_assets)
        for asset in lost_assets:
            del self._account_available_balances[asset]
            del self._account_balances[asset]

    async def _update_trade_fees(self):
        cdef:
            double current_timestamp = self._current_timestamp
            double update_interval = 60.0 * 60.0

        if current_timestamp - self._last_update_trade_fees_timestamp > \
                update_interval or len(self._trade_fees) < 1:
            try:
                response = await self._ocean_client.get_trading_fees()
                if 0 != response['code']:
                    self.logger().error(f"ocean failed to get trading fees: "
                                        f"code={response['code']}, message={response['message']}")
                    return

                all_fees = response['data']
                for entry in all_fees:
                    bid_fee = entry['bid_fee']['value']
                    ask_fee = entry['ask_fee']['value']
                    self._trade_fees[entry['market']] = (Decimal(bid_fee),
                                                         Decimal(ask_fee))
                self._last_update_trade_fees_timestamp = current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                msg="Could not fetch Ocean trading fees."
                self.logger().network("Error fetching Ocean trade fees.", exc_info=True,
                                      app_warning_msg=msg)
                raise

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        cdef:
            object bid_fee = Decimal("0.001")
            object ask_fee = Decimal("0.001")
            str trading_pair = base_currency + quote_currency

        if trading_pair in self._trade_fees:
            bid_fee, ask_fee = self._trade_fees.get(trading_pair)
        else:
            self.logger().warning(f"Unable to find trade fee for {trading_pair}. Using default 0.1% fee.")
        return TradeFee(percent=bid_fee if order_side is TradeType.BUY else ask_fee)
        """
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("ocean", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)

        if current_tick > last_tick or len(self._trading_rules) < 1:
            response = await self._ocean_client._get_markets_details()
            if 0 != response['code']:
                self.logger().error(f"ocean failed to get market details: "
                                    f"code={response['code']}, message={response['message']}")
                return

            trading_rules_list = self._format_trading_rules(response['data'])
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, all_rules: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in all_rules:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=info['id'],
                                min_price_increment=Decimal(f"1e-{info['price_precision']}"),
                                min_base_amount_increment=Decimal(f"1e-{info['amount_precision']}"),
                                min_notional_size=Decimal(info['minimum_trading_amount']))
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            await self._update_order_status_now()

    def _log_inflight_orders(self):
        for key, order in self._in_flight_orders.items():
            msg = f"inflight order: {key}: {repr(order)}"
            self.logger().info(msg)

    async def _update_order_status_now(self):
        tracked_orders = list(self._in_flight_orders.values())
        tracked_exch_order_ids = [await x.get_exchange_order_id()
                                  for x in tracked_orders]
        response = await self._ocean_client.get_order_status(tracked_exch_order_ids)
        if 0 != response['code']:
            self.logger().error(f"ocean failed to get order status: "
                                f"code={response['code']}, message={response['message']}, "
                                f"exch_order_ids={tracked_exch_order_ids}")
            return

        order_updates: [Int, Any] = {entry['id']: entry for entry in response['data']}
        for tracked_order in tracked_orders:
            exch_order_id = await tracked_order.get_exchange_order_id()
            client_order_id = tracked_order.client_order_id
            order_update = order_updates.get(int(exch_order_id))
            # order missing from exchange
            if order_update is None:
                self.c_stop_tracking_order(client_order_id)
                self.c_trigger_event(
                    self.MARKET_ORDER_FAILURE_EVENT_TAG,
                    MarketOrderFailureEvent(self._current_timestamp,
                                            client_order_id,
                                            tracked_order.order_type)
                )
                self.logger().warning(f"stop tracking order not in exchange "
                                      f"{repr(tracked_order)}")
                continue
            else:
                await self._update_an_order_status(tracked_order, order_update)

    ORDER_STATES = ('wait', 'done', 'cancelling', 'cancel')

    async def _update_an_order_status(self,
                                      order: OceanInFlightOrder,
                                      order_update: Dict[str, Any]):
        '''
        order: tracked order
        order_update: status of order in exchange
        '''
        order_state = order_update["state"]
        if order_state not in OceanMarket.ORDER_STATES:
            self.logger().warning(f"Unrecognized order update state - {order_update}")
        order.last_state = order_state

        # Calculate new executed amount for this update.
        new_confirmed_amount = Decimal(order_update["executed_volume"])
        execute_amount_diff = new_confirmed_amount - order.executed_amount_base
        if execute_amount_diff > s_decimal_0:
            order.executed_amount_base = new_confirmed_amount
            execute_price = Decimal(order_update["avg_price"])
            order.executed_amount_quote = new_confirmed_amount * execute_price
            exch_order_id = await order.get_exchange_order_id()

            tradefee: TradeFee = self.c_get_fee(
                order.base_asset, order.quote_asset, order.order_type,
                order.trade_type, execute_price, execute_amount_diff)
            order.apply_fee(tradefee.percent)

            order_filled_event = OrderFilledEvent(
                self._current_timestamp, order.client_order_id,
                order.trading_pair, order.trade_type, order.order_type,
                execute_price, execute_amount_diff, tradefee,
                exchange_trade_id=exch_order_id
            )
            self.logger().info(f"Filled {execute_amount_diff} out of {order.amount} of the "
                               f"order {order.client_order_id}.")
            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

        if order.is_open:
            return

        if order.is_done:
            self.c_stop_tracking_order(order.client_order_id)
            if not order.is_cancelled:
                if order.trade_type is TradeType.BUY:
                    self.logger().info(f"The market buy order {order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                         BuyOrderCompletedEvent(self._current_timestamp,
                                                                order.client_order_id,
                                                                order.base_asset,
                                                                order.quote_asset,
                                                                order.fee_asset or order.base_asset,
                                                                order.executed_amount_base,
                                                                order.executed_amount_quote,
                                                                order.fee_paid,
                                                                order.order_type))
                else:
                    self.logger().info(f"The market sell order {order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                         SellOrderCompletedEvent(self._current_timestamp,
                                                                 order.client_order_id,
                                                                 order.base_asset,
                                                                 order.quote_asset,
                                                                 order.fee_asset or order.quote_asset,
                                                                 order.executed_amount_base,
                                                                 order.executed_amount_quote,
                                                                 order.fee_paid,
                                                                 order.order_type))
            else:
                self.logger().info(f"The market order {order.client_order_id} "
                                   f"has been cancelled according to order status API.")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         order.client_order_id))

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                msg = f"{e}\n{traceback.format_exc()}"
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True, app_warning_msg=msg)
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                    self._update_trade_fees()
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                msg = f"{e}\n{traceback.format_exc()}"
                self.logger().network("Error while fetching trading rules.", exc_info=True,
                                      app_warning_msg=msg)
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trade_fees_initialized": len(self._trade_fees) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:
        '''
        :return: exchange order id
        '''
        path_url = "orders"
        side = "buy" if is_buy else "sell"
        order_type_str = "limit" if order_type is OrderType.LIMIT else "market"
        params = {
            "market": trading_pair,
            "side": side,
            "volume": f"{amount:f}",
            "ord_type": order_type_str
        }
        if order_type is OrderType.LIMIT:
            params["price"] = f"{price:f}"
        resp = await self._ocean_client.create_order(**params)
        if 0 != resp['code']:
            self.logger().error(f"ocean failed to create order: "
                                f"code={resp['code']}, message={resp['message']}")
            raise Exception('create order failed')

        order_id = str(resp['data']['id'])
        return order_id

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        decimal_price = self.c_quantize_order_price(trading_pair, price)

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Ocean for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Ocean. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"buy-{trading_pair}-{tracking_nonce}"

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        decimal_price = (self.c_quantize_order_price(trading_pair, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type is OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Ocean for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Ocean. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.MARKET, object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"sell-{trading_pair}-{tracking_nonce}"
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    ORDER_CANCELLED_STATES = ('cancel', 'cancelled', 'cancelling', 'done')

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order {order_id}. Order not found.")

            exch_order_id = int(tracked_order.exchange_order_id)
            response: Dict[str, Any] = await self._ocean_client.cancel_order(exch_order_id)
            if 0 != response['code']:
                self.logger().error(f"ocean failed to cancel order: "
                                    f"code={response['code']}, message={response['message']}, "
                                    f"order_id={order_id}, exch_order_id={exch_order_id}")
                return

            data = response['data']
            if data['state'] in OceanMarket.ORDER_CANCELLED_STATES:
                self.logger().info(f"Successfully cancelled order: "
                                   f"order_id={order_id} exch_order_id={exch_order_id}.")
                self.c_stop_tracking_order(tracked_order.client_order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
            else:
                self.logger().error(
                    f"ocean failed to cancel order: order_id={order_id} "
                    f"exch_order_id={exch_order_id} response={response}"
                )

        except Exception as e:
            msg = f"ocean failed to cancel order: order_id={order_id}"
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True, app_warning_msg=msg
            )

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        resp = None
        try:
            async with timeout(timeout_seconds):
                resp = await self._ocean_client.cancel_all_orders()
                if 0 != resp['code']:
                    self.logger().error(f"ocean failed to cancel all orders: "
                                        f"code={resp['code']}, message={resp['message']}")
                    return
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.", exc_info=True,
                app_warning_msg="Failed to cancel all orders with Ocean")
            return
        return self._calc_cancel_all_result(resp['data'])

    def _calc_cancel_all_result(self, order_updates: List) -> \
            List[CancellationResult]:
        results_exch_id = {}
        for entry in order_updates:
            exch_order_id = str(entry['id'])
            success = True if entry['state'] in \
                OceanMarket.ORDER_CANCELLED_STATES else False
            results_exch_id[exch_order_id] = success

        results: List[CancellationResult] = []
        for order in self._in_flight_orders.values():
            if order.is_done:
                continue
            success = results_exch_id.get(order.exchange_order_id, False)
            result = CancellationResult(order.client_order_id, success)
            results.append(result)

        return results

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books.get(trading_pair)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = OceanInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)

        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount
