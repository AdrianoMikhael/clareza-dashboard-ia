# Clareza — dashboard com IA local e memória revisada

Exemplo completo em **Python + pandas + PostgreSQL**, com interface Streamlit e
um modelo gratuito executado localmente, **sem login no dashboard ou em um
serviço de IA**. O modelo padrão é **Qwen2.5 1.5B**, servido pelo Ollama.

Você pode explorar 1.800 pedidos fictícios, perguntar sobre os indicadores,
consultar regras cadastradas e ensinar respostas quando faltar informação.
Perguntas, tentativas, conhecimento e revisões permanecem no PostgreSQL.

> O software não cobra por pergunta. Computação, energia e eventual hospedagem
> continuam sendo recursos necessários. A instalação inicial requer internet;
> as consultas funcionam localmente depois de baixar as dependências e o modelo.

## Perguntas não respondidas

No menu lateral, abra **Perguntas não respondidas**. A página consulta o
PostgreSQL e mostra pergunta, ID, situação, data, tentativas e motivo atual.
Inclui pendências e sugestões ainda não aprovadas. Há busca literal por texto,
filtro de situação, download em CSV e consulta da pergunta completa com histórico.
A opção de incluir falhas anteriores também mostra perguntas posteriormente
respondidas ou arquivadas, sem duplicar suas várias tentativas. O botão
**Atualizar lista** consulta novamente o banco. Os filtros de vendas não limitam
esta lista; as datas da listagem usam o horário de Brasília.
Para ensinar uma resposta ou reprocessar, abra **Pendências** e escolha o mesmo ID.

## Conversar com as consultas do dashboard

Na página **Assistente**, o modo **Consultar somente os dados do dashboard**
vem ativado. Digite o indicador e o recorte em linguagem natural; o resultado
aparece na conversa, com os filtros efetivos e a fonte. Exemplos:

- Mostre o resumo do dashboard.
- Mostre o gráfico de vendas por região.
- Qual o faturamento do Nordeste em maio?
- Compare junho com julho em faturamento e ticket médio.

O catálogo em `dashboard/query_catalog.py` descreve as operações existentes e
atalhos para elas. Não lê números da tela: consulta a mesma fonte PostgreSQL e
reutiliza `sales_frame`, `metric_value` e as análises já implementadas. A IA
seleciona operações permitidas; não gera nem executa SQL livre. Essa integração
é com este dashboard, não uma conexão automática a dashboards externos.

Neste modo, conhecimento textual aprovado não substitui consultas de dados.
Pedidos incompatíveis ficam pendentes. Para acrescentar outro indicador, é
necessário implementar sua consulta e regra de cálculo; cadastrar apenas uma
resposta não cria essa capacidade. Desative o modo para voltar a consultar também
o conhecimento aprovado. O modo fica salvo nos filtros da pergunta e é
respeitado pelo reprocessamento. Perguntas antigas mantêm seu comportamento.

## Comece por aqui

### Análises avançadas (atualização de 26/09/2026)

### Comparação de dois períodos

As comparações agora trazem **uma linha por indicador**, com período A,
período B, diferença absoluta (B − A) e variação relativa. O gráfico permite
escolher o indicador sem misturar dinheiro, quantidade e taxa no mesmo eixo.

Exemplos:

- “Compare junho com julho em faturamento e ticket médio”.
- “Julho x junho: faturamento e pedidos concluídos”.
- “Compare abril a junho com julho a setembro”.
- “Compare 01/04/2026 a 30/06/2026 com 01/07/2026 a 24/09/2026”.
- “Compare o primeiro semestre com o segundo semestre de 2026”.
- “Compare 2025 com 2026”.
- “Compare junho de 2025 com junho de 2026”.

Sem indicador explícito, a comparação mostra os seis indicadores disponíveis.
O primeiro período mencionado é A e o segundo é B; inverter a ordem inverte
a base percentual. Ticket médio é calculado por faturamento / pedidos concluídos
de cada período inteiro. A diferença entre taxas usa pontos percentuais e a
variação relativa fica em uma coluna separada. Base zero ou ausência de dados
gera N/D, sem divisão por zero.

