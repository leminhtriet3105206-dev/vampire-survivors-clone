"""Generic high-performance Object Pool to eliminate GC pauses and memory churn."""
from typing import Callable, Generic, List, Optional, TypeVar

T = TypeVar("T")


class ObjectPool(Generic[T]):
    """
    Generic Object Pool.
    Maintains a free list of recycled instances to eliminate dynamic memory allocation
    and garbage collection pressure during high-action gameplay (1000+ entities).
    """

    __slots__ = ("_factory", "_free_list", "_max_size", "_created_count", "_active_count")

    def __init__(self, factory: Callable[[], T], initial_capacity: int = 128, max_size: int = 4096):
        self._factory: Callable[[], T] = factory
        self._max_size: int = max(initial_capacity, max_size)
        self._free_list: List[T] = []
        self._created_count: int = 0
        self._active_count: int = 0

        # Warm-up pre-allocation
        for _ in range(initial_capacity):
            obj = self._factory()
            setattr(obj, "_pooled", True)
            self._free_list.append(obj)
            self._created_count += 1

    def acquire(self, *args, **kwargs) -> T:
        """
        Acquire an instance from the pool.
        Calls `reset(*args, **kwargs)` on the object if available.
        """
        if self._free_list:
            obj = self._free_list.pop()
        else:
            obj = self._factory()
            self._created_count += 1

        setattr(obj, "_pooled", False)
        self._active_count += 1

        reset_fn = getattr(obj, "reset", None)
        if callable(reset_fn):
            reset_fn(*args, **kwargs)

        return obj

    def release(self, obj: T) -> bool:
        """
        Return an instance to the pool.
        Guards against duplicate releases. Returns True if returned, False if ignored/capped.
        """
        if getattr(obj, "_pooled", False):
            # Already in pool, avoid double release
            return False

        setattr(obj, "_pooled", True)
        self._active_count = max(0, self._active_count - 1)

        if len(self._free_list) < self._max_size:
            self._free_list.append(obj)
            return True
        return False

    def release_many(self, objects: List[T]) -> int:
        """Bulk release a collection of objects back to the pool."""
        released = 0
        for obj in objects:
            if self.release(obj):
                released += 1
        return released

    @property
    def available_count(self) -> int:
        """Number of ready-to-use instances currently in the pool."""
        return len(self._free_list)

    @property
    def active_count(self) -> int:
        """Number of instances currently acquired and active in the game world."""
        return self._active_count

    @property
    def total_created(self) -> int:
        """Total instances ever allocated by this pool."""
        return self._created_count

    def clear(self) -> None:
        """Clear all pooled objects."""
        self._free_list.clear()
        self._active_count = 0

