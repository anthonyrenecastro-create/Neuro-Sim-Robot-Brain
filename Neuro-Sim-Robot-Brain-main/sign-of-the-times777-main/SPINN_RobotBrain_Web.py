"""
© 2026 Transcendental Gateways. All rights reserved.
Use of this software is governed by the LICENSE-RESEARCH.md file.

SPINN Robot Brain Web API
Real-time control interface for robot brain operations
"""

from flask import Flask, jsonify, request, render_template
from SPINN_RobotBrain import RobotBrain
from safety_layer import SafetyMonitor, SafetyConstraints
from lorenz_kalman import LorenzEnhancedKalmanFilter
from hardware_abstraction import create_hardware_adapter
import numpy as np
import os
import threading
import time

app = Flask(__name__)

class RuntimeState:
    """Shared runtime state guarded by a single re-entrant lock."""

    def __init__(self):
        self.lock = threading.RLock()
        self.brain = None
        self.hardware = None
        self.safety_monitor = None
        self.kalman_filter = None
        self.brain_active = False
        self.last_perception = None
        self.last_action = None


runtime = RuntimeState()

@app.route('/')
def index():
    return render_template('robot.html')

@app.route('/api/robot/init', methods=['POST'])
def init_robot():
    """Initialize robot brain"""
    old_brain = None
    old_hardware = None
    was_active = False
    with runtime.lock:
        old_brain = runtime.brain
        old_hardware = runtime.hardware
        was_active = runtime.brain_active

    if old_brain is not None and was_active:
        old_brain.stop()
    if old_hardware is not None:
        old_hardware.close()

    backend = os.getenv("SPINN_HARDWARE_BACKEND", "simulated")
    serial_port = os.getenv("SPINN_SERIAL_PORT")
    serial_baudrate = int(os.getenv("SPINN_SERIAL_BAUDRATE", "115200"))
    serial_timeout = float(os.getenv("SPINN_SERIAL_TIMEOUT", "0.2"))
    ros2_node_name = os.getenv("SPINN_ROS2_NODE_NAME", "spinn_robot_hardware")
    ros2_sensor_topic = os.getenv("SPINN_ROS2_SENSOR_TOPIC", "/robot/sensors")
    ros2_pose_topic = os.getenv("SPINN_ROS2_POSE_TOPIC", "/robot/pose2d")
    ros2_motor_topic = os.getenv("SPINN_ROS2_MOTOR_TOPIC", "/robot/cmd_motors")
    ros2_reset_service = os.getenv("SPINN_ROS2_RESET_SERVICE", "/robot/reset")
    ros2_timeout = float(os.getenv("SPINN_ROS2_TIMEOUT", "0.2"))

    try:
        adapter_timeout = ros2_timeout if backend.strip().lower() in {"ros2", "ros"} else serial_timeout
        hardware = create_hardware_adapter(
            backend,
            port=serial_port,
            baudrate=serial_baudrate,
            timeout=adapter_timeout,
            node_name=ros2_node_name,
            sensor_topic=ros2_sensor_topic,
            pose_topic=ros2_pose_topic,
            motor_topic=ros2_motor_topic,
            reset_service=ros2_reset_service,
        )
    except Exception as e:
        return jsonify({'error': f'Failed to initialize hardware backend {backend}: {e}'}), 400

    with runtime.lock:
        runtime.brain = RobotBrain()
        runtime.hardware = hardware
        runtime.safety_monitor = SafetyMonitor(SafetyConstraints())
        runtime.kalman_filter = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)
        runtime.brain_active = False
        runtime.last_perception = None
        runtime.last_action = None
    
    return jsonify({
        'status': 'initialized',
        'message': 'Robot brain with Lorenz-UKF ready',
        'hardware_backend': backend
    })

