"""Testes do motor de backtest. Rodar com:  python -m pytest -q"""

import numpy as np
import pandas as pd
import pytest

from bot.backtest import Custos, rodar_backtest
from bot.estrategias import cruzamento_medias, rompimento_donchian
from bot.metricas import calcular

SEM_CUSTO = Custos(taxa=0.0, slippage=0.0)


def candles(precos):
    idx = pd.date_range("2024-01-01", periods=len(precos), freq="h", tz="UTC")
    p = pd.Series(precos, index=idx, dtype=float)
    return pd.DataFrame({"open": p, "high": p, "low": p, "close": p, "volume": 1.0})


def test_sem_olhar_o_futuro():
    """Um sinal 'perfeito' que só liga no candle da alta NÃO pode capturar essa alta."""
    df = candles([100, 100, 110, 110])
    sinal = pd.Series([0, 0, 1, 0], index=df.index)  # liga no mesmo candle em que o preço sobe
    res = rodar_backtest(df, sinal, SEM_CUSTO)
    assert res.curva["patrimonio"].iloc[-1] == pytest.approx(1.0)


def test_captura_alta_quando_entrou_antes():
    df = candles([100, 100, 110, 110])
    sinal = pd.Series([0, 1, 0, 0], index=df.index)  # decidiu comprar no fechamento do candle 1
    res = rodar_backtest(df, sinal, SEM_CUSTO)
    assert res.curva["patrimonio"].iloc[-1] == pytest.approx(1.10)


def test_custos_ida_e_volta():
    df = candles([100, 100, 100, 100])
    sinal = pd.Series([1, 0, 0, 0], index=df.index)
    res = rodar_backtest(df, sinal, Custos(taxa=0.001, slippage=0.0))
    # preço parado: a única perda são as duas ordens (entrada e saída)
    assert res.curva["patrimonio"].iloc[-1] == pytest.approx((1 - 0.001) ** 2)
    assert len(res.trades) == 1
    assert res.trades["retorno"].iloc[0] == pytest.approx((1 - 0.001) ** 2 - 1)


def test_metricas_de_trades():
    # dois trades: +10% e -5%
    df = candles([100, 100, 110, 110, 110, 104.5, 104.5])
    sinal = pd.Series([1, 1, 0, 1, 1, 0, 0], index=df.index)
    m = calcular(rodar_backtest(df, sinal, SEM_CUSTO), "1H")
    assert m["n_trades"] == 2
    assert m["taxa_acerto"] == pytest.approx(0.5)
    assert m["payoff"] == pytest.approx(0.10 / 0.05)


def test_donchian_entra_no_rompimento_e_sai_na_perda_da_minima():
    df = candles([10, 11, 10, 12, 13, 9, 9])
    s = rompimento_donchian(df, entrada=2, saida=2)
    assert list(s) == [0, 0, 0, 1, 1, 0, 0]


def test_medias_parametros_invalidos():
    with pytest.raises(ValueError):
        cruzamento_medias(candles(np.arange(10)), rapida=20, lenta=10)
