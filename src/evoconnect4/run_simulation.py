"""Phase 0 stub entry point: proves config + package wiring end-to-end.

No real game, agent, or evolution logic runs here yet — see the project
plan's roadmap (plans/evoconnect4_project_plan.md §11) for later phases.
"""

from __future__ import annotations

import dataclasses

from evoconnect4 import agent, analytics, evolution, game, interface, storage
from evoconnect4.config import load_config

_SUBPACKAGES = (game, agent, evolution, storage, interface, analytics)


def main() -> None:
    config = load_config()

    print(f"Imported subpackages: {', '.join(m.__name__ for m in _SUBPACKAGES)}")
    print("Resolved config:")
    for field, value in dataclasses.asdict(config).items():
        print(f"  {field} = {value}")


if __name__ == "__main__":
    main()
