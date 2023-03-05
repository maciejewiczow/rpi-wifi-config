from typing import Any, Callable, Dict, Iterable, Optional, TypeVar

T = TypeVar('T')

def find(arr: Iterable[T], what: Optional[T] = None, matcher: Optional[Callable[[T], bool]] = None) -> Optional[T]:
    if what is None and matcher is None:
        raise TypeError("Either what or matcher should be specified")

    try:
        return next(e for e in arr if (what == e if what is not None else matcher(e))) # type: ignore
    except StopIteration:
        return None

def assignDefault(data: Dict[str, Any], key: str, default):
    if key in data:
        return

    data[key] = default

def split(path: str):
    if path == "":
        return ("", "")
    r = path.rsplit("/", 1)
    if len(r) == 1:
        return ("", path)
    head = r[0]  # .rstrip("/")
    if not head:
        head = "/"
    return (head, r[1])


def dirname(path: str):
    return split(path)[0]

def basename(path):
    return split(path)[1]
