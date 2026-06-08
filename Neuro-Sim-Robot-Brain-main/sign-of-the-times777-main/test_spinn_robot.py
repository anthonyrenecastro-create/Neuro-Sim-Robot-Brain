"""
SPINN Robot Brain - Comprehensive Test Suite
Continuous validation for production readiness
"""

import json
import unittest
import numpy as np
import time
from safety_layer import (SafetyMonitor, SafetyConstraints, FailureRecovery, 
                          FailureMode, SafetyLevel, ISO13482Compliance)
from lorenz_kalman import (LorenzEnhancedKalmanFilter, MultiSensorFusion, 
                           SensorReading)
from SPINN_RobotBrain import RobotBrain, RobotSimulator
from hardware_abstraction import (
    SimulatedRobotHardware,
    SerialJsonRobotHardware,
    Ros2RobotHardware,
    create_hardware_adapter,
)


class TestSafetyLayer(unittest.TestCase):
    """Safety system validation tests"""
    
    def setUp(self):
        self.constraints = SafetyConstraints()
        self.monitor = SafetyMonitor(self.constraints)
        self.recovery = FailureRecovery(self.monitor)
    
    def test_velocity_limits(self):
        """Verify velocity constraints enforced"""
        # Within limits
        self.assertTrue(self.monitor.check_velocity_limits(0.4, 0.8))
        
        # Exceeds limits
        self.assertFalse(self.monitor.check_velocity_limits(0.6, 0.8))
        self.assertFalse(self.monitor.check_velocity_limits(0.3, 1.5))
    
    def test_proximity_detection(self):
        """Verify proximity-based safety levels"""
        # Safe distance
        level = self.monitor.check_proximity(np.array([1.0, 1.0, 1.0]))
        self.assertEqual(level, SafetyLevel.NOMINAL)
        
        # Warning distance
        level = self.monitor.check_proximity(np.array([0.35, 0.4, 0.5]))
        self.assertIn(level, [SafetyLevel.CAUTION, SafetyLevel.WARNING])
        
        # Emergency distance
        level = self.monitor.check_proximity(np.array([0.1, 0.12, 0.2]))
        self.assertEqual(level, SafetyLevel.EMERGENCY)
    
    def test_emergency_stop(self):
        """Verify emergency stop engages correctly"""
        sensors = np.array([0.1, 0.1, 0.1])  # Too close!
        left, right = self.monitor.enforce_safe_command(100, 100, sensors)
        
        self.assertEqual(left, 0.0)
        self.assertEqual(right, 0.0)
        self.assertTrue(self.monitor.emergency_stop_active)
    
    def test_command_scaling(self):
        """Verify motor commands scaled by safety level"""
        # Caution: 70% power (don't pass distances to avoid recalculation)
        self.monitor.safety_level = SafetyLevel.CAUTION
        left, right = self.monitor.enforce_safe_command(100, 100, None)
        self.assertAlmostEqual(left, 70.0, delta=1.0)
        
        # Warning: 40% power
        self.monitor.safety_level = SafetyLevel.WARNING
        left, right = self.monitor.enforce_safe_command(100, 100, None)
        self.assertAlmostEqual(left, 40.0, delta=1.0)
    
    def test_watchdog(self):
        """Verify watchdog timeout detection"""
        self.monitor.pet_watchdog()
        self.assertTrue(self.monitor.check_watchdog())
        
        # Simulate timeout
        self.monitor.watchdog_last_pet -= 2.0  # 2 seconds ago
        self.assertFalse(self.monitor.check_watchdog())
    
    def test_iso13482_compliance(self):
        """Verify ISO 13482 companion robot standards met"""
        compliance = ISO13482Compliance.check_compliance(self.constraints)
        
        self.assertTrue(compliance['velocity_limits'])
        self.assertTrue(compliance['force_limits'])
        self.assertTrue(compliance['emergency_stop'])


class TestKalmanFilter(unittest.TestCase):
    """Lorenz-Enhanced Kalman Filter tests"""
    
    def setUp(self):
        self.kf = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)
    
    def test_initialization(self):
        """Verify filter initializes correctly"""
        self.assertEqual(self.kf.state_dim, 4)
        self.assertEqual(self.kf.measurement_dim, 2)
        self.assertEqual(len(self.kf.x), 4)
    
    def test_prediction(self):
        """Verify prediction step"""
        initial_state = self.kf.x.copy()
        self.kf.predict(dt=0.1)
        
        # State should change after prediction
        self.assertFalse(np.array_equal(initial_state, self.kf.x))
    
    def test_outlier_rejection(self):
        """Verify outlier detection works"""
        # Train with normal measurements
        for i in range(20):
            self.kf.predict(0.1)
            measurement = np.array([0.1 * i, 0.05 * i])
            self.kf.update(measurement)
        
        # Inject outlier
        outlier = np.array([100.0, 100.0])
        result = self.kf.update(outlier)
        
        self.assertTrue(result['outlier_detected'])
        self.assertFalse(result['updated'])
    
    def test_normal_update(self):
        """Verify normal measurements accepted"""
        self.kf.predict(0.1)
        measurement = np.array([0.1, 0.1])
        result = self.kf.update(measurement)
        
        self.assertTrue(result['updated'])
        self.assertFalse(result['outlier_detected'])
    
    def test_uncertainty_tracking(self):
        """Verify uncertainty computed correctly"""
        uncertainty = self.kf.get_position_uncertainty()
        self.assertGreater(uncertainty, 0.0)


