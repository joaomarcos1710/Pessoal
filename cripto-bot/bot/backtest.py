"""Motor de backtest vetorizado, com custos.

Convenção de tempo (o ponto onde mais backtest amador erra):
- O sinal do candle t só é conhecido no FECHAMENTO de t.
- Portanto a posição durante o candle t+1 é o sinal de t  ->  posicao = sinal.shift(1).
- Executamos a ordem pelo fechamento de t (≈ abertura de t+1) e cobramos
  taxa + slippage a cada troca de posição.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Custos:
    taxa: float = 0.0010      # 0,10% por ordem (taxa "taker" do nível básico da OKX spot)
    slippage: float = 0.0005  # 0,05% de preço pior que o esperado, por ordem

    @property
    def por_lado(self) -> float:
        return self.taxa + self.slippage


@dataclass
class Resultado:
    curva: pd.DataFrame   # colunas: posicao, retorno_bruto, custo, retorno_liquido, patrimonio
    trades: pd.DataFrame  # uma linha por operação fechada (ou aberta no fim do período)


def rodar_backtest(df: pd.DataFrame, sinal: pd.Series, custos: Custos | None = None) -> Resultado:
    custos = custos or Custos()

    retorno_ativo = df["close"].pct_change().fillna(0.0)
    posicao = sinal.shift(1).fillna(0).astype(float)

    # cada mudança de posição (0->1 ou 1->0) é uma ordem e paga custo
    trocas = posicao.diff().abs()
    trocas.iloc[0] = posicao.iloc[0]
    custo = trocas * custos.por_lado

    retorno_bruto = posicao * retorno_ativo
    retorno_liquido = retorno_bruto - custo
    patrimonio = (1 + retorno_liquido).cumprod()

    curva = pd.DataFrame(
        {
            "posicao": posicao,
            "retorno_bruto": retorno_bruto,
            "custo": custo,
            "retorno_liquido": retorno_liquido,
            "patrimonio": patrimonio,
        }
    )
    return Resultado(curva=curva, trades=_extrair_trades(curva, df["close"]))


def _extrair_trades(curva: pd.DataFrame, close: pd.Series) -> pd.DataFrame:
    """Agrupa os candles em operações: da entrada (0->1) até a saída (1->0).

    O custo da saída é cobrado no candle em que a posição volta a 0,
    então esse candle é atribuído à operação que está terminando.
    """
    pos = curva["posicao"].to_numpy()
    ret = curva["retorno_liquido"].to_numpy()
    idx = curva.index

    trades = []
    i, n = 0, len(pos)
    while i < n:
        if pos[i] == 1 and (i == 0 or pos[i - 1] == 0):
            inicio = i
            j = i
            while j + 1 < n and pos[j + 1] == 1:
                j += 1
            fim = j + 1 if j + 1 < n else j  # inclui o candle de saída (onde a taxa é cobrada)
            aberto = j + 1 >= n
            retorno = float(np.prod(1 + ret[inicio : fim + 1]) - 1)
            trades.append(
                {
                    "entrada": idx[inicio - 1] if inicio > 0 else idx[inicio],
                    "saida": idx[fim] if not aberto else pd.NaT,
                    "preco_entrada": close.iloc[inicio - 1] if inicio > 0 else close.iloc[inicio],
                    "preco_saida": close.iloc[fim] if not aberto else np.nan,
                    "candles": j - inicio + 1,
                    "retorno": retorno,
                    "aberto": aberto,
                }
            )
            i = fim + 1
        else:
            i += 1
    return pd.DataFrame(trades)
