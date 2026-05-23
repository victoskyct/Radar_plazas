from dataclasses import dataclass
from datetime import datetime


@dataclass
class Plaza:
    universidad: str        # "UMH", "UMU", "UPCT", "UAL"
    titulo: str
    fecha: datetime
    enlace: str
    referencia: str | None = None   # e.g. "00080/2026"
    tipo: str | None = None         # "ASO", "AYUDOC", "PPL", "TU", "CU", …
    descripcion: str | None = None
    fuente: str | None = None       # nombre de la sección/web de origen

    def uid(self) -> str:
        """Identificador único estable para detectar novedades."""
        return f"{self.universidad}::{self.enlace}"
