from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class Turno(str, Enum):
    M = "M"
    V = "V"


class GrupoInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    materia: str = Field(..., min_length=1, description="Nombre de la unidad de aprendizaje")
    grupo: str = Field(..., min_length=1, description="Identificador del grupo (ej. 1CM1)")
    turno: Turno = Field(..., description="Turno escolar (M: Matutino, V: Vespertino)")
    cupo_max: int = Field(default=35, ge=1, description="Cupo máximo de estudiantes")
    inscritos_actuales: int = Field(default=0, ge=0, description="Alumnos inscritos formalmente")
    demanda_estimada: int = Field(default=0, ge=0, description="Demanda proyectada o preinscrita")

