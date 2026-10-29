"""Read at most one directory entry; no recursion, names returned, or writes."""
import os
import sys


def main(path):
    try:
        with os.scandir(path) as entries:
            next(entries, None)
    except OSError:
        return 'unavailable'
    return 'available'


if __name__ == '__main__':
    sys.stdout.write(main(sys.argv[1]))
