"""Single source of truth for the application version.

Bump this when cutting a release and tag the commit ``v<this value>`` so the
GitHub Actions release workflow builds matching binaries. The in-app update
checker (:mod:`updater`) compares this against the newest GitHub Release.
"""

__version__ = "1.5.3"
