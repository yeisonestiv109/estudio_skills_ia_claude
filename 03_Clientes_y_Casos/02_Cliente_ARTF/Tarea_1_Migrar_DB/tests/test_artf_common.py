"""
Tests deterministas de la logica compartida (artf_common.py). Cada bug real
encontrado el 18/19-ago-2026 durante la reconciliacion Sheet-vs-Supabase
tiene aca un test que lo habria atrapado ANTES de tocar datos reales -- esa
es la idea: correr esto despues de cualquier cambio a artf_common.py o antes
de cualquier corrida de migracion/reconciliacion nueva.
"""
import artf_common as ac


class TestSanitizeWhatsapp:
    def test_no_agrega_cero_de_mas_por_formato_float_de_excel(self):
        """Bug real 18-ago-2026: el Sheet exporta numeros como float
        ('3023951842.0'). Un sanitizador que solo quita el punto (no el
        '.0' completo) deja un cero de mas -- corrompio 198 numeros de
        contacto reales en la migracion original."""
        assert ac.sanitize_whatsapp("3023951842.0") == "+573023951842"
        assert ac.sanitize_whatsapp("3023951842.0") != "+5730239518420"

    def test_numero_ya_formateado_con_mas_57_se_respeta(self):
        assert ac.sanitize_whatsapp("+573023951842") == "+573023951842"

    def test_numero_sin_indicativo_asume_colombia(self):
        assert ac.sanitize_whatsapp("3023951842") == "+573023951842"

    def test_valor_vacio_o_nulo_retorna_none(self):
        assert ac.sanitize_whatsapp(None) is None
        assert ac.sanitize_whatsapp("") is None
        assert ac.sanitize_whatsapp("   ") is None

    def test_numero_invalido_retorna_none_no_basura(self):
        assert ac.sanitize_whatsapp("abc") is None
        assert ac.sanitize_whatsapp("123") is None  # muy corto


class TestNombreSheetAUsuario:
    def test_los_4_setters_closers_originales_siguen_mapeados(self):
        for nombre in ("Andrew", "Gaby", "Cata", "Pipe"):
            assert nombre in ac.NOMBRE_SHEET_A_USUARIO

    def test_yeison_mapea_a_yeis_no_a_si_mismo(self):
        """Bug real 18-ago-2026: 14 leads con Setter='Yeison' en el Sheet
        casi quedan sin dueño en la importacion porque el diccionario
        original no conocia ese nombre -- y aunque se agregue, "Yeison"
        como texto del Sheet NO es el nombre real en Supabase ("Yeis")."""
        assert ac.NOMBRE_SHEET_A_USUARIO["Yeison"] == "Yeis"

    def test_yuli_esta_mapeada(self):
        assert ac.NOMBRE_SHEET_A_USUARIO["Yuli"] == "Yuli"

    def test_nombre_desconocido_no_esta_en_el_diccionario(self):
        """Si esto falla, alguien agrego un setter/closer nuevo al Pipeline
        sin agregarlo aca -- la proxima importacion lo va a dejar sin
        setter_id/closer_id en silencio, sin ningun error visible."""
        assert "Javier" not in ac.NOMBRE_SHEET_A_USUARIO  # ejemplo de nombre aun no onboardeado


class TestParseSalario:
    def test_formato_millones_con_m(self):
        assert ac.parse_salario("$5M COP") == (5_000_000.0, "COP")

    def test_valor_pendiente_retorna_none(self):
        assert ac.parse_salario("(pendiente)") == (None, None)

    def test_numero_crudo_asume_cop(self):
        assert ac.parse_salario(3_500_000) == (3_500_000.0, "COP")

    def test_valor_none_retorna_none(self):
        assert ac.parse_salario(None) == (None, None)


class TestEstadoMap:
    def test_ganado_mapea_a_ganado(self):
        assert ac.ESTADO_MAP["ganado"] == "ganado"

    def test_desistio_mapea_a_perdido(self):
        """Vocabulario nuevo detectado 18-ago-2026 -- si el Sheet vuelve a
        usar una palabra que no esta aca, cae en ESTADO_DEFAULT ('nuevo'),
        lo cual seria un bug silencioso para un lead que en realidad se
        perdio."""
        assert ac.ESTADO_MAP["desistió"] == "perdido"

    def test_estado_orden_contiene_todos_los_valores_del_mapa(self):
        """Si ESTADO_MAP gana un estado destino que no esta en ESTADO_ORDEN,
        la comparacion 'avanzo vs quedo atras' de reconciliar_18ago.py se
        rompe silenciosamente (cae siempre a ESTADO_DIFERENTE)."""
        for estado_destino in set(ac.ESTADO_MAP.values()):
            assert estado_destino in ac.ESTADO_ORDEN, f"'{estado_destino}' falta en ESTADO_ORDEN"


class TestSanitizeEmail:
    def test_email_valido(self):
        assert ac.sanitize_email("a@b.com") == "a@b.com"

    def test_email_invalido_retorna_none(self):
        assert ac.sanitize_email("no-es-email") is None
