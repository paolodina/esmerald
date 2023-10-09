import sys
import typing
from inspect import isclass
from typing import Any, Union

import slugify
from starlette._utils import is_async_callable as is_async_callable
from typing_extensions import get_args, get_origin

if sys.version_info >= (3, 10):
    from types import UnionType

    UNION_TYPES = {UnionType, Union}
else:  # pragma: no cover
    UNION_TYPES = {Union}


def is_class_and_subclass(value: typing.Any, _type: typing.Any) -> bool:
    original = get_origin(value)
    if not original and not isclass(value):
        return False

    try:
        if original:
            return original and issubclass(original, _type)
        return issubclass(value, _type)
    except TypeError:
        return False


def clean_string(value: str) -> str:
    return slugify.slugify(value, separator="_")  # type: ignore


def is_optional_union(annotation: Any) -> bool:
    return get_origin(annotation) in UNION_TYPES and type(None) in get_args(annotation)
