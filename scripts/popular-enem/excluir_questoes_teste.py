#!/usr/bin/env python3
"""Exclui questões e listas de questões de teste, em cascata na ordem correta."""
from database import supabase_admin


def main():
    questoes_teste = (
        supabase_admin.table("questoes").select("id").ilike("enunciado", "%teste%").execute().data or []
    )
    listas_teste = supabase_admin.table("listas_questoes").select("id").execute().data or []

    q_ids = [q["id"] for q in questoes_teste]
    l_ids = [l["id"] for l in listas_teste]

    print(f"Questões de teste: {len(q_ids)}")
    print(f"Listas de teste: {len(l_ids)}")

    if l_ids:
        r = supabase_admin.table("respostas_lista_questoes_aluno").delete().in_("lista_questoes_id", l_ids).execute()
        print(f"  respostas_lista_questoes_aluno (por lista) removidas: {len(r.data or [])}")

        r = supabase_admin.table("progresso_lista_questoes_aluno").delete().in_("lista_questoes_id", l_ids).execute()
        print(f"  progresso_lista_questoes_aluno removidos: {len(r.data or [])}")

        r = supabase_admin.table("planos_estudo_sessoes").delete().in_("lista_questoes_id", l_ids).execute()
        print(f"  planos_estudo_sessoes (por lista) removidas: {len(r.data or [])}")

        r = supabase_admin.table("itens_lista_questoes").delete().in_("lista_questoes_id", l_ids).execute()
        print(f"  itens_lista_questoes removidos: {len(r.data or [])}")

    if q_ids:
        r = supabase_admin.table("respostas_lista_questoes_aluno").delete().in_("questao_id", q_ids).execute()
        print(f"  respostas_lista_questoes_aluno (por questão) removidas: {len(r.data or [])}")

        r = supabase_admin.table("itens_lista_questoes").delete().in_("questao_id", q_ids).execute()
        print(f"  itens_lista_questoes (por questão, fora das listas de teste) removidos: {len(r.data or [])}")

        # zera alternativa_correta antes de apagar as alternativas (FK)
        supabase_admin.table("questoes").update({"alternativa_correta": None}).in_("id", q_ids).execute()
        r = supabase_admin.table("alternativas_questao").delete().in_("questao_id", q_ids).execute()
        print(f"  alternativas_questao removidas: {len(r.data or [])}")

    if l_ids:
        r = supabase_admin.table("listas_questoes").delete().in_("id", l_ids).execute()
        print(f"  listas_questoes removidas: {len(r.data or [])}")

    if q_ids:
        r = supabase_admin.table("questoes").delete().in_("id", q_ids).execute()
        print(f"  questoes removidas: {len(r.data or [])}")

    print("\nConcluído.")


if __name__ == "__main__":
    main()
