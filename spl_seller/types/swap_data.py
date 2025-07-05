from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class BuyData:
    buy_time: Optional[datetime] = None
    sol_price: Optional[float] = 0
    buy_amount: Optional[float] = 0
    sol_spent: Optional[float] = 0

    def __str__(self):
        parts = []

        if self.buy_time:
            parts.append(f"\n\tbuy_time: {self.buy_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.sol_price is not None:
            parts.append(f"\tsol_price: ${self.sol_price:.2f}")
        if self.buy_amount is not None:
            parts.append(f"\tbuy_amount: {self.buy_amount}")
        if self.sol_spent is not None:
            parts.append(f"\tsol_spent: {self.sol_spent:.8f}")
        return "\n".join(parts) or "BuyData (empty)"


@dataclass
class SellData:
    sell_time: Optional[datetime] = None
    sell_amount: Optional[float] = 0
    sol_received: Optional[float] = 0

    def __str__(self):
        parts = []

        if self.sell_time:
            parts.append(f"\n\tsell_time: {self.sell_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.sell_amount is not None:
            parts.append(f"\tsell_amount: {self.sell_amount}")
        if self.sol_received is not None:
            parts.append(f"\tsol_received: {self.sol_received:.8f}")
        return "\n".join(parts) or "SellData (empty)"
