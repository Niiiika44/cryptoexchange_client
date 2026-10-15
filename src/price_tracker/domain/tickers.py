from enum import StrEnum, unique


@unique
class Ticker(StrEnum):
    """Currency index tracked by the service, named ``<base>_<quote>``."""

    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"
