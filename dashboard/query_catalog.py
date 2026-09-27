"""Catálogo fechado das consultas disponíveis para conversar com o dashboard.

Não contém SQL recebido do usuário. Os destinos usam as funções de consulta e
cálculo existentes, também usadas pelos cartões e gráficos da aplicação.
"""
from .text import normalize

CATALOG = [
    {"Consulta": "Indicadores de vendas", "Exemplo": "Faça uma análise completa das vendas"},
    {"Consulta": "Evolução mensal", "Exemplo": "Mostre os valores mês a mês"},
    {"Consulta": "Vendas por região", "Exemplo": "Qual região mais faturou?"},
    {"Consulta": "Categorias e produtos", "Exemplo": "Top 3 produtos por faturamento"},
    {"Consulta": "Comparação de períodos", "Exemplo": "Compare junho com julho em faturamento e ticket médio"},
    {"Consulta": "Participações e cancelamentos", "Exemplo": "Qual a participação de cada região no faturamento em porcentagem?"},
]

# Atalhos exatos evitam retirar filtros ou mudar o significado de frases livres.
ALIASES = {
    normalize("Mostre o resumo do dashboard"): CATALOG[0]["Exemplo"],
    normalize("Mostre os indicadores do dashboard"): CATALOG[0]["Exemplo"],
    normalize("Mostre o gráfico de vendas por região"): "Mostre o faturamento por região",
    normalize("Mostre o gráfico de evolução do faturamento"): "Faturamento por mês",
}


def resolve(question):
    return ALIASES.get(normalize(question), question)
