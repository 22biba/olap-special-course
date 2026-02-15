"""
Base agent: all BI agents implement run(context, params) -> result dict.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    @abstractmethod
    def run(self, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
