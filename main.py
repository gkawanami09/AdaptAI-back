from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, usuarios, materias, questoes
from routers.admin import materias as admin_materias
from routers.admin import topicos as admin_topicos

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(admin_materias.router)
app.include_router(admin_topicos.router)
# app.include_router(materias.router)
# app.include_router(questoes.router)

@app.get("/")
def home():
    return {"mensagem" : "funcionado"} #colocar a rota do react