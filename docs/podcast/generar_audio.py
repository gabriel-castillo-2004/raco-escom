"""Script generador del Podcast Educativo RACO (ESCOM - IPN).

Lee el guion maestro en Markdown (`docs/podcast/guion_podcast_raco.md`),
limpia las marcas de formato para una locución fluida y sintetiza el archivo
MP3 (`docs/podcast/RACO_Audio_Guia_Maestra.mp3`) utilizando la voz neuronal
mexicana `es-MX-JorgeNeural` a través de `edge-tts`.
"""

import asyncio
import pathlib
import re
import edge_tts

VOICE = "es-MX-JorgeNeural"
BASE_DIR = pathlib.Path(__file__).resolve().parent
GUION_PATH = BASE_DIR / "guion_podcast_raco.md"
OUTPUT_MP3 = BASE_DIR / "RACO_Audio_Guia_Maestra.mp3"


def limpiar_markdown_para_locucion(texto_md: str) -> str:
    """Convierte el texto Markdown en texto plano optimizado para síntesis de voz."""
    lineas_limpias: list[str] = []

    for linea in texto_md.splitlines():
        strip_line = linea.strip()

        # Ignorar separadores horizontales o líneas vacías consecutivas
        if not strip_line or re.match(r"^[-*_]{3,}$", strip_line):
            lineas_limpias.append("")
            continue

        # Ignorar metadatos técnicos de cabecera del documento
        if strip_line.startswith(("**Título del Episodio:**", "**Voz sugerida:**", "**Audiencia:**")):
            continue

        # Convertir encabezados Markdown en pausas narrativas naturales
        if strip_line.startswith("#"):
            titulo = re.sub(r"^#+\s*", "", strip_line)
            if not titulo.endswith((".", "?", "!", ":")):
                titulo += "."
            lineas_limpias.append(titulo)
            continue

        # Limpiar viñetas y listas numeradas al inicio de línea
        strip_line = re.sub(r"^[\*\-]\s+", "", strip_line)

        # Eliminar negritas, cursivas y código inline conservando el contenido
        strip_line = re.sub(r"\*\*(.+?)\*\*", r"\1", strip_line)
        strip_line = re.sub(r"\*(.+?)\*", r"\1", strip_line)
        strip_line = re.sub(r"`(.+?)`", r"\1", strip_line)

        lineas_limpias.append(strip_line)

    texto = "\n".join(lineas_limpias)

    # Ajustes fonéticos para términos técnicos y siglas en español de México
    reemplazos_foneticos = {
        "core/rules.py": "core diagonal rules punto py",
        "core/parser.py": "core diagonal parser punto py",
        "core/models.py": "core diagonal models punto py",
        "core/validators.py": "core diagonal validators punto py",
        "core/exporter.py": "core diagonal exporter punto py",
        "test_parser.py": "test guion bajo parser punto py",
        "test_rules.py": "test guion bajo rules punto py",
        "test_exporter.py": "test guion bajo exporter punto py",
        "app.py": "app punto py",
        "override_cupo": "override guion bajo cupo",
        "calcular_cupo_modal": "calcular guion bajo cupo guion bajo modal",
        "frozen=True": "frozen igual a True",
        "7AX1": "siete A X uno",
        "8AX1": "ocho A X uno",
        "M-NUEVO-2": "M guion NUEVO guion dos",
        "V-NUEVO-2": "V guion NUEVO guion dos",
        "SHA-256": "S H A doscientos cincuenta y seis",
        "pytest": "Pytest",
        "Pytest": "Páitest",
        "Streamlit": "Strimlit",
        "Pydantic": "Paidántic",
    }

    for original, fonetico in reemplazos_foneticos.items():
        texto = texto.replace(original, fonetico)

    # Compactar saltos de línea múltiples
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return texto


async def sintetizar_podcast() -> None:
    """Ejecuta la síntesis de voz con edge-tts y guarda el archivo MP3."""
    if not GUION_PATH.exists():
        raise FileNotFoundError(f"No se encontró el guión en: {GUION_PATH}")

    raw_md = GUION_PATH.read_text(encoding="utf-8")
    texto_locucion = limpiar_markdown_para_locucion(raw_md)

    print(f"Iniciando síntesis con voz neuronal '{VOICE}'...")
    print(f"Longitud del guión limpio: {len(texto_locucion)} caracteres.")

    communicate = edge_tts.Communicate(texto_locucion, voice=VOICE)
    await communicate.save(str(OUTPUT_MP3))

    size_bytes = OUTPUT_MP3.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"Audio generado exitosamente: {OUTPUT_MP3}")
    print(f"Tamaño final: {size_bytes:,} bytes ({size_mb:.2f} MB)")


if __name__ == "__main__":
    asyncio.run(sintetizar_podcast())
