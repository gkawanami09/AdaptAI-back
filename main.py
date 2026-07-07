from fastapi import FastAPI
from routers import auth, usuarios, materias, questoes

app = FastAPI()

app.include_router(auth.router)
# app.include_router(usuarios.router)
# app.include_router(materias.router)
# app.include_router(questoes.router)

@app.get("/")
def home():
    return {"mensagem" : "funcionado"} #colocar a rota do react