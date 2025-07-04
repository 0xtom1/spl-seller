import base64
import os
from time import sleep

import requests
from dotenv import load_dotenv
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from tenacity import retry, stop_after_attempt, wait_exponential

from spl_seller.utils.log import get_logger

logger = get_logger()


class Swapper:
    def __init__(self, HELIUS_API_KEY: str):
        # Configuration
        self.RPC_ENDPOINT = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        self.sol_mint = "So11111111111111111111111111111111111111112"  # SOL

        self.COMMITMENT = "confirmed"  # Commitment level for RPC calls
        self.MAX_SOL_CHUNK = 10.0
        # Initialize Solana client
        try:
            self.client = Client(self.RPC_ENDPOINT, commitment=self.COMMITMENT)
            # version = self.client.get_version()
            # logger.info(f"Connected to Helius RPC, version: {version}")
        except Exception as e:
            raise Exception(f"Failed to connect to Helius RPC: {e}")

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def get_balance_with_retry(self, pubkey):
        """Fetch wallet balance with retry logic."""
        try:
            return self.client.get_balance(pubkey, commitment=self.COMMITMENT).value
        except Exception as e:
            raise Exception(f"RPC error during balance check: {e}")

    def place_sell_order(self, INPUT_MINT: str, AMOUNT: int, KEY_PAIR: Keypair):
        """Place a sell order for AMOUNT of INPUT_MINT"""
        try:
            logger.info("----Start Sell----")
            logger.info(KEY_PAIR.pubkey())
            # Get quote
            quote = self.get_quote(input_mint=INPUT_MINT, output_mint=self.sol_mint, amount=AMOUNT)
            output_sol = float(quote["outAmount"]) / (10**9)

            full_chunk = int((self.MAX_SOL_CHUNK / output_sol) * AMOUNT)
            chunk_amounts = self.get_chunk_amounts(total_amount=AMOUNT, chunk_amount=full_chunk)

            for sell_amount in chunk_amounts:
                logger.info("Selling {x} of {t}".format(x=AMOUNT, t=INPUT_MINT))
                if len(chunk_amounts) > 1:
                    sleep(2)
                    quote = self.get_quote(input_mint=INPUT_MINT, output_mint=self.sol_mint, amount=sell_amount)

                # Execute swap
                txid = self.execute_swap(quote=quote, key_pair=KEY_PAIR)
                logger.info(f"Sell order successful: https://solscan.io/tx/{txid}")

            logger.info("----End Sell----")
            return True

        except Exception as e:
            logger.error(f"Error in place_sell_order: {e}")
            return False

    def get_chunk_amounts(self, total_amount: int, chunk_amount: int):
        """_summary_"""
        chunk_amounts = list()
        i = 0
        while sum(chunk_amounts) != total_amount:
            i += 1
            remaining = total_amount - sum(chunk_amounts)
            if remaining < chunk_amount:
                chunk_amounts.append(remaining)
            else:
                chunk_amounts.append(chunk_amount)
            if i > 100:
                break
        return chunk_amounts

    def get_quote(self, input_mint: str, output_mint: str, amount: int) -> dict:
        """Get a swap quote from Jupiter API."""
        try:
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": 200,  # 2.0% slippage
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            quote_data = response.json()
            if not quote_data.get("inAmount") or not quote_data.get("outAmount"):
                raise ValueError("Invalid quote: missing inAmount or outAmount")
            return quote_data
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get quote: {e}")

    def create_swap(self, quote: dict, user_public_key: str) -> str:
        """Create a swap transaction using Jupiter API."""
        try:
            url = "https://quote-api.jup.ag/v6/swap"
            payload = {
                "quoteResponse": quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": {
                    "priorityLevelWithMaxLamports": {
                        "maxLamports": 100000000,
                        "global": False,
                        "priorityLevel": "veryHigh",
                    }
                },
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            swap_data = response.json()
            if not swap_data.get("swapTransaction"):
                raise ValueError("Invalid swap response: missing swapTransaction")
            logger.info(swap_data)
            swap_transaction = swap_data["swapTransaction"]
            # Validate base64
            try:
                base64.b64decode(swap_transaction)
            except Exception as e:
                raise ValueError(f"Invalid base64 swapTransaction: {e}")
            return swap_transaction
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to create swap: {e}")

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute_swap(self, quote: dict, key_pair: Keypair) -> str:
        """Sign and send the swap transaction with priority fee."""
        try:
            # Create swap transaction
            swap_transaction = self.create_swap(quote=quote, user_public_key=str(key_pair.pubkey()))

            # Decode the base64 transaction
            transaction_bytes = base64.b64decode(swap_transaction)
            logger.info(f"Decoded transaction length: {len(transaction_bytes)}")

            # Deserialize as a VersionedTransaction
            unsigned_tx = VersionedTransaction.from_bytes(transaction_bytes)
            logger.info(f"Deserialized transaction instructions: {len(unsigned_tx.message.instructions)}")

            # Create and sign the transaction
            signed_tx = VersionedTransaction(unsigned_tx.message, [key_pair])
            logger.info(f"Final transaction instructions: {len(signed_tx.message.instructions)}")

            # Send the transaction
            txid = self.client.send_transaction(signed_tx).value
            logger.info(f"Transaction sent: https://solscan.io/tx/{txid}")

            # Confirm the transaction
            self.client.confirm_transaction(txid, commitment=self.COMMITMENT)
            return txid

        except Exception as e:
            logger.error(f"Error in execute_swap: {e}")
            raise


if __name__ == "__main__":
    load_dotenv()
    SOLANA_PRIVATE_KEY = os.environ.get("SOLANA_PRIVATE_KEY")
    if not SOLANA_PRIVATE_KEY:
        raise ValueError("SOLANA_PRIVATE_KEY not found in environment variables")
    HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY")
    if not HELIUS_API_KEY:
        raise ValueError("HELIUS_API_KEY not found in environment variables")

    S = Swapper(WALLET_PRIVATE_KEY=SOLANA_PRIVATE_KEY, HELIUS_API_KEY=HELIUS_API_KEY)
    # a = S.place_buy_order(OUTPUT_MINT="Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", AMOUNT_IN_SOL=0.1)
    # S.place_sell_order(INPUT_MINT="Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", AMOUNT=110319682)
