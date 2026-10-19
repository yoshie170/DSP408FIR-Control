"""Public release and Windows build revision. No runtime dependencies."""
VERSION = '0.9.1'
BUILD = 163
WINDOWS_VERSION = tuple(map(int, VERSION.split('.'))) + (BUILD,)
