#!/usr/bin/env python3
"""
Busca a duração real de cada vídeo (campo lengthSeconds do player do YouTube,
embutido no HTML da página) e corrige aulas_conteudo.duracao no banco.
Não precisa de chave de API do YouTube.
"""
import re
import time
import urllib.request

from database import supabase_admin

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def duracao_real(video_link: str) -> int | None:
    match = re.search(r"[?&]v=([\w-]{11})", video_link)
    if not match:
        return None
    video_id = match.group(1)
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'"lengthSeconds":"(\d+)"', html)
        return int(m.group(1)) if m else None
    except Exception as erro:
        print(f"  erro ao buscar {video_id}: {erro}")
        return None


def main():
    tipos = supabase_admin.table("aulas_tipos").select("id, nome").execute().data
    id_video = next(t["id"] for t in tipos if t["nome"] == "video")

    conteudos = (
        supabase_admin.table("aulas_conteudo")
        .select("id, duracao")
        .eq("id_tipo", id_video)
        .execute()
        .data
        or []
    )
    print(f"Conteúdos de vídeo: {len(conteudos)}")

    videos = (
        supabase_admin.table("aulas_video")
        .select("aulas_conteudo_id, video_link, titulo")
        .execute()
        .data
        or []
    )
    video_por_conteudo = {v["aulas_conteudo_id"]: v for v in videos}

    cache_por_link = {}
    corrigidos = 0
    falhas = []

    for i, conteudo in enumerate(conteudos, 1):
        video = video_por_conteudo.get(conteudo["id"])
        if not video or not video.get("video_link"):
            continue

        link = video["video_link"]
        if link not in cache_por_link:
            cache_por_link[link] = duracao_real(link)
            time.sleep(0.15)

        segundos = cache_por_link[link]
        if segundos is None:
            falhas.append(video.get("titulo", link))
            continue

        if conteudo["duracao"] != segundos:
            supabase_admin.table("aulas_conteudo").update({"duracao": segundos}).eq(
                "id", conteudo["id"]
            ).execute()
            corrigidos += 1

        if i % 20 == 0:
            print(f"  {i}/{len(conteudos)} processados...")

    print(f"\nConcluído. {corrigidos} durações corrigidas de {len(conteudos)} conteúdos de vídeo.")
    if falhas:
        print(f"{len(falhas)} falhas ao obter duração:")
        for f in falhas:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
