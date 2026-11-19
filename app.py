from datetime import datetime
import hashlib
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import core.models
import core.parser
import core.rules

if (
    not hasattr(core.parser, "generar_plantilla_excel")
    or not hasattr(core.rules, "evaluar_semaforo_tiras")
):
    importlib.reload(core.models)
    importlib.reload(core.parser)
    importlib.reload(core.rules)

import core.exporter

if not hasattr(core.exporter, "evaluar_semaforo_tiras"):
    importlib.reload(core.exporter)

from core.exporter import generar_dictamen_excel
from core.models import AccionGrupo, GrupoInput, ResumenMateria, Turno
from core.parser import (
    generar_plantilla_excel,
    parse_academic_data,
    parse_saes_clipboard_text,
)
from core.rules import (
    aplicar_techo_global,
    evaluar_semaforo_tiras,
    optimizar_materia_turno,
)

# 1. Configuración Institucional
st.set_page_config(
    page_title="RACO | ESCOM-IPN",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

EJEMPLO_SAES_TEXT = (
    "1AM1\tA101\tFUNDAMENTOS DE PROGRAMACION\t1\t33\t33\t0\n"
    "2AM1\tA201\tALGEBRA LINEAL\t2\t36\t37\t-1\n"
    "2AV2\tA202\tCALCULO MULTIVARIABLE\t2\t36\t6\t30\n"
    "3AV2\tA301\tBASES DE DATOS\t3\t18\t8\t10\n"
    "7AV1\tA701\tADMINISTRACION DE PROYECTOS DE TI\t7\t35\t39\t-4\n"
    "7AX1\tA703\tTRABAJO TERMINAL I\t7\t250\t0\t250\n"
    "1LM1\tQ101\tLABORATORIO QUIMICA\t1\t18\t18\t0"
)


def _normalizar_busqueda(texto: str) -> str:
    """Normaliza una cadena eliminando acentos y convirtiendo a minúsculas para búsquedas."""
    if not texto:
        return ""
    nfd = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _generar_justificacion_minuta(
    resumenes: List[ResumenMateria],
    kpi_grupos_act: int,
    kpi_grupos_prop: int,
    kpi_delta: int,
    kpi_demanda_total: int,
    kpi_alumnos_atendidos: int,
    kpi_horas_docentes: int,
    tolerancia_tau: int,
    override_cupo: Optional[int],
    horas_por_materia: int,
    filtro_turno: str,
    input_sha256: str,
) -> str:
    """Genera un texto institucional formal listo para copiar a correos o minutas de academia."""
    cobertura_pct = (kpi_alumnos_atendidos / kpi_demanda_total * 100.0) if kpi_demanda_total > 0 else 100.0
    regimen_cupo = f"cupo uniforme forzado ({override_cupo} plazas)" if override_cupo else "cupo modal por asignatura"

    aperturas_lineas: List[str] = []
    cierres_lineas: List[str] = []

    for r in resumenes:
        nuevos_ids = [g.grupo_id for g in r.grupos if g.accion == AccionGrupo.ABRIR]
        cerrados_ids = [g.grupo_id for g in r.grupos if g.accion == AccionGrupo.CERRAR]
        conservados = [g for g in r.grupos if g.accion == AccionGrupo.CONSERVAR]
        cap_actual_absorbible = sum(g.cupo_asignado + (0 if g.es_atipico else tolerancia_tau) for g in conservados)
        excedente = max(0, r.demanda_total - cap_actual_absorbible)

        if nuevos_ids:
            aperturas_lineas.append(
                f"  - {r.materia} (Turno {r.turno.value}): abrir {len(nuevos_ids)} grupo(s) "
                f"[{', '.join(nuevos_ids)}] para atender matrícula de {r.demanda_total} alumnos "
                f"(excedente de +{excedente} sobre capacidad absorbible actual)."
            )
        if cerrados_ids:
            cierres_lineas.append(
                f"  - {r.materia} (Turno {r.turno.value}): consolidar/cerrar {len(cerrados_ids)} grupo(s) "
                f"[{', '.join(cerrados_ids)}] por baja matrícula acumulada ({r.demanda_total} alumnos en el turno)."
            )

    bloque_aperturas = (
        "\n".join(aperturas_lineas)
        if aperturas_lineas
        else "  - Ninguna asignatura requiere apertura de nuevas secciones con los parámetros actuales."
    )
    bloque_cierres = (
        "\n".join(cierres_lineas)
        if cierres_lineas
        else "  - Ninguna asignatura presenta grupos excedentarios sujetos a cierre o fusión."
    )

    hash_corto = input_sha256 if input_sha256 else "N/D"

    return (
        f"MINUTA / DICTAMEN TÉCNICO DE APOYO — PLANEACIÓN DE CAPACIDAD DOCENTE (ESCOM - IPN)\n"
        f"Alcance del filtro: {filtro_turno} | Régimen: {regimen_cupo} | Tolerancia (τ): +{tolerancia_tau} alumnos/grupo\n"
        f"----------------------------------------------------------------------------------\n"
        f"1. RESUMEN DE COBERTURA:\n"
        f"   Se analizaron {kpi_grupos_act} grupos registrados en SAES con una matrícula total observada de "
        f"{kpi_demanda_total} alumnos. El modelo propone operar {kpi_grupos_prop} grupos, garantizando una "
        f"atención de {kpi_alumnos_atendidos}/{kpi_demanda_total} estudiantes ({cobertura_pct:.1f}% de cobertura "
        f"bajo política de cero rechazo).\n\n"
        f"2. GRUPOS RECOMENDADOS PARA APERTURA (ABRIR):\n"
        f"{bloque_aperturas}\n\n"
        f"3. GRUPOS RECOMENDADOS PARA CIERRE O CONSOLIDACIÓN (CERRAR):\n"
        f"{bloque_cierres}\n\n"
        f"4. IMPACTO PRESUPUESTAL Y CARGA DOCENTE:\n"
        f"   - Diferencial neto de secciones: {kpi_delta:+d} grupo(s).\n"
        f"   - Horas docentes requeridas: {kpi_horas_docentes} hrs/semana "
        f"(calculadas a razón de {horas_por_materia} hrs/semana frente a grupo).\n\n"
        f"5. TRAZABILIDAD Y RESPALDO DE INTEGRIDAD:\n"
        f"   El presente análisis fue procesado mediante el motor RACO v1.2 (ADR-0002) y cuenta con "
        f"respaldo de integridad criptográfica SHA-256 sobre el corte de entrada:\n"
        f"   [{hash_corto}]"
    )


@st.cache_data(show_spinner=False)
def obtener_plantilla_bytes() -> bytes:
    """Genera y cachea en memoria los bytes de la plantilla Excel descargable."""
    return generar_plantilla_excel().getvalue()


@st.cache_data(show_spinner=False)
def obtener_dictamen_excel_cacheado(
    input_sha256: str,
    optimizaciones_dump: Tuple[Dict[str, Any], ...],
    grupos_dump: Tuple[Dict[str, Any], ...],
    tolerancia_tau: int,
    override_cupo: Optional[int],
    horas_materia: int,
    git_commit_tag: str,
    alertas_dump: Tuple[Dict[str, Any], ...],
) -> bytes:
    """
    Genera y cachea el libro Excel (.xlsx) oficial a partir de estructuras inmutables/serializables.
    Evita reconstruir el archivo de OpenPyXL en cada rerun cuando los parámetros no han cambiado.
    """
    optimizaciones_objs = [ResumenMateria.model_validate(d) for d in optimizaciones_dump]
    grupos_objs = [GrupoInput.model_validate(d) for d in grupos_dump]
    parametros = {
        "tolerancia_tau": tolerancia_tau,
        "override_cupo": override_cupo,
        "horas_materia": horas_materia,
        "git_commit_tag": git_commit_tag,
        "input_sha256": input_sha256,
    }
    stream = generar_dictamen_excel(
        raw_input_text="",
        optimizaciones=optimizaciones_objs,
        grupos_input=grupos_objs,
        parametros=parametros,
        alertas_saes=list(alertas_dump),
    )
    return stream.getvalue()


# Inicialización de Session State para persistencia sin desfase
if "saes_raw_text" not in st.session_state:
    st.session_state["saes_raw_text"] = ""
if "saes_clipboard_input" not in st.session_state:
    st.session_state["saes_clipboard_input"] = st.session_state["saes_raw_text"]
if "modo_fuente" not in st.session_state:
    st.session_state["modo_fuente"] = "clipboard"
if "es_sintetico" not in st.session_state:
    st.session_state["es_sintetico"] = False
if "expander_ingesta_abierto" not in st.session_state:
    st.session_state["expander_ingesta_abierto"] = True
if "mostrar_aviso_vacio" not in st.session_state:
    st.session_state["mostrar_aviso_vacio"] = False
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
if "mostrar_tutorial" not in st.session_state:
    st.session_state["mostrar_tutorial"] = True
if "tutorial_completado" not in st.session_state:
    st.session_state["tutorial_completado"] = False
if "tutorial_paso" not in st.session_state:
    st.session_state["tutorial_paso"] = 0


PASOS_TUTORIAL: List[Dict[str, str]] = [
    {
        "titulo": "🎓 Bienvenido a RACO (ESCOM - IPN)",
        "descripcion": (
            "**RACO (*Risk-Adjusted Capacity Optimizer*)** es el asistente técnico para Presidentes de Academia, "
            "Jefes de Departamento y Subdirección Académica de la **Escuela Superior de Cómputo (IPN)**.\n\n"
            "- **¿Qué resuelve?** Analiza en menos de un segundo los reportes de ocupabilidad del SAES para recomendar "
            "qué grupos **abrir, conservar o consolidar**.\n"
            "- **Política de Cero Rechazo:** Garantiza el **100% de cobertura** sobre la matrícula observada.\n"
            "- **Cero Invasión y Cero Costo:** Funciona sin pedir contraseñas ni conectarse a la base de datos del SAES."
        ),
        "elemento_ui": "📍 **Dónde mirar:** Encabezado principal y barra lateral izquierda de control.",
    },
    {
        "titulo": "📋 Paso 1: Ingresa la Tabla del SAES o Sube un Archivo",
        "descripcion": (
            "Tienes dos formas rápidas y a prueba de errores para cargar tus datos:\n\n"
            "1. **Pegar desde SAES (Portapapeles):** Entra al SAES (*Académica » Ocupabilidad Horario*), selecciona las filas "
            "con el ratón, cópialas (`Ctrl+C`), pégalas en el cuadro central (`Ctrl+V`) y presiona **`⚡ Analizar tabla pegada`** "
            "(o haz clic en **`📋 Cargar Ejemplo SAES`** para una demostración inmediata).\n"
            "2. **Subir archivo (`.csv` / `.xlsx`):** En la barra lateral izquierda puedes subir un archivo exportado con columnas "
            "del SAES o descargar la **`📄 Descargar plantilla (.xlsx)`** lista para llenar.\n"
            "3. Para analizar otro corte en cualquier momento, usa el botón **`🔄 Nuevo análisis / Limpiar datos`**."
        ),
        "elemento_ui": "📍 **Dónde mirar:** Selector `Método de Entrada` (barra lateral) y recuadro central `📋 Ingesta de datos SAES`.",
    },
    {
        "titulo": "⚙️ Paso 2: Simula Escenarios con Cupo Blando (τ) y Horas Docentes",
        "descripcion": (
            "En la sección **`⚙️ Parámetros de Optimización`** de la barra lateral izquierda puedes ajustar en vivo:\n\n"
            "- **Tolerancia de Sobrecupo ($\\tau = 2$):** Margen de alumnos extra que un grupo actual puede absorber antes de "
            "justificar la apertura de una nueva sección ($\\text{Capacidad Efectiva} = \\text{Cupo} + \\tau$).\n"
            "- **Cupo Modal y Blindaje Automático (ADR-0002):** RACO detecta el cupo típico de cada asignatura y protege "
            "automáticamente **Laboratorios (18 plazas)** y **Trabajo Terminal (`Turno X`, 250 plazas)** para que nunca se "
            "cierren por error.\n"
            "- **Horas Semanales, Filtro de Turno (`M`, `V`, `X`) y Techo Presupuestal Global.**"
        ),
        "elemento_ui": "📍 **Dónde mirar:** Controles deslizantes y selectores en la barra lateral izquierda (`st.sidebar`).",
    },
    {
        "titulo": "📊 Paso 3: Explora los KPIs, el Buscador y el Semáforo de Tiras",
        "descripcion": (
            "Al cargar los datos, el tablero central se divide en indicadores ejecutivos y **4 pestañas de diagnóstico**:\n\n"
            "- **5 KPIs Superiores:** Grupos Actuales, Propuestos, Diferencial Neto, Alumnos Atendidos (`100%`) y **Horas Docentes Requeridas**.\n"
            "- **📊 Resumen Directivo:** Tabla consolidada, gráfica comparativa y el bloque **`✉️ Justificación Lista para Correo / Minuta de Academia`** para copiar en 1 clic.\n"
            "- **📋 Detalle Operativo por Grupo:** Incluye buscador instantáneo (`🔍`) por materia, clave o grupo y filtro por acción (`ABRIR`, `CERRAR`, `CONSERVAR`).\n"
            "- **🚦 Semáforo de Tiras Curriculares:** Evalúa cada bloque `(Semestre, Turno)` en 🟢 **Tira Fluida**, 🟡 **Tira Comprometida** o 🔴 **Tira Bloqueada**."
        ),
        "elemento_ui": "📍 **Dónde mirar:** Franja superior de métricas y las 4 pestañas centrales del tablero.",
    },
    {
        "titulo": "📥 Paso 4: Descarga el Dictamen Oficial en Excel con Sello SHA-256",
        "descripcion": (
            "Cuando termines de simular tu escenario, dirígete al final de la barra lateral izquierda:\n\n"
            "- Haz clic en **`📥 Descargar Informe Técnico de Apoyo (.xlsx)`**.\n"
            "- Obtendrás un libro oficial de Microsoft Excel con **4 pestañas formateadas** (*Carátula y Supuestos*, "
            "*Resumen Directivo*, *Detalle por Grupo* y *Semáforo de Tiras*).\n"
            "- Incluye un **Sello Digital de Integridad SHA-256** que certifica ante Academias y Subdirección Académica "
            "que el corte de entrada del SAES no fue alterado manualmente."
        ),
        "elemento_ui": "📍 **Dónde mirar:** Sección `📄 Exportación Oficial` al final de la barra lateral izquierda.",
    },
]


def _on_abrir_tutorial_click() -> None:
    """Reabre el tutorial interactivo desde el Paso 1 sin borrar ningún dato ni parámetro cargado."""
    st.session_state["tutorial_paso"] = 0
    st.session_state["mostrar_tutorial"] = True


def _on_tutorial_prev() -> None:
    """Retrocede un paso en el tutorial manteniendo abierto el modal."""
    paso_actual = int(st.session_state.get("tutorial_paso", 0))
    st.session_state["tutorial_paso"] = max(0, paso_actual - 1)
    st.session_state["mostrar_tutorial"] = True


def _on_tutorial_next() -> None:
    """Avanza un paso en el tutorial manteniendo abierto el modal."""
    total_pasos = len(PASOS_TUTORIAL)
    paso_actual = int(st.session_state.get("tutorial_paso", 0))
    st.session_state["tutorial_paso"] = min(total_pasos - 1, paso_actual + 1)
    st.session_state["mostrar_tutorial"] = True


def _on_tutorial_close() -> None:
    """Cierra el tutorial (al saltar o finalizar) y evita reaperturas automáticas."""
    st.session_state["tutorial_completado"] = True
    st.session_state["mostrar_tutorial"] = False
    st.session_state["tutorial_paso"] = 0


def _on_tutorial_demo() -> None:
    """Carga el lote de ejemplo del SAES y cierra el tutorial listo para explorar."""
    st.session_state["modo_fuente"] = "clipboard"
    st.session_state["saes_clipboard_input"] = EJEMPLO_SAES_TEXT
    st.session_state["saes_raw_text"] = EJEMPLO_SAES_TEXT
    st.session_state["mostrar_aviso_vacio"] = False
    st.session_state["expander_ingesta_abierto"] = False
    st.session_state["tutorial_completado"] = True
    st.session_state["mostrar_tutorial"] = False
    st.session_state["tutorial_paso"] = 0


@st.dialog("🎓 Guía Interactiva de Uso — RACO v1.2 (ESCOM - IPN)", width="large")
def mostrar_modal_tutorial() -> None:
    """Renderiza el tour interactivo paso a paso dentro de una ventana modal nativa."""
    total_pasos = len(PASOS_TUTORIAL)
    paso_idx = max(0, min(int(st.session_state.get("tutorial_paso", 0)), total_pasos - 1))
    paso_actual = PASOS_TUTORIAL[paso_idx]

    st.progress(
        (paso_idx + 1) / total_pasos,
        text=f"Paso {paso_idx + 1} de {total_pasos}",
    )

    st.subheader(paso_actual["titulo"])
    st.markdown(paso_actual["descripcion"])
    st.info(paso_actual["elemento_ui"])
    st.divider()

    if paso_idx < total_pasos - 1:
        col_skip, col_prev, col_next = st.columns([1.2, 1, 1.2])
        with col_skip:
            if st.button(
                "⏭️ Saltar tutorial",
                use_container_width=True,
                key="btn_tut_skip",
                on_click=_on_tutorial_close,
            ):
                st.rerun()
        with col_prev:
            st.button(
                "⬅️ Anterior",
                use_container_width=True,
                disabled=(paso_idx == 0),
                key="btn_tut_prev",
                on_click=_on_tutorial_prev,
            )
        with col_next:
            st.button(
                "Siguiente ➡️",
                type="primary",
                use_container_width=True,
                key="btn_tut_next",
                on_click=_on_tutorial_next,
            )
    else:
        col_prev, col_demo, col_finish = st.columns([1, 1.3, 1.3])
        with col_prev:
            st.button(
                "⬅️ Anterior",
                use_container_width=True,
                key="btn_tut_prev_last",
                on_click=_on_tutorial_prev,
            )
        with col_demo:
            if st.button(
                "🚀 Probar con Ejemplo SAES",
                use_container_width=True,
                key="btn_tut_demo",
                on_click=_on_tutorial_demo,
            ):
                st.rerun()
        with col_finish:
            if st.button(
                "✅ ¡Empezar a usar RACO!",
                type="primary",
                use_container_width=True,
                key="btn_tut_finish",
                on_click=_on_tutorial_close,
            ):
                st.rerun()


def _on_textarea_change() -> None:
    """Sincroniza el área de texto al presionar Ctrl+Enter o perder foco."""
    texto = st.session_state.get("saes_clipboard_input", "")
    st.session_state["saes_raw_text"] = texto
    if texto.strip():
        st.session_state["mostrar_aviso_vacio"] = False
        st.session_state["expander_ingesta_abierto"] = False


def _on_analizar_tabla_click() -> None:
    """Fuerza la lectura inmediata del texto pegado en el área de portapapeles."""
    texto = st.session_state.get("saes_clipboard_input", "")
    st.session_state["saes_raw_text"] = texto
    if texto.strip():
        st.session_state["mostrar_aviso_vacio"] = False
        st.session_state["expander_ingesta_abierto"] = False
    else:
        st.session_state["mostrar_aviso_vacio"] = True
        st.session_state["expander_ingesta_abierto"] = True


def _on_cargar_ejemplo_click() -> None:
    """Inyecta el conjunto de datos de ejemplo del SAES de forma instantánea."""
    st.session_state["saes_clipboard_input"] = EJEMPLO_SAES_TEXT
    st.session_state["saes_raw_text"] = EJEMPLO_SAES_TEXT
    st.session_state["mostrar_aviso_vacio"] = False
    st.session_state["expander_ingesta_abierto"] = False


def _on_limpiar_datos_click() -> None:
    """Limpia el texto o archivo cargado y reabre la zona de entrada para un nuevo análisis."""
    st.session_state["saes_clipboard_input"] = ""
    st.session_state["saes_raw_text"] = ""
    st.session_state["es_sintetico"] = False
    st.session_state["mostrar_aviso_vacio"] = False
    st.session_state["expander_ingesta_abierto"] = True
    st.session_state["uploader_key"] += 1


col_header_title, col_header_help = st.columns([4.5, 1])
with col_header_title:
    st.title("🎓 RACO: Risk-Adjusted Capacity Optimizer")
    st.caption("Planificación y Optimización de Capacidad Docente — Escuela Superior de Cómputo (ESCOM IPN)")
with col_header_help:
    st.write("")
    st.button(
        "❓ ¿Cómo funciona?",
        use_container_width=True,
        on_click=_on_abrir_tutorial_click,
        help="Abre la guía rápida interactiva paso a paso sin borrar los datos cargados.",
    )
st.divider()

# Disparo automático del tour de bienvenida con blindaje contra reaperturas fantasma
if st.session_state.get("mostrar_tutorial", False):
    st.session_state["mostrar_tutorial"] = False
    st.session_state["tutorial_completado"] = True
    mostrar_modal_tutorial()

# 2. Barra Lateral de Simulación (Sidebar)
st.sidebar.header("📥 Ingesta de Datos")

metodo_ingesta = st.sidebar.radio(
    "Método de Entrada:",
    options=["Pegar desde SAES (Portapapeles)", "Subir archivo (.csv / .xlsx)"],
    index=0 if st.session_state["modo_fuente"] == "clipboard" else 1,
)

grupos_input: List[GrupoInput] = []
demanda_agregada: Dict[Tuple[str, Turno], int] = {}
df_clipboard_raw: pd.DataFrame = pd.DataFrame()
hubo_error_ingesta = False
input_sha256 = ""
lineas_omitidas = 0

if metodo_ingesta == "Pegar desde SAES (Portapapeles)":
    st.session_state["modo_fuente"] = "clipboard"
    st.session_state["es_sintetico"] = False

    with st.expander(
        "📋 Ingesta de datos SAES (Copiar / Pegar)",
        expanded=st.session_state["expander_ingesta_abierto"],
    ):
        st.text_area(
            "Pega directamente la tabla copiada del SAES (Ctrl+V):",
            height=160,
            key="saes_clipboard_input",
            on_change=_on_textarea_change,
            placeholder=(
                "1AM1\tA101\tFUNDAMENTOS DE PROGRAMACION\t1\t33\t33\t0\n"
                "2AM1\tA201\tALGEBRA LINEAL\t2\t36\t37\t-1\n"
                "7AX1\tA703\tTRABAJO TERMINAL I\t7\t250\t0\t250"
            ),
        )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.button(
                "⚡ Analizar tabla pegada",
                type="primary",
                use_container_width=True,
                on_click=_on_analizar_tabla_click,
            )
        with btn_col2:
            st.button(
                "📋 Cargar Ejemplo SAES",
                use_container_width=True,
                on_click=_on_cargar_ejemplo_click,
            )

        if st.session_state.get("mostrar_aviso_vacio", False):
            st.warning(
                "📋 El cuadro de texto está vacío. Para analizar un corte: entra al SAES "
                "(**Académica » Ocupabilidad Horario**), selecciona las filas de la tabla con el ratón, "
                "cópialas con **Ctrl+C**, pégalas arriba con **Ctrl+V** y presiona **⚡ Analizar tabla pegada**."
            )

    raw_source_content = st.session_state["saes_raw_text"]

    if raw_source_content.strip():
        text_norm = raw_source_content.replace("\r\n", "\n").replace("\r", "\n").strip()
        input_sha256 = hashlib.sha256(text_norm.encode("utf-8")).hexdigest().upper()
        try:
            total_lineas_no_vacias = len([l for l in raw_source_content.splitlines() if l.strip()])
            df_clipboard_raw = parse_saes_clipboard_text(raw_source_content)
            lineas_omitidas = max(0, total_lineas_no_vacias - len(df_clipboard_raw))

            if not df_clipboard_raw.empty:
                for _, row in df_clipboard_raw.iterrows():
                    demanda_calc = int(row["cupo"]) - int(row["disponibles"])
                    demanda_final = max(int(row["inscritos"]), demanda_calc)
                    g_obj = GrupoInput(
                        materia=str(row["nombre_materia"]).strip(),
                        grupo=str(row["grupo"]).strip(),
                        turno=row["turno"],
                        cupo_max=int(row["cupo"]),
                        inscritos_actuales=int(row["inscritos"]),
                        demanda_estimada=demanda_final,
                        materia_id=str(row["materia_id"]).strip(),
                        semestre=int(row["semestre"]) if pd.notna(row["semestre"]) else None,
                        carrera=str(row["carrera"]).strip(),
                    )
                    grupos_input.append(g_obj)
                    key = (g_obj.materia, g_obj.turno)
                    demanda_agregada[key] = demanda_agregada.get(key, 0) + g_obj.demanda_estimada

                col_met1, col_met2, col_met3 = st.columns([2, 2, 1])
                col_met1.success(f"✅ **{len(grupos_input)}** grupos procesados correctamente")
                if lineas_omitidas > 0:
                    col_met2.warning(f"⚠️ Se omitieron **{lineas_omitidas}** líneas no conformes con el formato SAES.")
                with col_met3:
                    st.button(
                        "🔄 Nuevo análisis / Limpiar datos",
                        use_container_width=True,
                        on_click=_on_limpiar_datos_click,
                    )
            else:
                st.warning("⚠️ No se detectaron filas válidas en el texto pegado.")
        except Exception as e:
            st.error(f"❌ Error al procesar portapapeles: {e}")
            hubo_error_ingesta = True
else:
    st.session_state["modo_fuente"] = "file"
    uploaded_file = st.sidebar.file_uploader(
        "Cargar Oferta / Demanda (.csv, .xlsx)",
        type=["csv", "xlsx", "xls"],
        key=f"file_uploader_{st.session_state['uploader_key']}",
        help=(
            "Acepta tablas exportadas directamente del SAES (columnas: Grupo, Clave, Materia, Cupo, Inscritos, Disponibles) "
            "o el esquema estándar (materia, grupo, turno, cupo_max, inscritos_actuales, demanda_estimada)."
        ),
    )
    st.sidebar.download_button(
        label="📄 Descargar plantilla (.xlsx)",
        data=obtener_plantilla_bytes(),
        file_name="Plantilla_SAES_RACO_ESCOM.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    btn_sintetico = st.sidebar.button("Cargar sintéticos de ESCOM (Demo)", use_container_width=True)

    default_csv = Path("data/synthetic_escom.csv")
    file_to_parse = None

    if uploaded_file is not None:
        file_to_parse = uploaded_file
        # Hash SHA-256 directo sobre los bytes binarios del archivo subido
        file_bytes = uploaded_file.getvalue()
        input_sha256 = hashlib.sha256(file_bytes).hexdigest().upper()
        st.session_state["es_sintetico"] = False
    elif btn_sintetico or st.session_state["es_sintetico"]:
        st.session_state["es_sintetico"] = True
        file_to_parse = default_csv
        raw_text_syn = default_csv.read_text(encoding="utf-8") if default_csv.exists() else "synthetic"
        text_norm_syn = raw_text_syn.replace("\r\n", "\n").replace("\r", "\n").strip()
        input_sha256 = hashlib.sha256(text_norm_syn.encode("utf-8")).hexdigest().upper()

    if file_to_parse:
        try:
            grupos_input, demanda_agregada = parse_academic_data(file_to_parse)
            col_f1, col_f2 = st.columns([3, 1])
            col_f1.success(f"✅ **{len(grupos_input)}** grupos cargados desde archivo.")
            with col_f2:
                st.button(
                    "🔄 Nuevo análisis / Limpiar datos",
                    use_container_width=True,
                    on_click=_on_limpiar_datos_click,
                )
        except Exception as e:
            st.sidebar.error(f"❌ Error al procesar archivo: {e}")
            hubo_error_ingesta = True

# Banner claro de datos sintéticos (Fila 33)
if st.session_state.get("es_sintetico", False):
    st.warning("⚠️ **MODO DEMOSTRACIÓN:** Utilizando datos sintéticos de prueba. No representan registros de matrícula real del SAES.")

st.sidebar.header("⚙️ Parámetros de Optimización")

# Slider de Tolerancia de Sobrecupo (tau)
tolerancia_tau = st.sidebar.slider(
    "Tolerancia de Sobrecupo (τ)",
    min_value=0,
    max_value=5,
    value=2,
    step=1,
    help="Cupo blando (ADR-0002): margen de alumnos absorbibles antes de abrir un nuevo grupo (capacidad efectiva = cupo + τ).",
)

# Forzar cupo uniforme global (override)
forzar_cupo = st.sidebar.checkbox(
    "Forzar cupo uniforme global",
    value=False,
    help="Si está desactivado, el motor utiliza automáticamente el cupo modal de cada materia. Si se activa, manda el slider siguiente.",
)

override_cupo_val = None
if forzar_cupo:
    override_cupo_val = st.sidebar.slider(
        "Cupo Uniforme Global Objetivo",
        min_value=20,
        max_value=45,
        value=35,
        step=1,
    )

# Selector numérico editable de horas semanales frente a grupo
horas_por_materia = st.sidebar.number_input(
    "Horas semanales frente a grupo por materia",
    min_value=1,
    max_value=10,
    value=4,
    step=1,
    help="Horas docentes asignadas por cada grupo activo frente a grupo.",
)

# Filtro de turno con soporte Turno.X
filtro_turno = st.sidebar.selectbox(
    "Filtro de Turno",
    options=["Todos", "Matutino (M)", "Vespertino (V)", "Mixto / Admin (X)"],
    index=0,
)

# Expander de Glosario e Interpretación (Fila 4)
with st.expander("📖 ¿Cómo interpretar este informe?", expanded=False):
    st.markdown("""
    - **Matrícula Observada:** Alumnos registrados o con cupo agotado en SAES (no sustituye encuestas de demanda no atendida).
    - **Tolerancia tau (τ) / Cupo Blando:** Excedente de sobrecupo admisible por grupo antes de justificar la apertura de una nueva aula.
    - **Grupos Zombi:** Grupos con matrícula nula o mínima (≤ 0.6 del cupo modal) que ameritan consolidación.
    - **Macro-grupos Administrativos (Turno X):** Grupos de Trabajo Terminal (250+ cupos) protegidos de partición física en aulas.
    - **Acciones:**
      * **CONSERVAR:** El grupo se mantiene operativo con su cupo asignado.
      * **ABRIR:** Se requiere aperturar un grupo nuevo por exceso de matrícula observada.
      * **CERRAR / CONSOLIDAR:** Grupo excedentario sugerido para reubicación docente.
    """)

# 3. Pipeline de Procesamiento
if grupos_input and not hubo_error_ingesta:
    claves_unicas = sorted(list(demanda_agregada.keys()), key=lambda x: (x[0], x[1].value))
    resumenes_iniciales: List[ResumenMateria] = []

    for materia, turno in claves_unicas:
        demanda = demanda_agregada[(materia, turno)]
        resumen = optimizar_materia_turno(
            materia=materia,
            turno=turno,
            demanda=demanda,
            grupos_existentes=grupos_input,
            override_cupo=override_cupo_val,
            tolerancia=tolerancia_tau,
        )
        resumenes_iniciales.append(resumen)

    total_grupos_actuales = sum(r.grupos_actuales for r in resumenes_iniciales)

    # Techo Presupuestal Global
    habilitar_techo = st.sidebar.checkbox(
        "Habilitar Techo Presupuestal Global",
        value=False,
        help="Limita el total máximo de grupos a ofertar aplicando algoritmo greedy por menor saturación.",
    )

    resumenes_finales = resumenes_iniciales
    if habilitar_techo:
        max_grupos_global = st.sidebar.slider(
            "Máximo de Grupos Permitidos",
            min_value=1,
            max_value=max(1, total_grupos_actuales * 2),
            value=max(1, total_grupos_actuales),
            step=1,
        )
        resumenes_finales = aplicar_techo_global(resumenes_iniciales, max_grupos_global)

    # Filtrar según selección de turno
    if filtro_turno == "Matutino (M)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.M]
    elif filtro_turno == "Vespertino (V)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.V]
    elif filtro_turno == "Mixto / Admin (X)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.X]
    else:
        resumenes_mostrados = resumenes_finales

    # 4. Sección de Métricas Clave (KPIs superiores con semántica de negocio) (Filas 1 y 24)
    kpi_grupos_act = sum(r.grupos_actuales for r in resumenes_mostrados)
    kpi_grupos_prop = sum(r.grupos_propuestos for r in resumenes_mostrados)
    kpi_delta = kpi_grupos_prop - kpi_grupos_act
    kpi_demanda_total = sum(r.demanda_total for r in resumenes_mostrados)
    kpi_alumnos_atendidos = sum(
        sum(g.inscritos_estimados for g in r.grupos if g.accion != AccionGrupo.CERRAR)
        for r in resumenes_mostrados
    )
    kpi_horas_docentes = kpi_grupos_prop * int(horas_por_materia)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Grupos Actuales (SAES)", kpi_grupos_act)
    col2.metric("Grupos Propuestos", kpi_grupos_prop)
    col3.metric(
        "Grupos a Abrir (+) / Cerrar (−)",
        f"{kpi_delta:+d}",
        delta=kpi_delta,
        delta_color="inverse",
    )
    col4.metric(
        "Alumnos Atendidos",
        f"{kpi_alumnos_atendidos} / {kpi_demanda_total}",
        f"{(kpi_alumnos_atendidos / kpi_demanda_total * 100):.1f}%" if kpi_demanda_total > 0 else "0%",
        help="Proporción de alumnos cubiertos respecto a la matrícula observada.",
    )
    col5.metric(
        "Horas Docentes Requeridas",
        f"{kpi_horas_docentes} hrs/sem",
        help=f"Calculado como {kpi_grupos_prop} grupos propuestos × {horas_por_materia} hrs/materia",
    )

    # Alerta de discrepancias del SAES si aplica
    alertas_saes_list = []
    if not df_clipboard_raw.empty and "discrepancia_saes" in df_clipboard_raw.columns:
        discrepancias = df_clipboard_raw[df_clipboard_raw["discrepancia_saes"] == True]
        if not discrepancias.empty:
            alertas_saes_list = discrepancias.to_dict(orient="records")
            with st.expander(f"⚠️ Alerta: Se detectaron {len(discrepancias)} inconsistencias en datos SAES (cupo - inscritos ≠ disponibles)", expanded=False):
                st.caption("Estas discrepancias suelen ocurrir por bajas no consolidadas o sobrecupos no autorizados en el SAES.")
                st.dataframe(
                    discrepancias[["grupo", "materia_id", "nombre_materia", "cupo", "inscritos", "disponibles"]],
                    use_container_width=True,
                    hide_index=True,
                )

    # 4.1 Generación Cacheada y Botón de Descarga del Informe Técnico Oficial en Excel
    tz_cdmx = ZoneInfo("America/Mexico_City")
    timestamp_str = datetime.now(tz_cdmx).strftime("%Y%m%d_%H%M%S")

    excel_bytes = obtener_dictamen_excel_cacheado(
        input_sha256=input_sha256,
        optimizaciones_dump=tuple(r.model_dump() for r in resumenes_finales),
        grupos_dump=tuple(g.model_dump() for g in grupos_input),
        tolerancia_tau=tolerancia_tau,
        override_cupo=override_cupo_val,
        horas_materia=int(horas_por_materia),
        git_commit_tag="v1.2.1-hardened",
        alertas_dump=tuple(alertas_saes_list),
    )

    st.sidebar.divider()
    st.sidebar.subheader("📄 Exportación Oficial")
    st.sidebar.download_button(
        label="📥 Descargar Informe Técnico de Apoyo (.xlsx)",
        data=excel_bytes,
        file_name=f"Informe_Tecnico_RACO_ESCOM_{timestamp_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.write("")

    # 5. Pestañas de Visualización (Fila 24: Semántica de Matrícula Observada)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Resumen Directivo",
        "📋 Detalle Operativo por Grupo",
        "⚠️ Diagnóstico de Sobrecupo y Cierres",
        "🚦 Semáforo de Tiras",
    ])

    # Pestaña 1: Resumen Directivo
    with tab1:
        st.subheader("Consolidado por Materia y Turno")
        filas_resumen = []
        for r in resumenes_mostrados:
            filas_resumen.append({
                "Materia": r.materia,
                "Turno": r.turno.value,
                "Matrícula Observada": r.demanda_total,
                "Grupos Act.": r.grupos_actuales,
                "Grupos Prop.": r.grupos_propuestos,
                "Delta": r.delta_grupos,
                "Cupo Promedio": f"{r.cupo_promedio:.1f}",
            })
        df_resumen = pd.DataFrame(filas_resumen)
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        st.subheader("Comparativa de Grupos: Actuales vs Propuestos")
        if not df_resumen.empty:
            chart_data = df_resumen.copy()
            chart_data["Materia-Turno"] = chart_data["Materia"] + " (" + chart_data["Turno"] + ")"
            chart_df = chart_data.set_index("Materia-Turno")[["Grupos Act.", "Grupos Prop."]]
            st.bar_chart(chart_df, height=350)

        st.divider()
        st.subheader("✉️ Justificación Lista para Correo / Minuta de Academia")
        st.caption(
            "Usa el botón de copiado rápido (esquina superior derecha del recuadro) para pegar esta justificación "
            "formal en correos oficiales, minutas de academia o solicitudes a la Subdirección Académica."
        )
        texto_justificacion = _generar_justificacion_minuta(
            resumenes=resumenes_mostrados,
            kpi_grupos_act=kpi_grupos_act,
            kpi_grupos_prop=kpi_grupos_prop,
            kpi_delta=kpi_delta,
            kpi_demanda_total=kpi_demanda_total,
            kpi_alumnos_atendidos=kpi_alumnos_atendidos,
            kpi_horas_docentes=kpi_horas_docentes,
            tolerancia_tau=tolerancia_tau,
            override_cupo=override_cupo_val,
            horas_por_materia=int(horas_por_materia),
            filtro_turno=filtro_turno,
            input_sha256=input_sha256,
        )
        st.code(texto_justificacion, language=None)

    # Pestaña 2: Detalle Operativo por Grupo
    with tab2:
        st.subheader("Oferta Detallada por Grupo")

        # Índice rápido de claves de materia para enriquecer la búsqueda
        clave_por_materia: Dict[str, str] = {}
        for g_in in grupos_input:
            if g_in.materia_id and g_in.materia not in clave_por_materia:
                clave_por_materia[g_in.materia] = g_in.materia_id

        col_busq, col_acc = st.columns([2, 1])
        with col_busq:
            busqueda_detalle = st.text_input(
                "Buscar por materia, clave o grupo",
                placeholder="🔍 Buscar por materia, clave o grupo (ej. Cálculo, 1AM1)...",
                label_visibility="collapsed",
            )
        with col_acc:
            filtro_accion = st.selectbox(
                "Filtrar por acción recomendada",
                options=["Todas las acciones", "ABRIR", "CERRAR", "CONSERVAR"],
                index=0,
                label_visibility="collapsed",
            )

        filas_detalle = []
        termino_norm = _normalizar_busqueda(busqueda_detalle.strip())

        for r in resumenes_mostrados:
            clave_mat = clave_por_materia.get(r.materia, "")
            for g in r.grupos:
                if filtro_accion != "Todas las acciones" and g.accion.value != filtro_accion:
                    continue

                if termino_norm:
                    texto_buscable = _normalizar_busqueda(f"{g.materia} {clave_mat} {g.grupo_id}")
                    if termino_norm not in texto_buscable:
                        continue

                filas_detalle.append({
                    "Materia": g.materia,
                    "Turno": g.turno.value,
                    "Grupo ID": g.grupo_id,
                    "Acción": g.accion.value,
                    "Inscritos Estimados": g.inscritos_estimados,
                    "Cupo Asignado": g.cupo_asignado,
                    "Atípico / Protegido": "Sí" if g.es_atipico else "No",
                    "Justificación": g.justificacion,
                })
        df_detalle = pd.DataFrame(filas_detalle)

        def highlight_accion(val):
            if val == "CONSERVAR":
                return "background-color: #d1e7dd; color: #0f5132; font-weight: bold;"
            elif val == "ABRIR":
                return "background-color: #cfe2ff; color: #084298; font-weight: bold;"
            elif val == "CERRAR":
                return "background-color: #f8d7da; color: #842029; font-weight: bold;"
            return ""

        if not df_detalle.empty:
            styled_df = df_detalle.style.map(highlight_accion, subset=["Acción"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info(
                "ℹ️ No se encontraron grupos que coincidan con el criterio de búsqueda o acción seleccionada. "
                "Prueba limpiando el texto de búsqueda o eligiendo 'Todas las acciones'."
            )

    # Pestaña 3: Diagnóstico de Sobrecupo y Cierres
    with tab3:
        st.subheader("Diagnóstico de Capacidad y Quiebre")
        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown("#### 🚨 Materias con Sobrecupo (Requieren Nuevos Grupos)")
            sobresaturadas = [r for r in resumenes_mostrados if r.delta_grupos > 0]
            if sobresaturadas:
                for s in sobresaturadas:
                    st.warning(
                        f"**{s.materia} [{s.turno.value}]**: Matrícula de **{s.demanda_total}** alumnos "
                        f"excede la capacidad absorbible de los {s.grupos_actuales} grupos actuales. "
                        f"Se sugiere abrir **{s.delta_grupos}** nuevo(s) grupo(s)."
                    )
            else:
                st.success("No hay materias que requieran apertura de nuevos grupos con la configuración actual.")

        with col_der:
            st.markdown("#### 📉 Materias Subutilizadas (Candidatas a Consolidación / Cierre)")
            subutilizadas = [r for r in resumenes_mostrados if r.delta_grupos < 0]
            if subutilizadas:
                for u in subutilizadas:
                    st.info(
                        f"**{u.materia} [{u.turno.value}]**: Matrícula de **{u.demanda_total}** alumnos. "
                        f"Se sugiere consolidar **{abs(u.delta_grupos)}** grupo(s) "
                        f"para optimizar la asignación docente."
                    )
            else:
                st.success("No hay grupos sobrantes para cierre en la selección actual.")

    # Pestaña 4: Semáforo de Tiras (Unificado por semestre y turno)
    with tab4:
        st.subheader("🚦 Diagnóstico de Paquetes Curriculares por Semestre y Turno")
        st.caption(
            "Identifica si los alumnos que inscriben un semestre completo en un mismo turno encuentran materias "
            "agotadas o saturadas (disponibles ≤ 0), lo que rompe la tira reglamentaria."
        )

        turno_filtro_enum: Optional[Turno] = None
        if filtro_turno == "Matutino (M)":
            turno_filtro_enum = Turno.M
        elif filtro_turno == "Vespertino (V)":
            turno_filtro_enum = Turno.V
        elif filtro_turno == "Mixto / Admin (X)":
            turno_filtro_enum = Turno.X

        nombres_turno = {
            Turno.M: "Matutino (M)",
            Turno.V: "Vespertino (V)",
            Turno.X: "Mixto / Admin (X)",
        }

        diagnosticos_tiras = evaluar_semaforo_tiras(grupos_input, filtro_turno=turno_filtro_enum)

        if diagnosticos_tiras:
            for tira in diagnosticos_tiras:
                sem = tira["semestre"]
                t_enum = tira["turno"]
                t_label = nombres_turno.get(t_enum, t_enum.value)
                total_g = tira["total_grupos"]
                sat_g = tira["grupos_saturados"]
                mat_sat = ", ".join(tira["materias_saturadas"])

                if tira["estado"] == "VERDE":
                    st.success(
                        f"🟢 **Semestre {sem} — Turno {t_label} [Tira Fluida / Libre]**: "
                        f"Todas las materias tienen cupo disponible ({total_g} grupo(s) evaluados)."
                    )
                elif tira["estado"] == "AMARILLO":
                    st.warning(
                        f"🟡 **Semestre {sem} — Turno {t_label} [Tira Comprometida]**: "
                        f"{sat_g} de {total_g} grupo(s) tienen cupo agotado (disponibles ≤ 0): {mat_sat}"
                    )
                else:
                    st.error(
                        f"🔴 **Semestre {sem} — Turno {t_label} [Tira Bloqueada]**: "
                        f"Todas las materias/grupos ({sat_g} de {total_g}) están saturados o con sobrecupo negativo: {mat_sat}"
                    )
        else:
            st.info("No hay bloques de semestre y turno para mostrar con el filtro seleccionado.")
else:
    st.info("Por favor ingresa datos pegados del SAES o carga un archivo para iniciar la optimización.")

# 6. Pie de Página Institucional con Preguntas Frecuentes (FAQs) y acceso al Tour Guiado
st.divider()
col_faq_header, col_faq_btn = st.columns([4, 1])
with col_faq_header:
    st.subheader("❓ Preguntas Frecuentes (FAQs) y Soporte Académico")
    st.caption("Guía rápida de interpretación para Academias y Jefaturas de Departamento — ESCOM IPN")
with col_faq_btn:
    st.write("")
    st.button(
        "🎓 Ver Tour Guiado",
        key="btn_footer_tour",
        on_click=_on_abrir_tutorial_click,
        use_container_width=True,
        help="Reabre el tutorial paso a paso desde el inicio conservando todos los datos actuales.",
    )

with st.expander("1. ¿RACO se conecta, lee o modifica algo directamente en el SAES?", expanded=False):
    st.markdown(
        "**No.** RACO opera de forma **100% independiente y no invasiva** sobre la tabla que el usuario copia desde "
        "su navegador (`Ctrl+C` / `Ctrl+V`) o sube en formato `.csv` / `.xlsx`. No solicita contraseñas, no requiere "
        "permisos especiales ni realiza consultas automatizadas al servidor del SAES."
    )

with st.expander("2. ¿Por qué un grupo con 37 alumnos y cupo de 36 no recomienda abrir otro grupo?", expanded=False):
    st.markdown(
        "Porque RACO aplica por defecto una **Tolerancia de Sobrecupo ($\\tau = 2$)** bajo el modelo de *Cupo Blando* "
        "(**ADR-0002**). Este margen absorbe excedentes mínimos de 1 o 2 estudiantes ($\\text{Capacidad Efectiva} = \\text{Cupo} + \\tau$) "
        "para evitar abrir grupos nuevos antieconómicos o subutilizados por un solo alumno extra. Cuando el excedente "
        "supera la tolerancia $\\tau$, RACO sí recomienda **`ABRIR`** una nueva sección."
    )

with st.expander("3. ¿Cómo protege RACO los Laboratorios y Trabajo Terminal (Turno X)?", expanded=False):
    st.markdown(
        "El motor identifica y aísla automáticamente los grupos con capacidad especial (**`Atípico / Protegido = Sí`**):\n"
        "- **Laboratorios (ej. 18 plazas):** Respeta su límite físico de equipamiento ($\\le 60\\%$ del cupo modal) para no saturar espacios especializados.\n"
        "- **Trabajo Terminal / Estancia Profesional (`Turno X`, 250+ plazas):** Los protege como macro-grupos administrativos para que nunca se sugiera su cierre automático aunque temporalmente registren `0` inscritos en el SAES."
    )

with st.expander("4. ¿Qué significa cuando el SAES muestra disponibles negativos (-1, -2) o discrepancias?", expanded=False):
    st.markdown(
        "Durante las inscripciones y reinscripciones reales, el SAES permite altas manuales por encima del cupo nominal "
        "del aula, lo que genera valores negativos en la columna `Disponibles` (ya que $\\text{Disponibles} = \\text{Cupo} - \\text{Inscritos}$). "
        "RACO procesa nativamente estos sobrecupos calculando la demanda real como $\\max(\\text{inscritos}, \\text{cupo} - \\text{disponibles})$ "
        "y reporta cualquier inconsistencia aritmética de origen sin alterar el dato original."
    )

with st.expander("5. ¿Para qué sirve el Sello Criptográfico SHA-256 en el Excel descargable?", expanded=False):
    st.markdown(
        "El archivo `.xlsx` oficial incluye en su primera pestaña (*Carátula y Supuestos*) una firma digital **SHA-256** "
        "de 64 caracteres hexadecimales calculada directamente sobre los datos de entrada del SAES. Este sello certifica "
        "ante la Subdirección Académica y las Academias que las cifras base no fueron alteradas manualmente."
    )

st.caption(
    "ESCOM — Instituto Politécnico Nacional · RACO (Recomendador de Apertura y Cierre de Oferta) · "
    "Herramienta de apoyo a la decisión académica (sin conexión directa al SAES)."
)
