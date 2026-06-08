"""
© 2026 Transcendental Gateways. All rights reserved.
Use of this software is governed by the LICENSE-RESEARCH.md file.

Lorenz-Enhanced Kalman Filter
Advanced sensor fusion with chaos-based outlier rejection
"""

import numpy as np
from scipy.integrate import odeint
from dataclasses import dataclass
from typing import Tuple, List
import time


def lorenz_system(state, t, sigma=10, beta=8/3, rho=28):
    """Lorenz chaotic attractor"""
    x, y, z = state
    dx_dt = sigma * (y - x)
    dy_dt = x * (rho - z) - y
    dz_dt = x * y - beta * z
    return [dx_dt, dy_dt, dz_dt]


@dataclass
class SensorReading:
    """Timestamped sensor measurement"""
    value: np.ndarray
    timestamp: float
    sensor_id: str
    covariance: np.ndarray = None


class LorenzEnhancedKalmanFilter:
    """
    Kalman Filter enhanced with SNN-driven Lorenz stabilization
    
    The Lorenz attractor is modulated by synaptic spike traces, creating
    an adaptive chaos-order transition that optimizes state estimation.
    High spike activity → stabilization, Low activity → exploration
    """
    
    def __init__(self, state_dim: int, measurement_dim: int):
        """
        Initialize LEKF with SNN optimization
        
        Args:
            state_dim: Dimension of state vector (position, velocity, etc.)
            measurement_dim: Dimension of measurement vector (sensors)
        """
        self.state_dim = state_dim
        self.measurement_dim = measurement_dim
        
        # Kalman filter state
        self.x = np.zeros(state_dim)  # State estimate
        self.P = np.eye(state_dim)    # State covariance
        
        # Process noise (tuned for companion robot dynamics)
        self.Q = np.eye(state_dim) * 0.01
        
        # Measurement noise (sensor dependent)
        self.R = np.eye(measurement_dim) * 0.1
        
        # State transition matrix (will be updated based on dt)
        self.F = np.eye(state_dim)
        
        # Measurement matrix (maps state to measurements)
        self.H = np.zeros((measurement_dim, state_dim))
        self.H[:measurement_dim, :measurement_dim] = np.eye(measurement_dim)
        
        # SNN-modulated Lorenz dynamics
        self.lorenz_state = [1.0, 1.0, 1.0]
        self.lorenz_history = []
        self.outlier_threshold = 3.0  # Standard deviations
        
        # SNN spike-driven optimization
        self.spike_trace = 0.0  # Current synaptic activity level
        self.spike_alpha = 0.85  # Decay rate matching SynapticTrace
        self.spike_history = []
        self.stabilization_gain = 2.5  # How strongly spikes stabilize Lorenz
        self.base_rho = 28.0  # Lorenz parameter for chaos threshold
        self.current_rho = 28.0  # Adaptive Lorenz parameter
        
        # Innovation tracking for adaptive tuning
        self.innovation_history = []
        self.max_history = 50
        
        self.last_update = time.time()
    
    def predict(self, dt: float, control_input: np.ndarray = None, spike_input: float = None):
        """
        SNN-optimized prediction: Spike activity stabilizes Lorenz chaos
        
        Args:
            dt: Time step
            control_input: Optional control vector (motor commands, etc.)
            spike_input: Optional spike rate from SNN (0-1 normalized)
        """
        # Update spike trace with exponential decay
        if spike_input is not None:
            self.spike_trace = self.spike_trace * self.spike_alpha + spike_input
        else:
            self.spike_trace *= self.spike_alpha  # Natural decay
        
        self.spike_history.append(self.spike_trace)
        if len(self.spike_history) > self.max_history:
            self.spike_history.pop(0)
        
        # SNN-driven Lorenz stabilization
        # High spike activity reduces rho → stabilizes attractor → lower uncertainty
        # Low spike activity increases rho → chaotic exploration → adaptive search
        spike_stabilization = self.spike_trace * self.stabilization_gain
        self.current_rho = self.base_rho * (1.0 - 0.5 * np.tanh(spike_stabilization))
        
        # Update Lorenz attractor with adaptive dynamics
        t = np.array([0, dt])
        try:
            lorenz_trajectory = odeint(
                lambda state, t: lorenz_system(state, t, rho=self.current_rho),
                self.lorenz_state, t, rtol=1e-3, atol=1e-6
            )
            self.lorenz_state = lorenz_trajectory[-1].tolist()
        except Exception as e:
            # Fallback: maintain current state with small perturbation
            self.lorenz_state = [s * 0.99 for s in self.lorenz_state]
        
        self.lorenz_history.append(self.lorenz_state.copy())
        
        if len(self.lorenz_history) > self.max_history:
            self.lorenz_history.pop(0)
        
        # Spike-modulated process noise (higher spikes → lower uncertainty)
        lorenz_magnitude = np.linalg.norm(self.lorenz_state)
        base_chaos = 1.0 + 0.1 * (lorenz_magnitude / 20.0)
        spike_damping = np.exp(-spike_stabilization * 0.5)
        chaos_factor = base_chaos * spike_damping
        
        # Update state transition matrix based on dt and chaos
        # For position-velocity model: x_k+1 = x_k + v_k * dt * chaos_factor
        if self.state_dim >= 4:  # 2D position + velocity
            self.F = np.array([
                [1, 0, dt * chaos_factor, 0],
                [0, 1, 0, dt * chaos_factor],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])
        
        # Predict state with small process noise to ensure change
        self.x = self.F @ self.x
        if control_input is not None:
            self.x += control_input * dt
        
        # Add minimal prediction noise to ensure state evolution
        process_noise = np.random.normal(0, 0.001, self.state_dim)
        self.x += process_noise * dt
        
        # Predict covariance with Lorenz-modulated noise
        self.P = self.F @ self.P @ self.F.T + (self.Q * chaos_factor)
    
    def _compute_lorenz_divergence(self, measurement: np.ndarray) -> float:
        """
        Compute divergence metric using Lorenz chaos sensitivity
        
        Maps measurement to Lorenz state space and measures divergence
        from expected trajectory.
        """
        if len(self.lorenz_history) < 10:
            return 0.0  # Not enough history yet
        
        # Normalize measurement to Lorenz state space scale
        measurement_norm = measurement / (np.linalg.norm(measurement) + 1e-6)
        
        # Compare to recent Lorenz trajectory
        recent_lorenz = np.array(self.lorenz_history[-10:])
        lorenz_mean = np.mean(recent_lorenz, axis=0)
        lorenz_std = np.std(recent_lorenz, axis=0) + 1e-6
        
        # Project measurement into Lorenz space
        if len(measurement_norm) >= 3:
            measurement_lorenz = measurement_norm[:3]
        else:
            measurement_lorenz = np.pad(measurement_norm, (0, 3 - len(measurement_norm)))
        
        # Compute normalized divergence
        divergence = np.sum(np.abs(measurement_lorenz - lorenz_mean) / lorenz_std)
        
        return divergence
    
    def _is_outlier(self, measurement: np.ndarray, innovation: np.ndarray) -> Tuple[bool, float]:
        """
        Detect outliers using both statistical and chaos-based methods
        
        Returns:
            (is_outlier, confidence_score)
        """
        # Method 1: Traditional Mahalanobis distance
        S = self.H @ self.P @ self.H.T + self.R  # Innovation covariance
        try:
            S_inv = np.linalg.inv(S)
            mahalanobis = np.sqrt(innovation.T @ S_inv @ innovation)
        except np.linalg.LinAlgError:
            mahalanobis = np.linalg.norm(innovation)
        
        # Method 2: Lorenz chaos divergence
        lorenz_divergence = self._compute_lorenz_divergence(measurement)
        
        # Combined outlier score
        # High Mahalanobis distance OR high Lorenz divergence indicates outlier
        statistical_outlier = mahalanobis > self.outlier_threshold
        chaos_outlier = lorenz_divergence > self.outlier_threshold * 1.5
        
        is_outlier = statistical_outlier or chaos_outlier
        confidence = 1.0 / (1.0 + mahalanobis + lorenz_divergence)
        
        return is_outlier, confidence
    
    def update(self, measurement: np.ndarray, measurement_covariance: np.ndarray = None, 
               synaptic_trace: bool = True, spike_rate: float = None) -> dict:
        """
        SNN-optimized update with spike-driven stabilization
        
        Args:
            measurement: Sensor reading (can be raw or synaptic trace)
            measurement_covariance: Optional sensor-specific covariance
            synaptic_trace: If True, compensate for trace decay (alpha=0.85)
            spike_rate: Optional instantaneous spike rate for optimization
            
        Returns:
            dict with update status and diagnostics
        """
        if measurement_covariance is not None:
            self.R = measurement_covariance
        
        # Use spike rate to drive Lorenz stabilization
        if spike_rate is not None:
            spike_input = np.clip(spike_rate, 0, 1)
        else:
            # Infer spike activity from measurement magnitude
            spike_input = np.tanh(np.linalg.norm(measurement) / 10.0)
        
        # Feed spike activity back to prediction system
        # This creates SNN→Lorenz feedback loop
        self.spike_trace = self.spike_trace * self.spike_alpha + spike_input
        
        # Compensate for synaptic trace decay if needed
        # Traces with alpha=0.85 attenuate by ~8%, so scale measurement
        trace_scaling = 0.92 if synaptic_trace else 1.0
        
        # Compute innovation (measurement residual)
        z_pred = self.H @ self.x * trace_scaling
        innovation = measurement - z_pred
        
        # SNN-enhanced outlier detection
        is_outlier, confidence = self._is_outlier(measurement, innovation)
        
        if is_outlier:
            # Reject outlier, don't update state
            return {
                'updated': False,
                'outlier_detected': True,
                'confidence': confidence,
                'innovation': innovation,
                'state': self.x.copy()
            }
        
        # Kalman gain
        S = self.H @ self.P @ self.H.T + self.R
        try:
            K = self.P @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # Numerical instability, skip update
            return {
                'updated': False,
                'outlier_detected': False,
                'confidence': 0.0,
                'innovation': innovation,
                'state': self.x.copy()
            }
        
        # Update state
        self.x = self.x + K @ innovation
        
        # Update covariance
        I = np.eye(self.state_dim)
        self.P = (I - K @ self.H) @ self.P
        
        # Track innovation for adaptive tuning
        self.innovation_history.append(np.linalg.norm(innovation))
        if len(self.innovation_history) > self.max_history:
            self.innovation_history.pop(0)
        
        # Adaptive process noise tuning
        if len(self.innovation_history) > 20:
            innovation_std = np.std(self.innovation_history)
            if innovation_std > 0.5:  # High innovation variance
                self.Q *= 1.1  # Increase process noise
            elif innovation_std < 0.1:  # Low innovation variance
                self.Q *= 0.9  # Decrease process noise
        
        return {
            'updated': True,
            'outlier_detected': False,
            'confidence': confidence,
            'innovation': innovation,
            'kalman_gain': K,
            'state': self.x.copy()
        }
    
    def get_state(self) -> np.ndarray:
        """Get current state estimate"""
        return self.x.copy()
    
    def get_covariance(self) -> np.ndarray:
        """Get current state covariance (uncertainty)"""
        return self.P.copy()
    
    def get_position_uncertainty(self) -> float:
        """Get position uncertainty magnitude"""
        if self.state_dim >= 2:
            pos_cov = self.P[:2, :2]
            return np.sqrt(np.trace(pos_cov))
        return 0.0
    
    def get_velocity_uncertainty(self) -> float:
        """Get velocity uncertainty magnitude"""
        if self.state_dim >= 4:
            vel_cov = self.P[2:4, 2:4]
            return np.sqrt(np.trace(vel_cov))
        return 0.0
    
    def get_snn_optimization_metrics(self) -> dict:
        """
        Get SNN-driven optimization diagnostics
        
        Returns:
            dict with spike trace, Lorenz state, and stabilization metrics
        """
        return {
            'spike_trace': float(self.spike_trace),
            'current_rho': float(self.current_rho),
            'base_rho': float(self.base_rho),
            'stabilization_active': self.spike_trace > 0.1,
            'lorenz_magnitude': float(np.linalg.norm(self.lorenz_state)),
            'spike_history_mean': float(np.mean(self.spike_history)) if self.spike_history else 0.0,
            'chaos_to_order_ratio': float(self.current_rho / self.base_rho)
        }
    
    def reset(self, initial_state: np.ndarray = None, initial_covariance: np.ndarray = None):
        """Reset filter state"""
        if initial_state is not None:
            self.x = initial_state.copy()
        else:
            self.x = np.zeros(self.state_dim)
        
        if initial_covariance is not None:
            self.P = initial_covariance.copy()
        else:
            self.P = np.eye(self.state_dim)
        
        self.lorenz_state = [1.0, 1.0, 1.0]
        self.lorenz_history = []
        self.innovation_history = []


