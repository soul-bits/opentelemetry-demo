"""Atomic read/write helpers for ``src/flagd/demo.flagd.json``.

Provides ``read_flags``, ``write_flags``, and ``restore_from_backup`` with
``tempfile + os.replace`` semantics, preserving unrelated flags byte-for-
byte so Property 11 (flagd round-trip) holds. Populated by task 2.2.
"""
