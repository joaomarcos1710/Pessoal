"""Métricas de desempenho. Todas calculadas sobre o retorno LÍQUIDO (já com custos)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import Resultado

# Quantos candles existem em um ano (cripto opera 24h, 365 dias)
CANDLES_POR_ANO = {
    "1m": 525_600, "5m": 105_120, "15m": 35_040, "30m": 17_520,
    "1H": 8_760, "2H": 4_380, "4H": 2_190, "1D": 365,
}


def calcular(res: Resultado, timeframe: str) -> dict:
    curva, trades = res.curva, res.trades
    ret = curva["retorno_liquido"]
    n_ano = CANDLES_POR_ANO[timeframe]

    anos = len(ret) / n_ano
    retorno_total = curva["patrimonio"].iloc[-1] - 1
    cagr = (1 + retorno_total) ** (1 / anos) - 1 if anos > 0 and retorno_total > -1 else -1.0
    vol_anual = ret.std() * np.sqrt(n_ano)
    sharpe = (ret.mean() * n_ano) / vol_anual if vol_anual > 0 else 0.0

    pico = curva["patrimonio"].cummax()
    drawdown_max = (curva["patrimonio"] / pico - 1).min()

    m = {
        "retorno_total": retorno_total,
        "cagr": cagr,
        "volatilidade_anual": vol_anual,
        "sharpe": sharpe,
        "drawdown_max": drawdown_max,
        "tempo_exposto": curva["posicao"].mean(),
        "custos_totais": curva["custo"].sum(),
        "n_trades": 0,
        "taxa_acerto": np.nan,
        "ganho_medio": np.nan,
        "perda_media": np.nan,
        "payoff": np.nan,
        "expectativa_por_trade": np.nan,
    }

    if not trades.empty:
        r = trades["retorno"]
        ganhos, perdas = r[r > 0], r[r <= 0]
        m["n_trades"] = len(r)
        m["taxa_acerto"] = len(ganhos) / len(r)
        m["ganho_medio"] = ganhos.mean() if len(ganhos) else 0.0
        m["perda_media"] = perdas.mean() if len(perdas) else 0.0
        if len(perdas) and perdas.mean() != 0:
            m["payoff"] = m["ganho_medio"] / abs(m["perda_media"])
        m["expectativa_por_trade"] = r.mean()

    return m


def formatar(m: dict) -> dict:
    """Versão legível (percentuais) para relatório."""
    pct = lambda x: "—" if pd.isna(x) else f"{x * 100:,.2f}%"
    num = lambda x: "—" if pd.isna(x) else f"{x:,.2f}"
    return {
        "Retorno total": pct(m["retorno_total"]),
        "Retorno anualizado (CAGR)": pct(m["cagr"]),
        "Volatilidade anual": pct(m["volatilidade_anual"]),
        "Sharpe": num(m["sharpe"]),
        "Drawdown máximo": pct(m["drawdown_max"]),
        "Tempo exposto": pct(m["tempo_exposto"]),
        "Custos pagos (soma)": pct(m["custos_totais"]),
        "Nº de trades": str(m["n_trades"]),
        "Taxa de acerto": pct(m["taxa_acerto"]),
        "Ganho médio": pct(m["ganho_medio"]),
        "Perda média": pct(m["perda_media"]),
        "Payoff": num(m["payoff"]),
        "Expectativa por trade": pct(m["expectativa_por_trade"]),
    }
