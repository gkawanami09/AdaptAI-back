"""Telemetria de desempenho em memória.

Mantém uma janela deslizante de amostras (latência/erro) por rota e por
provider de IA, para alimentar o painel de monitoramento do admin
(routers/admin/dashboard.py). Não persiste em banco — é telemetria de
processo, reiniciada a cada deploy, o que é aceitável para os
indicadores de saúde que expõe (latência recente, taxa de erro recente).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from statistics import mean
from threading import Lock

JANELA_MAXIMA = 500


@dataclass
class _SerieAmostras:
    amostras: deque = field(default_factory=lambda: deque(maxlen=JANELA_MAXIMA))
    erros: int = 0
    total: int = 0

    def registrar(self, duracao_ms: float, sucesso: bool) -> None:
        self.amostras.append(duracao_ms)
        self.total += 1
        if not sucesso:
            self.erros += 1

    def resumo(self) -> dict:
        amostras = list(self.amostras)
        return {
            "amostras": len(amostras),
            "latencia_media_ms": round(mean(amostras), 1) if amostras else 0,
            "latencia_p95_ms": round(_percentil(amostras, 95), 1) if amostras else 0,
            "total_chamadas": self.total,
            "total_erros": self.erros,
            "taxa_erro_pct": round((self.erros / self.total) * 100, 1) if self.total else 0,
        }


def _percentil(valores: list[float], percentil: int) -> float:
    if not valores:
        return 0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(len(ordenados) * percentil / 100))
    return ordenados[indice]


class MonitorDesempenho:
    """Coletor thread-safe de métricas de requests HTTP e chamadas de IA."""

    def __init__(self) -> None:
        self._lock = Lock()
        # Chave (metodo, rota) — a mesma rota pode ter métodos diferentes
        # com perfis de latência/erro bem diferentes (GET de leitura vs.
        # POST que grava), então não faz sentido agregar os dois juntos.
        self._rotas: dict[tuple[str, str], _SerieAmostras] = {}
        self._ia: dict[str, _SerieAmostras] = {}
        self._inicio = time.time()

    def registrar_request(self, metodo: str, rota: str, duracao_ms: float, status_code: int) -> None:
        with self._lock:
            serie = self._rotas.setdefault((metodo, rota), _SerieAmostras())
            serie.registrar(duracao_ms, sucesso=status_code < 500)

    def registrar_chamada_ia(self, operacao: str, duracao_ms: float, sucesso: bool) -> None:
        with self._lock:
            serie = self._ia.setdefault(operacao, _SerieAmostras())
            serie.registrar(duracao_ms, sucesso=sucesso)

    def resumo(self) -> dict:
        with self._lock:
            return {
                "uptime_seg": round(time.time() - self._inicio),
                "rotas": [
                    {
                        "rota": rota,
                        "metodo": metodo,
                        "latencia_media_ms": serie.resumo()["latencia_media_ms"],
                        "taxa_erro_pct": serie.resumo()["taxa_erro_pct"],
                        "total_requisicoes": serie.total,
                    }
                    for (metodo, rota), serie in self._rotas.items()
                ],
                "operacoes_ia": [
                    {
                        "operacao": operacao,
                        "latencia_media_ms": serie.resumo()["latencia_media_ms"],
                        "taxa_erro_pct": serie.resumo()["taxa_erro_pct"],
                        "total_chamadas": serie.total,
                    }
                    for operacao, serie in self._ia.items()
                ],
            }


monitor = MonitorDesempenho()