@app.route('/api/robot/start', methods=['POST'])
def start_robot():
    """Start autonomous operation with safety monitoring"""
    with runtime.lock:
        brain = runtime.brain
        already_active = runtime.brain_active

    if brain is None:
        return jsonify({'error': 'Brain not initialized'}), 400

    if not already_active:
        def safe_sensor_callback():
            with runtime.lock:
                hardware = runtime.hardware
                if hardware is None:
                    return np.array([0.0, 0.0, 0.0])
            return hardware.get_sensors()

        def on_perception(perception):
            with runtime.lock:
                runtime.last_perception = perception
        
        def safe_motor_callback(cmd):
            with runtime.lock:
                hardware = runtime.hardware
                safety_monitor = runtime.safety_monitor
                kalman_filter = runtime.kalman_filter
                last_perception = runtime.last_perception

            if hardware is None:
                return None

            if kalman_filter and last_perception:
                trace_signals = last_perception.get('trace_signals', [0, 0, 0])
                spike_rate = np.mean(trace_signals)
                kalman_filter.predict(dt=0.1, spike_input=spike_rate)
                pose = hardware.get_pose()
                measurement = np.array([pose.x, pose.y])
                kalman_filter.update(measurement, synaptic_trace=True, spike_rate=spike_rate)

            if safety_monitor:
                safety_monitor.pet_watchdog()
                sensors = hardware.get_sensors()
                safe_left, safe_right = safety_monitor.enforce_safe_command(
                    cmd['left_motor'],
                    cmd['right_motor'],
                    sensors
                )
                cmd['left_motor'] = safe_left
                cmd['right_motor'] = safe_right

            with runtime.lock:
                runtime.last_action = dict(cmd)

            return hardware.set_motors(cmd)

        started = brain.start(
            sensor_callback=safe_sensor_callback,
            motor_callback=safe_motor_callback,
            hz=10,
            perception_callback=on_perception
        )
        with runtime.lock:
            runtime.brain_active = bool(started)

        return jsonify({
            'status': 'running' if started else 'already_running',
            'message': 'Robot brain started with Lorenz-UKF and safety monitoring'
        })

    return jsonify({'status': 'already_running'})

@app.route('/api/robot/stop', methods=['POST'])
def stop_robot():
    """Stop autonomous operation"""
    with runtime.lock:
        brain = runtime.brain
        brain_active = runtime.brain_active

    if brain and brain_active:
        brain.stop()
        with runtime.lock:
            runtime.brain_active = False

        return jsonify({
            'status': 'stopped',
            'message': 'Robot brain stopped'
        })

    return jsonify({'status': 'not_running'})

@app.route('/api/robot/status', methods=['GET'])
def get_status():
    """Get current robot status with all metrics"""
    with runtime.lock:
        brain = runtime.brain
        hardware = runtime.hardware
        brain_active = runtime.brain_active
        safety_monitor = runtime.safety_monitor
        last_perception = runtime.last_perception
        last_action = runtime.last_action
        kalman_filter = runtime.kalman_filter

    if brain is None:
        return jsonify({'error': 'Brain not initialized'}), 400

    brain_status = brain.get_status()

    if hardware is None:
        return jsonify({'error': 'Hardware backend not initialized'}), 400

    pose = hardware.get_pose()

    position = {
        'x': float(pose.x),
        'y': float(pose.y),
        'orientation': float(np.degrees(pose.theta))
    }
    
    sensors = hardware.get_sensors()
    
    # Get latest perception if available
    if brain_active and last_perception:
        snn_metrics = {
            'synaptic_traces': last_perception.get('trace_signals', [0, 0, 0]),
            'lorenz_state': last_perception.get('chaos_trajectory', [0, 0, 0]),
            'field_energy': last_perception.get('field_energy', 0.0),
            'threat_level': last_perception.get('threat_level', 0.0)
        }
    else:
        snn_metrics = {
            'synaptic_traces': [0, 0, 0],
            'lorenz_state': [0, 0, 0],
            'field_energy': 0.0,
            'threat_level': 0.0
        }
    
    # Get safety metrics
    if safety_monitor:
        safety_status = safety_monitor.get_status()
        estop_response_ms = safety_monitor.simulate_emergency_stop_response()
        safety_metrics = {
            'safety_level': safety_status['safety_level'],
            'motor_left': last_action.get('left_motor', 0.0) if last_action else 0.0,
            'motor_right': last_action.get('right_motor', 0.0) if last_action else 0.0,
            'velocity': float(np.linalg.norm([pose.x, pose.y]) / 10.0),
            'min_obstacle': float(np.min(sensors)),
            'watchdog_ok': safety_status['watchdog_ok'],
            'emergency_stop': safety_status['emergency_stop'],
            'failure_count': len(safety_status['active_failures']),
            'safety_transitions': safety_status.get('safety_transitions', 0),
            'last_transition': safety_status.get('last_transition'),
            'estop_response_ms': float(estop_response_ms) if estop_response_ms is not None else None
        }
    else:
        safety_metrics = {
            'safety_level': 'UNKNOWN',
            'motor_left': 0.0,
            'motor_right': 0.0,
            'velocity': 0.0,
            'min_obstacle': 0.0,
            'watchdog_ok': True,
            'emergency_stop': False,
            'failure_count': 0,
            'safety_transitions': 0,
            'last_transition': None,
            'estop_response_ms': None
        }
    
    # Get Kalman filter metrics with SNN optimization
    if kalman_filter:
        kalman_state = kalman_filter.get_state()
        snn_opt = kalman_filter.get_snn_optimization_metrics()
        pos_unc = kalman_filter.get_position_uncertainty()
        vel_unc = kalman_filter.get_velocity_uncertainty()
        chaos_ratio = snn_opt['chaos_to_order_ratio']
        stability_score = float(np.exp(-(pos_unc + vel_unc + abs(chaos_ratio - 1.0))))
        kalman_metrics = {
            'estimated_pos_x': float(kalman_state[0]),
            'estimated_pos_y': float(kalman_state[1]),
            'estimated_vel_x': float(kalman_state[2]),
            'estimated_vel_y': float(kalman_state[3]),
            'position_uncertainty': float(kalman_filter.get_position_uncertainty()),
            'velocity_uncertainty': float(kalman_filter.get_velocity_uncertainty()),
            'lorenz_state': [float(x) for x in kalman_filter.lorenz_state],
            'lorenz_magnitude': float(np.linalg.norm(kalman_filter.lorenz_state)),
            'snn_spike_trace': snn_opt['spike_trace'],
            'snn_current_rho': snn_opt['current_rho'],
            'snn_stabilization_active': bool(snn_opt['stabilization_active']),
            'chaos_to_order_ratio': snn_opt['chaos_to_order_ratio'],
            'stability_score': stability_score
        }
    else:
        kalman_metrics = {
            'estimated_pos_x': 0.0,
            'estimated_pos_y': 0.0,
            'estimated_vel_x': 0.0,
            'estimated_vel_y': 0.0,
            'position_uncertainty': 0.0,
            'velocity_uncertainty': 0.0,
            'lorenz_state': [0.0, 0.0, 0.0],
            'lorenz_magnitude': 0.0,
            'snn_spike_trace': 0.0,
            'snn_current_rho': 28.0,
            'snn_stabilization_active': False,
            'chaos_to_order_ratio': 1.0,
            'stability_score': 0.0
        }
    
    return jsonify({
        'brain': brain_status,
        'position': position,
        'sensors': sensors.tolist(),
        'active': brain_active,
        'snn_metrics': snn_metrics,
        'safety_metrics': safety_metrics,
        'kalman_metrics': kalman_metrics
    })

