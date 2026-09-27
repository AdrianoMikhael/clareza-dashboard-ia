# Relatório de validação

Validação atualizada em 27/09/2026, no ambiente Windows desta entrega.

## Resultado

**62 testes passaram**, incluindo banco PostgreSQL real, interface Streamlit
AppTest e inferência real com Qwen2.5 1.5B pelo motor local llama.cpp.

Última execução da suíte completa: **26,95 segundos**. Esse tempo é uma
observação do ambiente de teste, com o modelo já carregado; não é uma garantia
de desempenho para outro computador ou para a primeira pergunta.

## O que foi verificado

- Modo somente dashboard: igualdade de faturamento com o cálculo do painel, persistência do modo, bloqueio de fontes textuais e reprocessamento restrito.
- Catálogo e envio de pedido pelo chat verificados na interface com AppTest.

- Listagem de perguntas não respondidas, busca, histórico resolvido e ausência de duplicação entre tentativas.

- Comparações lado a lado entre meses, intervalos, semestres e anos.
- Ordem A/B preservada, datas inválidas, anos ambíguos e limites de cobertura.
- Diferenças e percentuais individuais para faturamento, ticket, pedidos e taxas.
- Ticket médio ponderado pelos pedidos, bases zero e períodos com durações distintas.
- Gravação da comparação no banco e troca do indicador no gráfico via AppTest.

- Perguntas sobre qual região mais/menos faturou, vendeu unidades ou cancelou pedidos.
- Participação percentual por região e de uma região nomeada, com denominador explícito.
- Diferença entre participação nos cancelamentos e taxa de cancelamento interna.
- Continuação “e em porcentagem?” com contexto salvo para reprocessamento.
- Verificação do ranking real: Centro-Oeste, R$ 479.789,70, 21,94% do faturamento no período completo.

- Tabelas mensais com meses sem registros, base zero e meses fora da cobertura.
- Comparações entre meses, inclusive escritos na ordem inversa, e filtros por nomes.
- Perguntas reais “quanto ela faturou no mes 5” e “faturamento do Nordeste no mes 5”.
- Meses numéricos 5/05 e rejeição de mês inválido.
- Vários indicadores na mesma resposta e crescimento por mês/região.
- Rankings de produtos, participação sobre o total e taxa de cancelamento.
- Persistência das tabelas no JSONB de evidências e apresentação no Streamlit.

- Exclusão dos cancelamentos nos totais; ticket médio com arredondamento em centavos.
- Agrupamento por região e comportamento com recorte vazio.
- Rejeição de operações e agrupamentos fora da lista permitida.
- PostgreSQL com 1.800 pedidos, geração idempotente e filtros parametrizados.
- Persistência da pergunta antes da inferência e recuperação em uma nova conexão.
- Fluxo: pergunta sem resposta → ensino → reprocessamento → sugestão → aprovação.
- Fontes editadas/desativadas, revisões e recusa de aprovar uma sugestão obsoleta.
- Falha de inferência, tempo limite, retorno inválido e identificador de fonte inexistente.
- Proteção contra sobrescrever uma pergunta resolvida durante outra tentativa.
- As quatro seções da interface e o fluxo de ensino pelo Streamlit AppTest.
- Modelo real: pergunta sem fonte e recuperação da regra de faturamento.
  Consultas numéricas reconhecidas agora passam pelo interpretador determinístico.

Também foi aberta a aplicação no navegador e enviada a pergunta
**“Quanto vendemos por categoria?”**, com resposta observada:

| Categoria | Faturamento |
|---|---:|
| Tecnologia | R$ 1.251.204,60 |
| Escritório | R$ 721.424,40 |
| Casa | R$ 213.819,70 |

Na validação original a consulta passou pelo modelo. Na versão atual ela usa
o método `Análise estruturada em português • cálculos com pandas`.

Em 26/09 também foi verificada a resposta “Mostre os valores mês a mês” no
navegador, com seis linhas, variações, gráfico e CSV. Maio totalizou
R$ 392.876,60; setembro foi identificado como parcial.

As duas perguntas de maio pendentes foram reprocessadas no banco da aplicação
e ficaram como sugestões, sem aprovação automática. Os filtros originais de
ambas incluíam Nordeste: faturamento de maio de R$ 59.059,60.

## Ambiente

- Python 3.12.14; PostgreSQL 18.3.
- Versões diretas Python registradas em `requirements-tested.txt`.
- Modelo Qwen2.5 1.5B Q4_K_M, baixado do registro oficial Ollama;
  integridade dos arquivos validada por SHA-256.
- llama.cpp fornecido no pacote oficial Ollama 0.34.4, execução em CPU.
- Testes de integração em banco separado: `dashboard_test`.

## Limitações da validação

- Docker não está disponível neste ambiente: o Compose não foi executado.
  Seu YAML foi validado sintaticamente. A subida dos contêineres ainda precisa
  ser verificada em uma máquina com Docker.
- O serviço Ollama não pôde iniciar por falta de acesso à sua pasta de
  configuração no Windows. A inferência foi testada com o backend llama.cpp.
  A integração HTTP Ollama está implementada, mas não foi validada ponta a ponta aqui.
- Os testes comuns simulam o retorno da inferência para exercitar erros e estados
  de maneira reproduzível; o teste final utiliza o modelo real.
- O loop horário do worker não foi mantido rodando durante horas. Seu processamento
  de lote e a persistência das sugestões foram testados.
- Não foram feitos testes de carga, múltiplos usuários ou um estudo estatístico
  de acurácia. Um modelo pequeno pode interpretar perguntas incorretamente.
- O ZIP contém código e documentação; binários, modelo, banco de avaliação e
  ambiente virtual ficam fora dele. O Compose baixa e prepara esses componentes.