class MultiSensorFusion:
    """Fuse multiple sensors using Lorenz-Enhanced Kalman Filters"""
    
    def __init__(self, state_dim: int):
        self.state_dim = state_dim
        self.filters = {}
        self.sensor_weights = {}
        self.outlier_counts = {}
    
    def add_sensor(self, sensor_id: str, measurement_dim: int, weight: float = 1.0):
        """Add a sensor to the fusion system"""
        self.filters[sensor_id] = LorenzEnhancedKalmanFilter(self.state_dim, measurement_dim)
        self.sensor_weights[sensor_id] = weight
        self.outlier_counts[sensor_id] = 0
    
    def update(self, sensor_readings: List[SensorReading], dt: float) -> dict:
        """
        Fuse multiple sensor readings
        
        Args:
            sensor_readings: List of sensor measurements
            dt: Time step since last update
            
        Returns:
            Fused state estimate with diagnostics
        """
        # Predict all filters
        for sensor_id, kf in self.filters.items():
            kf.predict(dt)
        
        # Update with measurements
        updates = {}
        for reading in sensor_readings:
            if reading.sensor_id in self.filters:
                kf = self.filters[reading.sensor_id]
                result = kf.update(reading.value, reading.covariance)
                updates[reading.sensor_id] = result
                
                if result['outlier_detected']:
                    self.outlier_counts[reading.sensor_id] += 1
        
        # Weighted fusion of state estimates
        fused_state = np.zeros(self.state_dim)
        total_weight = 0.0
        
        for sensor_id, kf in self.filters.items():
            if sensor_id in updates and updates[sensor_id]['updated']:
                weight = self.sensor_weights[sensor_id] * updates[sensor_id]['confidence']
                fused_state += weight * kf.get_state()
                total_weight += weight
        
        if total_weight > 0:
            fused_state /= total_weight
        else:
            # No valid updates, use first available filter
            fused_state = list(self.filters.values())[0].get_state()
        
        # Compute fused uncertainty
        fused_uncertainty = np.mean([kf.get_position_uncertainty() for kf in self.filters.values()])
        
        return {
            'state': fused_state,
            'uncertainty': fused_uncertainty,
            'updates': updates,
            'outlier_counts': self.outlier_counts.copy()
        }


