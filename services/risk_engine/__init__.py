"""Risk Engine package.

Importing this package (or anything inside it) triggers factors.py to
import, which runs every @register_factor decorator and populates the
registry. Without this, the registry would stay empty until something
happened to import factors.py directly — an easy, subtle bug to hit.
"""

from services.risk_engine import factors  # noqa: F401  (import triggers registration)
