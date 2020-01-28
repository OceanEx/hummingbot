from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional
)

from hummingbot.core.event.events import (
    OrderType,
    TradeType
)
from hummingbot.market.ocean.ocean_market import OceanMarket
from hummingbot.market.in_flight_order_base import InFlightOrderBase


cdef class OceanInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 initial_state: str = "wait"):
        super().__init__(
            OceanMarket,
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            initial_state
        )

    @property
    def is_done(self) -> bool:
        return self.last_state in {"done", "cancel"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"cancel"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"cancel"}

    @property
    def is_open(self) -> bool:
        return self.last_state in {"wait", "cancelling"}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> InFlightOrderBase:
        cdef:
            OceanInFlightOrder retval = OceanInFlightOrder(
                client_order_id=data["client_order_id"],
                exchange_order_id=data["exchange_order_id"],
                trading_pair=data["trading_pair"],
                order_type=getattr(OrderType, data["order_type"]),
                trade_type=getattr(TradeType, data["trade_type"]),
                price=Decimal(data["price"]),
                amount=Decimal(data["amount"]),
                initial_state=data["last_state"]
            )
        retval.executed_amount_base = Decimal(data["executed_amount_base"])
        retval.executed_amount_quote = Decimal(data["executed_amount_quote"])
        retval.fee_asset = data["fee_asset"]
        retval.fee_paid = Decimal(data["fee_paid"])
        retval.last_state = data["last_state"]
        return retval

    def apply_fee(self, fee_rate: Decimal):
        if TradeType.BUY == self.trade_type:
            self.fee_asset = self.base_asset
            self.fee_paid = fee_rate * self.executed_amount_base
        else:
            self.fee_asset = self.quote_asset
            self.fee_paid = fee_rate * self.executed_amount_quote
