
# app/services/cv/state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

@dataclass
class Track:
    id: str
    cls: str
    box: Tuple[int,int,int,int]
    alive: bool = True
    lost: int = 0

@dataclass
class DetectionState:
    device_type: str = "unknown"
    modules: List[Dict[str,Any]] = field(default_factory=list)
    tracks: Dict[str, Track] = field(default_factory=dict)