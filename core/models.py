from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Turno(str, Enum):
    M = "M"
    V = "V"
    X = "X"


class GrupoInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    materia: str = Field(..., min_length=1, description="Nombre de la unidad de aprendizaje")
    grupo: str = Field(..., min_length=1, description="Identificador del grupo (ej. 1CM1)")
    turno: Turno = Field(..., description="Turno escolar (M: Matutino, V: Vespertino, X: Mixto/Admin)")
    cupo_max: int = Field(default=35, ge=1, description="Cupo máximo de estudiantes")
    inscritos_actuales: int = Field(default=0, ge=0, description="Alumnos inscritos formalmente")
    demanda_estimada: int = Field(default=0, ge=0, description="Demanda proyectada o preinscrita")
    materia_id: Optional[str] = Field(default=None, description="Clave de materia SAES")
    semestre: Optional[int] = Field(default=None, description="Semestre lectivo")
    carrera: Optional[str] = Field(default=None, description="Sigla de la carrera")


class AccionGrupo(str, Enum):
    CONSERVAR = "CONSERVAR"
    ABRIR = "ABRIR"
    CERRAR = "CERRAR"
    FUSIONAR = "FUSIONAR"


class OptimizacionGrupo(BaseModel):
    model_config = ConfigDict(frozen=True)

    grupo_id: str
    materia: str
    turno: Turno
    inscritos_estimados: int = Field(..., ge=0)
    cupo_asignado: int = Field(..., gt=0)
    accion: AccionGrupo
    justificacion: str
    es_atipico: bool = Field(default=False, description="Indica si el grupo tiene cupo atípico protegido")


class ResumenMateria(BaseModel):
    materia: str
    turno: Turno
    demanda_total: int
    grupos_actuales: int
    grupos_propuestos: int
    delta_grupos: int
    cupo_promedio: float
    grupos: List[OptimizacionGrupo]
