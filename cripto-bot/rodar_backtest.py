"""Roda o estudo completo: baixa dados, otimiza no TREINO, valida no TESTE.

Uso:
    python rodar_backtest.py                              # BTC-USDT, 1H, desde 2023
    python rodar_backtest.py --par ETH-USDT --timeframe 15m --inicio 2024-01-01
    python rodar_backtest.py --taxa 0.0008 --slippage 0.0003

Lógica anti-autoengano:
1. Os dados são divididos em TREINO (70% mais antigos) e TESTE (30% mais recentes).
2. Os parâmetros são escolhidos SÓ olhando o treino.
3. O resultado que vale é o do TESTE, que a otimização nunca viu.
4. Tudo é comparado com "comprar e segurar" no mesmo período.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bot import metricas
from bot.backtest import Custos, rodar_backtest
from bot.dados import baixar_candles
from bot.estrategias import GRADES, comprar_e_segurar

PASTA_RESULTADOS = Path(__file__).resolve().parent / "resultados"
MIN_TRADES_TREINO = 20  # menos que isso é amostra pequena demais para confiar


def avaliar(df: pd.DataFrame, sinal: pd.Series, custos: Custos, timeframe: str) -> dict:
    return metricas.calcular(rodar_backtest(df, sinal, custos), timeframe)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--par", default="BTC-USDT")
    ap.add_argument("--timeframe", default="1H", choices=list(metricas.CANDLES_POR_ANO))
    ap.add_argument("--inicio", default="2023-01-01")
    ap.add_argument("--treino", type=float, default=0.7, help="fração dos dados usada para otimizar")
    ap.add_argument("--taxa", type=float, default=0.0010)
    ap.add_argument("--slippage", type=float, default=0.0005)
    ap.add_argument("--sem-cache", action="store_true")
    args = ap.parse_args()

    custos = Custos(taxa=args.taxa, slippage=args.slippage)
    df = baixar_candles(args.par, args.timeframe, args.inicio, usar_cache=not args.sem_cache)

    corte = int(len(df) * args.treino)
    treino_idx, teste_idx = df.index[:corte], df.index[corte:]
    df_treino, df_teste = df.loc[treino_idx], df.loc[teste_idx]

    linhas_rel: list[str] = []
    add = linhas_rel.append

    add(f"# Backtest {args.par} · {args.timeframe}\n")
    add(f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.\n")
    add(f"- **Dados:** {len(df):,} candles, de {df.index[0]:%Y-%m-%d} a {df.index[-1]:%Y-%m-%d}")
    add(f"- **Treino:** {treino_idx[0]:%Y-%m-%d} → {treino_idx[-1]:%Y-%m-%d} ({len(df_treino):,} candles)")
    add(f"- **Teste (fora da amostra):** {teste_idx[0]:%Y-%m-%d} → {teste_idx[-1]:%Y-%m-%d} ({len(df_teste):,} candles)")
    add(f"- **Custo por ordem:** {custos.taxa*100:.2f}% taxa + {custos.slippage*100:.2f}% slippage "
        f"= {custos.por_lado*100:.2f}% (ida e volta: {2*custos.por_lado*100:.2f}%)\n")

    bh = comprar_e_segurar(df)
    bh_treino = avaliar(df_treino, bh.loc[treino_idx], custos, args.timeframe)
    bh_teste = avaliar(df_teste, bh.loc[teste_idx], custos, args.timeframe)

    total_testadas = 0
    resumo_final = []

    for nome, cfg in GRADES.items():
        funcao, grade = cfg["funcao"], cfg["params"]
        total_testadas += len(grade)

        # 1) roda cada combinação de parâmetros no treino e no teste
        tabela = []
        for p in grade:
            sinal = funcao(df, **p)  # indicadores só olham para trás, então calcular no df inteiro é seguro
            m_tr = avaliar(df_treino, sinal.loc[treino_idx], custos, args.timeframe)
            m_te = avaliar(df_teste, sinal.loc[teste_idx], custos, args.timeframe)
            tabela.append({"params": p, "treino": m_tr, "teste": m_te})

        # 2) escolhe a melhor olhando SÓ o treino (maior Sharpe com nº mínimo de trades)
        elegiveis = [t for t in tabela if t["treino"]["n_trades"] >= MIN_TRADES_TREINO] or tabela
        melhor = max(elegiveis, key=lambda t: t["treino"]["sharpe"])

        positivas_teste = sum(t["teste"]["retorno_total"] > 0 for t in tabela)
        batem_bh_teste = sum(t["teste"]["sharpe"] > bh_teste["sharpe"] for t in tabela)

        add(f"## {nome.replace('_', ' ').title()}\n")
        add(f"Combinações testadas: **{len(grade)}**. Melhor no treino: `{melhor['params']}`.\n")
        add("| Métrica | Treino (otimizado) | **Teste (o que vale)** | Comprar e segurar (teste) |")
        add("|---|---|---|---|")
        f_tr, f_te, f_bh = (metricas.formatar(x) for x in (melhor["treino"], melhor["teste"], bh_teste))
        for k in f_tr:
            add(f"| {k} | {f_tr[k]} | **{f_te[k]}** | {f_bh[k]} |")
        add("")
        add(f"- Das {len(grade)} combinações, **{positivas_teste}** deram lucro no teste "
            f"e **{batem_bh_teste}** tiveram Sharpe maior que comprar e segurar.")
        queda = melhor["treino"]["sharpe"] - melhor["teste"]["sharpe"]
        add(f"- Degradação do Sharpe treino → teste: **{queda:+.2f}** "
            f"(positivo = piorou fora da amostra, sinal típico de overfitting).\n")

        add("<details><summary>Todas as combinações</summary>\n")
        add("| Parâmetros | Sharpe treino | Sharpe teste | Retorno teste | Trades teste |")
        add("|---|---|---|---|---|")
        for t in sorted(tabela, key=lambda t: -t["treino"]["sharpe"]):
            add(f"| `{t['params']}` | {t['treino']['sharpe']:.2f} | {t['teste']['sharpe']:.2f} "
                f"| {t['teste']['retorno_total']*100:.1f}% | {t['teste']['n_trades']} |")
        add("\n</details>\n")

        resumo_final.append((nome, melhor))

    add("## Comprar e segurar (referência)\n")
    add("| Métrica | Treino | Teste |")
    add("|---|---|---|")
    f_tr, f_te = metricas.formatar(bh_treino), metricas.formatar(bh_teste)
    for k in ("Retorno total", "Retorno anualizado (CAGR)", "Sharpe", "Drawdown máximo"):
        add(f"| {k} | {f_tr[k]} | {f_te[k]} |")
    add("")

    add("## Veredito automático\n")
    for nome, melhor in resumo_final:
        te = melhor["teste"]
        ok_lucro = te["retorno_total"] > 0
        ok_bh = te["sharpe"] > bh_teste["sharpe"]
        ok_trades = te["n_trades"] >= 30
        if ok_lucro and ok_bh and ok_trades:
            v = "✅ passou no teste fora da amostra. Próximo passo: paper trading (não é dinheiro real ainda)."
        elif ok_lucro and not ok_bh:
            v = "⚠️ lucrou, mas perdeu para comprar e segurar (em risco ajustado). Não justifica o trabalho e o risco."
        elif not ok_trades:
            v = "⚠️ poucos trades no teste para qualquer conclusão estatística."
        else:
            v = "❌ reprovada: perdeu dinheiro fora da amostra."
        add(f"- **{nome.replace('_', ' ')}**: {v}")
    add(f"\nTotal de combinações testadas neste estudo: **{total_testadas}**. "
        "Lembre: quanto mais combinações, maior a chance de uma parecer boa por pura sorte.")

    relatorio = "\n".join(linhas_rel)
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    saida = PASTA_RESULTADOS / f"relatorio_{args.par}_{args.timeframe}.md"
    saida.write_text(relatorio, encoding="utf-8")
    print(relatorio)
    print(f"\nRelatório salvo em: {saida}")


if __name__ == "__main__":
    main()
