"""Entry point for `python -m claimsense_agent`.

sys.exit(main()) — NOT a bare main().

This was `main()` alone, and the effect was as bad as a bug gets here: the eval
gate printed GATE FAILED in red and the process still exited 0. CI would have
gone green on a red gate, and the one milestone requirement that matters most
— a failing evaluation blocks the image push — would have been decorative.

Caught by deliberately regressing three eval cases and checking $? rather than
reading the output. A gate is only a gate if something downstream can tell.
"""
import sys

from .cli import main

sys.exit(main())
