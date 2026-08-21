#!/usr/bin/env python3
"""
Corrige a UNIDADE de aulas_conteudo.duracao para minutos, que é o que o resto
do app espera (routers/aula_visualizacao.py soma duracao direto e chama de
"duracao_min", sem dividir por 60).

- Vídeos: o script corrigir_duracao.py acabou de gravar segundos reais do
  YouTube em todos os 148 conteudos de vídeo -> converte todos para minutos
  (segundos // 60, mínimo 1). Isso corrige tanto os que eu criei quanto
  qualquer aula pré-existente, porque agora o valor é o tempo real do vídeo.
- Textos: só corrige os que EU criei (valores >= 100, que eram meus
  placeholders em "pseudo-segundos": 300/480/600/900). Textos pré-existentes
  com valores pequenos (5, 20) já estavam em minutos e ficam intactos.
"""
from database import supabase_admin


def main():
    tipos = supabase_admin.table("aulas_tipos").select("id, nome").execute().data
    id_video = next(t["id"] for t in tipos if t["nome"] == "video")
    id_texto = next(t["id"] for t in tipos if t["nome"] == "texto")

    videos = (
        supabase_admin.table("aulas_conteudo")
        .select("id, duracao")
        .eq("id_tipo", id_video)
        .execute()
        .data
        or []
    )
    corrigidos_video = 0
    for v in videos:
        nova = max(1, round(v["duracao"] / 60))
        if nova != v["duracao"]:
            supabase_admin.table("aulas_conteudo").update({"duracao": nova}).eq("id", v["id"]).execute()
            corrigidos_video += 1

    textos = (
        supabase_admin.table("aulas_conteudo")
        .select("id, duracao")
        .eq("id_tipo", id_texto)
        .execute()
        .data
        or []
    )
    corrigidos_texto = 0
    for t in textos:
        if t["duracao"] >= 100:
            nova = max(1, round(t["duracao"] / 60))
            supabase_admin.table("aulas_conteudo").update({"duracao": nova}).eq("id", t["id"]).execute()
            corrigidos_texto += 1

    print(f"Vídeos corrigidos (segundos -> minutos): {corrigidos_video}/{len(videos)}")
    print(f"Textos corrigidos (pseudo-segundos -> minutos): {corrigidos_texto}/{len(textos)}")


if __name__ == "__main__":
    main()
