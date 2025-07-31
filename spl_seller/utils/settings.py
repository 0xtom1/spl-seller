import os
from typing import List

import dotenv
from solders.keypair import Keypair

from spl_seller.types.exit_strategy import ExitStrategy
from spl_seller.types.wallet_data import WalletInfo

dotenv.load_dotenv()


def get_wallet_list() -> List[WalletInfo]:
    # test line
    private_key_1 = os.environ.get("SOLANA_PRIVATE_KEY1")
    private_key_2 = os.environ.get("SOLANA_PRIVATE_KEY2")
    private_key_3 = os.environ.get("SOLANA_PRIVATE_KEY3")
    private_key_4 = os.environ.get("SOLANA_PRIVATE_KEY4")
    pv_exit_index1 = os.environ.get("PV_EXIT_INDEX1")
    pv_exit_index2 = os.environ.get("PV_EXIT_INDEX2")
    pv_exit_index3 = os.environ.get("PV_EXIT_INDEX3")
    pv_exit_index4 = os.environ.get("PV_EXIT_INDEX4")

    private_key_list = [
        (private_key_1, pv_exit_index1),
        (private_key_2, pv_exit_index2),
        (private_key_3, pv_exit_index3),
        (private_key_4, pv_exit_index4),
    ]

    wallets = list()
    for pv, index in private_key_list:
        if pv is None or index is None:
            continue

        key_pair = Keypair.from_base58_string(pv)
        public_key = str(key_pair.pubkey())
        exit_strat = get_exit_strategy(index=int(index))
        wallets.append(WalletInfo(public_key=public_key, key_pair=key_pair, exit_strategy=exit_strat))
    return wallets


def get_exit_strategy(index=1) -> ExitStrategy:
    EXIT_STRATEGY = dict()
    EXIT_STRATEGY[1] = [
        ExitStrategy(
            amount_remaining_percent_gt=0.51,
            amount_remaining_percent_lte=1.0,
            stop_price_per_token_percent_change=-0.3,
            profit_price_per_token_percent_change=0.5,
            profit_sell_amount_percent=0.5,
        ),
        ExitStrategy(
            amount_remaining_percent_gt=0.35,
            amount_remaining_percent_lte=0.51,
            stop_price_per_token_percent_change=0.0,
            profit_price_per_token_percent_change=1.0,
            profit_sell_amount_percent=0.25,
        ),
        ExitStrategy(
            amount_remaining_percent_gt=0.0,
            amount_remaining_percent_lte=0.35,
            stop_price_per_token_percent_change=0.5,
            profit_price_per_token_percent_change=2.0,
            profit_sell_amount_percent=0.25,
        ),
    ]
    EXIT_STRATEGY[2] = [
        ExitStrategy(
            amount_remaining_percent_gt=0.51,
            amount_remaining_percent_lte=1.0,
            stop_price_per_token_percent_change=-0.5,
            profit_price_per_token_percent_change=0.5,
            profit_sell_amount_percent=0.5,
        ),
        ExitStrategy(
            amount_remaining_percent_gt=0.35,
            amount_remaining_percent_lte=0.51,
            stop_price_per_token_percent_change=0.0,
            profit_price_per_token_percent_change=1.0,
            profit_sell_amount_percent=0.25,
        ),
        ExitStrategy(
            amount_remaining_percent_gt=0.0,
            amount_remaining_percent_lte=0.35,
            stop_price_per_token_percent_change=0.5,
            profit_price_per_token_percent_change=2.0,
            profit_sell_amount_percent=0.25,
        ),
    ]
    return EXIT_STRATEGY[index]


settings_key_values = dict()
settings_key_values["wallets"] = get_wallet_list()
try:
    settings_key_values["HELIUS_API_KEY"] = os.environ.get("HELIUS_API_KEY")
    settings_key_values["BIRDEYE_API_TOKEN"] = os.environ.get("BIRDEYE_API_TOKEN")
except KeyError:
    raise ValueError("Environment variable is required but not set")
