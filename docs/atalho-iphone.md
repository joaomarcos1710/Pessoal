# Atalho do iPhone: Notion → Lembretes e Diário

Um único Atalho, rodando sozinho às **07h15**, faz duas coisas:

1. Lê os itens novos do banco **Lembretes** (Notion) e cria cada um no app **Lembretes**.
2. Lê a entrada de hoje do banco **Diário** (Notion) e cria uma entrada no app **Diário** da Apple.

Depois marca cada item no Notion (`NoIPhone` / `NoDiario`) para não repetir.

> O app Diário ganhou a ação de Atalhos **"Criar Entrada"** no iOS 18.1. Se o seu iPhone
> não mostrar essa ação, atualize o iOS.

---

## Parte 1: Chave do Notion (uma vez)

1. Abra **notion.so/profile/integrations** → **New integration** → nome `Atalho iPhone`,
   tipo **Internal** → salve e copie o **secret** (trate como senha).
2. No Notion, abra a página **Assessor** → **⋯** → **Conexões** → adicione `Atalho iPhone`.
   (Isso libera os dois bancos, Lembretes e Diário, de uma vez.)

## Parte 2: Lista no Lembretes

App Lembretes → **Adicionar Lista** → `Assessor`.

## Parte 3: O Atalho

App **Atalhos** → **+** → nome `Assessor`.

### Bloco A: Lembretes

1. **Texto**: cole o secret → renomeie a variável para `Token`.
2. **Texto**:
   ```json
   {"filter":{"property":"NoIPhone","checkbox":{"equals":false}}}
   ```
   → renomeie para `FiltroLembretes`.
3. **Obter Conteúdo do URL**
   - URL: `https://api.notion.com/v1/databases/9207f7a699fd41bca7cd83defdfb7cf2/query`
   - Método **POST**; cabeçalhos:
     `Authorization` = `Bearer ` + **Token** · `Notion-Version` = `2022-06-28` · `Content-Type` = `application/json`
   - Corpo: **Arquivo** → `FiltroLembretes`
4. **Obter Valor do Dicionário**: chave `results`.
5. **Repetir com Cada** item:
   - Obter Valor do Dicionário `properties.Lembrete.title.1.plain_text` → `Titulo`
     *(se o iPhone não aceitar o `.1`, use a chave `properties.Lembrete.title`, depois **Obter Item da Lista** → Primeiro Item → **Obter Valor do Dicionário** `plain_text`)*
   - Obter Valor do Dicionário `properties.QuandoISO.formula.string` → `Quando`
   - Obter Valor do Dicionário `properties.Link.url` → `Link`
   - Obter Valor do Dicionário `id` → `PaginaID`
   - **Se** `Quando` tem qualquer valor:
     **Ajustar Data** (+9 horas em `Quando`) → **Adicionar Novo Lembrete** (Título `Titulo`, Lista `Assessor`, Alerta em **Data Ajustada**, Notas `Link`)
     **Senão**: **Adicionar Novo Lembrete** (Título `Titulo`, Lista `Assessor`, Notas `Link`)
   - **Texto** `{"properties":{"NoIPhone":{"checkbox":true}}}` → `Marcar`
   - **Obter Conteúdo do URL**: `https://api.notion.com/v1/pages/` + `PaginaID`, método **PATCH**,
     mesmos cabeçalhos, corpo **Arquivo** → `Marcar`

### Bloco B: Diário

6. **Texto**:
   ```json
   {"filter":{"property":"NoDiario","checkbox":{"equals":false}}}
   ```
   → `FiltroDiario`
7. **Obter Conteúdo do URL**: `https://api.notion.com/v1/databases/883d64e4e5a34189b239b6a4e46b5145/query`,
   POST, mesmos cabeçalhos, corpo **Arquivo** → `FiltroDiario`
8. **Obter Valor do Dicionário** `results`
9. **Repetir com Cada** item:
   - `properties.Dia.title.1.plain_text` → `TituloDia`
   - `properties.Texto.rich_text.1.plain_text` → `TextoDia`
   - `id` → `DiaID`
   - **Criar Entrada** (app Diário): Título `TituloDia`, Texto `TextoDia`
   - **Texto** `{"properties":{"NoDiario":{"checkbox":true}}}` → `MarcarDia`
   - **Obter Conteúdo do URL**: `https://api.notion.com/v1/pages/` + `DiaID`, **PATCH**, corpo `MarcarDia`

### Teste
Toque em ▶️ e permita o acesso a `api.notion.com`, ao Lembretes e ao Diário (**Permitir sempre**).

## Parte 4: Automação diária
Atalhos → **Automação** → **+** → **Hora do Dia** → **07:15**, diariamente →
**Executar Imediatamente** → ação **Executar Atalho** `Assessor`.

---

| Erro | Causa | Solução |
|---|---|---|
| 401 | Token errado ou sem `Bearer ` | Confira o cabeçalho |
| 404 | Página Assessor não conectada à integração | Parte 1, passo 2 |
| Título vazio | Caminho da chave | Use a alternativa indicada no passo 5 |
| Ação "Criar Entrada" não aparece | iOS antigo | Atualize para iOS 18.1 ou mais novo |