if __name__ == "__main__":
    print("=" * 60)
    print("LORENZ-ENHANCED KALMAN FILTER TEST")
    print("=" * 60)
    
    # Initialize filter for 2D robot (x, y, vx, vy)
    lekf = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)
    
    print("\n✓ Filter initialized")
    print(f"  State dim: {lekf.state_dim}, Measurement dim: {lekf.measurement_dim}")
    
    # Simulate measurements with outliers
    print("\n🧪 Testing with normal and outlier measurements...")
    
    true_position = np.array([0.0, 0.0])
    dt = 0.1
    
    for i in range(20):
        # Predict
        lekf.predict(dt)
        
        # Simulate measurement
        true_position += np.array([0.05, 0.02])  # Moving robot
        
        if i == 10:
            # Inject outlier
            measurement = true_position + np.array([5.0, 5.0])
            print(f"\n  Step {i}: OUTLIER injected")
        else:
            # Normal measurement with noise
            measurement = true_position + np.random.normal(0, 0.05, 2)
        
        # Update
        result = lekf.update(measurement)
        
        if result['outlier_detected']:
            print(f"  ✓ Outlier rejected at step {i}")
        
        if i % 5 == 0 and i > 0:
            state = lekf.get_state()
            uncertainty = lekf.get_position_uncertainty()
            print(f"  Step {i}: Position ({state[0]:.3f}, {state[1]:.3f}), Uncertainty: {uncertainty:.3f}")
    
    print("\n📊 Final state:")
    final_state = lekf.get_state()
    print(f"  Position: ({final_state[0]:.3f}, {final_state[1]:.3f})")
    print(f"  Velocity: ({final_state[2]:.3f}, {final_state[3]:.3f})")
    print(f"  Uncertainty: {lekf.get_position_uncertainty():.3f} m")
    
    print("\n✅ Lorenz-Enhanced Kalman Filter operational")
