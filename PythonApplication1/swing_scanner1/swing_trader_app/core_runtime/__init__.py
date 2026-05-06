"""Runtime support modules executed into app_runtime globals.

These files contain extracted helper/constants sections from the original
working monolith. app_runtime loads them with exec(..., globals()) so the
functions keep the same global namespace as the original single-file app.
"""
