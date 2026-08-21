#!/usr/bin/env python3
"""Exclui todas as aulas cujo título começa com "[TESTE]" (dados pré-existentes de teste)."""
from database import supabase_admin


def excluir_conteudos(aula_id: str):
    ids_conteudo = [
        c["id"]
        for c in (
            supabase_admin.table("aulas_conteudo").select("id").eq("aula_id", aula_id).execute().data or []
        )
    ]
    if ids_conteudo:
        supabase_admin.table("aulas_texto").delete().in_("aulas_conteudo_id", ids_conteudo).execute()
        supabase_admin.table("aulas_video").delete().in_("aulas_conteudo_id", ids_conteudo).execute()
        supabase_admin.table("aulas_conteudo").delete().in_("id", ids_conteudo).execute()


def main():
    aulas = (
        supabase_admin.table("aulas")
        .select("id, titulo")
        .ilike("titulo", "[TESTE]%")
        .execute()
        .data
        or []
    )
    print(f"Aulas [TESTE] encontradas: {len(aulas)}")

    excluidas = 0
    falhas = []
    for aula in aulas:
        try:
            supabase_admin.table("conceitos_aula").delete().eq("aula_id", aula["id"]).execute()
            excluir_conteudos(aula["id"])
            supabase_admin.table("aulas").delete().eq("id", aula["id"]).execute()
            excluidas += 1
        except Exception as erro:
            falhas.append((aula["titulo"], str(erro)))

    print(f"\nConcluído. {excluidas}/{len(aulas)} aulas excluídas.")
    if falhas:
        print(f"{len(falhas)} falhas:")
        for titulo, erro in falhas:
            print(f"  - {titulo}: {erro}")


if __name__ == "__main__":
    main()
