"""Estratégias de exemplo. Cada uma recebe candles e devolve um SINAL por candle:

    1 = quero estar comprado ao FINAL deste candle
    0 = quero estar fora (em USDT)

Só operamos comprado (spot, sem alavancagem e sem venda a descoberto).

O sinal do candle t usa apenas dados até o fechamento de t. Quem transforma
sinal em posição (com 1 candle de atraso, para não "ver o futuro") é o backtest.
"""

from __future__ import annotations

import pandas as pd


def cruzamento_medias(df: pd.DataFrame, rapida: int, lenta: int) -> pd.Series:
    """Comprado enquanto a média móvel rápida estiver acima da lenta."""
    if rapida >= lenta:
        raise ValueError("A média rápida precisa ser menor que a lenta.")
    mm_rapida = df["close"].rolling(rapida).mean()
    mm_lenta = df["close"].rolling(lenta).mean()
    return (mm_rapida > mm_lenta).astype(int)


def rompimento_donchian(df: pd.DataFrame, entrada: int, saida: int) -> pd.Series:
    """Canal de Donchian (lógica das "tartarugas"):

    - ENTRA quando o fechamento rompe a máxima dos últimos `entrada` candles;
    - SAI quando o fechamento perde a mínima dos últimos `saida` candles.

    O canal é calculado com `.shift(1)` para comparar o fechamento atual
    com os candles ANTERIORES (senão o candle atual entraria no próprio canal).
    """
    maxima = df["high"].rolling(entrada).max().shift(1)
    minima = df["low"].rolling(saida).min().shift(1)

    sinal = pd.Series(0, index=df.index, dtype=int)
    comprado = False
    for i, (fech, mx, mn) in enumerate(zip(df["close"], maxima, minima)):
        if not comprado and fech > mx:
            comprado = True
        elif comprado and fech < mn:
            comprado = False
        sinal.iat[i] = int(comprado)
    return sinal


def comprar_e_segurar(df: pd.DataFrame) -> pd.Series:
    """Referência (benchmark): comprado o tempo todo."""
    return pd.Series(1, index=df.index, dtype=int)


# Grade de parâmetros testada na otimização (amostra de treino).
# Quanto MAIS combinações, maior a chance de achar uma boa só por sorte.
GRADES = {
    "cruzamento_medias": {
        "funcao": cruzamento_medias,
        "params": [
            {"rapida": r, "lenta": l}
            for r in (5, 10, 20, 50)
            for l in (50, 100, 200)
            if r < l
        ],
    },
    "rompimento_donchian": {
        "funcao": rompimento_donchian,
        "params": [
            {"entrada": e, "saida": s}
            for e in (20, 50, 100)
            for s in (10, 20, 50)
            if s <= e
        ],
    },
}