Cada período pode ter até dez anos. Intervalos numéricos exigem quatro datas
completas (duas por período); aceitam DD/MM/AAAA ou AAAA-MM-DD. Meses e
semestres sem ano usam o ano da data final do painel. Ao misturar anos,
escreva o ano junto a cada mês/semestre. Períodos com durações distintas,
sobreposição ou cobertura parcial recebem avisos. Os totais não são
normalizados por dia. A cobertura continua sendo inferida dos registros.

As comparações usam o mesmo recorte de região/categoria/produto para ambos os
períodos e substituem as datas do painel. Para detalhar rankings por grupo,
use uma consulta separada. A base fictícia só tem abril a setembro de 2026;
comparar anos inteiros demonstra o tratamento de falta de cobertura.

O assistente agora responde com **tabela, gráfico, resumo e CSV**, incluindo:

- “Mostre os valores mês a mês”.
- “Faça uma análise completa das vendas”.
- “Faturamento e ticket médio por mês e região”.
- “Compare o faturamento de agosto e setembro de 2026”.
- “Top 3 produtos por faturamento”.
- “Taxa de cancelamento por categoria”.
- “Compare as vendas do Sul e Norte”.
- “Quanto ela faturou no mês 5?” e “Faturamento do Nordeste no mês 5”.
- “Qual região mais faturou?” / “Qual região menos faturou?”.
- “Qual região vendeu mais unidades?” / “Qual região cancelou mais pedidos?”.
- “Qual a participação de cada região no faturamento em porcentagem?”.
- “Qual a porcentagem do Nordeste no faturamento do mês 5?”.
- “Qual região teve a maior taxa de cancelamento?”.

Depois de uma pergunta no chat, também é possível perguntar **“e em porcentagem?”**.
A pergunta anterior é reaproveitada e a consulta completa fica salva para que
o reprocessamento não dependa do histórico do navegador. Sem contexto, o
assistente pede que você informe o indicador.

**Percentuais:** participação divide o valor da região pelo total do recorte.
Se uma região é nomeada explicitamente na pergunta percentual, o denominador
inclui todas as regiões, mantendo período, categoria e produto. Nos demais
casos, preserva as regiões selecionadas no painel. Em mês + região, usa o total
do respectivo mês. A taxa de cancelamento usa cancelados ÷ todos os pedidos
da própria região. Ticket médio não é somado como participação. Bases zero
geram N/D. Os denominadores ficam salvos nas evidências.

Inclui variação relativa entre meses listados, participação em agrupamentos
aditivos, até dois agrupamentos e vários indicadores na mesma pergunta.
Meses parciais são sinalizados; meses fora da cobertura de registros ficam com
N/D. Uma base zero não produz crescimento infinito. A cobertura é inferida das
datas mínima e máxima dos registros, não de uma certificação de carga completa.

O novo interpretador `dashboard/analysis_queries.py` reconhece essas análises e
executa cálculos fechados com pandas. Não depende do acerto de classificação do
modelo pequeno. A IA continua disponível para outras formulações e recuperação
de conhecimento. O método utilizado aparece junto à fonte.

- **Neste computador:** veja [AVALIACAO_LOCAL.md](AVALIACAO_LOCAL.md). A demonstração
  preparada usa o mesmo Qwen com llama.cpp, por uma restrição de pasta do Windows.
- **Em outro computador:** use o Docker Compose abaixo. É o caminho recomendado
  para subir PostgreSQL, Ollama, download do modelo e dashboard juntos.
- **Para avaliar o código:** comece em `app.py`, depois `dashboard/assistant.py`,
  `dashboard/db.py` e `dashboard/worker.py`.

## 1. Executar com Docker Compose

Pré-requisitos: Docker Engine/Desktop em funcionamento, Docker Compose v2,
conexão para os downloads e recursos para o modelo. Recomenda-se pelo menos
8 GB de RAM disponíveis para uma avaliação confortável; desempenho varia com
CPU, memória e quantidade de usuários. GPU não é necessária no exemplo.

