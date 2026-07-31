from fastapi import APIRouter, HTTPException, Depends, Query, Response
from database import supabase_admin
from utils.autenticacao import exigir_administrador
from datetime import datetime, timedelta, timezone

router = APIRouter(
    prefix='/admin/relatorios',
    tags=['Admin - Relatórios'],
    dependencies=[Depends(exigir_administrador)]
)

PERIODO_DIAS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "12m": 365,
}


# Calculates the interval (start_date, end_date, previous_start_date) for the given period
def calcular_intervalo(periodo: str):
    dias = PERIODO_DIAS.get(periodo, 30)
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=dias)
    inicio_anterior = inicio - timedelta(days=dias)
    return inicio, agora, inicio_anterior


@router.get('')
def obter_relatorios(
    periodo: str = Query(default="30d"),
):
    try:
        if periodo not in PERIODO_DIAS:
            raise HTTPException(
                status_code=400,
                detail="Período inválido"
            )

        inicio, agora, inicio_anterior = calcular_intervalo(periodo)

        # TODO: user and answer KPIs depend on user/answer tables that don't exist yet
        kpis = {
            "total_usuarios": 0,
            "total_usuarios_variacao_pct": 0,
            "questoes_respondidas": 0,
            "questoes_respondidas_variacao_pct": 0,
            "listas_concluidas": 0,
            "listas_concluidas_variacao_pct": 0,
            "taxa_media_acerto_pct": 0,
            "taxa_media_acerto_variacao_pct": 0,
        }

        # Questões por dia (criação real de questões no período)
        questoes_periodo = (
            supabase_admin.table("questoes")
            .select("criado_em")
            .gte("criado_em", inicio.isoformat())
            .execute()
            .data or []
        )

        contagem_por_dia: dict[str, int] = {}
        for questao in questoes_periodo:
            data_str = questao["criado_em"][:10]
            contagem_por_dia[data_str] = contagem_por_dia.get(data_str, 0) + 1

        questoes_por_dia = [
            {"data": datetime.fromisoformat(data_str).strftime("%d/%m"), "total": total}
            for data_str, total in sorted(contagem_por_dia.items())
        ]

        # Distribuição por dificuldade
        todas_questoes = (
            supabase_admin.table("questoes")
            .select("dificuldade")
            .execute()
            .data or []
        )

        total_questoes = len(todas_questoes)
        contagem_dificuldade = {"facil": 0, "medio": 0, "dificil": 0}
        for questao in todas_questoes:
            if questao["dificuldade"] in contagem_dificuldade:
                contagem_dificuldade[questao["dificuldade"]] += 1

        distribuicao_dificuldade = [
            {
                "dificuldade": dificuldade,
                "total": total,
                "percentual": round((total / total_questoes) * 100, 1) if total_questoes else 0,
            }
            for dificuldade, total in contagem_dificuldade.items()
        ]

        # Matérias mais estudadas (proporção de questões por matéria)
        materias = (
            supabase_admin.table("materias")
            .select("id, nome")
            .execute()
            .data or []
        )

        questoes_materia = (
            supabase_admin.table("questoes")
            .select("materia_id")
            .execute()
            .data or []
        )

        contagem_materia: dict[str, int] = {}
        for questao in questoes_materia:
            materia_id = questao["materia_id"]
            contagem_materia[materia_id] = contagem_materia.get(materia_id, 0) + 1

        total_questoes_materia = len(questoes_materia)
        materias_mais_estudadas = sorted(
            [
                {
                    "materia_id": materia["id"],
                    "nome": materia["nome"],
                    "percentual": round((contagem_materia.get(materia["id"], 0) / total_questoes_materia) * 100, 1) if total_questoes_materia else 0,
                }
                for materia in materias
                if contagem_materia.get(materia["id"], 0) > 0
            ],
            key=lambda item: item["percentual"],
            reverse=True,
        )

        # Tipos de prova (proporção de questões por tipo de prova)
        tipos_prova_lista = (
            supabase_admin.table("tipos_prova")
            .select("id, nome")
            .execute()
            .data or []
        )

        questoes_tipo_prova = (
            supabase_admin.table("questoes")
            .select("tipo_prova_id")
            .execute()
            .data or []
        )

        contagem_tipo_prova: dict[str, int] = {}
        for questao in questoes_tipo_prova:
            tipo_prova_id = questao["tipo_prova_id"]
            if tipo_prova_id:
                contagem_tipo_prova[tipo_prova_id] = contagem_tipo_prova.get(tipo_prova_id, 0) + 1

        total_questoes_tipo_prova = sum(contagem_tipo_prova.values())
        tipos_prova = sorted(
            [
                {
                    "tipo_prova_id": tipo["id"],
                    "nome": tipo["nome"],
                    "percentual": round((contagem_tipo_prova.get(tipo["id"], 0) / total_questoes_tipo_prova) * 100, 1) if total_questoes_tipo_prova else 0,
                }
                for tipo in tipos_prova_lista
                if contagem_tipo_prova.get(tipo["id"], 0) > 0
            ],
            key=lambda item: item["percentual"],
            reverse=True,
        )

        # Atividades recentes (baseadas na criação de questões e listas)
        atividades_recentes = []

        questoes_recentes = (
            supabase_admin.table("questoes")
            .select("id, enunciado, criado_em")
            .order("criado_em", desc=True)
            .limit(10)
            .execute()
            .data or []
        )

        for questao in questoes_recentes:
            atividades_recentes.append({
                "id": questao["id"],
                "tipo": "questao_criada",
                "titulo": "Nova questão criada",
                "descricao": questao["enunciado"][:80],
                "criado_em": questao["criado_em"],
            })

        listas_recentes = (
            supabase_admin.table("listas_questoes")
            .select("id, titulo, criado_em")
            .order("criado_em", desc=True)
            .limit(10)
            .execute()
            .data or []
        )

        for lista in listas_recentes:
            atividades_recentes.append({
                "id": lista["id"],
                "tipo": "lista_publicada",
                "titulo": "Nova lista publicada",
                "descricao": lista["titulo"],
                "criado_em": lista["criado_em"],
            })

        atividades_recentes = sorted(
            atividades_recentes,
            key=lambda atividade: atividade["criado_em"],
            reverse=True,
        )[:10]

        return {
            "sucesso": True,
            "kpis": kpis,
            "questoes_por_dia": questoes_por_dia,
            "distribuicao_dificuldade": distribuicao_dificuldade,
            "materias_mais_estudadas": materias_mais_estudadas,
            "tipos_prova": tipos_prova,
            "atividades_recentes": atividades_recentes,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter relatórios: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter relatórios"
        )


