import sys
import traceback

try:
    from . import main
    main()
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
