"""
Hardware abstraction layer for SPINN robot runtime.

This keeps control code independent from concrete hardware backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import threading
import time
import os
from typing import Any, Dict, Optional
import logging

import numpy as np

from SPINN_RobotBrain import RobotSimulator


logger = logging.getLogger(__name__)
MOTOR_ABS_MAX = 100.0


class _MotorCommandGuard:
    """Normalizes, clamps, and slew-rate limits motor commands."""

    def __init__(self, max_abs: float = MOTOR_ABS_MAX, max_delta_per_sec: float = 400.0):
        self.max_abs = float(max_abs)
        self.max_delta_per_sec = float(max_delta_per_sec)
        self._last_cmd = np.zeros(2, dtype=float)
        self._last_ts = time.monotonic()
        self._last_warn_ts = 0.0
        self._lock = threading.RLock()

    def sanitize(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        with self._lock:
            left = float(motor_cmd.get("left_motor", 0.0))
            right = float(motor_cmd.get("right_motor", 0.0))
            cmd = np.array([left, right], dtype=float)
            cmd = np.nan_to_num(cmd, nan=0.0, posinf=self.max_abs, neginf=-self.max_abs)
            cmd = np.clip(cmd, -self.max_abs, self.max_abs)

            now = time.monotonic()
            dt = max(now - self._last_ts, 1e-6)
            max_step = self.max_delta_per_sec * dt
            delta = np.clip(cmd - self._last_cmd, -max_step, max_step)
            limited = self._last_cmd + delta

            self._last_cmd = limited
            self._last_ts = now

            if not np.allclose(cmd, limited):
                should_warn = (now - self._last_warn_ts) >= 1.0
                self._last_warn_ts = now if should_warn else self._last_warn_ts
                if should_warn:
                    logger.warning(
                        "motor_command_rate_limited requested=%s applied=%s dt=%.6f",
                        cmd.tolist(),
                        limited.tolist(),
                        dt,
                    )

            return {
                "left_motor": float(limited[0]),
                "right_motor": float(limited[1]),
            }


@dataclass
class Pose2D:
    """Planar robot pose representation."""

    x: float
    y: float
    theta: float


class RobotHardwareInterface(ABC):
    """Minimal contract required by the robot control loop."""

    @abstractmethod
    def get_sensors(self) -> np.ndarray:
        """Return current sensor vector."""

    @abstractmethod
    def set_motors(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        """Apply motor command and return resulting pose/state."""

    @abstractmethod
    def get_pose(self) -> Pose2D:
        """Return current pose estimate from the hardware backend."""

    @abstractmethod
    def reset(self) -> None:
        """Reset robot state to a safe baseline."""

    def close(self) -> None:
        """Release backend resources if needed."""


class SimulatedRobotHardware(RobotHardwareInterface):
    """Robot hardware adapter backed by the in-repo simulator."""

    def __init__(self, simulator: Optional[RobotSimulator] = None):
        self._sim = simulator if simulator is not None else RobotSimulator()
        self._lock = threading.RLock()
        self._guard = _MotorCommandGuard(
            max_abs=float(os.getenv("SPINN_MOTOR_ABS_MAX", str(MOTOR_ABS_MAX))),
            max_delta_per_sec=float(os.getenv("SPINN_MOTOR_MAX_DELTA_PER_SEC", "400.0")),
        )

    def get_sensors(self) -> np.ndarray:
        with self._lock:
            return self._sim.get_sensors()

    def set_motors(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        with self._lock:
            safe_cmd = self._guard.sanitize(motor_cmd)
            return self._sim.set_motors(safe_cmd)

    def get_pose(self) -> Pose2D:
        with self._lock:
            return Pose2D(
                x=float(self._sim.position[0]),
                y=float(self._sim.position[1]),
                theta=float(self._sim.orientation),
            )

    def reset(self) -> None:
        with self._lock:
            self._sim.position = np.array([0.0, 0.0])
            self._sim.orientation = 0.0

    def close(self) -> None:
        # Simulator has no external resources to release.
        return

    @property
    def simulator(self) -> RobotSimulator:
        """Expose wrapped simulator for compatibility and diagnostics."""
        return self._sim


class SerialJsonRobotHardware(RobotHardwareInterface):
    """Serial-backed robot hardware using newline-delimited JSON RPC.

    Expected device protocol (request -> response):
    - {"cmd":"get_sensors"} -> {"status":"ok","sensors":[f,l,r]}
    - {"cmd":"set_motors","left_motor":x,"right_motor":y} ->
      {"status":"ok","pose":{"x":..,"y":..,"theta":..}}
    - {"cmd":"get_pose"} -> {"status":"ok","pose":{"x":..,"y":..,"theta":..}}
    - {"cmd":"reset"} -> {"status":"ok"}
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        timeout: float = 0.2,
        serial_conn: Optional[Any] = None,
    ):
        self._lock = threading.RLock()
        self._guard = _MotorCommandGuard(
            max_abs=float(os.getenv("SPINN_MOTOR_ABS_MAX", str(MOTOR_ABS_MAX))),
            max_delta_per_sec=float(os.getenv("SPINN_MOTOR_MAX_DELTA_PER_SEC", "400.0")),
        )
        if serial_conn is not None:
            self._ser = serial_conn
            return

        if not port:
            raise ValueError("SerialJsonRobotHardware requires a serial port")

        try:
            import serial  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is required for serial hardware adapter. "
                "Install with: pip install pyserial"
            ) from exc

        self._ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def _rpc(self, cmd: str, **payload: Any) -> Dict[str, Any]:
        with self._lock:
            message = {"cmd": cmd, **payload}
            raw = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
            self._ser.write(raw)
            self._ser.flush()

            line = self._ser.readline()
            if not line:
                raise TimeoutError(f"No response from hardware for command '{cmd}'")

            try:
                response = json.loads(line.decode("utf-8").strip())
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSON response for command '{cmd}'") from exc

            if response.get("status") != "ok":
                error = response.get("error", "unknown error")
                raise RuntimeError(f"Hardware command '{cmd}' failed: {error}")

            return response

    def get_sensors(self) -> np.ndarray:
        response = self._rpc("get_sensors")
        sensors = response.get("sensors", [0.0, 0.0, 0.0])
        values = np.asarray(sensors, dtype=float)
        values = np.nan_to_num(values, nan=0.0, posinf=1000.0, neginf=0.0)
        return values

    def set_motors(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        safe_cmd = self._guard.sanitize(motor_cmd)
        left = float(safe_cmd.get("left_motor", 0.0))
        right = float(safe_cmd.get("right_motor", 0.0))
        response = self._rpc("set_motors", left_motor=left, right_motor=right)
        pose = response.get("pose", {})
        return {
            "x": float(pose.get("x", 0.0)),
            "y": float(pose.get("y", 0.0)),
            "theta": float(pose.get("theta", 0.0)),
        }

    def get_pose(self) -> Pose2D:
        response = self._rpc("get_pose")
        pose = response.get("pose", {})
        return Pose2D(
            x=float(pose.get("x", 0.0)),
            y=float(pose.get("y", 0.0)),
            theta=float(pose.get("theta", 0.0)),
        )

    def reset(self) -> None:
        self._rpc("reset")

    def close(self) -> None:
        with self._lock:
            close_fn = getattr(self._ser, "close", None)
            if callable(close_fn):
                close_fn()


def create_hardware_adapter(backend: str, **kwargs: Any) -> RobotHardwareInterface:
    """Factory for hardware adapter creation.

    Supported backends:
    - simulated
    - serial
    """
    backend_normalized = (backend or "simulated").strip().lower()

    if backend_normalized in {"sim", "simulated", "simulator"}:
        return SimulatedRobotHardware(kwargs.get("simulator"))

    if backend_normalized in {"serial", "uart"}:
        return SerialJsonRobotHardware(
            port=kwargs.get("port"),
            baudrate=int(kwargs.get("baudrate", 115200)),
            timeout=float(kwargs.get("timeout", 0.2)),
            serial_conn=kwargs.get("serial_conn"),
        )

    if backend_normalized in {"ros2", "ros"}:
        return Ros2RobotHardware(
            node_name=str(kwargs.get("node_name", "spinn_robot_hardware")),
            sensor_topic=str(kwargs.get("sensor_topic", "/robot/sensors")),
            pose_topic=str(kwargs.get("pose_topic", "/robot/pose2d")),
            motor_topic=str(kwargs.get("motor_topic", "/robot/cmd_motors")),
            reset_service=str(kwargs.get("reset_service", "/robot/reset")),
            timeout=float(kwargs.get("timeout", 0.2)),
            ros_client=kwargs.get("ros_client"),
        )

    raise ValueError(f"Unsupported hardware backend: {backend}")


class _RclpyRos2Client:
    """Best-effort ROS2 transport implementation using rclpy."""

    def __init__(
        self,
        node_name: str,
        sensor_topic: str,
        pose_topic: str,
        motor_topic: str,
        reset_service: str,
        timeout: float,
    ):
        try:
            import rclpy  # type: ignore
            from geometry_msgs.msg import Pose2D as RosPose2D  # type: ignore
            from std_msgs.msg import Float32MultiArray  # type: ignore
            from std_srvs.srv import Trigger  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ROS2 backend requires rclpy + message packages. "
                "Install ROS2 runtime (e.g., apt install ros-<distro>-rclpy)."
            ) from exc

        self._rclpy = rclpy
        self._RosPose2D = RosPose2D
        self._Float32MultiArray = Float32MultiArray
        self._Trigger = Trigger
        self._timeout = timeout
        self._lock = threading.RLock()

        self._owns_rclpy_context = not self._rclpy.ok()
        if self._owns_rclpy_context:
            self._rclpy.init(args=None)

        self._node = self._rclpy.create_node(node_name)
        self._last_sensors = np.zeros(3, dtype=float)
        self._last_pose = Pose2D(x=0.0, y=0.0, theta=0.0)

        self._node.create_subscription(
            self._Float32MultiArray,
            sensor_topic,
            self._on_sensors,
            10,
        )
        self._node.create_subscription(
            self._RosPose2D,
            pose_topic,
            self._on_pose,
            10,
        )
        self._motor_pub = self._node.create_publisher(self._Float32MultiArray, motor_topic, 10)
        self._reset_client = self._node.create_client(self._Trigger, reset_service)

    def _on_sensors(self, msg: Any) -> None:
        data = list(getattr(msg, "data", []))
        if len(data) >= 3:
            with self._lock:
                self._last_sensors = np.asarray(data[:3], dtype=float)

    def _on_pose(self, msg: Any) -> None:
        with self._lock:
            self._last_pose = Pose2D(
                x=float(getattr(msg, "x", 0.0)),
                y=float(getattr(msg, "y", 0.0)),
                theta=float(getattr(msg, "theta", 0.0)),
            )

    def _spin_once(self, timeout: Optional[float] = None) -> None:
        self._rclpy.spin_once(self._node, timeout_sec=self._timeout if timeout is None else timeout)

    def get_sensors(self) -> np.ndarray:
        self._spin_once(timeout=0.0)
        with self._lock:
            return self._last_sensors.copy()

    def get_pose(self) -> Pose2D:
        self._spin_once(timeout=0.0)
        with self._lock:
            return Pose2D(self._last_pose.x, self._last_pose.y, self._last_pose.theta)

    def set_motors(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        msg = self._Float32MultiArray()
        msg.data = [
            float(motor_cmd.get("left_motor", 0.0)),
            float(motor_cmd.get("right_motor", 0.0)),
        ]
        self._motor_pub.publish(msg)
        pose = self.get_pose()
        return {"x": pose.x, "y": pose.y, "theta": pose.theta}

    def reset(self) -> None:
        if not self._reset_client.wait_for_service(timeout_sec=self._timeout):
            raise TimeoutError("ROS2 reset service unavailable")

        req = self._Trigger.Request()
        future = self._reset_client.call_async(req)
        deadline = time.monotonic() + self._timeout
        while not future.done():
            self._spin_once(timeout=0.01)
            if time.monotonic() >= deadline:
                raise TimeoutError("ROS2 reset service timed out")

        response = future.result()
        if response is None or not getattr(response, "success", False):
            message = getattr(response, "message", "unknown error") if response else "null response"
            raise RuntimeError(f"ROS2 reset failed: {message}")

    def close(self) -> None:
        with self._lock:
            try:
                self._node.destroy_node()
            finally:
                if self._owns_rclpy_context and self._rclpy.ok():
                    self._rclpy.shutdown()


class Ros2RobotHardware(RobotHardwareInterface):
    """ROS2-backed hardware adapter for production robot integration."""

    def __init__(
        self,
        node_name: str = "spinn_robot_hardware",
        sensor_topic: str = "/robot/sensors",
        pose_topic: str = "/robot/pose2d",
        motor_topic: str = "/robot/cmd_motors",
        reset_service: str = "/robot/reset",
        timeout: float = 0.2,
        ros_client: Optional[Any] = None,
    ):
        self._lock = threading.RLock()
        self._guard = _MotorCommandGuard(
            max_abs=float(os.getenv("SPINN_MOTOR_ABS_MAX", str(MOTOR_ABS_MAX))),
            max_delta_per_sec=float(os.getenv("SPINN_MOTOR_MAX_DELTA_PER_SEC", "400.0")),
        )
        self._client = (
            ros_client
            if ros_client is not None
            else _RclpyRos2Client(
                node_name=node_name,
                sensor_topic=sensor_topic,
                pose_topic=pose_topic,
                motor_topic=motor_topic,
                reset_service=reset_service,
                timeout=timeout,
            )
        )

    def get_sensors(self) -> np.ndarray:
        with self._lock:
            return np.asarray(self._client.get_sensors(), dtype=float)

    def set_motors(self, motor_cmd: Dict[str, float]) -> Dict[str, float]:
        with self._lock:
            safe_cmd = self._guard.sanitize(motor_cmd)
            return self._client.set_motors(safe_cmd)

    def get_pose(self) -> Pose2D:
        with self._lock:
            pose = self._client.get_pose()
            return Pose2D(float(pose.x), float(pose.y), float(pose.theta))

    def reset(self) -> None:
        with self._lock:
            self._client.reset()

    def close(self) -> None:
        with self._lock:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                close_fn()
