r"""
Utilidades de matching de texto (Core puro) — El Prospector.

REGLA DE ARQUITECTURA: pertenece al Core. Solo usa la librería estándar
(`re`). No importa nada externo (requests, groq, bs4, etc.). Cualquier
adaptador que necesite comparar nombres/frases contra un texto libre reusa
estas funciones en vez de reimplementar su propio regex.

Diseño del matching:
    - Por PALABRA/FRASE COMPLETA, case-insensitive, con soporte de tildes
      (Unicode es el modo por defecto de `re` en Python 3).
    - El needle se escapa con re.escape para que caracteres no alfanuméricos
      (espacios, puntos, guiones) se traten literalmente — esto permite
      needles multi-palabra ("it services", "fábrica de software").
    - Los límites usan lookarounds `(?<!\w)` / `(?!\w)` en vez de `\b`:
      `\b` depende de que el borde sea alfanumérico y falla con needles que
      empiezan/terminan en caracteres no `\w`. Los lookarounds solo exigen
      que el carácter adyacente NO sea alfanumérico (o que sea el borde del
      texto), evitando falsos positivos tipo "solutions" dentro de
      "EcoSolutions".
"""

from __future__ import annotations

import re
from typing import Iterable


def contiene_palabra_completa(texto: str, palabra: str) -> bool:
    """
    True si `palabra` aparece como palabra/frase completa dentro de `texto`
    (case-insensitive, con tildes). Si `texto` o `palabra` son vacíos o None,
    retorna False.

    Uso real (secop_adapter): verificar que el `proveedor_adjudicado` de un
    contrato SECOP realmente contenga el nombre de la empresa buscada como
    palabra completa, filtrando los falsos positivos fuzzy que trae `$q`.
    """
    if not texto or not palabra:
        return False
    patron = r"(?<!\w)" + re.escape(palabra) + r"(?!\w)"
    return re.search(patron, texto, re.IGNORECASE) is not None


def cualquiera_como_palabra_completa(texto: str, palabras: Iterable[str]) -> bool:
    """
    True si CUALQUIERA de las cadenas en `palabras` aparece como palabra
    completa dentro de `texto` (reusa contiene_palabra_completa).

    Si `texto` es vacío/None o `palabras` es vacío/None, retorna False.

    Uso real (sandbox_tbbc_real): heurística barata de "vendor de TI" sobre
    el nombre público de la empresa candidata.
    """
    if not texto or not palabras:
        return False
    return any(contiene_palabra_completa(texto, palabra) for palabra in palabras)
