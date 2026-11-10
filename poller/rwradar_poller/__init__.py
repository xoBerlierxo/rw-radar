"""RW Radar poller: fetches ATS job boards and news RSS, diffs them against Firestore, writes the
changes and sends FCM topic pushes. Run as ``python -m rwradar_poller`` from ``poller/``.
See CLAUDE.md §4 for the data contracts and PLAN.md §4 for the algorithms.
"""

__version__ = "0.1.0"
