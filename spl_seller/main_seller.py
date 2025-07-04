import http.server
import os
import socketserver
import threading
import time

from solders.keypair import Keypair

from spl_seller.modules.swap import Swapper
from spl_seller.modules.wallet_info import Wallet
from spl_seller.types.holdings_data import HoldingData
from spl_seller.utils.log import get_logger
from spl_seller.utils.settings import settings_key_values

logger = get_logger()  # Get the logger instance


class SplSeller:
    def __init__(self):
        try:
            self.BIRDEYE_API_TOKEN = settings_key_values["BIRDEYE_API_TOKEN"]
            self.wallets = settings_key_values["wallets"]
            self.HELIUS_API_KEY = settings_key_values["HELIUS_API_KEY"]

        except KeyError:
            raise ValueError("Environment variable is required but not set")

        self.WalletInterface = Wallet(
            wallets=self.wallets,
            HELIUS_API_KEY=self.HELIUS_API_KEY,
            BIRDEYE_API_TOKEN=self.BIRDEYE_API_TOKEN,
        )

        self.SwapInterface = Swapper(HELIUS_API_KEY=self.HELIUS_API_KEY)
        self.prices_list = list()
        for each in self.wallets:
            balance = self.SwapInterface.get_balance_with_retry(pubkey=each.key_pair.pubkey()) / 1e9
            logger.info(f"Wallet {each.public_key} balance: {balance} SOL")

    def run(self):
        logger.info("----------------------------Starting Run----------------------------")
        self.WalletInterface.update_holdings()
        self.WalletInterface._print_holdings()
        holdings = self.WalletInterface.holdings

        for token in holdings:
            if token.current_price_per_token_usd <= token.stop_price_usd:
                logger.info("***Below stop price, sell all***")
                self.sell_tokens(token_to_sell=token, amount=token.current_amount_raw)
            elif token.buy_duration_hours >= 240 and abs(token.current_amount - token.buy_amount) < 0.01:
                logger.info("***Duration Elapsed, Sell all***")
                self.sell_tokens(token_to_sell=token, amount=token.current_amount_raw)
            elif token.current_price_per_token_usd >= token.profit_price_per_token:
                logger.info("***Profit Price reached***")
                self.sell_tokens(token_to_sell=token, amount=token.profit_sell_amount)
        logger.info("----------------------------Run End----------------------------")

    def sell_tokens(self, token_to_sell: HoldingData, amount: int):
        """Sell token

        Args:
            tokens_to_buy (List[]): _description_
        """
        logger.info("Selling token {s}: {t}".format(s=token_to_sell.symbol, t=token_to_sell.name))
        logger.info(token_to_sell)
        key_pair = self._get_key_pair(public_key=token_to_sell.public_key)
        try:
            self.SwapInterface.place_sell_order(INPUT_MINT=token_to_sell.mint, AMOUNT=amount, KEY_PAIR=key_pair)
        except Exception as e:
            logger.error("Error Selling {e}".format(e=e))

    def _get_key_pair(self, public_key: str) -> Keypair:
        """_summary_

        Args:
            public_key (str): _description_

        Returns:
            KeyPair: _description_
        """
        for each in self.wallets:
            if each.public_key == public_key:
                return each.key_pair
        return None

    def get_sleep_time(self) -> int:
        """_summary_

        Returns:
            int: _description_
        """
        number_of_holdings = len(self.WalletInterface.holdings)
        if number_of_holdings == 0:
            return 60
        else:
            return 10


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
            time.sleep(seconds_to_sleep)
        except KeyboardInterrupt:
            logger.info("\nStopped by user")
            break
