#!/usr/bin/env python3
"""
Popula conceitos_aula (checklist de conceitos-chave que aparece na tela de
aula do aluno) para as aulas que têm topico_id mapeado em conceitos_por_topico.py.
Pula aulas que já têm conceito cadastrado (idempotente).
"""
from database import supabase_admin
from conceitos_por_topico import CONCEITOS


def main():
    topicos = (
        supabase_admin.table("topicos")
        .select("topico_id, nome")
        .execute()
        .data
        or []
    )
    nome_por_topico = {t["topico_id"]: t["nome"] for t in topicos}

    aulas = (
        supabase_admin.table("aulas")
        .select("id, titulo, topico_id")
        .execute()
        .data
        or []
    )
    print(f"Total de aulas: {len(aulas)}")

    existentes = (
        supabase_admin.table("conceitos_aula")
        .select("aula_id")
        .execute()
        .data
        or []
    )
    aulas_com_conceito = {c["aula_id"] for c in existentes}
    print(f"Aulas que já têm conceito: {len(aulas_com_conceito)}")

    criados = 0
    sem_topico = 0
    sem_mapa = 0
    ja_tinha = 0

    for aula in aulas:
        if aula["id"] in aulas_com_conceito:
            ja_tinha += 1
            continue

        if not aula["topico_id"]:
            sem_topico += 1
            continue

        nome_topico = nome_por_topico.get(aula["topico_id"])
        conceitos = CONCEITOS.get(nome_topico)
        if not conceitos:
            sem_mapa += 1
            continue

        linhas = [
            {"aula_id": aula["id"], "titulo": titulo, "ordem": indice}
            for indice, titulo in enumerate(conceitos)
        ]
        supabase_admin.table("conceitos_aula").insert(linhas).execute()
        criados += len(linhas)

    print(f"\nConcluído. {criados} conceitos criados.")
    print(f"  Aulas que já tinham conceito (puladas): {ja_tinha}")
    print(f"  Aulas sem tópico (puladas): {sem_topico}")
    print(f"  Aulas com tópico sem mapa de conceitos (puladas): {sem_mapa}")


if __name__ == "__main__":
    main()