Na pasta que contém `compose.yaml`:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
docker compose up --build -d
docker compose logs -f model-init
```

Linux/macOS: use `cp .env.example .env` no lugar de `Copy-Item`.
Quando o download do modelo terminar, pressione Ctrl+C para sair apenas dos logs.

Abra **http://localhost:8501**. Não há cadastro nem tela de login.

O dashboard pode abrir antes de o download terminar. Nesse intervalo os gráficos,
as análises estruturadas e respostas exatas já cadastradas funcionam. A barra
lateral mostra quando a IA está disponível; clique em **Verificar conexão**.

O Compose cria:

| Serviço | Papel | Endereço no computador |
|---|---|---|
| `db` | PostgreSQL 18, dados e histórico | `localhost:5433` |
| `ollama` | Servidor de inferência local | `localhost:11434` |
| `model-init` | Baixa o modelo e termina | Sem porta |
| `app` | Interface Python / Streamlit | `localhost:8501` |
| `worker` | Reprocessamento opcional | Sem porta |

Os volumes `postgres_data` e `ollama_data` mantêm banco e modelo entre reinícios.
As portas são publicadas apenas em `127.0.0.1`, para uso neste computador.
O Compose usa os hosts internos `db` e `ollama`; não usa a `DATABASE_URL` local
do `.env`. A senha do banco vem de `POSTGRES_PASSWORD`.

Para parar, preservando os dados:

```sh
docker compose down
```

**Não use `down -v` se quiser manter o que ensinou:** essa opção remove os volumes.

Para reconstruir após editar o código:

```sh
docker compose up --build -d
```

## 2. Roteiro de avaliação em cinco minutos

1. Em **Visão geral**, veja o faturamento, pedidos, ticket médio e unidades.
   Selecione uma região ou categoria e confira a mudança nos números e gráficos.
2. Em **Assistente**, pergunte **“Quanto vendemos por categoria?”**.
   Essa formulação usa o interpretador analítico; o cálculo é feito com pandas.
   Confira **Fonte**, **método** e **Ver evidência e recorte**.
3. Pergunte **“Qual é o prazo de entrega?”**. Essa informação não existe na base
   inicial. A pergunta deve ficar pendente, com o motivo e os filtros utilizados.
4. Abra **Pendências**, selecione a pergunta e ensine:
   - Resposta: “Nesta demonstração, o prazo é de 5 dias úteis após a confirmação.”
   - Fonte: “Política fictícia de entregas — versão 1”.
5. Clique em **Salvar conhecimento e reprocessar esta pergunta**. A nova resposta
   aparece como **sugestão**. Confira e clique em **Aprovar resposta**.
6. Pergunte a mesma coisa novamente. A resposta cadastrada será encontrada,
   inclusive sem depender do modelo quando o texto normalizado for idêntico.
7. Em **Conhecimento**, edite a resposta, confira o histórico de revisões e
   experimente desativar a fonte. Fontes inativas deixam de ser consultadas.

A primeira tentativa do modelo pode ser mais lenta por causa do carregamento.
Se uma seleção de fonte estiver errada, use **A resposta não resolveu** para
devolver a pergunta à fila. O modelo pequeno pode errar interpretação.

### Números esperados da base inicial, sem filtros

| Indicador | Valor |
|---|---:|
| Pedidos totais | 1.800 |
| Pedidos concluídos | 1.660 |
| Pedidos cancelados | 140 |
| Faturamento | R$ 2.186.448,70 |
| Ticket médio | R$ 1.317,14 |
| Unidades vendidas | 4.931 |

Dados fictícios de **01/04/2026 a 24/09/2026**, com geração reproduzível.
Cada linha representa um pedido de um único produto. Cancelamentos são excluídos
do faturamento, das unidades vendidas e do ticket. Não há custos, impostos,
descontos, frete, clientes identificados nem lucro no esquema deste exemplo.

## 3. Como o assistente funciona

```text
Pergunta + filtros do painel
            |
            v
