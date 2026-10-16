"""Hardware transport contract. Intentionally no unverified commands."""
from abc import ABC, abstractmethod

class DSPTransport(ABC):
    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def disconnect(self): ...
    @abstractmethod
    def read_state(self): ...
    @abstractmethod
    def write_parameter(self, channel, parameter, value): ...

class DemoTransport(DSPTransport):
    def connect(self): return True
    def disconnect(self): return None
    def read_state(self): return None
    def write_parameter(self, channel, parameter, value): return None
