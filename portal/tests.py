from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .analisis import analizar
from .models import Caso, Estado


class FlujoDeMantenimiento(TestCase):
    def setUp(self):
        usuarios = get_user_model().objects
        self.reportante = usuarios.create_user("estudiante")
        self.personal = usuarios.create_user("mantenimiento", is_staff=True)
        self.otro = usuarios.create_user("docente")
        self.client.force_login(self.reportante)

    def reportar(self, texto, activo="ELE-204"):
        respuesta = self.client.post(reverse("nuevo"), {
            "edificio": "Edificio académico", "zona": "Aula 204",
            "activo": activo, "descripcion": texto,
        })
        self.assertEqual(respuesta.status_code, 302)
        caso = Caso.objects.latest("creado")
        self.assertRedirects(respuesta, reverse("detalle", args=[caso.pk]))
        return caso

    def actualizar(self, caso, estado, nota=""):
        respuesta = self.client.post(reverse("detalle", args=[caso.pk]), {
            "version": caso.version, "estado": estado, "categoria": "ELECTRICO",
            "prioridad": "Inmediata", "responsable": self.personal.pk, "nota": nota,
        })
        caso.refresh_from_db()
        return respuesta

    def test_riesgo_prioritario_se_revisa_y_cierra_con_bitacora(self):
        self.reportar("La pintura de la pared está descarapelada", activo="")
        caso = self.reportar("El apagador de la entrada saca chispitas.")
        self.assertTrue(caso.escalado)
        self.assertIn("R11", caso.decision["reglas"])
        self.assertEqual(caso.estado, Estado.PENDIENTE)

        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse("detalle", args=[caso.pk])).status_code, 404)

        self.client.force_login(self.personal)
        respuesta = self.client.get(reverse("bandeja"))
        self.assertEqual(respuesta.context["pagina"].object_list[0].pk, caso.pk)
        self.assertEqual(self.actualizar(caso, Estado.VALIDADO).status_code, 302)
        self.assertEqual(self.actualizar(caso, Estado.ATENCION).status_code, 302)
        self.assertEqual(self.actualizar(caso, Estado.CERRADO).status_code, 200)
        self.assertEqual(caso.estado, Estado.ATENCION)
        self.assertEqual(self.actualizar(caso, Estado.CERRADO, "Se cambió el apagador.").status_code, 302)
        guardado = Caso.objects.get(pk=caso.pk)
        self.assertEqual(guardado.estado, Estado.CERRADO)
        self.assertEqual(guardado.bitacora.count(), 4)
        self.assertIn("R11", guardado.decision["reglas"])

    def test_vinculo_conserva_evidencia_y_escalamiento(self):
        principal = self.reportar("La tapa del apagador está rayada.")
        nuevo = self.reportar("El apagador de la entrada saca chispitas.")
        self.client.force_login(self.personal)
        respuesta = self.client.post(reverse("vincular", args=[nuevo.pk, principal.pk]))
        self.assertEqual(respuesta.status_code, 302)
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.duplicado_de, principal)
        self.assertTrue(nuevo.escalado)
        self.assertIn("chispitas", nuevo.descripcion)

    def test_reportante_puede_enviar_aclaracion(self):
        caso = self.reportar("El apagador saca chispitas.")
        self.client.force_login(self.personal)
        self.assertEqual(self.actualizar(caso, Estado.INFORMACION, "Indica qué apagador.").status_code, 302)
        self.assertTrue(caso.escalado)
        self.client.force_login(self.reportante)
        respuesta = self.client.post(reverse("ampliar", args=[caso.pk]), {"nota": "El de la entrada."})
        self.assertEqual(respuesta.status_code, 302)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Estado.PENDIENTE)
        self.assertEqual(caso.bitacora.first().nota, "El de la entrada.")

    def test_patrones_distinguen_caidas_y_coladeras(self):
        for texto in ("Ya se cayó una maestra en las escaleras.", "La coladera está sin tapa."):
            decision = analizar(texto, "Aula 204", "", None, {})
            self.assertFalse(decision["escalamiento"])


class VistasVisuales(TestCase):
    def setUp(self):
        usuarios = get_user_model().objects
        self.reportante = usuarios.create_user("estudiante")
        self.personal = usuarios.create_user("mantenimiento", is_staff=True)

    def crear(self, texto):
        self.client.force_login(self.reportante)
        self.client.post(reverse("nuevo"), {"edificio": "Edificio académico", "zona": "Aula 204",
                                            "activo": "ELE-204", "descripcion": texto})
        return Caso.objects.latest("creado")

    def test_formulario_nuevo_no_muestra_errores_al_abrir(self):
        self.client.force_login(self.reportante)
        self.assertNotContains(self.client.get(reverse("nuevo")), "Este campo es obligatorio")

    def test_panel_solo_para_personal(self):
        self.client.force_login(self.reportante)
        self.assertRedirects(self.client.get(reverse("panel")), reverse("bandeja"))
        self.client.force_login(self.personal)
        respuesta = self.client.get(reverse("panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("prioridad", respuesta.context["datos"])

    def test_tablero_agrupa_por_estado(self):
        self.crear("El apagador de la entrada saca chispitas.")
        self.client.force_login(self.personal)
        respuesta = self.client.get(reverse("bandeja"), {"vista": "tablero"})
        columnas = {c["valor"]: c["total"] for c in respuesta.context["columnas"]}
        self.assertEqual(columnas[Estado.PENDIENTE], 1)

    def test_resaltado_marca_palabras_de_riesgo_y_escapa_html(self):
        caso = self.crear("El apagador saca chispitas <script>x</script>")
        self.client.force_login(self.personal)
        pagina = self.client.get(reverse("detalle", args=[caso.pk])).content.decode()
        self.assertIn("<mark", pagina)
        self.assertNotIn("<script>x</script>", pagina)
