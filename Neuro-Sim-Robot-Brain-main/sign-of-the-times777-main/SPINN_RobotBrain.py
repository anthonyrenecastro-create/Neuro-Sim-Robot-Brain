"""
© 2026 Transcendental Gateways. All rights reserved.
Use of this software is governed by the LICENSE-RESEARCH.md file.

SPINN Robot Brain - Syntropic Perennial Intelligence Neural Network
Reconfigured for autonomous robot control and decision making
"""

import numpy as np
from scipy.integrate import odeint
from sklearn.cluster import KMeans
import random
from math import factorial, log
import json
from datetime import datetime
from collections import deque
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CORE SNN MODULES
# ============================================================================

def lorenz_system(state, t, sigma=10, beta=8/3, rho=28):
    """Chaotic attractor for adaptive behavior generation"""
    x, y, z = state
    dx_dt = sigma * (y - x)
    dy_dt = x * (rho - z) - y
    dz_dt = x * y - beta * z
    return [dx_dt, dy_dt, dz_dt]

class PIDController:
    """Motor control and servo stabilization"""
    def __init__(self, Kp=1.0, Ki=0.1, Kd=0.05, set_point=0):
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        self.set_point = set_point
        self.integral = 0
        self.last_error = None

    def control(self, measurement, dt=0.1):
        error = self.set_point - measurement
        self.integral += error * dt
        derivative = 0 if self.last_error is None else (error - self.last_error) / dt
        self.last_error = error
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        return np.clip(output, -100, 100)  # Limit motor commands

    def reset(self):
        self.integral = 0
        self.last_error = None

class SynapticTrace:
    """Convert discrete SNN spikes to continuous analog signal"""
    def __init__(self, alpha=0.85):
        self.alpha = alpha  # Leak rate: 0.95=long memory, 0.50=short memory
        self.trace_value = 0.0
    
    def update(self, spike):
        """
        Decode spike to continuous trace
        Args:
            spike: 1 if firing, 0 if silent
        Returns:
            Continuous analog value for Kalman filter
        """
        # Exponential decay + new spike integration
        self.trace_value = (self.trace_value * self.alpha) + spike
        return self.trace_value
    
    def reset(self):
        self.trace_value = 0.0


class SensorFusion:
    """Multi-sensor integration and pattern recognition"""
    def __init__(self, n_clusters=5):
        self.n_clusters = n_clusters
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.sensor_history = deque(maxlen=100)
        self.fitted = False
        
        # Synaptic trace decoder for each sensor channel
        self.synaptic_traces = [SynapticTrace(alpha=0.85) for _ in range(3)]

    def process_sensors(self, sensor_data):
        """Process raw sensor readings into actionable patterns with synaptic trace decoding"""
        # Convert discrete sensor readings to continuous traces
        # Treat sensor readings as spike trains (normalized to 0-1)
        spikes = sensor_data / (np.max(sensor_data) + 1e-6)
        
        # Decode each sensor channel through synaptic trace
        continuous_signals = np.array([
            self.synaptic_traces[i].update(spikes[i]) 
            for i in range(min(len(spikes), len(self.synaptic_traces)))
        ])
        
        # Use continuous analog signal for clustering (smoother, more stable)
        sensor_mean = np.mean(continuous_signals)
        self.sensor_history.append(sensor_mean)
        
        if len(self.sensor_history) >= 10:
            data_array = np.array(list(self.sensor_history)).reshape(-1, 1)
            
            if not self.fitted:
                self.kmeans.fit(data_array)
                self.fitted = True
            
            cluster = self.kmeans.predict([[sensor_mean]])
            distances = np.linalg.norm(self.kmeans.cluster_centers_ - sensor_mean, axis=1)
            confidence = float(np.min(distances))
            
            return {
                'cluster': int(cluster[0]),
                'confidence': confidence,
                'pattern': 'obstacle' if cluster[0] < 2 else 'clear',
                'trace_values': continuous_signals.tolist()  # Continuous analog signals
            }
        
        return {
            'cluster': -1, 
            'confidence': 0.0, 
            'pattern': 'calibrating',
            'trace_values': continuous_signals.tolist()
        }

