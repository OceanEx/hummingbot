#!/usr/bin/env python
import logging
from typing import (
    Dict,
    Optional
)
import ujson

from aiokafka import ConsumerRecord
from sqlalchemy.engine import RowProxy

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

_oob_logger = None


cdef class OceanOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _oob_logger
        if _oob_logger is None:
            _oob_logger = logging.getLogger(__name__)
        return _oob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            # no update id in API so use timestamp which may not be unique
            "update_id": timestamp,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["s"],
            "update_id": msg["u"],
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=timestamp)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["lastUpdateId"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=record["timestamp"] * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record["json"])  # Ocean json in DB is TEXT
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["s"],
            "update_id": msg["u"],
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=record["timestamp"] * 1e-3)

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        msg = record["json"]
        if metadata:
            msg.update(metadata)
        ts = record.timestamp
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["s"],
            "trade_type": float(TradeType.SELL.value) if msg["m"] else float(TradeType.BUY.value),
            "trade_id": msg["t"],
            "update_id": ts,
            "price": msg["p"],
            "amount": msg["q"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        ts = msg['date']
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg['trading_pair'],
            "trade_type": float(TradeType.SELL.value) if 'sell' == msg["type"] else float(TradeType.BUY.value),
            "trade_id": msg["tid"],
            "update_id": ts,
            "price": msg["price"],
            "amount": msg["amount"]
        }, timestamp=ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = OceanOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
