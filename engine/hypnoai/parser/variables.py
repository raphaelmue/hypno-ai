"""Variable injection for HypnoScript — {{variable}} substitution."""
from __future__ import annotations

import re
import warnings

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def inject_variables(text: str, variables: dict[str, str]) -> str:
    """Replace {{var}} placeholders with values from the variables dict.

    Undefined variables emit a UserWarning and are left unchanged in the
    output so the author can spot them easily.

    Per the design spec (§2.4), variable injection runs *before* directive
    parsing, so call this on the raw script source before passing to parse().
    """

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            warnings.warn(
                "Undefined variable {{" + key + "}}: no value provided. "
                "The placeholder will remain in the output.",
                UserWarning,
                stacklevel=3,
            )
            return match.group(0)  # leave unchanged
        return str(variables[key])

    return _VAR_RE.sub(replace, text)


def find_variables(text: str) -> list[str]:
    """Return a list of every variable name referenced in text (including duplicates)."""
    return _VAR_RE.findall(text)