@router.get('/ranking-conteudos')
def obter_ranking_conteudos(
    periodo: str = Query(default="30d"),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=5, ge=1, le=50),
):
    try:
        if periodo not in PERIODO_DIAS:
            raise HTTPException(
                status_code=400,
                detail="Período inválido"
            )

        aulas = (
            supabase_admin.table("aulas")
            .select("id, titulo, materia_id")
            .execute()
            .data or []
        )

        materias = (
            supabase_admin.table("materias")
            .select("id, nome")
            .execute()
            .data or []
        )
        nomes_materias = {materia["id"]: materia["nome"] for materia in materias}

        questoes = (
            supabase_admin.table("questoes")
            .select("aula_id, dificuldade")
            .execute()
            .data or []
        )

        contagem_por_aula: dict[str, int] = {}
        for questao in questoes:
            aula_id = questao["aula_id"]
            if aula_id:
                contagem_por_aula[aula_id] = contagem_por_aula.get(aula_id, 0) + 1

        # TODO: accuracy rate, average time and total accesses depend on a response/access table that doesn't exist yet
        ranking_completo = sorted(
            [
                {
                    "materia_id": aula["materia_id"],
                    "materia": nomes_materias.get(aula["materia_id"], ""),
                    "aula_id": aula["id"],
                    "aula": aula["titulo"],
                    "total_questoes": contagem_por_aula.get(aula["id"], 0),
                    "taxa_acerto_pct": 0,
                    "tempo_medio_seg": 0,
                    "total_acessos": 0,
                }
                for aula in aulas
                if contagem_por_aula.get(aula["id"], 0) > 0
            ],
            key=lambda item: item["total_acessos"],
            reverse=True,
        )

        total_registros = len(ranking_completo)
        total_paginas = max(1, (total_registros + limite - 1) // limite)

        inicio = (pagina - 1) * limite
        fim = inicio + limite

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": total_paginas,
            "total_registros": total_registros,
            "ranking": ranking_completo[inicio:fim],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter ranking de conteúdos: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter ranking de conteúdos"
        )


