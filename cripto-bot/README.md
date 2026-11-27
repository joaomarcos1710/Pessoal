# cripto-bot: backtester de estratégias para cripto

**Fase 1 (pesquisa).** Este código **não envia ordens** e não precisa de chave de API.
Ele baixa candles públicos da OKX e testa se uma regra de compra e venda teria dado
lucro no passado, **depois de custos** e **fora da amostra**.

> Robô não cria vantagem, só automatiza uma regra. Se a regra não passa aqui,
> automatizar só faz perder dinheiro mais rápido.

## Como rodar

```bash
cd cripto-bot
pip install -r requirements.txt
python -m pytest -q            # testes do motor (6 testes)
python rodar_backtest.py       # BTC-USDT, candles de 1h, desde 2023-01-01
```

Outras opções:

```bash
python rodar_backtest.py --par ETH-USDT --timeframe 15m --inicio 2024-01-01
python rodar_backtest.py --taxa 0.0008 --slippage 0.0003   # custos diferentes
python rodar_backtest.py --sem-cache                       # baixa os dados de novo
```

O relatório sai na tela e em `resultados/relatorio_<par>_<timeframe>.md`.
Os dados baixados ficam em `dados/`. As duas pastas não vão para o Git.

## Estrutura

| Arquivo | O que faz |
|---|---|
| `bot/dados.py` | Baixa candles da API pública da OKX, paginando para trás, com cache em CSV |
| `bot/estrategias.py` | Estratégias de exemplo (cruzamento de médias, canal de Donchian) e a grade de parâmetros |
| `bot/backtest.py` | Motor: transforma sinal em posição **com 1 candle de atraso** e cobra taxa + slippage em cada ordem |
| `bot/metricas.py` | Sharpe, drawdown, taxa de acerto, payoff, expectativa por trade… |
| `rodar_backtest.py` | Estudo completo: otimiza no treino, valida no teste, compara com comprar e segurar |
| `tests/` | Testes que garantem, por exemplo, que o backtest não "vê o futuro" |

## Como o estudo evita autoengano

1. **Sem olhar o futuro:** a decisão tomada no fechamento do candle *t* só vale a partir do candle *t+1*.
2. **Custos reais:** 0,10% de taxa (taker, nível básico da OKX spot) + 0,05% de slippage **por ordem**,
   ou seja, 0,30% por operação completa (entrada e saída).
3. **Treino × teste:** os parâmetros são escolhidos nos 70% mais antigos dos dados.
   O número que importa é o dos 30% mais recentes, que a otimização nunca viu.
4. **Benchmark:** toda estratégia é comparada com simplesmente comprar e segurar.
5. **Transparência:** o relatório mostra **todas** as combinações testadas, não só a melhor.

## Como ler o relatório

- **Expectativa por trade:** quanto você ganha ou perde, em média, por operação. Precisa ser positiva **no teste**.
- **Payoff:** ganho médio ÷ perda média. Combinado com a taxa de acerto, define se a conta fecha.
- **Sharpe:** retorno por unidade de risco. Abaixo de 0 é perda; acima de 1 de forma consistente é raro.
- **Drawdown máximo:** a maior queda do topo ao fundo. É o que testa seu psicológico.
- **Degradação treino → teste:** se o Sharpe despenca fora da amostra, a "estratégia" era ajuste ao ruído.

## Primeiro resultado (BTC-USDT, 1h, 2023-01 → 2026-11)

| Estratégia | Sharpe treino | Sharpe teste | Retorno teste | Veredito |
|---|---|---|---|---|
| Cruzamento de médias (50/100) | 1,53 | −1,45 | −39,8% | ❌ |
| Canal de Donchian (100/50) | 1,17 | −0,80 | −21,5% | ❌ |
| Comprar e segurar | 1,72 | −0,94 | −45,1% | referência |

Nenhuma das 19 combinações deu lucro no período de teste. Mesmo no treino, a melhor
estratégia perdeu para comprar e segurar em risco ajustado. Os custos consumiram cerca de 18%
do capital no teste da estratégia de médias (59 operações × 0,30%).

## Próximas fases (só se alguma estratégia passar no teste)

1. **Paper trading:** o robô roda em tempo real, mas registra ordens fictícias.
2. **Execução real:** chave de API **sem permissão de saque**, capital pequeno, stop diário e
   rodando num servidor ou no seu PC (o ambiente do Claude na nuvem é temporário).

## Avisos

- Resultado passado não garante resultado futuro, e um backtest bom é condição **necessária, não suficiente**.
- **Tributação de cripto no Brasil:** há regras específicas, inclusive para exchanges no exterior
  (Lei 14.754/2023). Confirme com um contador antes de operar com dinheiro real; este projeto não calcula imposto.