@app.route('/api/robot/manual', methods=['POST'])
def manual_control():
    """Manual motor control override"""
    with runtime.lock:
        hardware = runtime.hardware

    data = request.json
    left = data.get('left', 0)
    right = data.get('right', 0)

    if hardware:
        motor_cmd = {'left_motor': left, 'right_motor': right}
        pos = hardware.set_motors(motor_cmd)
        with runtime.lock:
            runtime.last_action = dict(motor_cmd)
        
        return jsonify({
            'status': 'ok',
            'position': pos
        })

    return jsonify({'error': 'Hardware backend not initialized'}), 400

@app.route('/api/robot/sensors', methods=['GET'])
def get_sensors():
    """Get raw sensor data"""
    with runtime.lock:
        hardware = runtime.hardware

    if hardware:
        sensors = hardware.get_sensors()
        return jsonify({
            'sensors': sensors.tolist(),
            'timestamp': time.time()
        })

    return jsonify({'error': 'Hardware backend not initialized'}), 400

@app.route('/api/robot/behavior', methods=['GET'])
def get_behavior():
    """Get current behavior library"""
    with runtime.lock:
        brain = runtime.brain

    if brain:
        status = brain.get_status()
        return jsonify({
            'current': str(brain.current_behavior) if brain.current_behavior else None,
            'state': status['behavior'],
            'library_size': len(brain.behavior_library)
        })

    return jsonify({'error': 'Brain not initialized'}), 400

@app.route('/api/robot/reset', methods=['POST'])
def reset_robot():
    """Reset robot to origin"""
    with runtime.lock:
        hardware = runtime.hardware
        brain = runtime.brain

        if hardware:
            hardware.reset()

        if brain:
            brain.motor_left.reset()
            brain.motor_right.reset()
            brain.syntropic_field = np.zeros(100)
            runtime.last_action = None
            runtime.last_perception = None
    
    return jsonify({
        'status': 'reset',
        'message': 'Robot reset to origin'
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 SPINN ROBOT BRAIN WEB INTERFACE")
    print("=" * 60)
    print("\n📊 API Endpoints:")
    print("  POST /api/robot/init      - Initialize robot brain")
    print("  POST /api/robot/start     - Start autonomous mode")
    print("  POST /api/robot/stop      - Stop autonomous mode")
    print("  GET  /api/robot/status    - Get robot status")
    print("  POST /api/robot/manual    - Manual control")
    print("  GET  /api/robot/sensors   - Get sensor readings")
    print("  GET  /api/robot/behavior  - Get behavior info")
    print("  POST /api/robot/reset     - Reset to origin")
    print("\n🚀 Starting server on port 8000...")
    
    # Production mode - debug disabled for security
    app.run(host='0.0.0.0', port=8000, debug=False)
