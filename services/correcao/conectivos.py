CONECTIVOS_POR_CATEGORIA: dict[str, list[str]] = {
    "aditivos": [
        "além disso", "ademais", "e", "não só", "mas também", "bem como",
        "outrossim", "assim como", "não apenas",
    ],
    "adversativos": [
        "mas", "porém", "contudo", "todavia", "entretanto", "no entanto",
        "apesar de", "ainda que", "embora", "por outro lado",
    ],
    "conclusivos": [
        "portanto", "logo", "assim", "dessa forma", "desse modo",
        "por conseguinte", "consequentemente", "sendo assim", "em suma",
    ],
    "explicativos": [
        "pois", "porque", "visto que", "já que", "uma vez que",
        "isto é", "ou seja", "por exemplo",
    ],
    "temporais": [
        "enquanto", "quando", "logo após", "em seguida", "posteriormente",
        "atualmente", "primeiramente", "por fim", "finalmente",
    ],
    "condicionais": [
        "caso", "se", "a menos que", "desde que",
    ],
}

CONECTIVOS: list[str] = sorted(
    {conectivo for lista in CONECTIVOS_POR_CATEGORIA.values() for conectivo in lista},
    key=len,
    reverse=True,
)