# ============================================================================
# MORPHOGENIC BEHAVIOR GENERATION
# ============================================================================

BEHAVIOR_PRIMITIVES = ['forward', 'backward', 'left', 'right', 'stop', 'scan']
MODIFIERS = ['fast', 'slow', 'careful', 'aggressive']

def generate_behavior_sequences(iterations=5, n_sequences=8):
    """Evolve complex behavior patterns from primitives"""
    sequences = [[random.choice(BEHAVIOR_PRIMITIVES)] for _ in range(n_sequences)]
    
    for i in range(iterations):
        new_sequences = []
        for seq in sequences:
            if len(seq) < 6:  # Max sequence length
                action = random.choice(BEHAVIOR_PRIMITIVES)
                modifier = random.choice(MODIFIERS) if random.random() > 0.5 else None
                new_sequences.append(seq + [(action, modifier) if modifier else action])
            else:
                new_sequences.append(seq)
        sequences = new_sequences
    
    return sequences

def syntropy_field(phi_0, t, lambda_damp=0.2):
    """Temporal coherence for smooth motor transitions"""
    def dphi_dt(phi, t):
        return -lambda_damp * phi + np.random.normal(0, 0.1, len(phi))
    try:
        # Use method='lsoda' with relaxed tolerances to avoid warnings
        return odeint(dphi_dt, phi_0, t, rtol=1e-3, atol=1e-6)
    except Exception as e:
        logger.warning(f"ODE integration warning: {e}")
        # Fallback to simple exponential decay
        result = np.zeros((len(t), len(phi_0)))
        for i, ti in enumerate(t):
            result[i] = phi_0 * np.exp(-lambda_damp * ti)
        return result

def perennial_morphogenic(t, omega=2, n_terms=5):
    """Cyclical behavior patterns (patrol, search, etc.)"""
    fib = [0, 1]
    for _ in range(2, n_terms + 1):
        fib.append(fib[-1] + fib[-2])
    return sum((fib[k] / factorial(k)) * np.exp(-1j * omega * t) for k in range(n_terms)).real

# ============================================================================
# ROBOT BRAIN CORE
# ============================================================================

