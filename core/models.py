from dataclasses import dataclass, field
from typing import List, Dict, Any


def _num_fallback(row, chave, padrao):
    try:
        v = row.get(chave)
        return int(float(v)) if v not in (None, '') else padrao
    except Exception:
        return padrao

@dataclass
class Pad:
    id: int
    cx: int
    cy: int
    w: int = 12
    h: int = 12
    area: int = 100
    manual: bool = False
    @property
    def x(self): return self.cx
    @property
    def y(self): return self.cy
    def to_dict(self): return {"id": self.id, "cx": self.cx, "cy": self.cy, "x": self.cx, "y": self.cy, "w": self.w, "h": self.h, "area": self.area, "manual": self.manual}
    @staticmethod
    def from_csv_row(row: dict):
        return Pad(id=_num_fallback(row, 'id', 0), cx=_num_fallback(row, 'x', 0), cy=_num_fallback(row, 'y', 0), w=_num_fallback(row, 'w', 12), h=_num_fallback(row, 'h', 12), area=_num_fallback(row, 'area', 100), manual=row.get('manual', 'N') == 'S')

@dataclass
class Net:
    id: int
    nome: str
    pads: List[int] = field(default_factory=list)
    cor: List[int] = field(default_factory=lambda: [80,140,255])
    def to_dict(self): return {"id": self.id, "nome": self.nome, "pads": self.pads, "cor": self.cor}

@dataclass
class Componente:
    id: int
    nome: str
    tipo: str
    forma: str
    x1: int; y1: int; x2: int; y2: int
    pads: List[int] = field(default_factory=list)
    cor: List[int] = field(default_factory=lambda: [80,140,255])
    valor: str = ""; tensao: str = ""; obs: str = ""; sugestao: str = ""
