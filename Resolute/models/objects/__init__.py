from typing import Callable, TypeVar, Generic

T = TypeVar("T")


class RelatedList(Generic[T], list):
    def __init__(self, obj: T, update_func: Callable[[], None], *args):
        self.obj = obj
        self.update_func = update_func
        super().__init__(*args)

    def update(self):
        self.update_func()

    def append(self, item):
        super().append(item)
        self.update()

    def extend(self, items):
        super().extend(items)
        self.update()

    def insert(self, index, item):
        super().insert(index, item)
        self.update()

    def remove(self, item):
        super().remove(item)

        self.update()

    def pop(self, index=-1):
        item = super().pop(index)
        self.update()
        item

    def clear(self):
        super().clear()
        self.update()

    def __setitem__(self, index, item):
        super().__setitem__(index, item)
        self.update()

    def __delitem__(self, index):
        super().__delitem__(index)
        self.update()
