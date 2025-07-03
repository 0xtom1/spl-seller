import http.server
import os
import socketserver
import threading
import time
from datetime import datetime, timezone
from typing import List

from spl_seller.modules.swap import Swapper
from spl_seller.modules.wallet_info import Wallet
from spl_seller.types.exit_strategy import ExitStrategy
from spl_seller.types.holdings_data import HoldingData
from spl_seller.utils.log import get_logger
from spl_seller.utils.settings import settings_key_values

logger = get_logger()  # Get the logger instance


class SplSeller:
    def __init__(self):
        try:
            self.BIRDEYE_API_TOKEN = settings_key_values["BIRDEYE_API_TOKEN"]
            self.SOLANA_PRIVATE_KEY = settings_key_values["SOLANA_PRIVATE_KEY"]
            self.HELIUS_API_KEY = settings_key_values["HELIUS_API_KEY"]

        except KeyError:
            raise ValueError("Environment variable is required but not set")

        self.WalletInterface = Wallet(
            WALLET_PRIVATE_KEY=self.SOLANA_PRIVATE_KEY,
            HELIUS_API_KEY=self.HELIUS_API_KEY,
            BIRDEYE_API_TOKEN=self.BIRDEYE_API_TOKEN,
        )


        self.SwapInterface = Swapper(WALLET_PRIVATE_KEY=self.SOLANA_PRIVATE_KEY, HELIUS_API_KEY=self.HELIUS_API_KEY)
        self.prices_list = list()

    def run(self):
        logger.info("----------------------------Starting Run----------------------------")
        self.WalletInterface.update_holdings()

        holdings = self.WalletInterface.holdings

        for token in holdings:
            if not token.current_price_per_token_usd or not token.current_price_per_token_sol:
                logger.info("Quote not found for token: {t}".format(t=token))
                continue
            exit_strategy = self._get_exit_strategy(percent_remaining=token.sell_percent_remaining)
            if not exit_strategy:
                logger.info("Exit Strategy is None")

            token.stop_price_usd = max(
                (1 + exit_strategy.stop_price_per_token_percent_change) * token.buy_price_per_token_usd,
                token.initial_stop_price_usd,
            )

            logger.info(token)
            logger.info(exit_strategy)

            original_buy_amount = int(token.current_amount_raw / token.sell_percent_remaining)
            logger.info("Original Buy Amount: {t}".format(t=original_buy_amount))

            profit_sell_amount = min(
                int(original_buy_amount * exit_strategy.profit_sell_amount_percent) - 1, token.current_amount_raw
            )
            logger.info("Profit Sell Amount: {t}".format(t=profit_sell_amount))

            profit_price_per_token = (
                1 + exit_strategy.profit_price_per_token_percent_change
            ) * token.buy_price_per_token_usd

            logger.info("Profit Price per token: {t}".format(t=profit_price_per_token))

            if token.current_price_per_token_usd <= token.stop_price_usd:
                logger.info("***Below stop price, sell all***")
                self.sell_tokens(token_to_sell=token, amount=token.current_amount_raw)
            elif token.buy_duration_hours >= 240 and abs(token.current_amount - token.buy_amount) < 0.01:
                logger.info("***Duration Elapsed, Sell all***")
                self.sell_tokens(token_to_sell=token, amount=token.current_amount_raw)
            elif token.current_price_per_token_usd >= profit_price_per_token:
                logger.info("***Profit Price reached***")
                self.sell_tokens(token_to_sell=token, amount=profit_sell_amount)
            logger.info("----------------------------Run End----------------------------")

    def get_holdings(self) -> List[HoldingData]:
        return self.WalletInterface.holdings

    def sell_tokens(self, token_to_sell: HoldingData, amount: int):
        """Sell token

        Args:
            tokens_to_buy (List[]): _description_
        """
        logger.info("Selling token {s}: {t}".format(s=token_to_sell.symbol, t=token_to_sell.name))
        try:
            self.SwapInterface.place_sell_order(INPUT_MINT=token_to_sell.mint, AMOUNT=amount)
        except Exception as e:
            logger.error("Error Selling {e}".format(e=e))

    def _get_exit_strategy(self, percent_remaining: float) -> ExitStrategy:
        for strat in self.EXIT_STRATEGY:
            if strat["amount_remaining_percent_lte"] >= percent_remaining > strat["amount_remaining_percent_gt"]:
                return ExitStrategy(
                    amount_remaining_percent_gt=strat["amount_remaining_percent_gt"],
                    amount_remaining_percent_lte=strat["amount_remaining_percent_lte"],
                    stop_price_per_token_percent_change=strat["stop_price_per_token_percent_change"],
                    profit_price_per_token_percent_change=strat["profit_price_per_token_percent_change"],
                    profit_sell_amount_percent=strat["profit_sell_amount_percent"],
                )
        return None

    def get_sleep_time(self) -> int:
        """_summary_

        Returns:
            int: _description_
        """
        number_of_holdings = len(self.WalletInterface.holdings)
        utc_minute = datetime.now(timezone.utc).minute
        seconds_to_top_of_hour = (60 - utc_minute) * 60
        if number_of_holdings == 0 and utc_minute <= 59 and utc_minute >= 25:
            return seconds_to_top_of_hour
        else:
            return 8


def run_server():
    port = int(os.getenv("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"Serving HTTP on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    # Start HTTP server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    Seller = SplSeller()
    while True:
        try:
            Seller.run()
            seconds_to_sleep = Seller.get_sleep_time()
            if seconds_to_sleep > 15:
                logger.info("Sleeping {x} seconds".format(x=seconds_to_sleep))
            time.sleep(seconds_to_sleep)
        except KeyboardInterrupt:
            logger.info("\nStopped by user")
            break
