# app/main.py
"""Ponto de entrada da API.

Local:   uvicorn app.main:app --reload        -> http://127.0.0.1:8000/docs
Render:  uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rotas import router

# Cria a aplicação. title e description aparecem no topo da página /docs.
# O uvicorn procura esta variável: "app.main:app" = arquivo app/main.py, variável app.
app = FastAPI(title="PASIBot API", description="Assistente do PASI: CRAS, CREAS e CAPS — FATEC / PLN")
# Libera o navegador da landing page do PASI (e do Vite local) para chamar a API.
# Sem isso, o navegador bloqueia as chamadas feitas a partir de outro domínio (CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pasi-landing-page.onrender.com",
        "http://localhost:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
# Liga as rotas de app/api/rotas.py à aplicação.
app.include_router(router)