"""Download de candles históricos da API pública da OKX (sem chave, sem conta).

Endpoint usado: GET /api/v5/market/history-candles
- Devolve no máximo 100 candles por chamada, do mais novo para o mais antigo.
- O parâmetro `after=<timestamp ms>` pede candles MAIS ANTIGOS que esse instante,
  então paginamos "para trás" até chegar na data de início.

Os dados ficam em cache em `dados/<par>_<timeframe>.csv` para não baixar tudo de novo.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.okx.com/api/v5/market/history-candles"
PASTA_CACHE = Path(__file__).resolve().parent.parent / "dados"
COLUNAS = ["ts", "open", "high", "low", "close", "volume"]


def _buscar(sessao: requests.Session, params: dict, tentativas: int = 6) -> dict:
    """Faz uma chamada à API, repetindo com espera crescente se der erro de rede
    ou se a OKX responder 429 (limite de requisições estourado)."""
    for n in range(tentativas):
        try:
            resp = sessao.get(URL, params=params, timeout=20)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if n == tentativas - 1:
                raise
            time.sleep(2 ** n)  # 1 s, 2 s, 4 s, ...
    raise RuntimeError("inalcançável")


def baixar_candles(
    par: str = "BTC-USDT",
    timeframe: str = "1H",
    inicio: str = "2023-01-01",
    usar_cache: bool = True,
    pausa_s: float = 0.12,
) -> pd.DataFrame:
    """Retorna um DataFrame OHLCV indexado por data/hora (UTC), do mais antigo ao mais novo.

    par:       instrumento da OKX, ex. "BTC-USDT", "ETH-USDT".
    timeframe: "15m", "1H", "4H", "1D" etc. (formato da OKX).
    inicio:    data mínima desejada (AAAA-MM-DD).
    """
    PASTA_CACHE.mkdir(exist_ok=True)
    arquivo = PASTA_CACHE / f"{par}_{timeframe}.csv"
    inicio_ms = int(pd.Timestamp(inicio, tz="UTC").timestamp() * 1000)

    if usar_cache and arquivo.exists():
        df = pd.read_csv(arquivo, index_col="data", parse_dates=["data"])
        if df.index.min() <= pd.Timestamp(inicio, tz="UTC") + pd.Timedelta(days=1):
            return df.loc[pd.Timestamp(inicio, tz="UTC"):]

    linhas: list[list[str]] = []
    after: int | None = None
    sessao = requests.Session()

    while True:
        params = {"instId": par, "bar": timeframe, "limit": "100"}
        if after is not None:
            params["after"] = str(after)

        corpo = _buscar(sessao, params)
        if corpo.get("code") != "0":
            raise RuntimeError(f"Erro da OKX: {corpo}")

        lote = corpo["data"]
        if not lote:
            break  # chegamos ao início do histórico disponível

        linhas.extend(lote)
        after = int(lote[-1][0])  # timestamp do candle mais antigo deste lote
        if after <= inicio_ms:
            break
        time.sleep(pausa_s)  # respeita o limite de requisições (20 a cada 2 s)

    if not linhas:
        raise RuntimeError(f"Nenhum candle retornado para {par} {timeframe}.")

    df = pd.DataFrame([l[:6] for l in linhas], columns=COLUNAS).astype(float)
    df["data"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = (
        df.drop(columns="ts")
        .drop_duplicates("data")
        .set_index("data")
        .sort_index()
    )
    # o candle mais recente ainda está em formação: descartamos para não usar dado incompleto
    df = df.iloc[:-1]

    df.to_csv(arquivo)
    return df.loc[pd.Timestamp(inicio, tz="UTC"):]
