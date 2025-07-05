from datetime import datetime, timedelta, timezone
from time import sleep
from typing import List

from heliuspy import HeliusAPI
from solana.rpc.api import Client

from spl_seller.modules.token_charts import TokenCharts
from spl_seller.types.exit_strategy import ExitStrategy
from spl_seller.types.holdings_data import HoldingData
from spl_seller.types.swap_data import BuyData, SellData
from spl_seller.types.wallet_data import WalletInfo
from spl_seller.utils.log import get_logger

logger = get_logger()


class Wallet:
    def __init__(self, wallets: List[WalletInfo], HELIUS_API_KEY: str, BIRDEYE_API_TOKEN: str):
        self.wallets = wallets
        # Configuration
        self.RPC_ENDPOINT = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        self.BIRDEYE_API_TOKEN = BIRDEYE_API_TOKEN
        self.Helius = HeliusAPI(api_key=HELIUS_API_KEY)
        self.COMMITMENT = "confirmed"  # Commitment level for RPC calls
        self.holdings = list()
        self.sol_mint = "So11111111111111111111111111111111111111112"  # SOL
        self.usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        # Initialize Solana client
        try:
            self.client = Client(self.RPC_ENDPOINT, commitment=self.COMMITMENT)
        except Exception as e:
            raise Exception(f"Failed to connect to Helius RPC: {e}")

        self.exclusion_list = list()
        self.TokenChart = TokenCharts(BIRDEYE_API_TOKEN=self.BIRDEYE_API_TOKEN)

    @property
    def wallets(self) -> List[WalletInfo]:
        return self._wallets

    @wallets.setter
    def wallets(self, value: List[WalletInfo]):
        self._wallets = value

    @property
    def holdings(self) -> List[HoldingData]:
        return self._holdings

    @holdings.setter
    def holdings(self, value: List[HoldingData]):
        self._holdings = value

    def get_token_accounts_all(self) -> List[HoldingData]:
        """_summary_

        Returns:
            List[HoldingData]: _description_
        """
        results = list()
        for wallet in self.wallets:
            results += self.get_token_accounts(pub_key=wallet.public_key)
        return results

    def get_token_accounts(self, pub_key: str) -> List[HoldingData]:
        """Get token accounts for wallet

        Raises:
            Exception: _description_

        Returns:
            list: _description_
        """
        ignore_mints = [
            "BfSbstVpvUPaqEm57ZiPBN7fmkQ41NxdGCmARBNFpump",
        ]
        try:
            token_accounts = self.Helius.get_token_accounts(
                owner=pub_key,
                displayOptions={"showZeroBalance": False},
                page=1,
                limit=100,  # Adjust limit as needed
            )
        except Exception as e:
            logger.info("Error getting token accounts: {e}".format(e=e))
            sleep(2)
            return list()

        assert token_accounts

        expected_keys = sorted(["jsonrpc", "result", "id"])
        response_keys = sorted(token_accounts.keys())

        if expected_keys != response_keys:
            return list()

        response_result_keys = sorted(token_accounts["result"].keys())

        if (
            "token_accounts" not in response_result_keys
            or "total" not in response_result_keys
            or "limit" not in response_result_keys
        ):
            return list()

        token_list = list()
        for each in token_accounts["result"]["token_accounts"]:
            if each["mint"] in ignore_mints:
                continue

            if each["amount"] > 1000 and each["mint"] not in self.exclusion_list:
                token_list.append(
                    HoldingData(
                        public_key=pub_key,
                        mint=each["mint"],
                        address=each["address"],
                        current_amount_raw=each["amount"],
                    )
                )
        return token_list

    def update_holdings(self):
        """Update self.holdings"""
        current_tokens = self.get_token_accounts_all()
        tokens_to_update = list()
        for each in current_tokens:
            existing_token = self.get_holdings_token_from_list(mint=each.mint, pub_key=each.public_key)
            if not existing_token:
                tokens_to_update.append(each)
            elif each.current_amount_raw != existing_token.current_amount_raw:
                tokens_to_update.append(each)

        if len(tokens_to_update) > 0:
            logger.info("Tokens to updates, sleeping for 120")
            sleep(120)
            current_tokens = self.get_token_accounts_all()
            tokens_to_update = list()
            for each in current_tokens:
                existing_token = self.get_holdings_token_from_list(mint=each.mint, pub_key=each.public_key)
                if not existing_token:
                    tokens_to_update.append(each)
                elif each.current_amount_raw != existing_token.current_amount_raw:
                    tokens_to_update.append(each)

        # Remove tokens from self.holdings that have amounts updated so they get re-added
        tokens_to_update_accounts = [x.address for x in tokens_to_update]
        self.holdings = [x for x in self.holdings if x.address not in tokens_to_update_accounts]

        # Remove tokens from list that aren't in current holdings
        current_tokens_address = [x.address for x in current_tokens]
        self.holdings = [x for x in self.holdings if x.address in current_tokens_address]

        if len(tokens_to_update) > 0:
            logger.info("Updating {a} tokens".format(a=len(tokens_to_update)))
        for token in tokens_to_update:
            self.populate_holding_token(token=token)

        self.update_prices()

    def update_prices(self):
        quote_time = datetime.now(timezone.utc)
        mints_to_quote = list()
        quotes_to_get_symbols = list()
        for each in self.holdings:
            if (
                each.current_price_per_token_usd is None
                or each.current_price_time is None
                or each.current_price_per_token_sol is None
                or each.percent_from_sell is None
            ):
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)
                continue
            time_diff = quote_time - each.current_price_time
            if time_diff > timedelta(seconds=10) and each.percent_from_sell <= 0.2:
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)
            elif time_diff > timedelta(seconds=30) and each.percent_from_sell <= 0.3:
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)
            elif time_diff > timedelta(seconds=60) and each.percent_from_sell <= 0.4:
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)
            elif time_diff > timedelta(seconds=180) and each.percent_from_sell <= 0.5:
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)
            elif time_diff > timedelta(seconds=300):
                mints_to_quote.append(each.mint)
                quotes_to_get_symbols.append(each.symbol)

        mints_to_quote = list(set(mints_to_quote))
        logger.info("Quotes to get: {s}".format(s=quotes_to_get_symbols))
        quotes = self.TokenChart.get_quotes(mints=mints_to_quote, liquidity=100000)
        if len(quotes) < len(mints_to_quote):
            new_mints = [x for x in mints_to_quote if x not in quotes]
            quotes_less_liquidity = self.TokenChart.get_quotes(mints=new_mints, liquidity=40000)
            quotes.update(quotes_less_liquidity)

        for token in self.holdings:
            if token.mint not in mints_to_quote:
                continue

            quote_values = quotes.get(token.mint)
            if quote_values is None:
                logger.info("Quote is None")
                logger.info(token)
                logger.info(quote_values)
                continue

            token.buy_duration_hours = int((quote_time - token.buy_time).total_seconds() / 60.0 / 60.0)
            token.current_price_per_token_sol = quote_values["current_price_per_token_sol"]
            token.current_price_per_token_usd = quote_values["current_price_per_token_usd"]

            if not token.current_price_per_token_usd or not token.current_price_per_token_sol:
                continue

            token.current_value_sol = token.current_price_per_token_sol * token.current_amount
            token.current_price_time = quote_time
            token = self._populate_exit_data(token=token)

    def _populate_exit_data(self, token: HoldingData) -> HoldingData:
        """ """
        if not token.current_price_per_token_usd or not token.current_price_per_token_sol:
            logger.info("Quote not found for token: {t}".format(t=token))
            return token

        if not token.exit_strategy:
            logger.info("Exit Strategy is None")
            return token

        away_from_profit = (token.profit_price_per_token / token.current_price_per_token_usd) - 1.0
        away_from_sell = 1.0 - (token.stop_price_usd / token.current_price_per_token_usd)

        token.percent_from_sell = round(min(away_from_profit, away_from_sell), 4)
        return token

    def _get_exit_strategy(self, wallet_exit_strategies: List[ExitStrategy], percent_remaining: float) -> ExitStrategy:
        for strat in wallet_exit_strategies:
            if strat.amount_remaining_percent_lte >= percent_remaining > strat.amount_remaining_percent_gt:
                return strat
        return None

    def get_holdings_token_from_list(self, mint, pub_key) -> HoldingData:
        for x in self.holdings:
            if x.mint == mint and x.public_key == pub_key:
                return x
        return None

    def populate_holding_token(self, token: HoldingData) -> HoldingData:
        """Add to self.holdings if data populated successfully

        Args:
            token (HoldingData): _description_

        Returns:
            HoldingData: _description_
        """
        token = self.get_token_info(token=token)

        token = self.get_buy_swaps(token=token)

        if token.buy_price_sol_total == 0:
            self.exclusion_list.append(token.mint)
            return token

        token = self.get_sell_swaps(token=token)

        if (
            token.sell_percent_remaining is None
            or token.sell_percent is None
            or token.sell_percent_remaining > 1.0
            or token.sell_percent < 0.0
        ):
            logger.info("Sell percents are off for token: {t}".format(t=token))
            return token

        exit_strategies = [x.exit_strategy for x in self.wallets if x.public_key == token.public_key][0]
        token.exit_strategy = self._get_exit_strategy(
            wallet_exit_strategies=exit_strategies, percent_remaining=token.sell_percent_remaining
        )

        token.stop_price_usd = (
            1 + token.exit_strategy.stop_price_per_token_percent_change
        ) * token.buy_price_per_token_usd

        original_buy_amount = int(token.current_amount_raw / token.sell_percent_remaining)
        token.profit_sell_amount = min(
            int(original_buy_amount * token.exit_strategy.profit_sell_amount_percent) - 1, token.current_amount_raw
        )

        token.profit_price_per_token = (
            1 + token.exit_strategy.profit_price_per_token_percent_change
        ) * token.buy_price_per_token_usd

        self.holdings.append(token)
        return token

    def get_token_info(self, token: HoldingData) -> HoldingData:
        """Populates:
                symbol
                name
                decimals
                current_amount

        Args:
            mint_address (str): _description_

        Returns:
            dict: _description_
        """
        asset_info = self.Helius.get_asset(id=token.mint)
        expected_keys = sorted(["jsonrpc", "result", "id"])
        response_keys = sorted(asset_info.keys())

        if expected_keys != response_keys or "token_info" not in asset_info["result"]:
            return token

        try:
            token.symbol = asset_info["result"]["content"]["metadata"]["symbol"]
            token.name = asset_info["result"]["content"]["metadata"]["name"]
            token.decimals = asset_info["result"]["token_info"]["decimals"]
            token.current_amount = token.current_amount_raw / ((10**token.decimals) * 1.0)
            """
            quote_currency = asset_info["result"]["token_info"]["price_info"]["currency"]
            if quote_currency in ["USDC", "USDT"]:
                token.current_price_per_token_usd = asset_info["result"]["token_info"]["price_info"]["price_per_token"]
            if quote_currency in ["SOL", "WSOL"]:
                token.current_price_per_token_sol = asset_info["result"]["token_info"]["price_info"]["price_per_token"]
            """
        except KeyError as e:
            logger.info("Error getting token info: {e}".format(e=e))

        return token

    def get_buy_swaps(self, token: HoldingData) -> HoldingData:
        """Populate the buy fields of HoldingData and return the object

            Populates:
                    buy_time
                    buy_amount
                    buy_price_sol_total
                    buy_price_usd_total
        Args:
            token (HoldingData): _description_

        Returns:
            HoldingData: _description_
        """
        results = self.Helius.get_parsed_transactions(address=token.address)
        token_buys = list()

        for swap in results:
            native_transfers = swap.get("nativeTransfers")
            transfers = swap.get("tokenTransfers")

            if native_transfers is not None and transfers and len(transfers) == 1:
                for each in native_transfers:
                    swap["tokenTransfers"].append(
                        {
                            "fromUserAccount": each["fromUserAccount"],
                            "toUserAccount": each["toUserAccount"],
                            "tokenAmount": each["amount"] / (10**9),
                            "mint": self.sol_mint,
                        }
                    )

            # if buy is more than 15 min from first buy found, exit
            if len(token_buys) > 0:
                this_buy = datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc)
                min_buy_time = min([x.buy_time for x in token_buys if x.buy_time])
                time_diff = abs(min_buy_time - this_buy)
                if time_diff > timedelta(minutes=15):
                    break

            if not self.contains_mint_address(
                mint_address=token.mint, transfers=swap.get("tokenTransfers"), address=token.address, is_buy=True
            ):
                continue

            buy_data = BuyData(
                buy_time=datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc),
            )

            buy_data.sol_price = self.TokenChart.get_token_price_at_time(
                mint=self.sol_mint, start_time=buy_data.buy_time
            )

            for transfer in swap["tokenTransfers"]:
                if transfer["mint"] == token.mint and transfer["toTokenAccount"] == token.address:
                    buy_data.buy_amount += transfer["tokenAmount"]
                if transfer["mint"] == self.sol_mint and transfer["fromUserAccount"] == token.public_key:
                    buy_data.sol_spent += transfer["tokenAmount"]

            token_buys.append(buy_data)

        logger.info(
            "{p} - {l} Buys for {s} {a}".format(
                p=token.public_key, l=len(token_buys), s=token.symbol, a=token.mint[-6:]
            )
        )

        if len(token_buys) > 0:
            to_print = "\n".join([x.__str__() for x in token_buys])
            logger.info(to_print)

            token.buy_time = min([x.buy_time for x in token_buys if x.buy_time])
            token.buy_amount = sum([x.buy_amount for x in token_buys if x.buy_amount])
            token.buy_price_sol_total = sum([x.sol_spent for x in token_buys if x.sol_spent])
            token.buy_price_usd_total = sum(
                [x.sol_price * x.sol_spent for x in token_buys if x.sol_spent and x.sol_price]
            )
            if token.buy_amount != 0:
                token.buy_price_per_token_sol = token.buy_price_sol_total / token.buy_amount
                token.buy_price_per_token_usd = token.buy_price_usd_total / token.buy_amount
                token.sell_percent = (token.buy_amount - token.current_amount) / token.buy_amount
                token.sell_percent_remaining = 1.0 - token.sell_percent

        return token

    def get_sell_swaps(self, token: HoldingData) -> HoldingData:
        """Populate the sell fields of HoldingData and return the object
            sell_count: Optional[int] = None
            sell_amount_mint: Optional[float] = None
            sell_amount_sol: Optional[float] = None
        Args:
            token (HoldingData): _description_

        Returns:
            HoldingData: _description_
        """
        if token.sell_percent == 0:
            return token

        results = self.Helius.get_parsed_transactions(address=token.address)
        token_sells = list()

        for swap in results:
            if token.buy_amount - token.current_amount <= sum(
                [x.sell_amount for x in token_sells if x.sell_amount], start=0
            ):
                break
            if not self.contains_mint_address(
                mint_address=token.mint, transfers=swap.get("tokenTransfers"), address=token.address, is_sell=True
            ):
                continue
            sell_data = SellData(sell_time=datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc))
            if sell_data.sell_time < token.buy_time:
                continue

            for account in swap["accountData"]:
                if account["account"] not in [token.address, token.public_key]:
                    continue
                if account["account"] == token.public_key and "nativeBalanceChange" in account:
                    sell_data.sol_received += account["nativeBalanceChange"] / (10**9)
                if account["account"] == token.address and "tokenBalanceChanges" in account:
                    for balance_change in account["tokenBalanceChanges"]:
                        if balance_change["tokenAccount"] == token.address:
                            sell_data.sell_amount += (int(balance_change["rawTokenAmount"]["tokenAmount"]) * -1) / (
                                10 ** balance_change["rawTokenAmount"]["decimals"]
                            )
            token_sells.append(sell_data)

        logger.info(
            "{p} - {l} Sells for {s} {a}".format(
                p=token.public_key, l=len(token_sells), s=token.symbol, a=token.mint[-6:]
            )
        )

        if len(token_sells) > 0:
            to_print = "\n".join([x.__str__() for x in token_sells])
            logger.info(to_print)

            token.sell_count = len(token_sells)
            token.sell_amount_mint = sum([x.sell_amount for x in token_sells if x.sell_amount])
            token.sell_amount_sol = sum([x.sol_received for x in token_sells if x.sol_received])

        return token

    @staticmethod
    def contains_mint_address(
        mint_address: str, transfers: str, address: str, is_buy: bool = None, is_sell: bool = None
    ):
        for transfer in transfers:
            if transfer["mint"] == mint_address:
                if not is_buy and not is_sell:
                    return True
                if is_buy and transfer["toTokenAccount"] == address and len(transfers) >= 2:
                    return True
                if is_sell and transfer["fromTokenAccount"] == address and len(transfers) >= 2:
                    return True
        return False

    def _print_holdings(self):
        current_time = datetime.now(timezone.utc)
        for token in self.holdings:
            if not token.last_print_time:
                logger.info(token)
                token.last_print_time = current_time
                continue
            time_diff = current_time - token.last_print_time
            if time_diff > timedelta(seconds=60):
                if current_time.minute < 5:
                    logger.info(token)
                else:
                    logger.info(token.__str_medium__())
                token.last_print_time = current_time


if __name__ == "__main__":
    from spl_seller.utils.settings import settings_key_values

    W = Wallet(
        wallets=settings_key_values["wallets"],
        HELIUS_API_KEY=settings_key_values["HELIUS_API_KEY"],
        BIRDEYE_API_TOKEN=settings_key_values["BIRDEYE_API_TOKEN"],
    )

    # W.update_holdings()
    # W._print_holdings()
