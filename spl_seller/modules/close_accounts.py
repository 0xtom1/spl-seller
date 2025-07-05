from time import sleep
from typing import List

from heliuspy import HeliusAPI
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import BurnParams, CloseAccountParams, burn, close_account
from tenacity import retry, stop_after_attempt, wait_exponential

from spl_seller.types.holdings_data import HoldingData
from spl_seller.types.wallet_data import WalletInfo
from spl_seller.utils.log import get_logger
from spl_seller.utils.settings import settings_key_values

logger = get_logger()


class Closer:
    def __init__(self):
        self.wallets = settings_key_values["wallets"]
        self.HELIUS_API_KEY = settings_key_values["HELIUS_API_KEY"]
        # Configuration
        self.COMMITMENT = "confirmed"
        self.RPC_ENDPOINT = f"https://mainnet.helius-rpc.com/?api-key={self.HELIUS_API_KEY}"
        # Initialize Solana client
        try:
            self.client = Client(self.RPC_ENDPOINT, commitment=self.COMMITMENT)
            # version = self.client.get_version()
            # logger.info(f"Connected to Helius RPC, version: {version}")
        except Exception as e:
            raise Exception(f"Failed to connect to Helius RPC: {e}")
        self.Helius = HeliusAPI(api_key=self.HELIUS_API_KEY)
        self.tokens_to_close = [
            "BfSbstVpvUPaqEm57ZiPBN7fmkQ41NxdGCmARBNFpump",
            "7hBvn2dnqBoHYCh2vp7js3zaPSf6px2s4HMiPzw1pump",
            "3YQBXUDab4uEiMtRD4Y4Bhu1YJG9YD2ywYPMeyvAsJ23",
            "3MnqzEH6JrWeHL1MmZPSr81i9Tto7mbuctH5Hvv1pump",
            "28ZDne7nY6eFtuENqeoYwuu4sgjpVtegt7SsEC4dDLE7",
            "3bjiVrsRuRGq4XsFighja49fVvKzYEFF56vgubWAtmgM",
            "EDzaWCnQC5hmGjaBPgPAydj15qY9fvNxJFmArJAvVMvg",
            "BLqjgc4ebMK3qZXR3xosog517G22NDMcGxnmWwdXEDKJ",
            "3WRs7aZ71bhzuLkNyVaNAU2DcbwUMqAjNUJ36uPdyDwW",
            "51gUsfAzZya3dM99eoEPkEHGftsrJ5ZfiyThWjpQPXts",
            "8NmmjvHCczazUHBGpmQVJWDM64iY5TpKDLsz8bRssxZF",
            "ErNpMq1bAQ5KwWqYjTA7hS14rGnKmRXcJv8ELqF9XjHU",
            "EDzaWCnQC5hmGjaBPgPAydj15qY9fvNxJFmArJAvVMvg",
            "8wbxL9uAmniSENBv44ktN9qn4ZFGt27XwJ9RbqkG8pVV",
            "CTzG6CExynq52vHdnAcB7LtHuYuyVbnRNkoKFM1mgxFJ",
            "EJtocH3iHD415RE24HTgih2m6MtcbYgbPkjFQUuqxp3N",
            "3DB5npeJFBdthMpGxJzAcc54FsZGdpGMqYrLo9czmqCs",
            "8sgJmj2NSwKMDCFhtmeZFMRRsSamGz5fqQq7WcnLWWe",
            "F5DZXcSjUzUsyCX1fSYUg3z2TfARFdDh2UhJS7BPw4mD",
            "2uw4LxAQsmFqbR56GCFo8gDp5LpDEu2zj7TCEEbJdy23",
            "GEq9fT7FMdZN5rvyR7VCESgTzSsPvDJBxSNHP4sAyW32",
            "9X23ybhJuowjq84aNp1vCS9zaLKTVWaoYYMLTS6S1pgA",
            "4mhJH8GKWQJSDQtZ3qNb7c3cxk2uraG3KtZGnYHL3xFf",
            "AyJyrQrK1AjUgDUsQ3hbhuaZCN9nFP37wFPyrfao8VLP",
            "avkH1mHTREWEaRDvZqTjxCpCwdcXjN11NgCsqo56hXp",
        ]

    @property
    def wallets(self) -> List[WalletInfo]:
        return self._wallets

    @wallets.setter
    def wallets(self, value: List[WalletInfo]):
        self._wallets = value

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
            if each["amount"] > 1000:
                token_list.append(
                    HoldingData(
                        public_key=pub_key,
                        mint=each["mint"],
                        address=each["address"],
                        current_amount_raw=each["amount"],
                    )
                )
        return token_list

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def get_balance_with_retry(self, pubkey):
        """Fetch wallet balance with retry logic."""
        try:
            return self.client.get_balance(pubkey, commitment=self.COMMITMENT).value
        except Exception as e:
            raise Exception(f"RPC error during balance check: {e}")

    def close_account(self, key_pair: Keypair, token_to_close: HoldingData):
        logger.info(f"Processing token account for wallet: {key_pair.pubkey()} and token: {token_to_close.mint}")

        try:
            token_account_pubkey = Pubkey.from_string(token_to_close.address)
        except ValueError as e:
            logger.error(f"Invalid token account address {token_to_close.address}: {e}")
            return

        # Step 2: Create instructions
        instructions = []

        if token_to_close.current_amount_raw > 0:
            # Convert mint address to Pubkey
            try:
                mint_pubkey = Pubkey.from_string(token_to_close.mint)
            except ValueError as e:
                logger.error(f"Invalid mint address {token_to_close.mint}: {e}")
                return

            # Create the burn instruction
            burn_params = BurnParams(
                program_id=TOKEN_PROGRAM_ID,
                account=token_account_pubkey,
                mint=mint_pubkey,
                owner=key_pair.pubkey(),
                amount=token_to_close.current_amount_raw,
                signers=[],
            )
            burn_instruction = burn(burn_params)
            instructions.append(burn_instruction)
            logger.info(f"Added burn instruction for {token_to_close.current_amount_raw} tokens")
        else:
            logger.info(f"No tokens to burn for {token_to_close.address}")

        # Create the close account instruction
        close_params = CloseAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=token_account_pubkey,
            dest=key_pair.pubkey(),
            owner=key_pair.pubkey(),
            signers=[],
        )
        close_instruction = close_account(close_params)
        instructions.append(close_instruction)

        # Fetch the latest blockhash
        try:
            blockhash_response = self.client.get_latest_blockhash()
            recent_blockhash = blockhash_response.value.blockhash  # Already a Hash object
        except Exception as e:
            logger.error(f"Failed to fetch blockhash: {e}")
            return

        # Create the transaction
        try:
            # Build the message with instructions, payer, and blockhash
            message = Message.new_with_blockhash(
                instructions=instructions,
                payer=key_pair.pubkey(),
                blockhash=recent_blockhash,
            )
            # Create a VersionedTransaction
            transaction = VersionedTransaction(message, [key_pair])
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}")
            return

        # Execute the transaction
        self.execute_burn_and_close(transaction=transaction)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute_burn_and_close(self, transaction: VersionedTransaction) -> str:
        """Sign and send the transaction"""
        try:
            # Send the transaction
            txid = self.client.send_transaction(transaction).value
            logger.info(f"Transaction sent: https://solscan.io/tx/{txid}")

            # Confirm the transaction
            self.client.confirm_transaction(txid, commitment=self.COMMITMENT)
            return txid

        except Exception as e:
            logger.error(f"Error in execute_burn_and_close: {e}")
            raise

    def run(self):
        """_summary_"""

        token_accounts = self.get_token_accounts_all()
        filtered_accounts = list()
        for each in token_accounts:
            if each.mint in self.tokens_to_close:
                filtered_accounts.append(each)
                logger.info(each.__str_short__())

        for wallet in self.wallets:
            current_balance = self.get_balance_with_retry(pubkey=wallet.key_pair.pubkey()) / 1e9
            logger.info(f"Beginning Wallet {wallet.public_key[-6:]} balance: {current_balance} SOL")

        for each in filtered_accounts:
            wallet_to_use = self._get_wallet_key_pair(public_key=each.public_key)
            self.close_account(key_pair=wallet_to_use, token_to_close=each)

        sleep(10)
        for wallet in self.wallets:
            current_balance = self.get_balance_with_retry(pubkey=wallet.key_pair.pubkey()) / 1e9
            logger.info(f"End Wallet {wallet.public_key[-6:]} balance: {current_balance} SOL")

    def _get_wallet_key_pair(self, public_key: str) -> Keypair:
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


if __name__ == "__main__":
    C = Closer()
    C.run()