PostgreSQL: salva a pergunta antes de consultar a IA
            |
            +--> Análise reconhecida? Tabela, indicadores e gráfico com pandas
            |
            +--> Pergunta igual a uma fonte ativa? Resposta cadastrada
            |
            +--> Busca textual no PostgreSQL + interpretação pela IA local
                        |
                        +--> Indicador permitido: pandas calcula
                        +--> Fonte compatível: devolve a resposta aprovada
                        +--> Sem resposta / erro / tempo limite: pendência
```

Quando a análise não é reconhecida pelo interpretador, o modelo escolhe uma
ação em JSON estruturado. O Python valida os nomes de
indicadores, agrupamentos e identificadores de fontes. **O modelo não executa
SQL, Python ou comandos, e não calcula os totais.** Todos os acessos SQL recebem
parâmetros; as consultas de vendas são fixas.

Para conhecimento, o PostgreSQL usa busca textual em português e retorna até
seis candidatos ativos. O modelo escolhe a fonte, e o sistema devolve o texto
aprovado, sem gerar uma nova resposta factual livre. Essa é uma forma simples
de recuperação de conhecimento; não usa embeddings nem banco vetorial.

As sugestões da interface incluem consultas simples e compostas. Análises
estruturadas e correspondências exatas são identificadas no método da resposta.
Outras formulações passam pela IA real quando o servidor está disponível.
Não existe uma IA simulada como fallback da aplicação.

### Escopo das perguntas

Indicadores: faturamento, pedidos concluídos, ticket médio, unidades, quantidade
e taxa de cancelamentos. Agrupamentos: mês, região, categoria e produto; até dois
por consulta. Rankings aceitam um agrupamento e até 50 posições. São permitidos
até 36 meses e 240 linhas por análise.

Os filtros do painel são o padrão. Meses escritos por extenso ou como “mês 5”, um ano explícito
e nomes existentes de regiões/categorias/produtos substituem os filtros dessas
dimensões. Se nenhum ano for informado, usa-se o ano da data final do painel,
com aviso. “De abril a junho” inclui maio; “compare abril e junho” compara os
dois meses listados. A resposta sempre mostra o recorte efetivamente utilizado.

Datas numéricas e anos diferentes são aceitos no fluxo de comparação de dois
períodos descrito acima. Datas numéricas em consultas de um único período,
períodos relativos como “ano passado”, exclusões e medidas ausentes ainda
exigem ajuste do painel ou reformulação. O sistema
não inventa lucro, custos, previsões ou causas. O interpretador cobre construções
comuns, não toda a linguagem natural: confira o plano na evidência e sinalize
respostas que não atendam à intenção.

## 4. O que significa aprender

Aprender, aqui, significa **persistir conhecimento revisado e recuperá-lo em
perguntas futuras**. Não há treinamento dos pesos do modelo.

- `pending`: pergunta sem resposta, falha de serviço ou resposta sinalizada.
- `suggested`: uma nova tentativa encontrou resposta e aguarda revisão.
- `answered`: resposta inicial encontrada ou sugestão aprovada.
- `dismissed`: pergunta arquivada; pode ser reaberta.

Cadastrar uma resposta publica conhecimento imediatamente. Reprocessar uma
pergunta antiga cria uma sugestão. Aprovar uma sugestão resolve essa pergunta;
não cadastra automaticamente conhecimento novo nem grava valores de vendas como
regras permanentes. Revisões da base ficam em `knowledge_history` e todas as
tentativas em `question_attempts`.

Mais tempo sozinho não cria conhecimento. Uma nova tentativa ajuda quando:

- você adicionou uma fonte ou resposta;
- os dados do banco foram atualizados;
- o modelo passou a estar disponível ou foi substituído por um mais capaz.

### Reprocessamento opcional em segundo plano

Manual: botão **Reprocessar até 20 pendências** ou **Tentar esta pergunta novamente**.

Automático com Docker:

```sh
docker compose --profile worker up --build -d
```

O worker fica ativo enquanto o serviço estiver rodando e o computador estiver
ligado. Por padrão verifica a fila a cada hora e processa até 20 perguntas por
lote. Reutiliza os filtros originais, mas consulta os dados atuais. Há até cinco
tentativas automáticas; uma atualização da base de conhecimento libera nova
tentativa. Tentativas manuais não têm esse limite. Não existem notificações,
pesquisa na internet nem aprendizado autônomo fora das fontes cadastradas.

Sem Docker:

```sh
python -m dashboard.worker          # Um lote elegível
python -m dashboard.worker --loop   # Repetir até encerrar o processo
```

Sugestões preservam a data do cálculo e as fontes. Se uma fonte for editada ou
desativada antes da aprovação, a aprovação é recusada: rejeite e reprocesse.
Sugestões numéricas são fotografias do momento da consulta; reprocesse para
obter valores após uma atualização das vendas.

## 5. Executar Python sem Docker

Requer Python **3.12**, PostgreSQL **16 ou superior** e Ollama instalado.
Crie um banco vazio e um usuário próprio, com permissão para criar tabelas.
Configure a conexão em `.env`; o exemplo espera `dashboard` em `localhost:5433`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edite DATABASE_URL no .env para o seu PostgreSQL.
ollama pull qwen2.5:1.5b
.\.venv\Scripts\python.exe run.py
```

