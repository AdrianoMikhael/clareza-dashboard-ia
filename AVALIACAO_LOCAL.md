# Avaliar a demonstração já preparada

Abra **http://127.0.0.1:8501** neste computador.

O ambiente de avaliação usa:

- Python 3.12, Streamlit, pandas e SQLAlchemy;
- PostgreSQL 18.3, banco isolado `dashboard` na porta **55432**;
- Qwen2.5 1.5B real, carregado em CPU pelo **llama.cpp** na porta **11435**;
- os mesmos fluxos e código disponíveis no ZIP;
- nenhuma conta, chave de API de serviço externo ou login na interface.

O Ollama não conseguiu criar sua configuração em `.ollama` por uma restrição
de acesso do Windows. O motor llama.cpp, distribuído no pacote oficial do
Ollama, permitiu executar o mesmo modelo sem alterar essa proteção. A configuração
Docker entregue continua usando Ollama. O download do modelo foi conferido por
SHA-256 com o manifesto do registro oficial do Ollama.

## Experimentar

**Novidade:** teste “Mostre os valores mês a mês”, “Faça uma análise completa
das vendas”, “Compare agosto e setembro de 2026” e “Top 3 produtos por
faturamento”. As respostas agora trazem tabela, gráfico, resumo e download CSV.
Setembro aparece como parcial, pois os dados terminam no dia 24.

1. Em Assistente, pergunte **Quanto vendemos por categoria?**
2. Confira os valores, a fonte e a indicação de IA local na resposta.
3. Pergunte **Qual é o prazo de entrega?**
4. Em Pendências, cadastre uma resposta e fonte fictícias, reprocessando a pergunta.
5. Aprove a sugestão e pergunte novamente.

A base de demonstração não foi preenchida com o conhecimento criado pelos testes.
Os testes usam outro banco, `dashboard_test`.

## Reabrir após fechar a sessão ou reiniciar

Execute `INICIAR-NESTE-COMPUTADOR.ps1` no PowerShell a partir desta pasta:

```powershell
.\INICIAR-NESTE-COMPUTADOR.ps1
```

O script reutiliza os arquivos em `../../work/`, inicia os serviços necessários
e mantém a aplicação no terminal quando ela ainda não estiver aberta. Não baixe
novamente o modelo e não instale Docker para usar esse ambiente já preparado.
Se a política local bloquear scripts, siga a execução manual abaixo, sem mudar
a política do Windows.

## Execução manual

O ambiente preparado depende desta estrutura de pastas; não mova apenas a pasta
do projeto para outro lugar. Para distribuir, use o ZIP e o procedimento Docker.

Na pasta `dashboard-ia`, em um terminal separado para cada serviço:

```powershell
# 1. PostgreSQL, apenas se ainda não estiver ativo
& 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -D '..\..\work\runtime\pgdata' -p 55432 -h 127.0.0.1
```

```powershell
# 2. Modelo, apenas se ainda não estiver ativo
$taskModel = (Get-Content '..\..\work\runtime\model-path.txt' -Raw).Trim()
& '..\..\work\runtime\ollama\lib\ollama\llama-server.exe' -m $taskModel --host 127.0.0.1 --port 11435 -c 8192 -t 4 -ngl 0 --jinja
```

```powershell
# 3. Aplicação: a configuração local já está no .env desta pasta
& '..\..\work\venv\Scripts\python.exe' run.py
```

O banco fica em `../../work/runtime/pgdata`; o modelo, em
`../../work/runtime/models`. O ambiente usa autenticação `trust` somente no
PostgreSQL isolado de demonstração, vinculado ao loopback. Não reutilize essa
configuração para um banco de produção. A instalação Docker usa senha própria.

Os serviços ocupam memória enquanto estiverem ligados. Para encerrar o banco
de demonstração preservando os dados:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D '..\..\work\runtime\pgdata' -m fast stop
```

Para serviços iniciados manualmente no terminal, use Ctrl+C no respectivo
terminal. Se iniciou o modelo pelo script em segundo plano, encerre o processo
`llama-server` associado a esta demonstração pelo Gerenciador de Tarefas.
