# tests/test_aula4.py
"""Aula 4 — ferramenta buscar_unidade (CAPS, CRAS, CREAS) e o loop de tool-calling."""
# A fixture falso também troca as APIs (CNES, MDS, IBGE, ViaCEP, BrasilAPI) por respostas fixas.
from langchain_core.messages import HumanMessage

from app.agents import grafo
from app.agents.base import criar_agente
from app.config.settings import settings
from app.tools import unidades


# O LLM escolhe a ferramenta pela descrição: ela precisa ser longa e clara.
def test_ferramenta_tem_descricao_e_argumentos():
    for f in unidades.FERRAMENTAS_PASI:
        assert len(f.description) > 80, f"descrição curta demais em {f.name}"
    for argumento in ("tipo", "cep", "municipio", "uf"):
        assert unidades.buscar_unidade.args[argumento]["type"] == "string"


# O nome da cidade vira o código de 6 dígitos que o CNES e o MDS usam.
def test_converte_nome_da_cidade_no_codigo(falso):
    assert unidades.codigo_municipio("maua", "sp") == ("Mauá", 352940)
    assert unidades.codigo_municipio("3529401", "SP")[1] == 352940
    assert unidades.codigo_municipio("Atlântida", "SP") is None


# CAPS: lê o CNES, devolve só os campos úteis e tira as unidades desativadas.
def test_caps_por_cidade(falso):
    saida = unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "Mauá", "uf": "SP"})
    assert saida["total"] == 2
    assert saida["unidades"][0]["telefone"] == "(11) 4555-0000"
    assert saida["fonte"] == "CNES / Ministério da Saúde"


def test_caps_modalidade_e_bairro(falso):
    ad = unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "Mauá", "uf": "SP", "modalidade": "AD"})
    assert [u["nome"] for u in ad["unidades"]] == ["CAPS AD III MAUA"]
    centro = unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "Mauá", "uf": "SP", "bairro": "centro"})
    assert [u["nome"] for u in centro["unidades"]] == ["CAPS II ADULTO MAUA"]


# Com CEP: descobre a cidade e põe a unidade mais perto primeiro.
def test_caps_por_cep_ordena_por_distancia(falso):
    saida = unidades.buscar_unidade.invoke({"tipo": "CAPS", "cep": "09321-090"})
    assert saida["municipio"] == "Mauá/SP"
    assert saida["unidades"][0]["nome"] == "CAPS AD III MAUA"
    assert saida["unidades"][0]["distancia_km"] < saida["unidades"][1]["distancia_km"]


# CRAS: vem do MDS, com telefone formatado, ordenado por distância e com o aviso de território.
def test_cras_por_cep(falso):
    saida = unidades.buscar_unidade.invoke({"tipo": "CRAS", "cep": "09321090"})
    assert [u["nome"] for u in saida["unidades"]] == ["CRAS ZAIRA", "CRAS CENTRO"]
    assert saida["unidades"][0]["telefone"] == "(11) 4555-1234"
    assert "território" in saida["aviso"]
    assert saida["fonte"].startswith("MDS")


# CREAS: o MDS às vezes devolve cada campo como lista; a ferramenta entende os dois formatos.
def test_creas_campos_em_lista(falso):
    saida = unidades.buscar_unidade.invoke({"tipo": "creas", "municipio": "Mauá", "uf": "SP"})
    assert saida["unidades"][0] == {"nome": "CREAS MAUA", "endereco": "AVENIDA DO CREAS, 300",
                                    "bairro": "CENTRO", "telefone": "(11) 4555-7777"}


# O modelo às vezes manda o CEP no campo da cidade: a ferramenta entende mesmo assim.
def test_cep_no_lugar_da_cidade(falso):
    assert unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "09321090"})["municipio"] == "Mauá/SP"


# Entradas erradas viram avisos claros, sem inventar nada.
def test_entradas_invalidas(falso):
    assert "erro" in unidades.buscar_unidade.invoke({"tipo": "UBS", "cep": "09321090"})
    assert "erro" in unidades.buscar_unidade.invoke({"tipo": "CAPS", "cep": "99999-999"})
    assert "erro" in unidades.buscar_unidade.invoke({"tipo": "CAPS"})
    assert "erro" in unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "Atlântida", "uf": "SP"})


# Se o MDS cair, a ferramenta indica o mapa oficial (MOPS) em vez de quebrar.
def test_mds_fora_do_ar_indica_alternativa(falso, monkeypatch):
    original = unidades.get_json

    def mds_quebrado(url, params=None):
        if "sagi" in url:
            raise ValueError("resposta não é JSON")
        return original(url, params)
    monkeypatch.setattr(unidades, "get_json", mds_quebrado)
    saida = unidades.buscar_unidade.invoke({"tipo": "CRAS", "cep": "09321090"})
    assert "erro" in saida and "mops" in saida["alternativa"]


# Se a internet cair, a ferramenta devolve {"erro": ...} em vez de quebrar.
def test_ferramenta_nao_quebra_se_api_falhar(falso, monkeypatch):
    def sem_internet(*a, **k):
        raise ConnectionError("sem internet")
    monkeypatch.setattr(unidades, "get_json", sem_internet)
    unidades._municipios_da_uf.cache_clear()
    assert "erro" in unidades.buscar_unidade.invoke({"tipo": "CAPS", "municipio": "Mauá", "uf": "SP"})


# O modelo pede a ferramenta, recebe o dado e responde com ele, citando a fonte.
def test_loop_pede_ferramenta_e_responde_com_o_dado(falso):
    falso.ferramenta = "buscar_unidade"
    saida = grafo.executar("Onde tem CAPS em Mauá?", sessao="c1")
    assert falso.chamadas == ["tool:buscar_unidade", "resposta"]
    assert "4555-0000" in saida["resposta"]
    assert saida["fontes"] == ["CNES / Ministério da Saúde"]


def test_guardrail_limita_as_voltas(falso, monkeypatch):
    """Com limite de 1 passo, o agente pede a ferramenta e o código o interrompe."""
    monkeypatch.setattr(settings, "max_passos_agente", 1)
    agente = criar_agente("teste", "sistema", unidades.FERRAMENTAS_PASI)
    saida = agente.invoke({"messages": [HumanMessage("CAPS em Mauá?")]})
    assert "poucos passos" in saida["messages"][-1].content


def test_nome_de_ferramenta_inventado_tenta_de_novo(falso, monkeypatch):
    """Simula o erro real do Groq: 'attempted to call tool ... which was not in request.tools'."""
    original = falso.invoke
    falhas = {"n": 0}

    def invoke_com_erro(self, mensagens, config=None):
        if falhas["n"] == 0 and getattr(self, "_ferramentas", None):
            falhas["n"] += 1
            raise RuntimeError("Error code: 400 - tool call validation failed: attempted to call tool 'busca_unidade'")
        return original.__func__(self, mensagens, config)

    monkeypatch.setattr(type(falso), "invoke", invoke_com_erro)
    agente = criar_agente("teste", "sistema", unidades.FERRAMENTAS_PASI)
    saida = agente.invoke({"messages": [HumanMessage("CAPS em Mauá?")]})
    assert falhas["n"] == 1
    assert "tool:buscar_unidade" in falso.chamadas
    assert saida["messages"][-1].content.startswith("resposta de teste")
