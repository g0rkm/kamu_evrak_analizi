"""Merkezi log yapılandırması."""
import logging

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, datefmt="%H:%M:%S")
    # httpx her isteği INFO seviyesinde loglar; API anahtarı içeren URL'ler log'a düşmesin.
    logging.getLogger("httpx").setLevel(logging.WARNING)
