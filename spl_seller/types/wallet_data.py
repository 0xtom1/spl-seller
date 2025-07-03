from dataclasses import dataclass, field
from typing import List
from solders.keypair import Keypair
from spl_seller.types.exit_strategy import ExitStrategy


@dataclass
class WalletInfo:
    public_key: str
    key_pair: Keypair
    exit_strategy: List[ExitStrategy] = field(default_factory=list)

    def __str__(self):
        parts = []
        parts.append(f"public_key: {self.public_key[-10:]}")
        if self.exit_strategy:
            for each in self.exit_strategy:
                parts.append(
                    f"\tExitStrategy:\n"
                    f"\t\tAmount Remaining >: {each.amount_remaining_percent_gt*100:.2f}%\n"
                    f"\t\tAmount Remaining ≤: {each.amount_remaining_percent_lte*100:.2f}%\n"
                    f"\t\tStop Price Change: {each.stop_price_per_token_percent_change*100:.2f}%\n"
                    f"\t\tProfit Price Change: {each.profit_price_per_token_percent_change*100:.2f}%\n"
                    f"\t\tProfit Sell Amount: {each.profit_sell_amount_percent*100:.2f}%"
                )

        return "\n".join(parts) or "WalletInfo (empty)"
