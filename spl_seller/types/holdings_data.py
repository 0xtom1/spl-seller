from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from spl_seller.types.exit_strategy import ExitStrategy


@dataclass
class HoldingData:
    public_key: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    address: Optional[str] = None
    mint: Optional[str] = None
    decimals: Optional[int] = None
    current_amount_raw: Optional[int] = None
    current_amount: Optional[float] = None
    current_price_per_token_usd: Optional[float] = None
    current_price_per_token_sol: Optional[float] = None
    current_price_time: Optional[datetime] = None
    current_value_sol: Optional[float] = None
    buy_time: Optional[datetime] = None
    buy_duration_hours: Optional[int] = None
    buy_amount: Optional[int] = 0
    buy_price_per_token_usd: Optional[float] = None
    buy_price_per_token_sol: Optional[float] = None
    buy_price_usd_total: Optional[float] = 0
    buy_price_sol_total: Optional[float] = 0
    sell_count: Optional[int] = 0
    sell_amount_mint: Optional[float] = 0
    sell_amount_sol: Optional[float] = 0
    sell_percent: Optional[float] = None
    sell_percent_remaining: Optional[float] = None
    stop_price_usd: Optional[float] = None
    exit_strategy: Optional[ExitStrategy] = None
    profit_sell_amount: Optional[int] = None
    profit_price_per_token: Optional[float] = None

    def __str__(self):
        parts = []
        parts.append(f"\nPubKey: {self.public_key}")
        parts.append(f"Symbol: {self.symbol} - Name: {self.name} - Address: {self.address} - Mint: {self.mint}")
        parts.append(f"\tcurrent_amount_raw: {self.current_amount_raw}")
        parts.append(f"\tcurrent_amount: {self.current_amount:.2f}")
        if self.current_price_per_token_usd is not None:
            parts.append(f"\tcurrent_price_per_token_usd: ${self.current_price_per_token_usd:.15f}")
            parts.append(f"\tcurrent_price_per_token_sol: {self.current_price_per_token_sol:.15f}")
            parts.append(f"\tcurrent_price_time: {self.current_price_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.current_value_sol is not None:
            parts.append(f"\tcurrent_value_sol: {self.current_value_sol:.2f}")
        if self.buy_time:
            parts.append(f"\tbuy_time: {self.buy_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.buy_duration_hours is not None:
            parts.append(f"\tbuy_duration_hours: {self.buy_duration_hours}")
        if self.buy_amount is not None:
            parts.append(f"\tbuy_amount: {self.buy_amount}")
        if self.buy_price_per_token_usd is not None:
            parts.append(f"\tbuy_price_per_token_usd: ${self.buy_price_per_token_usd:.15f}")
        if self.buy_price_per_token_sol is not None:
            parts.append(f"\tbuy_price_per_token_sol: {self.buy_price_per_token_sol:.15f}")
        if self.buy_price_usd_total is not None:
            parts.append(f"\tbuy_price_usd_total: ${self.buy_price_usd_total:.2f}")
        if self.buy_price_sol_total is not None:
            parts.append(f"\tbuy_price_sol_total: {self.buy_price_sol_total:.4f}")
        if self.sell_percent is not None:
            parts.append(f"\tsell_count: {self.sell_count}")
            parts.append(f"\tsell_amount_mint: {self.sell_amount_mint:.2f}")
            parts.append(f"\tsell_amount_sol: {self.sell_amount_sol:.4f}")
            parts.append(f"\tsell_percent: {self.sell_percent*100:.2f}%")
            parts.append(f"\tsell_percent_remaining: {self.sell_percent_remaining*100:.2f}%")
        if self.stop_price_usd is not None:
            parts.append(f"\tstop_price_usd: ${self.stop_price_usd:.10f}")
        if self.exit_strategy:
            parts.append(f"\tprofit_sell_amount: {self.profit_sell_amount}")
            parts.append(f"\tprofit_price_per_token: ${self.profit_price_per_token:.15f}")
            parts.append(
                f"\tExitStrategy:\n"
                f"\t\tAmount Remaining >: {self.exit_strategy.amount_remaining_percent_gt*100:.2f}%\n"
                f"\t\tAmount Remaining ≤: {self.exit_strategy.amount_remaining_percent_lte*100:.2f}%\n"
                f"\t\tStop Price Change: {self.exit_strategy.stop_price_per_token_percent_change*100:.2f}%\n"
                f"\t\tProfit Price Change: {self.exit_strategy.profit_price_per_token_percent_change*100:.2f}%\n"
                f"\t\tProfit Sell Amount: {self.exit_strategy.profit_sell_amount_percent*100:.2f}%"
            )

        return "\n".join(parts) or "HoldingData (empty)"
