# tests/test_aula4.py
"""Aula 4 — ferramenta buscar_unidade (CAPS, CRAS, CREAS) e o loop de tool-calling."""
# A fixture falso também troca as APIs (CNES, MDS, IBGE, ViaCEP, BrasilAPI) por respostas fixas.
from langchain_core.messages import AIMessage, HumanMessage

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


# Se o MDS cair, a ferramenta usa a cópia local do Censo SUAS 2019 e avisa que pode estar desatualizada.
def test_mds_fora_do_ar_usa_copia_local(falso, monkeypatch):
    original = unidades.get_json

    def mds_quebrado(url, params=None):
        if "sagi" in url:
            raise ValueError("resposta não é JSON")
        return original(url, params)
    monkeypatch.setattr(unidades, "get_json", mds_quebrado)
    saida = unidades.buscar_unidade.invoke({"tipo": "CRAS", "cep": "09321090"})
    assert saida["fonte"] == unidades.FONTE_SUAS_LOCAL
    assert saida["municipio"] == "Mauá/SP"
    assert saida["unidades"] and all("CRAS" in u["nome"] for u in saida["unidades"])
    assert "2019" in saida["aviso"]
    # o mais perto do CEP de teste vem primeiro
    distancias = [u["distancia_km"] for u in saida["unidades"]]
    assert distancias == sorted(distancias)


# Depois de uma falha, o MDS fica 10 min sem ser chamado (cada tentativa demora).
def test_mds_fora_do_ar_nao_e_chamado_de_novo(falso, monkeypatch):
    chamadas = {"mds": 0}
    original = unidades.get_json

    def mds_quebrado(url, params=None):
        if "sagi" in url:
            chamadas["mds"] += 1
            raise ValueError("resposta não é JSON")
        return original(url, params)
    monkeypatch.setattr(unidades, "get_json", mds_quebrado)
    unidades.buscar_unidade.invoke({"tipo": "CRAS", "cep": "09321090"})
    unidades.buscar_unidade.invoke({"tipo": "CREAS", "cep": "09321090"})
    assert chamadas["mds"] == 1


# Sem MDS e sem a cidade na cópia local: erro claro com alternativa, sem inventar endereço.
def test_mds_fora_e_cidade_fora_da_copia(falso, monkeypatch):
    def mds_quebrado(url, params=None):
        raise ValueError("resposta não é JSON")
    monkeypatch.setattr(unidades, "_suas_do_municipio", mds_quebrado)
    monkeypatch.setattr(unidades, "_base_suas_local", lambda: {})
    saida = unidades.buscar_unidade.invoke({"tipo": "CREAS", "municipio": "Mauá", "uf": "SP"})
    assert "erro" in saida and "prefeitura" in saida["alternativa"]


# A cópia local corrige acentos e tem as unidades de Mauá.
def test_copia_local_tem_maua():
    unidades._base_suas_local.cache_clear()
    cras = unidades._suas_da_reserva(352940, "CRAS")
    creas = unidades._suas_da_reserva(352940, "CREAS")
    assert len(cras) >= 5 and len(creas) >= 1
    assert any(u["endereco"] == "Rua AVARÉ, 62" for u in creas)
    assert all(u["_lat"] and u["_lon"] for u in cras + creas)


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
    """Com limite de 1 passo, o agente pede a ferramenta, o código barra e ele responde SEM ferramentas."""
    monkeypatch.setattr(settings, "max_passos_agente", 1)
    agente = criar_agente("teste", "sistema", unidades.FERRAMENTAS_PASI)
    saida = agente.invoke({"messages": [HumanMessage("CAPS em Mauá?")]})
    assert falso.chamadas == ["tool:buscar_unidade", "resposta"]
    assert saida["messages"][-1].content.startswith("resposta de teste")


def test_pedido_repetido_vai_para_a_resposta_final(falso, monkeypatch):
    """Caso real: o modelo pedia a mesma busca de novo até estourar o limite."""
    original = falso.invoke

    def sempre_pede(self, mensagens, config=None):
        if getattr(self, "_ferramentas", None):
            self._registrar("tool:buscar_unidade", mensagens)
            return AIMessage(content="", tool_calls=[{"name": "buscar_unidade",
                                                      "args": {"tipo": "CAPS", "municipio": "Mauá", "uf": "SP"},
                                                      "id": f"call_{len(self._dono.chamadas)}"}])
        return original.__func__(self, mensagens, config)

    monkeypatch.setattr(type(falso), "invoke", sempre_pede)
    agente = criar_agente("teste", "sistema", unidades.FERRAMENTAS_PASI)
    saida = agente.invoke({"messages": [HumanMessage("CAPS em Mauá?")]})
    assert falso.chamadas == ["tool:buscar_unidade", "tool:buscar_unidade", "resposta"]
    assert saida["messages"][-1].content.startswith("resposta de teste")


def test_limite_conta_so_a_pergunta_atual(falso, monkeypatch):
    """Caso real: o contador de voltas era salvo na conversa e bloqueava as perguntas seguintes."""
    monkeypatch.setattr(settings, "max_passos_agente", 2)
    falso.ferramenta = "buscar_unidade"
    grafo.executar("Onde tem CAPS em Mauá?", sessao="c-limite")
    grafo.executar("E outro CAPS em Mauá?", sessao="c-limite")
    assert falso.chamadas.count("tool:buscar_unidade") == 2


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
