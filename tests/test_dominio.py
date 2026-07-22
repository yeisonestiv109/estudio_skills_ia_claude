"""
Tests del Core puro `src/core/domain/dominio.py`:
    - pais_por_tld: heurística de país por ccTLD (estándar IANA) antes del
      scraping caro (FIX #6, caso Revista Dinero/dinero.com.ve).
    - dominio_base / mismo_dominio_base: comparación de dominio registrable
      (eTLD+1), usada por la verificación de propiedad de org en GitHub
      (FIX #4, anti-colisión de nombre).

Deterministas, sin red, sin LLM.
"""

from __future__ import annotations

import pytest

from src.core.domain.dominio import (
    dominio_base,
    mismo_dominio_base,
    pais_por_tld,
)


class TestPaisPorTld:
    @pytest.mark.parametrize(
        "dominio, esperado",
        [
            # Segundo nivel colombiano inequívoco → CO
            ("empresa.com.co", "CO"),
            ("entidad.gov.co", "CO"),
            ("fundacion.org.co", "CO"),
            ("universidad.edu.co", "CO"),
            ("ejercito.mil.co", "CO"),
            ("red.net.co", "CO"),
            # ccTLD de país inequívoco → su ISO
            ("dinero.com.ve", "VE"),
            ("noticias.ve", "VE"),
            ("empresa.mx", "MX"),
            ("startup.ar", "AR"),
            ("negocio.cl", "CL"),
            ("compania.pe", "PE"),
            ("portal.br", "BR"),
            ("sitio.ec", "EC"),
            ("web.uy", "UY"),
            ("tienda.es", "ES"),
            # .uk mapea a ISO 'GB', no 'UK'
            ("company.co.uk", "GB"),
        ],
    )
    def test_sufijos_inequivocos_devuelven_pais(self, dominio: str, esperado: str):
        assert pais_por_tld(dominio) == esperado

    @pytest.mark.parametrize(
        "dominio",
        [
            "empresa.co",  # .co simple: se vende global, AMBIGUO
            "acme.com",
            "startup.io",
            "x.app",
            "tool.dev",
            "modelo.ai",
            "proyecto.org",
            "servicio.net",
        ],
    )
    def test_gtlds_y_co_simple_son_ambiguos_devuelven_none(self, dominio: str):
        assert pais_por_tld(dominio) is None

    def test_normaliza_esquema_www_y_ruta(self):
        assert pais_por_tld("https://www.Dinero.com.ve/economia") == "VE"

    @pytest.mark.parametrize("valor", ["", "   ", "sinpunto", None])
    def test_entradas_degeneradas_devuelven_none(self, valor):
        assert pais_por_tld(valor) is None  # type: ignore[arg-type]

    def test_no_lanza_para_ninguna_entrada(self):
        for v in ["a.b.c.d.ve", ".", "..", "http://", "co", ".co"]:
            # Solo se exige que no lance y devuelva str|None.
            resultado = pais_por_tld(v)
            assert resultado is None or isinstance(resultado, str)


class TestDominioBase:
    @pytest.mark.parametrize(
        "dominio, esperado",
        [
            ("acme.com", "acme.com"),
            ("https://www.forbes.com/co", "forbes.com"),
            ("forbes.co", "forbes.co"),
            ("blog.acme.com", "acme.com"),
            ("sub.dept.acme.com.co", "acme.com.co"),
            ("empresa.com.co", "empresa.com.co"),
            ("company.co.uk", "company.co.uk"),
            ("user@host.io:8080/path", "host.io"),
        ],
    )
    def test_extrae_dominio_registrable(self, dominio: str, esperado: str):
        assert dominio_base(dominio) == esperado

    @pytest.mark.parametrize("valor", ["", None, "sinpunto", "com.co"])
    def test_entradas_sin_nombre_registrable_devuelven_none(self, valor):
        assert dominio_base(valor) is None  # type: ignore[arg-type]


class TestMismoDominioBase:
    def test_mismo_dominio_ignora_www_esquema_y_ruta(self):
        assert mismo_dominio_base("https://www.acme.com/contacto", "acme.com") is True

    def test_subdominios_distintos_mismo_registrable_coinciden(self):
        assert mismo_dominio_base("blog.acme.com", "shop.acme.com") is True

    def test_colision_forbes_co_vs_forbes_com_no_coincide(self):
        """El corazón del FIX #4: forbes.co (Colombia) ≠ forbes.com (EE.UU.)."""
        assert mismo_dominio_base("forbes.co", "https://forbes.com") is False

    @pytest.mark.parametrize(
        "a, b",
        [
            (None, "acme.com"),
            ("acme.com", None),
            ("", "acme.com"),
            ("sinpunto", "acme.com"),
        ],
    )
    def test_entrada_no_derivable_es_false(self, a, b):
        assert mismo_dominio_base(a, b) is False
