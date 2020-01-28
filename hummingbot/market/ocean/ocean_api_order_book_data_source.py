#!/usr/bin/env python

import asyncio
import json
import logging
import os
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import time
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.market.ocean.ocean_order_book import OceanOrderBook
from hummingbot.market.ocean.ocean_client import OceanClient


OCEAN_WS_URL = os.environ.get('ocean_websocket_api_base_url',
                              'wss://ws-slanger.oceanex.pro/app/a4931d3a95e48863076c739e9527?protocol=7&version=4.3.1&flash=false&client=js')


class OceanAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _oaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._oaobds_logger is None:
            cls._oaobds_logger = logging.getLogger(__name__)
        return cls._oaobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs
        self._order_book_create_function = lambda: OrderBook()

        self.logger().debug(f"create OceanAPIOrderBookDataSource "
                            f"ws_base_api_url = {OCEAN_WS_URL} ")

    @staticmethod
    def get_usd_conversion_rates(tickers: Dict[str, Any]) -> Dict[str, float]:
        '''
        Use one of possible_sources as conversion rate from crypto to
        us dollar.
        '''
        possible_sources = ['last', 'open']
        conversion_rates = {}

        for pair, info in tickers.items():
            if 'usdt' != info['quote_unit']:
                continue

            for source in possible_sources:
                rate = float(info[source])
                if rate > 0:
                    base_asset = info['base_unit']
                    conversion_rates[base_asset] = rate
                    break

        return conversion_rates

    @classmethod
    def set_usd_volume_in_tickers(cls, tickers: Dict[str, Any]) -> Dict[str, Any]:
        '''
        tickers is response data from exchange. Fill same data with volume
        in us dollars.
        '''
        conversion_rates = OceanAPIOrderBookDataSource.get_usd_conversion_rates(tickers)

        for pair, info in tickers.items():
            volume = float(info['volume'])
            info['USDVolume'] = 0
            if 'usdt' == info['quote_unit']:
                info['USDVolume'] = volume
            elif volume > 0:
                quote_unit = info['quote_unit']
                if quote_unit in conversion_rates:
                    info['USDVolume'] = volume * conversion_rates[quote_unit]
                else:
                    cls.logger().warning(f"{pair} has no conversion rate")
        return tickers

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include usd volume, baseAsset and quoteAsset
        """
        async with OceanClient() as ocean_client:
            tickers = await ocean_client.get_all_tickers()

        if tickers['code'] != 0:
            raise IOError(f"Error fetching Ocean tickers information. "
                          f"HTTP response code is {tickers['code']}.")
        data = tickers['data']
        OceanAPIOrderBookDataSource.set_usd_volume_in_tickers(data)

        all_markets: pd.DataFrame = pd.DataFrame.from_dict(
            data=data, orient='index',
            columns=['base_unit', 'quote_unit', 'volume', 'USDVolume'])
        all_markets.rename({"base_unit": "baseAsset",
                            "quote_unit": "quoteAsset"},
                           axis="columns", inplace=True)
        all_markets.volume = all_markets.volume.astype(float)

        return all_markets

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception as e:
                msg = f"Error getting active exchange information." \
                    f" exception = {e}"
                self._trading_pairs = []
                self.logger().network(
                    f"Error getting active exchange information.",
                    exc_info=True, app_warning_msg=msg
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: OceanClient, trading_pair: str,
                           limit: int = 2) -> Dict[str, Any]:
        data: Dict[str, Any] = await client.get_order_book(trading_pair, limit)
        return data['data']

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        trading_pairs: List[str] = await self.get_trading_pairs()
        number_of_pairs: int = len(trading_pairs)
        trackers: Dict[str, OrderBookTrackerEntry] = {}
        async with OceanClient() as client:
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_timestamp = snapshot['timestamp']
                    snapshot_msg: OrderBookMessage = OceanOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        snapshot_timestamp,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    trackers[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index+1}/{number_of_pairs} completed.")
                    # stay under rate limit of 3000/min
                    await asyncio.sleep(1.0)
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ",
                                        exc_info=True)
                    await asyncio.sleep(1)
        return trackers

    async def _subscribe_to(self, ws: websockets.WebSocketClientProtocol,
                            channel: str):
        subscribe_request: Dict[str, Any] = {
            "event": "pusher:subscribe",
            "data": {"channel": channel}
        }
        await ws.send(json.dumps(subscribe_request))

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(OCEAN_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        channel = f"market-{trading_pair}-trade-global"
                        await self._subscribe_to(ws, channel)

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        event_type: str = msg['event']
                        if "trades" == event_type:
                            trading_pair = msg["channel"].split("-")[1]
                            data = json.loads(msg['data'])
                            trades = data['trades']
                            for trade in trades:
                                trade_message: OrderBookMessage = OceanOrderBook.trade_message_from_exchange(
                                    trade, metadata={"trading_pair": trading_pair}
                                )
                                output.put_nowait(trade_message)
                        elif "pusher:connection_established" == event_type:
                            pass
                        elif "pusher_internal:subscription_succeeded" == event_type:
                            pass
                        else:
                            self.logger().debug(f"Unrecognized message received from Ocean websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass  # no diffs on ocean

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        await self._listen_for_order_book_snapshots_ws(ev_loop, output)

    async def _listen_for_order_book_snapshots_http(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with OceanClient() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_timestamp = snapshot['timestamp']
                            snapshot_msg: OrderBookMessage = OceanOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            # stay below rate limit
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _listen_for_order_book_snapshots_ws(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(OCEAN_WS_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        channel = f"market-{trading_pair}-global"
                        await self._subscribe_to(ws, channel)

                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        event_type: str = msg['event']
                        if "update" == event_type:
                            trading_pair = msg["channel"].split("-")[1]
                            snapshot = json.loads(msg['data'])
                            snapshot_timestamp = int(time.time())
                            snapshot_msg: OrderBookMessage = OceanOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                        elif "pusher:connection_established" == event_type:
                            pass
                        elif "pusher_internal:subscription_succeeded" == event_type:
                            pass
                        else:
                            self.logger().debug(f"Unrecognized message received from Ocean websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
