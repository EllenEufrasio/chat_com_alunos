# PASIBot

Assistente do [PASI](https://pasi-landing-page.onrender.com) (Plataforma de Atendimento de Sistemas Integrados), projeto de TCC da Fatec Mauá. Ele orienta sobre os serviços públicos de assistência social e saúde mental (CRAS, CREAS e CAPS), ajuda a pessoa a entender qual procurar e encontra a unidade mais perto dela. Este projeto está sendo desenvolvido passo a passo como parte das aulas.

## Etapa atual

Na Aula 4, o PASIBot virou um **agente com ferramentas**: em vez de inventar endereços, ele consulta dados reais.

| Ferramenta | O que busca | Fonte |
|---|---|---|
| `buscar_caps` | CAPS de uma cidade ou perto de um CEP | CNES / Ministério da Saúde (API pública, sem token) |
| `buscar_cras_creas` | CRAS ou CREAS de uma cidade ou perto de um CEP | Cadastro do SUAS (MDS). Enquanto o MDS estiver fora do ar, usa a cópia do Censo SUAS 2019 em `app/data/` e avisa que pode estar desatualizada |

Para testar as ferramentas sozinhas, sem o LLM:

```powershell
python -m app.tools.unidades
```

Próxima etapa (Aula 5, RAG): textos oficiais do gov.br na pasta `documentos/`, explicando o que é cada serviço, quem pode ser atendido e como acessar.

## Requisitos

- Python 3.12
- Uma chave de API da Groq

## Como configurar no Windows

Abra o projeto no VS Code e, no terminal integrado, confirme que está na pasta principal `PASIbot`. Execute os comandos abaixo, um de cada vez:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Depois, abra o arquivo `.env` no VS Code e preencha `GROQ_API_KEY` com sua chave da Groq. Não compartilhe essa chave e não a coloque neste README.

## Como executar

Com o ambiente virtual ativado e o `.env` configurado, rode no terminal integrado:

```powershell
python -m scripts.chat_terminal
```

Digite `sair` para encerrar a conversa.

## Como executar os testes

Com o ambiente virtual ativado, rode:

```powershell
pytest -v
```

## Links do projeto

| O quê | Link |
|---|---|
| Chat publicado (Streamlit Cloud) | https://pasi-chatbot.streamlit.app/ |
| API publicada (Render) | https://finbot-api-rpj9.onrender.com |
| Documentação da API | https://finbot-api-rpj9.onrender.com/docs |

No plano gratuito, a API "dorme" depois de um tempo sem uso: a primeira pergunta pode demorar cerca de 1 minuto.

## Segurança

O arquivo `.env` contém chaves privadas e não deve ser enviado ao GitHub. O arquivo `.env.example` contém apenas o modelo das configurações e pode ser publicado.

## Próximas etapas

Este projeto será ampliado nas aulas seguintes. O link do aplicativo publicado será acrescentado aqui quando ele estiver disponível.
