def size_to_bytes(size):
    """
    Convert a human-readable size (e.g., 2g, 10M, 512k) to bytes.
    """
    size = str(size).strip().lower()
    units = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
    if size[-1] in units:
        return int(float(size[:-1]) * units[size[-1]])
    return int(size)

class FilterModule(object):
    def filters(self):
        return {
            "size_to_bytes": size_to_bytes,
        }