class RobotBrain:
    """SPINN-based autonomous robot control system"""
    
    def __init__(self):
        print("🤖 Initializing Robot Brain...")
        
        # Core neural substrate
        self.syntropic_field = np.zeros(100)
        self.morphogenic_memory = np.zeros(50)
        self.morphogenic_phase_time = 0.0  # Accumulating phase for temporal evolution
        
        # Control systems
        self.motor_left = PIDController(Kp=2.0, Ki=0.3, Kd=0.1)
        self.motor_right = PIDController(Kp=2.0, Ki=0.3, Kd=0.1)
        self.sensor_fusion = SensorFusion(n_clusters=5)
        
        # Behavior system
        self.behavior_library = generate_behavior_sequences(5, 8)
        self.current_behavior = None
        self.behavior_state = 'idle'
        
        # Environmental model
        self.world_model = {
            'obstacles': [],
            'position': np.array([0.0, 0.0]),
            'orientation': 0.0,
            'velocity': np.array([0.0, 0.0])
        }
        
        # Decision making
        self.decision_buffer = deque(maxlen=10)
        self.action_history = deque(maxlen=50)
        
        # Counters for total operations
        self.total_actions = 0
        self.total_decisions = 0
        self.total_loops = 0
        self.morphogenic_history = []  # Track phase evolution
        self.loop_durations = deque(maxlen=100)
        self.start_time = None
        
        # Real-time loop
        self.running = False
        self.brain_thread = None
        self.loop_hz = 0.0
        self.loop_period_sec = 0.0
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        
        # Timestamp tracking
        self.last_t0 = None
        self.last_t_action = None
        self.last_t1 = None
        
        print("✓ Robot Brain online")
    
    def perceive(self, sensor_data):
        """Process sensory input through SNN with synaptic trace decoding"""
        try:
            # Validate sensor data
            if sensor_data is None or len(sensor_data) == 0:
                logger.error("Invalid sensor data received")
                return self._get_default_perception()
            
            # Sensor fusion with continuous trace signals
            perception = self.sensor_fusion.process_sensors(sensor_data)
            
            # Use continuous trace values for smoother field updates
            trace_signals = np.array(perception.get('trace_values', sensor_data[:3]))
            
            # Update syntropic field with sensor harmonics (using decoded traces)
            vibes = np.array([np.sin(omega * np.arange(len(trace_signals)) + phi) 
                             for omega, phi in zip([1, 2, 3], [0, np.pi/2, np.pi])])
            with self._state_lock:
                self.syntropic_field[:len(trace_signals)] = trace_signals * np.mean(vibes, axis=0)[:len(trace_signals)]
            
            # Lorenz dynamics for adaptive response (using continuous signals)
            t = np.linspace(0, 1, 10)
            initial = [perception['confidence'], perception['cluster'], np.mean(trace_signals)]
            chaos = odeint(lorenz_system, initial, t, rtol=1e-3, atol=1e-6)
        except Exception as e:
            logger.error(f"Perception error: {e}")
            return self._get_default_perception()
        
        return {
            'perception': perception,
            'field_energy': float(np.mean(self.syntropic_field**2)),
            'chaos_trajectory': chaos[-1].tolist(),
            'threat_level': float(np.clip(perception['cluster'] / 5.0, 0, 1)),
            'trace_signals': trace_signals.tolist()  # Smooth continuous signals
        }
    
    def _get_default_perception(self):
        """Return safe default perception when sensors fail"""
        return {
            'perception': {'confidence': 0.0, 'cluster': 0, 'trace_values': [0, 0, 0]},
            'field_energy': 0.0,
            'chaos_trajectory': [0.0, 0.0, 0.0],
            'threat_level': 1.0,  # Maximum threat for safety
            'trace_signals': [0.0, 0.0, 0.0]
        }
    
    def think(self, perception):
        """High-level decision making through morphogenic evolution"""
        try:
            if perception is None:
                logger.warning("Null perception in think()")
                return {'decision': 'emergency_stop', 'motor_command': {'left_motor': 0, 'right_motor': 0}}
            
            with self._state_lock:
                self.decision_buffer.append(perception)
            
            # Evolve behavior based on recent perceptions
            with self._state_lock:
                threat_avg = np.mean([p.get('threat_level', 0) for p in self.decision_buffer])
        except Exception as e:
            logger.error(f"Decision making error: {e}")
            return {'decision': 'emergency_stop', 'motor_command': {'left_motor': 0, 'right_motor': 0}}
        
        # Select behavior from evolved library
        if threat_avg > 0.6:
            decision = 'avoid_obstacle'
            behavior_idx = 0  # Defensive behaviors
        elif threat_avg < 0.3:
            decision = 'explore'
            behavior_idx = min(len(self.behavior_library) - 1, 5)
        else:
            decision = 'navigate_careful'
            behavior_idx = 2
        
        with self._state_lock:
            self.current_behavior = self.behavior_library[behavior_idx]
        
        # Apply perennial morphogenic field for temporal coherence with evolving phase
        with self._state_lock:
            self.morphogenic_phase_time += 0.1  # Increment phase time
            phase_t0 = self.morphogenic_phase_time
        t = np.linspace(phase_t0, phase_t0 + 1, 20)
        morph_signal = perennial_morphogenic(t, omega=2)
        with self._state_lock:
            self.morphogenic_memory = morph_signal[:50]
        
        # Record morphogenic phase for tracking
        with self._state_lock:
            current_phase = float(np.mean(self.morphogenic_memory))
            if len(self.morphogenic_history) < 100:  # Keep last 100 samples
                self.morphogenic_history.append(current_phase)
            else:
                self.morphogenic_history.pop(0)
                self.morphogenic_history.append(current_phase)
            self.total_decisions += 1
        
        return {
            'decision': decision,
            'behavior_sequence': self.current_behavior,
            'confidence': float(1.0 - threat_avg),
            'morphogenic_phase': float(np.mean(self.morphogenic_memory))
        }
    
    def act(self, decision, motor_mode='differential'):
        """Execute motor commands through PID control"""
        try:
            if decision is None:
                logger.error("Null decision in act()")
                return {'left_motor': 0, 'right_motor': 0, 'mode': motor_mode, 'timestamp': time.time()}
            
            actions = {
                'avoid_obstacle': {'left': -50, 'right': 50},  # Turn right
                'explore': {'left': 70, 'right': 70},          # Move forward
                'navigate_careful': {'left': 40, 'right': 40}, # Slow forward
                'stop': {'left': 0, 'right': 0}
            }
            
            target = actions.get(decision['decision'], {'left': 0, 'right': 0})
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {'left_motor': 0, 'right_motor': 0, 'mode': motor_mode, 'timestamp': time.time()}
        
        # PID control for smooth motor actuation
        left_cmd = self.motor_left.control(target['left'])
        right_cmd = self.motor_right.control(target['right'])
        
        # Apply syntropy field damping for smooth transitions
        t = np.linspace(0, 0.5, 10)
        damp = syntropy_field(np.array([left_cmd, right_cmd]), t)
        
        motor_output = {
            'left_motor': float(damp[-1, 0]),
            'right_motor': float(damp[-1, 1]),
            'mode': motor_mode,
            'timestamp': time.time()
        }
        
        with self._state_lock:
            self.action_history.append(motor_output)
            self.total_actions += 1
        
        return motor_output
    
    def brain_loop(self, sensor_callback, motor_callback, hz=10, perception_callback=None):
        """Real-time brain processing loop with cooperative shutdown and stable cadence."""
        dt = 1.0 / max(float(hz), 1e-6)
        error_count = 0
        max_errors = 10
        next_tick = time.perf_counter()
        
        print(f"🧠 Brain loop started at {hz}Hz")
        
        while not self._stop_event.is_set():
            try:
                t0 = time.time()  # Loop start time
                with self._state_lock:
                    self.last_t0 = t0
                
                # Perception
                sensor_data = sensor_callback()
                perception = self.perceive(sensor_data)
                if perception_callback is not None:
                    try:
                        perception_callback(perception)
                    except Exception as e:
                        logger.warning(f"Perception callback error: {e}")
                
                # Cognition
                decision = self.think(perception)
                
                # Action
                t_action = time.time()  # Time right before action
                with self._state_lock:
                    self.last_t_action = t_action
                motor_cmd = self.act(decision)
                motor_callback(motor_cmd)
                
                t1 = time.time()  # Loop end time
                with self._state_lock:
                    self.last_t1 = t1
                    self.loop_durations.append(t1 - t0)
                    self.total_loops += 1
                
                # Reset error count on success
                error_count = 0
                
                # Maintain loop timing with drift correction.
                next_tick += dt
                sleep_for = next_tick - time.perf_counter()
                if sleep_for > 0:
                    self._stop_event.wait(sleep_for)
                else:
                    next_tick = time.perf_counter()
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Brain loop error ({error_count}/{max_errors}): {e}")
                
                # Emergency stop on repeated errors
                if error_count >= max_errors:
                    logger.critical("Too many errors, initiating emergency stop")
                    motor_callback({'left_motor': 0, 'right_motor': 0})
                    with self._state_lock:
                        self.running = False
                    self._stop_event.set()
                    break
                
                # Try to continue with safe defaults
                try:
                    motor_callback({'left_motor': 0, 'right_motor': 0})
                except:
                    pass
                
                self._stop_event.wait(dt)
                continue
        with self._state_lock:
            self.running = False
        
        print("🛑 Brain loop stopped")
    
    def start(self, sensor_callback, motor_callback, hz=10, perception_callback=None):
        """Start autonomous operation. Returns True if a new loop was started."""
        with self._state_lock:
            if self.running:
                return False
            self.start_time = time.time()
            self.loop_hz = float(hz)
            self.loop_period_sec = 1.0 / max(float(hz), 1e-6)
            self.running = True
            self._stop_event.clear()
            self.brain_thread = threading.Thread(
                target=self.brain_loop,
                args=(sensor_callback, motor_callback, hz, perception_callback),
                name="RobotBrainLoop"
            )
            self.brain_thread.start()
        return True
    
    def stop(self, timeout=5.0):
        """Stop autonomous operation. Returns True if loop is fully stopped."""
        with self._state_lock:
            self.running = False
            thread = self.brain_thread
        self._stop_event.set()

        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)

        with self._state_lock:
            alive = self.brain_thread.is_alive() if self.brain_thread else False
            if not alive:
                self.brain_thread = None
        return not alive
    
    def get_status(self):
        """Get current brain state"""
        with self._state_lock:
            loop_durations = list(self.loop_durations)
            total_loops = self.total_loops
            total_actions = self.total_actions
            total_decisions = self.total_decisions
            start_time = self.start_time
            running = self.running
            behavior_state = self.behavior_state
            field_coherence = float(np.var(self.syntropic_field))
            morphogenic_phase = float(np.mean(self.morphogenic_memory))
            decisions_queued = len(self.decision_buffer)
            last_t0 = self.last_t0
            last_t_action = self.last_t_action
            last_t1 = self.last_t1

        avg_loop_duration = float(np.mean(loop_durations)) if loop_durations else 0.0
        loop_frequency_hz = (1.0 / avg_loop_duration) if avg_loop_duration > 0 else 0.0
        if total_loops > 0 and loop_frequency_hz > 0:
            throughput_rate = (total_actions / total_loops) * loop_frequency_hz
            decision_rate = (total_decisions / total_loops) * loop_frequency_hz
        else:
            elapsed = (time.time() - start_time) if start_time else 0.0
            throughput_rate = (total_actions / elapsed) if elapsed > 0 else 0.0
            decision_rate = (total_decisions / elapsed) if elapsed > 0 else 0.0
        return {
            'running': running,
            'behavior': behavior_state,
            'field_coherence': field_coherence,
            'morphogenic_phase': morphogenic_phase,
            'decisions_queued': decisions_queued,
            'actions_taken': total_actions,
            'decisions_made': total_decisions,
            'total_loops': total_loops,
            'loop_frequency_hz': loop_frequency_hz,
            'throughput_rate': throughput_rate,
            'decision_rate': decision_rate,
            'last_t0': last_t0,
            'last_t_action': last_t_action,
            'last_t1': last_t1
        }

