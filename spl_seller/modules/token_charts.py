import json
from datetime import datetime
from typing import List

import requests

from spl_seller.utils.log import get_logger

logger = get_logger()


class TokenCharts:
    def __init__(self, BIRDEYE_API_TOKEN: str):
        self.BIRDEYE_API_TOKEN = BIRDEYE_API_TOKEN
        self.headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": self.BIRDEYE_API_TOKEN}

    def get_token_price_at_time(self, mint: str, start_time: datetime) -> float:
        """_summary_

        Args:
            mint (str): _description_
            time (datetime): _description_

        Returns:
            float: price
        """
        start_time = start_time.replace(second=0, microsecond=0)

        # From datetime object
        time_from = int(start_time.timestamp())

        params = {
            "address": mint,
            "type": "1m",
            "currency": "usd",
            "time_from": time_from,
            "time_to": time_from,
        }
        url = "https://public-api.birdeye.so/defi/ohlcv"
        response = requests.get(url, headers=self.headers, params=params)

        # Check if the request was successful
        if response.status_code != 200:
            logger.error("Response failed for {t}: {e}".format(t=mint, e=response.text))
            if mint == "So11111111111111111111111111111111111111112":
                logger.error("Returning 160 as default")
                return 160.0
            else:
                return None

        # Parse the JSON response
        response_json = json.loads(response.text)

        if "data" not in response_json or "items" not in response_json["data"]:
            logger.error("No OCLHV data for {t}: {e}".format(t=mint, e=response_json))
            if mint == "So11111111111111111111111111111111111111112":
                logger.error("Returning 160 as default")
                return 160.0
            else:
                return None

        for each in response_json["data"]["items"]:
            return (each["o"] + each["c"]) / 2.0

        logger.error("No Price found")
        if mint == "So11111111111111111111111111111111111111112":
            logger.error("Returning 160 as default")
            return 160.0

    def get_quotes(self, mints: List[str]) -> dict:
        """_summary_

        Args:
            mints (List[str]): _description_

        Returns:
            dict: _description_
        """
        if not mints or len(mints) == 0:
            return dict()

        comma_separated = ",".join(mints)
        url = "https://public-api.birdeye.so/defi/multi_price?check_liquidity=100000&include_liquidity=false"

        payload = {"list_address": comma_separated}

        response = requests.post(url, json=payload, headers=self.headers)

        # Check if the request was successful
        if response.status_code != 200:
            logger.info("Response failed for {t}: {e}".format(t=mints, e=response.text))
            return dict()

        # Parse the JSON response
        response_json = json.loads(response.text)

        if "data" not in response_json:
            logger.info("No quotes data for {t}: {e}".format(t=mints, e=response_json))
            return dict()

        result_dict = dict()
        for key in response_json["data"]:
            result_dict[key] = {
                "current_price_per_token_usd": response_json["data"][key]["value"],
                "current_price_per_token_sol": response_json["data"][key]["priceInNative"],
            }

        return result_dict


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    BIRDEYE_API_TOKEN = os.environ.get("BIRDEYE_API_TOKEN")

    S = TokenCharts(BIRDEYE_API_TOKEN=BIRDEYE_API_TOKEN)

    # S.set_token_list(token_list=token_list)
    # S.run()
    prices = S.get_quotes(
        mints=["Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", "DtR4D9FtVoTX2569gaL837ZgrB6wNjj6tkmnX9Rdk9B2"]
    )
    print(prices)
