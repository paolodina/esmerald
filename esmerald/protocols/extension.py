from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

if TYPE_CHECKING:
    from esmerald.types import ASGIApp


@runtime_checkable
class ExtensionProtocol(Protocol):  # pragma: no cover
    def __init__(self, app: "ASGIApp"):
        ...

    def plug(self, app: "ASGIApp", kwargs: Any) -> None:
        ...
