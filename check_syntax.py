import ast
import sys
from pathlib import Path


def main() -> int:
    code = 0
    for item in sys.argv[1:]:
        path = Path(item)
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            print(f"OK {path}")
        except Exception as exc:
            print(f"ERR {path}: {exc}")
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
