"""
SPINN Training Script - Lightweight Version
Tests SPINN effectiveness on real datasets
"""

import numpy as np
from datasets import load_dataset
import json
from datetime import datetime
from sklearn.cluster import KMeans
import random
from math import log, factorial
from scipy.integrate import odeint

# Core SPINN components (without heavy imports)
class PIDController:
    def __init__(self, Kp=1, Ki=0.1, Kd=0.05, set_point=0):
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        self.set_point = set_point
        self.integral = 0
        self.last_error = None

    def control(self, measurement, dt):
        error = self.set_point - measurement
        self.integral += error * dt
        derivative = 0 if self.last_error is None else (error - self.last_error) / dt
        self.last_error = error
        return self.Kp * error + self.Ki * self.integral + self.Kd * derivative

class PatternRecognitionModule:
    def __init__(self, n_clusters=3):
        self.n_clusters = n_clusters
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.fitted = False

    def fit(self, data):
        self.kmeans.fit(data)
        self.fitted = True
        return self.kmeans.labels_

    def analyze_clusters(self, data):
        if not self.fitted:
            self.fit(data)
        return self.kmeans.cluster_centers_

OPERATORS = ['+', '*', '-', '/']
VARIABLES = ['A', 'B', 'C']
N_GENOMES = 8

def initialize_expressions(num_expr=N_GENOMES):
    return [f"{random.choice(VARIABLES)}{random.choice(OPERATORS)}{random.choice(VARIABLES)}" for _ in range(num_expr)]

def morphofield_evo_coding(iterations=5):
    expressions = initialize_expressions()
    for i in range(iterations):
        new_expr = []
        for expr in expressions:
            if len(expr) < 20:
                new_expr.append(expr + random.choice(OPERATORS) + random.choice(VARIABLES))
            else:
                new_expr.append(expr)
        expressions = new_expr[:N_GENOMES]
    return expressions

def syntropy_field(phi_0, t, lambda_damp=0.1):
    def dphi_dt(phi, t):
        return np.concatenate(([0], np.diff(phi)))
    return odeint(dphi_dt, phi_0, t)[:, 0]

def perennial_morphogenic(t, omega=1, n_terms=5):
    fib = [0, 1]
    for _ in range(2, n_terms + 1):
        fib.append(fib[-1] + fib[-2])
    return sum((fib[k] / factorial(k)) * np.exp(-1j * omega * t) for k in range(n_terms)).real

class SPIPrototype:
    def __init__(self):
        self.core_field = np.zeros(100)
        self.pid = PIDController(set_point=0)
        self.pattern_mod = PatternRecognitionModule(n_clusters=3)
        self.three_field_net = {'creativity': [], 'logic': [], 'deduction': []}
        random.seed(42)

    def mode1_intake(self, input_text):
        input_data = np.array([ord(c) % 100 for c in input_text[:100]])
        vibes = np.array([np.sin(omega * np.arange(len(input_data)) + phi) 
                         for omega, phi in zip([1,2,3], [0, np.pi/2, np.pi])])
        self.core_field[:len(input_data)] = input_data * np.mean(vibes, axis=0)[:len(input_data)]
        return {"status": "Intake processed", "field_mean": float(np.mean(self.core_field))}

    def mode2_process(self):
        self.three_field_net['creativity'] = morphofield_evo_coding(5)
        if len(self.core_field) > 3:
            labels = self.pattern_mod.fit(self.core_field.reshape(-1, 1))
            centers = self.pattern_mod.analyze_clusters(self.core_field.reshape(-1, 1))
            self.three_field_net['logic'] = centers.flatten().tolist()
        
        return {
            "status": "Processed",
            "creativity": self.three_field_net['creativity'],
            "logic": self.three_field_net['logic']
        }

    def mode3_output(self, input_text="Sample query"):
        t = np.linspace(0, 1, 10)
        morph_field = perennial_morphogenic(t)
        
        creative_prompt = random.choice(self.three_field_net['creativity']) if self.three_field_net['creativity'] else "A+B"
        logical_val = np.mean(self.three_field_net['logic']) if self.three_field_net['logic'] else 0.0
        
        response = f"SPINN Analysis [{creative_prompt}] Logic:{logical_val:.2f}: {input_text[:50]}"
        
        return {
            "response": response,
            "morphogenic_field": morph_field.tolist(),
            "creative_prompt": creative_prompt,
            "logical_val": float(logical_val)
        }

class SPINNTrainer:
    def __init__(self):
        print("🌀 Initializing SPINN for training...")
        self.spi = SPIPrototype()
        self.training_log = []
        
    def prepare_text_data(self, dataset_name="wikitext", config="wikitext-2-raw-v1", split="train", max_samples=50):
        print(f"📚 Loading dataset: {dataset_name}...")
        try:
            dataset = load_dataset(dataset_name, config, split=split, streaming=True)
            
            texts = []
            for i, item in enumerate(dataset):
                if len(texts) >= max_samples:
                    break
                text = item.get('text', '')
                if text and len(text.strip()) > 20:
                    texts.append(text.strip())
                    
            print(f"✓ Loaded {len(texts)} text samples")
            return texts
        except Exception as e:
            print(f"Error loading dataset: {e}")
            return []
    
    def train_on_text(self, text):
        intake_result = self.spi.mode1_intake(text)
        process_result = self.spi.mode2_process()
        output_result = self.spi.mode3_output(text[:100])
        
        return {
            'intake': intake_result,
            'process': process_result,
            'output': output_result,
            'text_length': len(text),
            'field_variance': float(np.var(self.spi.core_field))
        }
    
    def train_batch(self, texts):
        print(f"\n🔄 Training on {len(texts)} samples...")
        
        results = []
        for i, text in enumerate(texts):
            if i % 10 == 0:
                print(f"  Sample {i+1}/{len(texts)}...")
            
            try:
                result = self.train_on_text(text)
                results.append(result)
            except Exception as e:
                print(f"  Error on sample {i}: {e}")
        
        avg_variance = np.mean([r['field_variance'] for r in results])
        
        print(f"\n📊 Results:")
        print(f"  Processed: {len(results)} samples")
        print(f"  Avg field variance: {avg_variance:.4f}")
        print(f"  Creativity expressions: {len(self.spi.three_field_net['creativity'])}")
        
        return results
    
    def test_understanding(self, queries):
        print("\n🧪 Testing understanding...")
        
        for query in queries:
            output = self.spi.mode3_output(query)
            print(f"  Q: {query}")
            print(f"  A: {output['response']}")
            print()

def main():
    print("=" * 60)
    print("SPINN EFFECTIVENESS TEST")
    print("=" * 60)
    
    trainer = SPINNTrainer()
    
    texts = trainer.prepare_text_data(max_samples=50)
    
    if texts:
        trainer.train_batch(texts)
        
        trainer.test_understanding([
            "What is intelligence?",
            "Explain consciousness",
            "How does learning work?"
        ])
        
        print("\n✅ Training complete!")

if __name__ == "__main__":
    main()
