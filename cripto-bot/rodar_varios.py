"""Roda o mesmo estudo em VÁRIOS pares e monta uma tabela consolidada.

Uso:
    python rodar_varios.py --timeframe 15m
    python rodar_varios.py --pares ETH-USDT SOL-USDT --timeframe 15m --inicio 2024-01-01

Cuidado estatístico: 8 pares × 2 estratégias = 16 "finalistas". Com tantas
tentativas, 1 ou 2 aprovadas podem ser pura sorte. O sinal que importa é o
conjunto (quantas passaram?), não o melhor caso isolado.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from bot.backtest import Custos
from rodar_backtest import PASTA_RESULTADOS, argumentos_comuns, estudar, salvar_relatorio

PARES_PADRAO = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT",
    "BNB-USDT", "DOGE-USDT", "ADA-USDT", "LINK-USDT",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pares", nargs="+", default=PARES_PADRAO)
    argumentos_comuns(ap)
    args = ap.parse_args()

    custos = Custos(taxa=args.taxa, slippage=args.slippage)
    resumo: list[dict] = []
    for par in args.pares:
        print(f"Estudando {par}…", flush=True)
        relatorio, linhas = estudar(par, args.timeframe, args.inicio, args.treino, custos, not args.sem_cache)
        salvar_relatorio(relatorio, par, args.timeframe)
        resumo.extend(linhas)

    out: list[str] = []
    add = out.append
    add(f"# Consolidado · {args.timeframe} · {len(args.pares)} pares\n")
    add(f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
        f"Custo por operação completa: {2*custos.por_lado*100:.2f}%. "
        "Parâmetros escolhidos no treino; os números abaixo são do **teste** (fora da amostra).\n")
    add("| Par | Estratégia | Parâmetros | Sharpe treino | Sharpe teste | Retorno teste | "
        "Comprar e segurar | Trades | Expectativa/trade | Custos | Combos com lucro | Veredito |")
    add("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in resumo:
        te, bh = r["teste"], r["bh_teste"]
        params = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        add(f"| {r['par']} | {r['estrategia'].replace('_', ' ')} | {params} "
            f"| {r['treino']['sharpe']:.2f} | {te['sharpe']:.2f} | {te['retorno_total']*100:.1f}% "
            f"| {bh['retorno_total']*100:.1f}% | {te['n_trades']} | {te['expectativa_por_trade']*100:.2f}% "
            f"| {te['custos_totais']*100:.0f}% | {r['positivas_teste']}/{r['n_combos']} | {r['simbolo']} |")

    aprovadas = sum(r["simbolo"] == "✅" for r in resumo)
    lucraram = sum(r["teste"]["retorno_total"] > 0 for r in resumo)
    combos_total = sum(r["n_combos"] for r in resumo)
    combos_lucro = sum(r["positivas_teste"] for r in resumo)
    add("")
    add(f"- **Aprovadas:** {aprovadas} de {len(resumo)} (lucro no teste, Sharpe acima de comprar e segurar e trades suficientes).")
    add(f"- **Com lucro no teste:** {lucraram} de {len(resumo)} finalistas.")
    add(f"- **Todas as combinações (sem escolher a melhor):** {combos_lucro} de {combos_total} deram lucro no teste.")

    texto = "\n".join(out)
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    saida = PASTA_RESULTADOS / f"consolidado_{args.timeframe}.md"
    saida.write_text(texto, encoding="utf-8")
    print("\n" + texto)
    print(f"\nConsolidado salvo em: {saida}")


if __name__ == "__main__":
    main()
