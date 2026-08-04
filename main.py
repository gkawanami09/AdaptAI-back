from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS
from routers import auth, usuarios, materias, questoes, onboarding, dashboard, plano_estudos, biblioteca_aulas, aula_visualizacao
from routers.admin import materias as admin_materias
from routers.admin import topicos as admin_topicos
from routers.admin import aulas as admin_aulas
from routers.admin import questoes as admin_questoes
from routers.admin import tipos_prova as admin_tipos_prova
from routers.admin import listas_questoes as admin_listas_questoes
from routers.admin import relatorios as admin_relatorios
from routers.admin import configuracoes as admin_configuracoes
from routers.admin import usuarios as admin_usuarios
from routers.admin import dashboard as admin_dashboard

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(onboarding.router)
app.include_router(admin_materias.router)
app.include_router(admin_topicos.router)
app.include_router(admin_aulas.router)
app.include_router(admin_questoes.router)
app.include_router(admin_tipos_prova.router)
app.include_router(admin_listas_questoes.router)
app.include_router(admin_relatorios.router)
app.include_router(admin_configuracoes.router)
app.include_router(admin_usuarios.router)
app.include_router(admin_dashboard.router)
app.include_router(dashboard.router)
app.include_router(plano_estudos.router)
app.include_router(aula_visualizacao.router)
app.include_router(biblioteca_aulas.router)
# app.include_router(materias.router)
# app.include_router(questoes.router)

@app.get("/")
def home():
    return {"mensagem" : "funcionado"} #colocar a rota do react


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
