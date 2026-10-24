from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.exporter import generar_dictamen_excel
from core.models import AccionGrupo, GrupoInput, ResumenMateria, Turno
from core.parser import parse_academic_data, parse_saes_clipboard_text
from core.rules import aplicar_techo_global, optimizar_materia_turno

# 1. Configuración Institucional
st.set_page_config(
    page_title="RACO | ESCOM-IPN",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎓 RACO: Risk-Adjusted Capacity Optimizer")
st.caption("Optimización de Cupos y Oferta Académica — Escuela Superior de Cómputo (ESCOM IPN)")
st.divider()

# 2. Barra Lateral de Simulación (Sidebar)
st.sidebar.header("📥 Ingesta de Datos")

metodo_ingesta = st.sidebar.radio(
    "Método de Entrada:",
    options=["Pegar desde SAES (Portapapeles)", "Subir archivo (.csv / .xlsx)"],
    index=0,
)

grupos_input: List[GrupoInput] = []
demanda_agregada: Dict[Tuple[str, Turno], int] = {}
df_clipboard_raw: pd.DataFrame = pd.DataFrame()
hubo_error_ingesta = False
raw_source_content = ""

if metodo_ingesta == "Pegar desde SAES (Portapapeles)":
    raw_clipboard = st.sidebar.text_area(
        "Copiar y pegar reporte del SAES:",
        height=180,
        placeholder=(
            "1AM1\tA101\tCALCULO MULTIVARIABLE\t35\t36\t-1\n"
            "3AV2\tA204\tREDES DE COMPUTADORAS\t18\t18\t0\n"
            "5CM1\tB301\tSISTEMAS DISTRIBUIDOS\t7\t0\t7"
        ),
        help="Copia directamente la tabla de ocupación/oferta del SAES y pégala aquí.",
    )
    col_btn1, col_btn2 = st.sidebar.columns([1, 1])
    cargar_ejemplo = col_btn2.button("Ejemplo SAES", use_container_width=True)

    if cargar_ejemplo and not raw_clipboard:
        raw_clipboard = (
            "1CM1\tA101\tCALCULO\t35\t35\t0\n"
            "1CV1\tA101\tCALCULO\t35\t37\t-2\n"
            "1CM2\tA102\tALGEBRA LINEAL\t35\t33\t2\n"
            "1CV2\tA102\tALGEBRA LINEAL\t35\t12\t23\n"
            "3CV1\tA204\tREDES\t35\t31\t4\n"
            "1LM1\tQ101\tLABORATORIO QUIMICA\t18\t18\t0\n"
            "4CM1\tA405\tCOMPILADORES\t35\t14\t21\n"
            "4CV1\tA405\tCOMPILADORES\t35\t10\t25"
        )

    raw_source_content = raw_clipboard
    if raw_clipboard.strip():
        try:
            df_clipboard_raw = parse_saes_clipboard_text(raw_clipboard)
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
                    )
                    grupos_input.append(g_obj)
                    key = (g_obj.materia, g_obj.turno)
                    demanda_agregada[key] = demanda_agregada.get(key, 0) + g_obj.demanda_estimada
            else:
                st.sidebar.warning("⚠️ No se detectaron filas válidas en el texto pegado.")
        except Exception as e:
            st.sidebar.error(f"❌ Error al procesar portapapeles: {e}")
            hubo_error_ingesta = True
else:
    uploaded_file = st.sidebar.file_uploader(
        "Cargar Oferta / Demanda (.csv, .xlsx)",
        type=["csv", "xlsx", "xls"],
        help="Archivo con columnas: materia, grupo, turno, cupo_max, inscritos_actuales, demanda_estimada",
    )
    btn_sintetico = st.sidebar.button("Cargar sintéticos de ESCOM", use_container_width=True)

    default_csv = Path("data/synthetic_escom.csv")
    file_to_parse = None

    if uploaded_file is not None:
        file_to_parse = uploaded_file
        raw_source_content = uploaded_file.name
    elif btn_sintetico or "loaded_synthetic" in st.session_state or default_csv.exists():
        st.session_state["loaded_synthetic"] = True
        file_to_parse = default_csv
        raw_source_content = default_csv.read_text(encoding="utf-8") if default_csv.exists() else "synthetic"

    if file_to_parse:
        try:
            grupos_input, demanda_agregada = parse_academic_data(file_to_parse)
        except Exception as e:
            st.sidebar.error(f"❌ Error al procesar archivo: {e}")
            hubo_error_ingesta = True

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