# ============================================================================
# SIMULATION INTERFACE
# ============================================================================

class RobotSimulator:
    """Simulated robot for testing the brain"""
    
    def __init__(self):
        self.position = np.array([0.0, 0.0])
        self.orientation = 0.0
        self.obstacles = [
            np.array([5.0, 5.0]),
            np.array([-3.0, 8.0]),
            np.array([10.0, -2.0])
        ]
        self.max_sensor_range = 15.0
        self.obstacle_radius = 0.5
        
    def get_sensors(self):
        """Simulate distance sensors (front, left, right)"""
        sensors = []
        for angle in [-45, 0, 45]:
            direction = self.orientation + np.radians(angle)
            ray = np.array([np.cos(direction), np.sin(direction)])
            
            min_dist = self.max_sensor_range
            for obs in self.obstacles:
                rel = obs - self.position
                proj = np.dot(rel, ray)
                if proj <= 0:
                    continue
                closest = rel - proj * ray
                perp = np.linalg.norm(closest)
                if perp <= self.obstacle_radius:
                    offset = np.sqrt(max(self.obstacle_radius**2 - perp**2, 0.0))
                    dist = max(proj - offset, 0.0)
                    min_dist = min(min_dist, dist)
            
            noisy = min_dist + np.random.normal(0, 0.05)
            sensors.append(float(np.clip(noisy, 0.0, self.max_sensor_range)))
        
        return np.array(sensors)
    
    def set_motors(self, motor_cmd):
        """Update robot state from motor commands"""
        left = motor_cmd['left_motor'] / 100.0
        right = motor_cmd['right_motor'] / 100.0
        
        # Differential drive kinematics
        v = (left + right) / 2.0
        omega = (right - left) / 2.0
        
        dt = 0.1
        self.position += dt * v * np.array([np.cos(self.orientation), np.sin(self.orientation)])
        self.orientation += dt * omega
        
        return {'x': float(self.position[0]), 'y': float(self.position[1]), 'theta': float(self.orientation)}

