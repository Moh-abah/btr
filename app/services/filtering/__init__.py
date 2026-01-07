from .core import FilteringEngine
from .schemas import FilterCriteria, FilterResult, FilterRule, CompositeFilter

__all__ = [
    "FilteringEngine",
    "FilterCriteria",
    "FilterResult",
    "FilterRule",
    "CompositeFilter"
]

# إنشاء كائن FilteringEngine عالمي
_filtering_engine = None

def get_filtering_engine() -> FilteringEngine:
    """الحصول على كائن FilteringEngine"""
    global _filtering_engine
    if _filtering_engine is None:
        _filtering_engine = FilteringEngine()
    return _filtering_engine