# Filtro de turno
filtro_turno = st.sidebar.selectbox(
    "Filtro de Turno",
    options=["Todos", "Matutino (M)", "Vespertino (V)"],
    index=0,
)

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
    else:
        resumenes_mostrados = resumenes_finales

    # 4. Sección de Métricas Clave (KPIs superiores)
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
        "Delta de Grupos",
        f"{kpi_delta:+d}",
        delta=kpi_delta,
        delta_color="normal",
    )
    col4.metric(
        "Alumnos Atendidos",
        f"{kpi_alumnos_atendidos} / {kpi_demanda_total}",
        f"{(kpi_alumnos_atendidos / kpi_demanda_total * 100):.1f}%" if kpi_demanda_total > 0 else "0%",
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

    # 4.1 Generación y Botón de Descarga del Dictamen Oficial en Excel
    tz_cdmx = ZoneInfo("America/Mexico_City")
    timestamp_dt = datetime.now(tz_cdmx)
    timestamp_str = timestamp_dt.strftime("%Y%m%d_%H%M%S")

    parametros_dictamen = {
        "tolerancia_tau": tolerancia_tau,
        "override_cupo": override_cupo_val,
        "horas_materia": horas_por_materia,
        "timestamp": timestamp_str,
        "git_commit_tag": "v1.2-ADR0002",
    }

    excel_bytes = generar_dictamen_excel(
        raw_input_text=raw_source_content,
        optimizaciones=resumenes_finales,
        grupos_input=grupos_input,
        parametros=parametros_dictamen,
        alertas_saes=alertas_saes_list,
    )

    st.sidebar.divider()
    st.sidebar.subheader("📄 Exportación Oficial")
    st.sidebar.download_button(
        label="📥 Descargar Dictamen Técnico Oficial (.xlsx)",
        data=excel_bytes,
        file_name=f"Dictamen_RACO_ESCOM_{timestamp_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.write("")

    # 5. Pestañas de Visualización
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
                "Demanda Total": r.demanda_total,
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

    # Pestaña 2: Detalle Operativo por Grupo
    with tab2:
        st.subheader("Oferta Detallada por Grupo")
        filas_detalle = []
        for r in resumenes_mostrados:
            for g in r.grupos:
                filas_detalle.append({
                    "Materia": g.materia,
                    "Turno": g.turno.value,
                    "Grupo ID": g.grupo_id,
                    "Acción": g.accion.value,
                    "Inscritos Estimados": g.inscritos_estimados,
                    "Cupo Asignado": g.cupo_asignado,
                    "Atípico / Protegido": "Sí (Lab)" if g.es_atipico else "No",
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
            st.info("No hay grupos para mostrar con el filtro seleccionado.")

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
                        f"**{s.materia} [{s.turno.value}]**: Demanda de **{s.demanda_total}** alumnos "
                        f"excede la capacidad absorbible de los {s.grupos_actuales} grupos actuales. "
                        f"Se abren **{s.delta_grupos}** nuevo(s) grupo(s)."
                    )
            else:
                st.success("No hay materias que requieran apertura de nuevos grupos con la configuración actual.")

        with col_der:
            st.markdown("#### 📉 Materias Subutilizadas (Candidatas a Consolidación / Cierre)")
            subutilizadas = [r for r in resumenes_mostrados if r.delta_grupos < 0]
            if subutilizadas:
                for u in subutilizadas:
                    st.info(
                        f"**{u.materia} [{u.turno.value}]**: Demanda de **{u.demanda_total}** alumnos. "
                        f"Se sugiere cerrar/consolidar **{abs(u.delta_grupos)}** grupo(s) "
                        f"para optimizar la asignación docente."
                    )
            else:
                st.success("No hay grupos sobrantes para cierre en la selección actual.")

    # Pestaña 4: Semáforo de Tiras
    with tab4:
        st.subheader("🚦 Diagnóstico de Paquetes Curriculares por Semestre y Turno")
        st.caption(
            "Identifica si los alumnos que inscriben un semestre completo en un mismo turno encuentran materias "
            "agotadas o saturadas (disponibles ≤ 0), lo que rompe la tira reglamentaria."
        )

        if not df_clipboard_raw.empty and "semestre" in df_clipboard_raw.columns:
            df_tiras = df_clipboard_raw.copy()
            if filtro_turno == "Matutino (M)":
                df_tiras = df_tiras[df_tiras["turno"] == Turno.M]
            elif filtro_turno == "Vespertino (V)":
                df_tiras = df_tiras[df_tiras["turno"] == Turno.V]

            semestres_disponibles = sorted(df_tiras["semestre"].unique())

            if semestres_disponibles:
                for sem in semestres_disponibles:
                    df_sem = df_tiras[df_tiras["semestre"] == sem]
                    materias_saturadas = df_sem[df_sem["disponibles"] <= 0]
                    total_materias = len(df_sem)
                    num_bloqueadas = len(materias_saturadas)

                    if num_bloqueadas == 0:
                        status_color = "🟢"
                        mensaje = f"Semestre {sem} completo: Todas las materias tienen cupo disponible."
                        st.success(f"{status_color} **Semestre {sem}**: {mensaje} ({total_materias} grupos evaluados)")
                    elif num_bloqueadas < total_materias:
                        status_color = "🟡"
                        st.warning(
                            f"{status_color} **Semestre {sem} [Tira en Riesgo]**: {num_bloqueadas} de {total_materias} "
                            f"materias tienen cupo agotado (disponibles ≤ 0): {', '.join(materias_saturadas['nombre_materia'].unique())}"
                        )
                    else:
                        status_color = "🔴"
                        st.error(
                            f"{status_color} **Semestre {sem} [Tira Bloqueada]**: Todas las materias ({num_bloqueadas}) "
                            f"están saturadas o con sobrecupo negativo."
                        )
            else:
                st.info("No hay datos de semestre para mostrar con el filtro actual.")
        else:
            filas_tira = []
            for g in grupos_input:
                sem_char = g.grupo[0]
                semestre = int(sem_char) if sem_char.isdigit() else 1
                disponibles_est = g.cupo_max - g.demanda_estimada
                filas_tira.append({
                    "semestre": semestre,
                    "turno": g.turno,
                    "materia": g.materia,
                    "grupo": g.grupo,
                    "disponibles": disponibles_est,
                })
            df_fallback = pd.DataFrame(filas_tira)
            if filtro_turno == "Matutino (M)":
                df_fallback = df_fallback[df_fallback["turno"] == Turno.M]
            elif filtro_turno == "Vespertino (V)":
                df_fallback = df_fallback[df_fallback["turno"] == Turno.V]

            for sem in sorted(df_fallback["semestre"].unique()):
                df_sem = df_fallback[df_fallback["semestre"] == sem]
                saturadas = df_sem[df_sem["disponibles"] <= 0]
                if len(saturadas) == 0:
                    st.success(f"🟢 **Semestre {sem}**: Tira completa sin quiebre de cupo.")
                else:
                    st.warning(
                        f"🟡 **Semestre {sem} [Tira Comprometida]**: Materias con sobrecupo estimado: "
                        f"{', '.join(saturadas['materia'].unique())}"
                    )
else:
    st.info("Por favor ingresa datos pegados del SAES o carga un archivo para iniciar la optimización.")
