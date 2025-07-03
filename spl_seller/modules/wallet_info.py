from datetime import datetime, timedelta, timezone
from time import sleep
from typing import List

from heliuspy import HeliusAPI
from solana.rpc.api import Client
from solders.keypair import Keypair

from spl_seller.modules.token_charts import TokenCharts
from spl_seller.types.exit_strategy import ExitStrategy
from spl_seller.types.holdings_data import HoldingData
from spl_seller.types.wallet_data import WalletInfo
from spl_seller.utils.log import get_logger

logger = get_logger()


class Wallet:
    def __init__(self, wallet_info: List[WalletInfo], HELIUS_API_KEY: str, BIRDEYE_API_TOKEN: str):
        self.wallets = wallet_info
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
            "3YQBXUDab4uEiMtRD4Y4Bhu1YJG9YD2ywYPMeyvAsJ23",
            "28ZDne7nY6eFtuENqeoYwuu4sgjpVtegt7SsEC4dDLE7",
            "7hBvn2dnqBoHYCh2vp7js3zaPSf6px2s4HMiPzw1pump",
            "3MnqzEH6JrWeHL1MmZPSr81i9Tto7mbuctH5Hvv1pump",
            "8Pg897t8NFe9sxGWsnAfnxP6NPu1ACUsgedSBacHpump",
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

        # Remove tokens from holdings that have amounts updated so they get re-added
        tokens_to_update_accounts = [x.address for x in tokens_to_update]
        self.holdings = [x for x in self.holdings if x.address not in tokens_to_update_accounts]

        # Remove tokens from list that aren't in current holdings
        current_tokens_address = [x.address for x in current_tokens]
        self.holdings = [x for x in self.holdings if x.address in current_tokens_address]

        if len(tokens_to_update) > 0:
            logger.info("Updating {a} tokens".format(a=len(tokens_to_update)))
        for token in tokens_to_update:
            self.populate_holding_token(token=token)

        # Update all prices
        if len(tokens_to_update) > 0:
            logger.info("Updating current price for {a} tokens".format(a=len(self.holdings)))

        mints = list(set([x.mint for x in self.holdings]))
        quotes = self.TokenChart.get_quotes(mints=mints)
        quote_time = datetime.now(timezone.utc)
        for token in self.holdings:
            # Update time held
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

    def _populate_exit_data(self, token: HoldingData) -> HoldingData:
        """
        """
        pass
    
    def _get_exit_strategy(self, wallet: WalletInfo, percent_remaining: float) -> ExitStrategy:
        for strat in wallet.exit_strategy:
            if strat["amount_remaining_percent_lte"] >= percent_remaining > strat["amount_remaining_percent_gt"]:
                return ExitStrategy(
                    amount_remaining_percent_gt=strat["amount_remaining_percent_gt"],
                    amount_remaining_percent_lte=strat["amount_remaining_percent_lte"],
                    stop_price_per_token_percent_change=strat["stop_price_per_token_percent_change"],
                    profit_price_per_token_percent_change=strat["profit_price_per_token_percent_change"],
                    profit_sell_amount_percent=strat["profit_sell_amount_percent"],
                )
        return None            

    def get_holdings_token_from_list(self, mint, pub_key) -> HoldingData:
        for x in self.holdings:
            if x.mint == mint and x.public_key == pub_key:
                return x
        return None

    def populate_holding_token(self, token: HoldingData) -> HoldingData:
        """_summary_

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
            if token.buy_time is not None:
                this_buy = datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc)
                time_diff = abs(token.buy_time - this_buy)
                if time_diff > timedelta(minutes=15):
                    break

            if not self.contains_mint_address(
                mint_address=token.mint, transfers=swap.get("tokenTransfers"), address=token.address, is_buy=True
            ):
                continue

            token.buy_time = datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc)

            sol_price = self.TokenChart.get_token_price_at_time(mint=self.sol_mint, start_time=token.buy_time)

            for transfer in swap["tokenTransfers"]:
                if transfer["mint"] == token.mint and transfer["toTokenAccount"] == token.address:
                    token.buy_amount += transfer["tokenAmount"]

                if transfer["mint"] == self.sol_mint and transfer["fromUserAccount"] == token.public_key:
                    token.buy_price_sol_total += transfer["tokenAmount"]
                    if sol_price:
                        token.buy_price_usd_total += transfer["tokenAmount"] * sol_price

            if token.buy_price_sol_total == 0:
                logger.error("Could not find buy amount for token: {t}".format(t=token))
                return token

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

        for swap in results:
            if token.buy_amount - token.current_amount <= token.sell_amount_mint:
                break
            if not self.contains_mint_address(
                mint_address=token.mint, transfers=swap.get("tokenTransfers"), address=token.address, is_sell=True
            ):
                continue
            swap_time = datetime.fromtimestamp(swap["timestamp"], tz=timezone.utc)
            if swap_time < token.buy_time:
                continue
            token.sell_count += 1
            for account in swap["accountData"]:
                if account["account"] not in [token.address, token.public_key]:
                    continue

                if account["account"] == token.public_key and "nativeBalanceChange" in account:
                    token.sell_amount_sol += account["nativeBalanceChange"] / (10**9)
                if account["account"] == token.address and "tokenBalanceChanges" in account:
                    for balance_change in account["tokenBalanceChanges"]:
                        if balance_change["tokenAccount"] == token.address:
                            token.sell_amount_mint += (int(balance_change["rawTokenAmount"]["tokenAmount"]) * -1) / (
                                10 ** balance_change["rawTokenAmount"]["decimals"]
                            )

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
        logger.info("-------------------------------")
        for token in self.holdings:
            logger.info(token)
        logger.info("-------------------------------")


if __name__ == "__main__":
    from spl_seller.utils.settings import settings_key_values

    W = Wallet(
        wallet_info=settings_key_values["wallets"],
        HELIUS_API_KEY=settings_key_values["HELIUS_API_KEY"],
        BIRDEYE_API_TOKEN=settings_key_values["BIRDEYE_API_TOKEN"],
    )

    W.update_holdings()
    W._print_holdings()
