"""ACE device adapter for the xarm-vision simulator.

This file is *only* the ACE integration layer.  All business logic lives in
``xarm_vision.core.XArmVisionCore`` (a plain Python class with no ACE
dependencies).  When ACE loads this device it gets a ``SimulatorDevice``
implementation; under the hood every operation is delegated to the core
simulator.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from ace.core.simulator.base import DeviceState, OperationResult, SimulatorDevice

# Ensure repo root is on sys.path so ``xarm_vision`` is importable regardless
# of where ACE loads this device from.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xarm_vision.core import XArmVisionCore  # noqa: E402


class XArmVisionSimulator(SimulatorDevice):
    """ACE-compatible wrapper around ``XArmVisionCore``."""

    def __init__(self, simulator_id: str = "xarm-vision", **kwargs: Any) -> None:
        super().__init__(simulator_id=simulator_id, device_type="RoboticArm")
        self._core = XArmVisionCore()

    # ------------------------------------------------------------------
    # Abstract properties (pulled from core)
    # ------------------------------------------------------------------
    @property
    def vendor(self) -> str:
        return self._core.vendor

    @property
    def model(self) -> str:
        return self._core.model

    @property
    def description(self) -> str:
        return self._core.description

    @property
    def capabilities(self) -> list[str]:
        return self._core.capabilities

    # ------------------------------------------------------------------
    # Lifecycle (forward to core + sync state back into ACE)
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self._core.connect()
        self._connected = True
        self._state = DeviceState(properties=self._core._state)

    def disconnect(self) -> None:
        self._core.disconnect()
        self._connected = False

    # ------------------------------------------------------------------
    # Operations — delegate to core and wrap result for ACE
    # ------------------------------------------------------------------
    async def execute_operation(
        self, operation: str, params: dict[str, Any]
    ) -> OperationResult:
        if not self._connected:
            return OperationResult(
                success=False,
                operation=operation,
                error="Device not connected",
            )

        handler = {
            "move": self._core.move,
            "grab": self._core.grab,
            "release": self._core.release,
            "take_photo": self._core.take_photo,
            "detect_object": self._core.detect_object,
        }.get(operation)

        if handler is None:
            return OperationResult(
                success=False,
                operation=operation,
                error=f"Unsupported operation: {operation}",
            )

        start = time.time()
        raw = handler(params)
        duration = time.time() - start

        # Sync any state changes made by the core back into ACE's DeviceState.
        if "state_delta" in raw:
            for key, delta in raw["state_delta"].items():
                if isinstance(delta, dict) and "to" in delta:
                    self._state.set(key, delta["to"])
                else:
                    self._state.set(key, delta)

        return OperationResult(
            success=raw.get("success", False),
            operation=operation,
            output=raw.get("output"),
            error=raw.get("error"),
            state_delta=raw.get("state_delta"),
            duration_seconds=duration,
        )

    # ------------------------------------------------------------------
    # Fault injection (no-op for this mock)
    # ------------------------------------------------------------------
    def inject_fault(self, fault_type: str, severity: float = 0.5) -> None:
        pass
