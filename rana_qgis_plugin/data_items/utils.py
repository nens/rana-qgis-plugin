"""Shared helpers for Rana Browser data items."""


def get_loader_from_parent(parent):
    """Return the loader exposed by a parent data item."""
    if parent is None:
        raise RuntimeError("Rana data item has no parent")
    return parent.loader