@router.get('/exportar')
def exportar_relatorio(
    periodo: str = Query(default="30d"),
):
    try:
        if periodo not in PERIODO_DIAS:
            raise HTTPException(
                status_code=400,
                detail="Período inválido"
            )

        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        dados = obter_relatorios(periodo=periodo)

        estilo_cabecalho = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        arquivo = BytesIO()
        documento = SimpleDocTemplate(arquivo, pagesize=A4)
        estilos = getSampleStyleSheet()

        elementos = [
            Paragraph("Relatório AdaptAI", estilos["Title"]),
            Paragraph(f"Período: {periodo}", estilos["Normal"]),
            Spacer(1, 16),
        ]

        elementos.append(Paragraph("Indicadores Gerais", estilos["Heading2"]))
        kpis = dados["kpis"]
        linhas_kpis = [
            ["Indicador", "Valor", "Variação"],
            ["Total de usuários", kpis["total_usuarios"], f"{kpis['total_usuarios_variacao_pct']}%"],
            ["Questões respondidas", kpis["questoes_respondidas"], f"{kpis['questoes_respondidas_variacao_pct']}%"],
            ["Listas concluídas", kpis["listas_concluidas"], f"{kpis['listas_concluidas_variacao_pct']}%"],
            ["Taxa média de acerto", f"{kpis['taxa_media_acerto_pct']}%", f"{kpis['taxa_media_acerto_variacao_pct']}%"],
        ]
        tabela_kpis = Table(linhas_kpis, colWidths=[7 * cm, 5 * cm, 4 * cm])
        tabela_kpis.setStyle(estilo_cabecalho)
        elementos.append(tabela_kpis)
        elementos.append(Spacer(1, 16))

        elementos.append(Paragraph("Distribuição por Dificuldade", estilos["Heading2"]))
        linhas_dificuldade = [["Dificuldade", "Total", "Percentual"]] + [
            [item["dificuldade"].capitalize(), item["total"], f"{item['percentual']}%"]
            for item in dados["distribuicao_dificuldade"]
        ]
        tabela_dificuldade = Table(linhas_dificuldade, colWidths=[7 * cm, 5 * cm, 4 * cm])
        tabela_dificuldade.setStyle(estilo_cabecalho)
        elementos.append(tabela_dificuldade)
        elementos.append(Spacer(1, 16))

        elementos.append(Paragraph("Matérias Mais Estudadas", estilos["Heading2"]))
        linhas_materias = [["Matéria", "Percentual de Questões"]] + [
            [item["nome"], f"{item['percentual']}%"]
            for item in dados["materias_mais_estudadas"]
        ] or [["Matéria", "Percentual de Questões"]]
        tabela_materias = Table(linhas_materias, colWidths=[9 * cm, 7 * cm])
        tabela_materias.setStyle(estilo_cabecalho)
        elementos.append(tabela_materias)
        elementos.append(Spacer(1, 16))

        elementos.append(Paragraph("Tipos de Prova", estilos["Heading2"]))
        linhas_tipos_prova = [["Tipo de Prova", "Percentual de Questões"]] + [
            [item["nome"], f"{item['percentual']}%"]
            for item in dados["tipos_prova"]
        ] or [["Tipo de Prova", "Percentual de Questões"]]
        tabela_tipos_prova = Table(linhas_tipos_prova, colWidths=[9 * cm, 7 * cm])
        tabela_tipos_prova.setStyle(estilo_cabecalho)
        elementos.append(tabela_tipos_prova)
        elementos.append(Spacer(1, 16))

        elementos.append(Paragraph("Questões Criadas por Dia", estilos["Heading2"]))
        linhas_questoes_dia = [["Data", "Total"]] + [
            [item["data"], item["total"]]
            for item in dados["questoes_por_dia"]
        ] or [["Data", "Total"]]
        tabela_questoes_dia = Table(linhas_questoes_dia, colWidths=[9 * cm, 7 * cm])
        tabela_questoes_dia.setStyle(estilo_cabecalho)
        elementos.append(tabela_questoes_dia)
        elementos.append(Spacer(1, 16))

        elementos.append(Paragraph("Atividades Recentes", estilos["Heading2"]))
        linhas_atividades = [["Título", "Descrição", "Data"]] + [
            [item["titulo"], item["descricao"], item["criado_em"][:10]]
            for item in dados["atividades_recentes"]
        ] or [["Título", "Descrição", "Data"]]
        tabela_atividades = Table(linhas_atividades, colWidths=[5 * cm, 8 * cm, 3 * cm])
        tabela_atividades.setStyle(estilo_cabecalho)
        elementos.append(tabela_atividades)

        documento.build(elementos)
        arquivo.seek(0)

        return Response(
            content=arquivo.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="relatorio-{periodo}.pdf"'
            },
        )

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao exportar relatório: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao exportar relatório"
        )
