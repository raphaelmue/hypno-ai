import sys
import traceback

try:
    from hypnoai.sidecar import main
    main()
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