Se o Ollama não estiver em execução, inicie `ollama serve` em outro terminal.
Em Linux/macOS use `.venv/bin/python`.

`run.py` cria o esquema e dados iniciais sem apagar vendas existentes. Depois
inicia o Streamlit. Para preparar só o banco: `python -m dashboard.seed`.

Para execução somente local do Ollama, use `OLLAMA_NO_CLOUD=1` no ambiente do
**servidor Ollama**. Colocar essa variável só na aplicação não configura um
servidor que já está rodando. O Compose já aplica essa configuração.

### Motor alternativo: llama.cpp

O código também aceita um servidor **llama.cpp** com o mesmo modelo Qwen e
respostas JSON estruturadas. É a alternativa usada na avaliação deste computador.
Exemplo, com binário e arquivo GGUF já baixados:

```sh
llama-server -m caminho/modelo.gguf --host 127.0.0.1 --port 11435 -c 8192 -t 4 -ngl 0 --jinja
```

No `.env`, defina `AI_BACKEND=llamacpp` e
`OLLAMA_BASE_URL=http://127.0.0.1:11435`. O nome da variável da URL foi mantido
para compartilhar a configuração dos dois motores. A API compatível de chat é
**local**; não há chamada à OpenAI ou necessidade de chave de API.

## 6. Estrutura comentada

```text
app.py                    Interface, filtros, chat, revisão e conhecimento
run.py                    Prepara o banco e inicia a aplicação
dashboard/
  config.py               Ambiente e configuração
  db.py                   PostgreSQL, parâmetros, transações e revisões
  seed.py                 Pedidos fictícios e conhecimento inicial
  analytics.py            Métricas e agrupamentos em pandas
  analysis_queries.py     Análises compostas, meses, comparação, ranking e evidências
  period_comparison.py    Duas janelas temporais e diferenças por indicador
  assistant.py            Busca, chamadas à IA e validação das ações
  worker.py               Reprocessamento manual e automático
  text.py                 Normalização de perguntas
sql/001_schema.sql        Tabelas, restrições e índices
tests/                    Cálculos, banco, interface e IA opcional
compose.yaml              Serviços e volumes locais
Dockerfile                Imagem Python do dashboard e do worker
.env.example              Configuração de exemplo
.streamlit/config.toml    Tema e telemetria desativada
```

## 7. Testes

Sem PostgreSQL, os testes unitários rodam e os testes de integração pulam:

```sh
python -m pytest -q
```

