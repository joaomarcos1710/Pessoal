"""Roda o estudo completo de UM par: baixa dados, otimiza no TREINO, valida no TESTE.

Uso:
    python rodar_backtest.py                              # BTC-USDT, 1H, desde 2023
    python rodar_backtest.py --par ETH-USDT --timeframe 15m --inicio 2024-01-01
    python rodar_backtest.py --taxa 0.0008 --slippage 0.0003

Para vários pares de uma vez, use `rodar_varios.py`.

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
MIN_TRADES_TESTE = 30


def avaliar(df: pd.DataFrame, sinal: pd.Series, custos: Custos, timeframe: str) -> dict:
    return metricas.calcular(rodar_backtest(df, sinal, custos), timeframe)


def veredito(teste: dict, bh_teste: dict) -> tuple[str, str]:
    """Classifica o resultado fora da amostra. Retorna (símbolo, explicação)."""
    lucrou = teste["retorno_total"] > 0
    bateu_bh = teste["sharpe"] > bh_teste["sharpe"]
    if teste["n_trades"] < MIN_TRADES_TESTE:
        return "⚠️", "poucos trades no teste para qualquer conclusão estatística."
    if lucrou and bateu_bh:
        return "✅", "passou no teste fora da amostra. Próximo passo: paper trading (não é dinheiro real ainda)."
    if lucrou:
        return "⚠️", "lucrou, mas perdeu para comprar e segurar (em risco ajustado). Não justifica o trabalho e o risco."
    return "❌", "reprovada: perdeu dinheiro fora da amostra."


def estudar(
    par: str,
    timeframe: str,
    inicio: str,
    fracao_treino: float,
    custos: Custos,
    usar_cache: bool = True,
) -> tuple[str, list[dict]]:
    """Roda o estudo de um par.

    Retorna (relatório em Markdown, resumo), onde o resumo tem uma linha por
    estratégia com os números da combinação escolhida no treino.
    """
    df = baixar_candles(par, timeframe, inicio, usar_cache=usar_cache)

    corte = int(len(df) * fracao_treino)
    treino_idx, teste_idx = df.index[:corte], df.index[corte:]
    df_treino, df_teste = df.loc[treino_idx], df.loc[teste_idx]

    linhas_rel: list[str] = []
    add = linhas_rel.append

    add(f"# Backtest {par} · {timeframe}\n")
    add(f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.\n")
    add(f"- **Dados:** {len(df):,} candles, de {df.index[0]:%Y-%m-%d} a {df.index[-1]:%Y-%m-%d}")
    add(f"- **Treino:** {treino_idx[0]:%Y-%m-%d} → {treino_idx[-1]:%Y-%m-%d} ({len(df_treino):,} candles)")
    add(f"- **Teste (fora da amostra):** {teste_idx[0]:%Y-%m-%d} → {teste_idx[-1]:%Y-%m-%d} ({len(df_teste):,} candles)")
    add(f"- **Custo por ordem:** {custos.taxa*100:.2f}% taxa + {custos.slippage*100:.2f}% slippage "
        f"= {custos.por_lado*100:.2f}% (ida e volta: {2*custos.por_lado*100:.2f}%)\n")

    bh = comprar_e_segurar(df)
    bh_treino = avaliar(df_treino, bh.loc[treino_idx], custos, timeframe)
    bh_teste = avaliar(df_teste, bh.loc[teste_idx], custos, timeframe)

    total_testadas = 0
    resumo: list[dict] = []

    for nome, cfg in GRADES.items():
        funcao, grade = cfg["funcao"], cfg["params"]
        total_testadas += len(grade)

        # 1) roda cada combinação de parâmetros no treino e no teste
        tabela = []
        for p in grade:
            sinal = funcao(df, **p)  # indicadores só olham para trás, então calcular no df inteiro é seguro
            m_tr = avaliar(df_treino, sinal.loc[treino_idx], custos, timeframe)
            m_te = avaliar(df_teste, sinal.loc[teste_idx], custos, timeframe)
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

        simbolo, explicacao = veredito(melhor["teste"], bh_teste)
        resumo.append(
            {
                "par": par,
                "estrategia": nome,
                "params": melhor["params"],
                "treino": melhor["treino"],
                "teste": melhor["teste"],
                "bh_teste": bh_teste,
                "n_combos": len(grade),
                "positivas_teste": positivas_teste,
                "simbolo": simbolo,
                "explicacao": explicacao,
            }
        )

    add("## Comprar e segurar (referência)\n")
    add("| Métrica | Treino | Teste |")
    add("|---|---|---|")
    f_tr, f_te = metricas.formatar(bh_treino), metricas.formatar(bh_teste)
    for k in ("Retorno total", "Retorno anualizado (CAGR)", "Sharpe", "Drawdown máximo"):
        add(f"| {k} | {f_tr[k]} | {f_te[k]} |")
    add("")

    add("## Veredito automático\n")
    for r in resumo:
        add(f"- **{r['estrategia'].replace('_', ' ')}**: {r['simbolo']} {r['explicacao']}")
    add(f"\nTotal de combinações testadas neste estudo: **{total_testadas}**. "
        "Lembre: quanto mais combinações, maior a chance de uma parecer boa por pura sorte.")

    return "\n".join(linhas_rel), resumo


def salvar_relatorio(relatorio: str, par: str, timeframe: str) -> Path:
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    saida = PASTA_RESULTADOS / f"relatorio_{par}_{timeframe}.md"
    saida.write_text(relatorio, encoding="utf-8")
    return saida


def argumentos_comuns(ap: argparse.ArgumentParser) -> None:
    """Opções compartilhadas entre este script e o `rodar_varios.py`."""
    ap.add_argument("--timeframe", default="1H", choices=list(metricas.CANDLES_POR_ANO))
    ap.add_argument("--inicio", default="2023-01-01")
    ap.add_argument("--treino", type=float, default=0.7, help="fração dos dados usada para otimizar")
    ap.add_argument("--taxa", type=float, default=0.0010)
    ap.add_argument("--slippage", type=float, default=0.0005)
    ap.add_argument("--sem-cache", action="store_true")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--par", default="BTC-USDT")
    argumentos_comuns(ap)
    args = ap.parse_args()

    custos = Custos(taxa=args.taxa, slippage=args.slippage)
    relatorio, _ = estudar(args.par, args.timeframe, args.inicio, args.treino, custos, not args.sem_cache)
    saida = salvar_relatorio(relatorio, args.par, args.timeframe)
    print(relatorio)
    print(f"\nRelatório salvo em: {saida}")


if __name__ == "__main__":
    main()
