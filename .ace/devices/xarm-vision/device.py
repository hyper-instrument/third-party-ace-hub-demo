"""XArm-Vision simulator — 6-DOF robotic arm with camera."""

import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ace.core.simulator.base import DeviceState, OperationResult, SimulatorDevice


class XArmVisionSimulator(SimulatorDevice):
    """Mock vision-capable robotic arm simulator.

    Enhancement A: ``take_photo`` renders a scene diagram (PIL) showing arm
    position, visible objects, and the held object.

    Enhancement B: ``move`` updates the held object's position in real time,
    so the object tracks the arm while gripped.
    """

    def __init__(self, simulator_id: str = "xarm-vision", **kwargs: Any) -> None:
        super().__init__(simulator_id=simulator_id, device_type="RoboticArm")
        self._workspace = {"x": (0, 500), "y": (0, 500), "z": (0, 300)}
        self._gripper_force_range = (0, 100)
        self._camera_resolution = (640, 480)

    # ------------------------------------------------------------------
    # Abstract properties
    # ------------------------------------------------------------------
    @property
    def vendor(self) -> str:
        return "MockCorp"

    @property
    def model(self) -> str:
        return "XArm-V1"

    @property
    def description(self) -> str:
        return "6-DOF robotic arm with camera for vision-guided manipulation"

    @property
    def capabilities(self) -> List[str]:
        return ["move", "grab", "release", "take_photo", "detect_object"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self._connected = True
        self._state = DeviceState(
            properties={
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "gripper_open": True,
                "held_object": None,
                "held_object_position": None,
                "objects": [
                    {"name": "red_block", "position": {"x": 100, "y": 100, "z": 10}},
                    {"name": "green_block", "position": {"x": 200, "y": 200, "z": 10}},
                    {"name": "blue_block", "position": {"x": 300, "y": 300, "z": 10}},
                ],
            }
        )

    def disconnect(self) -> None:
        self._connected = False

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    async def execute_operation(
        self, operation: str, params: Dict[str, Any]
    ) -> OperationResult:
        if not self._connected:
            return OperationResult(
                success=False,
                operation=operation,
                error="Device not connected",
            )

        handler = {
            "move": self._op_move,
            "grab": self._op_grab,
            "release": self._op_release,
            "take_photo": self._op_take_photo,
            "detect_object": self._op_detect_object,
        }.get(operation)

        if handler is None:
            return OperationResult(
                success=False,
                operation=operation,
                error=f"Unsupported operation: {operation}",
            )

        start = time.time()
        result = handler(params)
        result.duration_seconds = time.time() - start
        return result

    # ------------------------------------------------------------------
    # Fault injection (no-op for this mock)
    # ------------------------------------------------------------------
    def inject_fault(self, fault_type: str, severity: float = 0.5) -> None:
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_position(self) -> Dict[str, float]:
        return dict(self._state.get("position", {"x": 0.0, "y": 0.0, "z": 0.0}))

    def _set_position(self, pos: Dict[str, float]) -> None:
        self._state.set("position", pos)

    def _distance(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        return math.sqrt(
            (a["x"] - b["x"]) ** 2
            + (a["y"] - b["y"]) ** 2
            + (a["z"] - b["z"]) ** 2
        )

    def _in_workspace(self, pos: Dict[str, float]) -> bool:
        return (
            self._workspace["x"][0] <= pos["x"] <= self._workspace["x"][1]
            and self._workspace["y"][0] <= pos["y"] <= self._workspace["y"][1]
            and self._workspace["z"][0] <= pos["z"] <= self._workspace["z"][1]
        )

    # ------------------------------------------------------------------
    # Rendering helper for take_photo (Enhancement A)
    # ------------------------------------------------------------------
    def _render_scene_image(self, file_path: str) -> None:
        """Render a scene diagram showing arm, objects, and workspace."""
        try:
            from PIL import Image, ImageDraw
        except Exception:
            # Fallback: minimal valid JPEG if PIL unavailable
            with open(file_path, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
            return

        w, h = self._camera_resolution
        img = Image.new("RGB", (w, h), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        # Workspace grid (every 100 units)
        for i in range(0, 501, 100):
            x_p = int(i / 500 * (w - 1))
            draw.line([(x_p, 0), (x_p, h - 1)], fill=(60, 60, 60), width=1)
            y_p = int(i / 500 * (h - 1))
            draw.line([(0, y_p), (w - 1, y_p)], fill=(60, 60, 60), width=1)

        def _wx(x: float) -> int:
            return int(x / 500 * (w - 1))

        def _wy(y: float) -> int:
            return int(y / 500 * (h - 1))

        # Draw objects on the scene
        color_map = {
            "red_block": (255, 60, 60),
            "green_block": (60, 255, 60),
            "blue_block": (60, 60, 255),
        }

        for obj in self._state.get("objects", []):
            p = obj["position"]
            cx, cy = _wx(p["x"]), _wy(p["y"])
            color = color_map.get(obj["name"], (200, 200, 200))
            r = 8
            draw.rectangle(
                [cx - r, cy - r, cx + r, cy + r],
                fill=color,
                outline=(255, 255, 255),
                width=2,
            )
            draw.text((cx + 12, cy - 6), obj["name"], fill=(255, 255, 255))

        # Draw held object (if any) — tracked in real time
        held = self._state.get("held_object")
        if held:
            held_pos = self._state.get("held_object_position") or self._get_position()
            cx, cy = _wx(held_pos["x"]), _wy(held_pos["y"])
            color = color_map.get(held, (255, 255, 255))
            r = 10
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=color,
                outline=(255, 255, 0),
                width=3,
            )
            draw.text(
                (cx + 14, cy - 6),
                f"{held} (held)",
                fill=(255, 255, 0),
            )

        # Draw arm position (red crosshair)
        arm = self._get_position()
        ax, ay = _wx(arm["x"]), _wy(arm["y"])
        draw.line([(ax - 10, ay), (ax + 10, ay)], fill=(255, 0, 0), width=2)
        draw.line([(ax, ay - 10), (ax, ay + 10)], fill=(255, 0, 0), width=2)
        draw.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=(255, 0, 0))
        draw.text(
            (ax + 10, ay + 10),
            f"arm ({arm['x']:.0f},{arm['y']:.0f},{arm['z']:.0f})",
            fill=(255, 0, 0),
        )

        img.save(file_path, format="JPEG", quality=90)

    # ------------------------------------------------------------------
    # Operation implementations
    # ------------------------------------------------------------------
    def _op_move(self, params: Dict[str, Any]) -> OperationResult:
        target = {
            "x": float(params.get("x", self._state.get("position.x", 0))),
            "y": float(params.get("y", self._state.get("position.y", 0))),
            "z": float(params.get("z", self._state.get("position.z", 0))),
        }
        if not self._in_workspace(target):
            return OperationResult(
                success=False,
                operation="move",
                error=f"Target {target} is outside workspace",
            )
        old_pos = self._get_position()
        self._set_position(target)

        # Enhancement B: move the held object together with the arm
        held = self._state.get("held_object")
        state_delta: Dict[str, Any] = {"position": {"from": old_pos, "to": target}}
        if held is not None:
            old_held_pos = self._state.get("held_object_position")
            self._state.set("held_object_position", target)
            state_delta["held_object_position"] = {
                "from": old_held_pos,
                "to": target,
            }

        return OperationResult(
            success=True,
            operation="move",
            output={"position": target},
            state_delta=state_delta,
        )

    def _op_grab(self, params: Dict[str, Any]) -> OperationResult:
        if not self._state.get("gripper_open", True):
            return OperationResult(
                success=False,
                operation="grab",
                error="Gripper is already closed",
            )

        objects: List[Dict[str, Any]] = list(self._state.get("objects", []))
        target_name = params.get("object_name")
        if target_name:
            obj = next((o for o in objects if o["name"] == target_name), None)
            if obj is None:
                return OperationResult(
                    success=False,
                    operation="grab",
                    error=f"Object '{target_name}' not found",
                )
        else:
            # Grab the closest object
            pos = self._get_position()
            candidates = [(o, self._distance(pos, o["position"])) for o in objects]
            if not candidates:
                return OperationResult(
                    success=False,
                    operation="grab",
                    error="No objects available to grab",
                )
            obj, dist = min(candidates, key=lambda x: x[1])
            target_name = obj["name"]

        if self._distance(self._get_position(), obj["position"]) >= 10.0:
            return OperationResult(
                success=False,
                operation="grab",
                error=f"Object '{target_name}' is not within 10 mm proximity",
            )

        # Close gripper and pick up object
        new_objects = [o for o in objects if o["name"] != target_name]
        self._state.set("gripper_open", False)
        self._state.set("held_object", target_name)
        self._state.set("held_object_position", obj["position"])
        self._state.set("objects", new_objects)

        return OperationResult(
            success=True,
            operation="grab",
            output={"grabbed": target_name},
            state_delta={
                "gripper_open": {"from": True, "to": False},
                "held_object": {"from": None, "to": target_name},
                "held_object_position": {"from": None, "to": obj["position"]},
                "objects": {"from": objects, "to": new_objects},
            },
        )

    def _op_release(self, params: Dict[str, Any]) -> OperationResult:
        if self._state.get("gripper_open", True):
            return OperationResult(
                success=False,
                operation="release",
                error="Gripper is already open",
            )

        held = self._state.get("held_object")
        if held is None:
            return OperationResult(
                success=False,
                operation="release",
                error="No object is currently held",
            )

        # Use tracked held_object_position ( Enhancement B ), fallback to arm pos
        held_pos = self._state.get("held_object_position")
        if held_pos is None:
            held_pos = self._get_position()

        objects: List[Dict[str, Any]] = list(self._state.get("objects", []))
        new_obj = {
            "name": held,
            "position": {
                "x": held_pos["x"],
                "y": held_pos["y"],
                "z": held_pos["z"],
            },
        }
        new_objects = objects + [new_obj]

        old_held = held
        old_held_pos = held_pos
        self._state.set("gripper_open", True)
        self._state.set("held_object", None)
        self._state.set("held_object_position", None)
        self._state.set("objects", new_objects)

        return OperationResult(
            success=True,
            operation="release",
            output={"released": held, "at": held_pos},
            state_delta={
                "gripper_open": {"from": False, "to": True},
                "held_object": {"from": old_held, "to": None},
                "held_object_position": {"from": old_held_pos, "to": None},
                "objects": {"from": objects, "to": new_objects},
            },
        )

    def _op_take_photo(self, params: Dict[str, Any]) -> OperationResult:
        image_id = f"img_{int(time.time() * 1000)}"
        base_dir = params.get("base_dir")
        file_path: Optional[str] = None

        if base_dir:
            out_dir = Path(base_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(out_dir / f"{image_id}.jpg")
            self._render_scene_image(file_path)

        output: Dict[str, Any] = {
            "image_id": image_id,
            "resolution": list(self._camera_resolution),
            "format": "jpeg",
            "mock": False,  # now renders a real scene diagram
        }
        if file_path:
            output["file_path"] = file_path

        # Build a summary of what the "camera" sees
        objects = self._state.get("objects", [])
        held = self._state.get("held_object")
        visible_names = [o["name"] for o in objects]
        if held:
            visible_names.append(f"{held} (held)")
        output["visible_objects"] = visible_names
        output["count"] = len(visible_names)

        return OperationResult(
            success=True,
            operation="take_photo",
            output=output,
        )

    def _op_detect_object(self, params: Dict[str, Any]) -> OperationResult:
        objects: List[Dict[str, Any]] = list(self._state.get("objects", []))
        held = self._state.get("held_object")
        visible = [o["name"] for o in objects]
        if held:
            visible.append(f"{held} (held)")
        return OperationResult(
            success=True,
            operation="detect_object",
            output={
                "visible_objects": visible,
                "count": len(visible),
            },
        )