Para integração, crie um **banco descartável chamado exatamente `dashboard_test`**.
Os testes limpam somente as tabelas de aplicação nesse banco; recusam outro nome.

```powershell
$env:DATABASE_URL='postgresql+psycopg://dashboard:dashboard_local@localhost:5433/dashboard_test'
$env:RUN_DB_TESTS='1'
python -m pytest -q
```

Para acrescentar inferência real, tenha o modelo funcionando e defina
`RUN_OLLAMA_TESTS=1`. O teste utiliza o motor configurado por `AI_BACKEND`.

Os testes cobrem cancelamentos, arredondamento, recorte vazio, filtros
parametrizados, ensino, revisão, fonte desativada, erro de inferência,
persistência entre conexões, proteção contra resposta tardia e navegação/ensino
na interface via Streamlit AppTest. Nos testes comuns, só a inferência é
simulada; o banco e os componentes Streamlit são reais. Veja o relatório de
validação entregue para os resultados observados neste ambiente.

## 8. Limites e próximos passos

- Exemplo de uso pessoal/local. Como solicitado, não tem login. Qualquer pessoa
  que acessar a interface pode ensinar, editar e revisar. Antes de disponibilizar
  numa rede, implemente autenticação e permissões, especialmente na área de ensino.
- O modelo de 1,5 bilhão de parâmetros é econômico, mas limitado. Pode selecionar
  uma fonte ou indicador errado. Fontes e recortes ajudam a conferir; os testes
  não garantem precisão em todas as formulações.
- Busca textual depende das palavras usadas. Para uma base maior, considere
  busca híbrida/embeddings, curadoria de fontes e avaliação com perguntas reais.
- A consulta carrega os pedidos do recorte em pandas. Para milhões de linhas,
  agregue no PostgreSQL e pagine a tabela antes de levar resultados ao Python.
- O exemplo usa um usuário de banco para criar tabelas e operar a aplicação.
  Em produção, separe migração, leitura de vendas e escrita do histórico.
- Dependências têm faixas em `requirements.txt`; `requirements-tested.txt`
  registra as versões diretas usadas na validação. Ollama e PostgreSQL estão
  configurados no Compose. O Compose precisa ser validado no seu Docker.
- Conhecimento não deve guardar fatos numéricos que mudam continuamente. Para
  novos indicadores, adicione uma consulta permitida em `analytics.py` e no
  esquema de roteamento, com um teste que confira o valor esperado.

## 9. Solução de problemas

| Sintoma | O que conferir |
|---|---|
| IA indisponível | Serviço Ollama ativo, URL correta e `ollama list` com o modelo |
| Modelo não encontrado | `docker compose logs model-init` ou `ollama pull qwen2.5:1.5b` |
| Tempo limite | CPU/memória disponíveis; aumente `OLLAMA_TIMEOUT` e tente a pendência |
| Banco indisponível | Credenciais, porta, serviço PostgreSQL e `DATABASE_URL` |
| Porta ocupada | Mude o lado esquerdo do mapeamento no Compose ou pare o serviço conflitante |
| Pergunta ficou pendente | Confira o motivo; cadastre fonte ou ajuste o recorte/escopo |
| Resposta antiga na conversa | Histórico é uma fotografia; faça uma nova pergunta após atualizar a fonte |
| Fonte já cadastrada | Selecione a entrada existente na seção Conhecimento e edite |

## Referências e licenças

- [Ollama: autenticação local](https://docs.ollama.com/api/authentication)
- [Ollama: execução local e privacidade](https://docs.ollama.com/faq)
- [Ollama: saídas estruturadas](https://docs.ollama.com/capabilities/structured-outputs)
- [Qwen2.5 1.5B: modelo de aproximadamente 986 MB, licença Apache 2.0](https://ollama.com/library/qwen2.5:1.5b)
- [llama.cpp e servidor local](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing)

O código deste exemplo pode ser adaptado; as dependências e o modelo mantêm
suas próprias licenças. Nenhum modelo, binário de terceiro ou dado privado foi
incluído no ZIP do código-fonte.