class TestRobotBrain(unittest.TestCase):
    """Robot brain integration tests"""
    
    def setUp(self):
        self.brain = RobotBrain()
        self.sim = RobotSimulator()
    
    def test_initialization(self):
        """Verify brain initializes correctly"""
        self.assertIsNotNone(self.brain.motor_left)
        self.assertIsNotNone(self.brain.motor_right)
        self.assertIsNotNone(self.brain.sensor_fusion)
    
    def test_perception(self):
        """Verify sensor processing"""
        sensors = self.sim.get_sensors()
        perception = self.brain.perceive(sensors)
        
        self.assertIn('perception', perception)
        self.assertIn('field_energy', perception)
        self.assertIn('threat_level', perception)
    
    def test_decision_making(self):
        """Verify decision generation"""
        sensors = self.sim.get_sensors()
        perception = self.brain.perceive(sensors)
        decision = self.brain.think(perception)
        
        self.assertIn('decision', decision)
        self.assertIn('confidence', decision)
        self.assertIn('behavior_sequence', decision)
    
    def test_motor_control(self):
        """Verify motor command generation"""
        sensors = self.sim.get_sensors()
        perception = self.brain.perceive(sensors)
        decision = self.brain.think(perception)
        action = self.brain.act(decision)
        
        self.assertIn('left_motor', action)
        self.assertIn('right_motor', action)
        self.assertIsInstance(action['left_motor'], float)
    
    def test_brain_loop_timing(self):
        """Verify brain loop meets real-time requirements"""
        start = time.time()
        
        sensors = self.sim.get_sensors()
        perception = self.brain.perceive(sensors)
        decision = self.brain.think(perception)
        action = self.brain.act(decision)
        
        elapsed = time.time() - start
        
        # Should complete in < 100ms for 10Hz operation
        self.assertLess(elapsed, 0.1)


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests"""
    
    def test_safe_navigation(self):
        """Verify robot navigates safely"""
        brain = RobotBrain()
        sim = RobotSimulator()
        safety = SafetyMonitor(SafetyConstraints())
        
        for i in range(10):
            sensors = sim.get_sensors()
            perception = brain.perceive(sensors)
            decision = brain.think(perception)
            action = brain.act(decision)
            
            # Apply safety layer
            safety.pet_watchdog()
            safe_left, safe_right = safety.enforce_safe_command(
                action['left_motor'],
                action['right_motor'],
                sensors
            )
            
            # Commands should be safe
            self.assertLessEqual(abs(safe_left), 100.0)
            self.assertLessEqual(abs(safe_right), 100.0)
    
    def test_sensor_fusion_integration(self):
        """Verify sensor fusion with Kalman filter"""
        fusion = MultiSensorFusion(state_dim=4)
        fusion.add_sensor('distance', measurement_dim=3, weight=1.0)
        
        sim = RobotSimulator()
        
        for i in range(20):
            sensors = sim.get_sensors()
            readings = [SensorReading(
                value=sensors,
                timestamp=time.time(),
                sensor_id='distance'
            )]
            
            result = fusion.update(readings, dt=0.1)
            
            self.assertIn('state', result)
            self.assertIn('uncertainty', result)
            self.assertIsInstance(result['uncertainty'], float)


class TestPerformance(unittest.TestCase):
    """Performance and stress tests"""
    
    def test_brain_throughput(self):
        """Measure brain loop throughput"""
        brain = RobotBrain()
        sim = RobotSimulator()
        
        iterations = 100
        start = time.time()
        
        for i in range(iterations):
            sensors = sim.get_sensors()
            perception = brain.perceive(sensors)
            decision = brain.think(perception)
            action = brain.act(decision)
        
        elapsed = time.time() - start
        hz = iterations / elapsed
        
        print(f"\n  Brain throughput: {hz:.1f} Hz")
        
        # Should achieve at least 10Hz
        self.assertGreater(hz, 10.0)
    
    def test_kalman_throughput(self):
        """Measure Kalman filter throughput"""
        kf = LorenzEnhancedKalmanFilter(state_dim=4, measurement_dim=2)
        
        iterations = 1000
        start = time.time()
        
        for i in range(iterations):
            kf.predict(0.01)
            measurement = np.random.rand(2)
            kf.update(measurement)
        
        elapsed = time.time() - start
        hz = iterations / elapsed
        
        print(f"  Kalman throughput: {hz:.1f} Hz")
        
        # Should handle at least 100Hz
        self.assertGreater(hz, 100.0)


class TestHardwareAbstraction(unittest.TestCase):
    """Hardware abstraction conformance tests"""

    def test_simulated_hardware_pose_and_reset(self):
        hw = SimulatedRobotHardware()

        pose0 = hw.get_pose()
        self.assertAlmostEqual(pose0.x, 0.0, delta=1e-6)
        self.assertAlmostEqual(pose0.y, 0.0, delta=1e-6)

        hw.set_motors({'left_motor': 50, 'right_motor': 50})
        pose1 = hw.get_pose()
        self.assertNotEqual((pose1.x, pose1.y), (pose0.x, pose0.y))

        hw.reset()
        pose2 = hw.get_pose()
        self.assertAlmostEqual(pose2.x, 0.0, delta=1e-6)
        self.assertAlmostEqual(pose2.y, 0.0, delta=1e-6)

    def test_simulated_hardware_sensors_shape(self):
        hw = SimulatedRobotHardware()
        sensors = hw.get_sensors()

        self.assertEqual(sensors.shape, (3,))
        self.assertTrue(np.all(sensors >= 0.0))

    def test_serial_json_hardware_adapter(self):
        class FakeSerial:
            def __init__(self):
                self._next_line = b''

            def write(self, data):
                req = json.loads(data.decode('utf-8').strip())
                cmd = req.get('cmd')

                if cmd == 'get_sensors':
                    resp = {'status': 'ok', 'sensors': [1.0, 2.0, 3.0]}
                elif cmd == 'set_motors':
                    left = req.get('left_motor', 0.0)
                    right = req.get('right_motor', 0.0)
                    resp = {
                        'status': 'ok',
                        'pose': {'x': float(left) * 0.01, 'y': float(right) * 0.01, 'theta': 0.1}
                    }
                elif cmd == 'get_pose':
                    resp = {'status': 'ok', 'pose': {'x': 0.5, 'y': -0.1, 'theta': 0.2}}
                elif cmd == 'reset':
                    resp = {'status': 'ok'}
                else:
                    resp = {'status': 'error', 'error': 'unknown_cmd'}

                self._next_line = (json.dumps(resp) + '\n').encode('utf-8')

            def flush(self):
                return

            def readline(self):
                line = self._next_line
                self._next_line = b''
                return line

            def close(self):
                return

        fake_serial = FakeSerial()
        hw = SerialJsonRobotHardware(serial_conn=fake_serial)

        sensors = hw.get_sensors()
        self.assertEqual(sensors.shape, (3,))
        self.assertAlmostEqual(float(np.sum(sensors)), 6.0, delta=1e-6)

        pose_from_cmd = hw.set_motors({'left_motor': 50, 'right_motor': 10})
        self.assertIn('x', pose_from_cmd)
        self.assertIn('y', pose_from_cmd)

        pose = hw.get_pose()
        self.assertAlmostEqual(pose.x, 0.5, delta=1e-6)
        self.assertAlmostEqual(pose.theta, 0.2, delta=1e-6)

        hw.reset()
        hw.close()

    def test_ros2_hardware_adapter_with_fake_client(self):
        class FakeRosClient:
            def __init__(self):
                self._pose = type("Pose", (), {"x": 0.0, "y": 0.0, "theta": 0.0})()

            def get_sensors(self):
                return np.array([0.2, 0.4, 0.6])

            def set_motors(self, motor_cmd):
                self._pose.x += float(motor_cmd.get('left_motor', 0.0)) * 0.001
                self._pose.y += float(motor_cmd.get('right_motor', 0.0)) * 0.001
                return {'x': self._pose.x, 'y': self._pose.y, 'theta': self._pose.theta}

            def get_pose(self):
                return self._pose

            def reset(self):
                self._pose.x = 0.0
                self._pose.y = 0.0
                self._pose.theta = 0.0

            def close(self):
                return

        fake = FakeRosClient()
        hw = Ros2RobotHardware(ros_client=fake)

        sensors = hw.get_sensors()
        self.assertEqual(sensors.shape, (3,))

        hw.set_motors({'left_motor': 100, 'right_motor': 50})
        pose = hw.get_pose()
        self.assertGreater(pose.x, 0.0)
        self.assertGreater(pose.y, 0.0)

        hw.reset()
        pose2 = hw.get_pose()
        self.assertAlmostEqual(pose2.x, 0.0, delta=1e-6)
        self.assertAlmostEqual(pose2.y, 0.0, delta=1e-6)
        hw.close()

    def test_factory_ros2_backend_with_injected_client(self):
        class FakeRosClient:
            def get_sensors(self):
                return np.array([1.0, 1.0, 1.0])

            def set_motors(self, motor_cmd):
                return {'x': 0.0, 'y': 0.0, 'theta': 0.0}

            def get_pose(self):
                return type("Pose", (), {"x": 0.0, "y": 0.0, "theta": 0.0})()

            def reset(self):
                return

            def close(self):
                return

        adapter = create_hardware_adapter('ros2', ros_client=FakeRosClient())
        self.assertTrue(hasattr(adapter, 'get_sensors'))
        self.assertEqual(adapter.get_sensors().shape, (3,))


def run_continuous_validation():
    """Run full test suite with coverage reporting"""
    print("=" * 60)
    print("SPINN ROBOT BRAIN - CONTINUOUS VALIDATION")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestKalmanFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestRobotBrain))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestHardwareAbstraction))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_continuous_validation()
    exit(0 if success else 1)