# ============================================================================
# TESTING
# ============================================================================

def test_robot_brain():
    """Test robot brain in simulation"""
    print("=" * 60)
    print("SPINN ROBOT BRAIN TEST - 5 MINUTE RUN")
    print("=" * 60)
    
    brain = RobotBrain()
    sim = RobotSimulator()
    
    print("\n🎮 Running simulation for 5 minutes...")
    
    start_time = time.time()
    
    brain.start(
        sensor_callback=lambda: sim.get_sensors(),
        motor_callback=lambda cmd: sim.set_motors(cmd),
        hz=10
    )
    
    time.sleep(300)  # 5 minutes
    
    brain.stop()
    
    elapsed_time = time.time() - start_time
    
    print("\n📊 Final Status:")
    status = brain.get_status()
    for key, value in status.items():
        if key != 'morphogenic_history':  # Skip history array in main display
            print(f"  {key}: {value}")
    
    # Show morphogenic phase evolution
    morph_history = brain.morphogenic_history
    if len(morph_history) > 0:
        print(f"\n🌀 Morphogenic Phase Evolution:")
        print(f"  Initial: {morph_history[0]:.6f}")
        print(f"  Final: {morph_history[-1]:.6f}")
        print(f"  Range: [{min(morph_history):.6f}, {max(morph_history):.6f}]")
        print(f"  Mean: {np.mean(morph_history):.6f}")
        print(f"  Std Dev: {np.std(morph_history):.6f}")
    
    print(f"\n📍 Final Position: ({sim.position[0]:.2f}, {sim.position[1]:.2f})")
    print(f"📐 Final Orientation: {np.degrees(sim.orientation):.1f}°")
    
    print(f"\n⏱️  Performance Metrics:")
    print(f"  Runtime: {elapsed_time:.2f} seconds")
    print(f"  Total Loops: {status.get('total_loops', 0)}")
    print(f"  Loop Frequency: {status.get('total_loops', 0) / elapsed_time:.2f} Hz")
    print(f"  Total Actions: {status.get('actions_taken', 0)}")
    print(f"  Action Throughput: {status.get('actions_taken', 0) / elapsed_time:.2f} actions/sec")
    print(f"  Total Decisions: {status.get('decisions_made', 0)}")
    print(f"  Decision Rate: {status.get('decisions_made', 0) / elapsed_time:.2f} decisions/sec")
    
    print(f"\n🕐 Last Loop Timestamps:")
    if status.get('last_t0') and status.get('last_t_action') and status.get('last_t1'):
        t0 = status['last_t0']
        t_action = status['last_t_action']
        t1 = status['last_t1']
        print(f"  Loop start (t0): {t0:.6f}")
        print(f"  Before action (t_action): {t_action:.6f}")
        print(f"  Loop end (t1): {t1:.6f}")
        print(f"  Perception+Cognition time: {(t_action - t0)*1000:.3f} ms")
        print(f"  Action time: {(t1 - t_action)*1000:.3f} ms")
        print(f"  Total loop time: {(t1 - t0)*1000:.3f} ms")
    else:
        print("  No timestamp data available")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_robot_brain()
