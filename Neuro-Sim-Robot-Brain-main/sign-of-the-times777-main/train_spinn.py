"""
SPINN Training Script
Tests SPINN effectiveness on real datasets using HuggingFace datasets
"""

import numpy as np
from datasets import load_dataset
from SPINN_Web import SPIPrototype
import json
from datetime import datetime

class SPINNTrainer:
    def __init__(self):
        print("🌀 Initializing SPINN for training...")
        self.spi = SPIPrototype()
        self.training_log = []
        
    def prepare_text_data(self, dataset_name="wikitext", config="wikitext-2-raw-v1", split="train", max_samples=100):
        """Load and prepare dataset"""
        print(f"📚 Loading dataset: {dataset_name}...")
        try:
            dataset = load_dataset(dataset_name, config, split=split, streaming=True)
            
            texts = []
            for i, item in enumerate(dataset):
                if i >= max_samples:
                    break
                text = item.get('text', '')
                if text and len(text.strip()) > 20:  # Filter short/empty texts
                    texts.append(text.strip())
                    
            print(f"✓ Loaded {len(texts)} text samples")
            return texts
        except Exception as e:
            print(f"Error loading dataset: {e}")
            return []
    
    def train_on_text(self, text):
        """Train SPINN on a single text sample"""
        # Mode 1: Intake - encode text into core field
        intake_result = self.spi.mode1_intake(text)
        
        # Mode 2: Process - evolve patterns
        process_result = self.spi.mode2_process()
        
        # Mode 3: Generate output to test understanding
        output_result = self.spi.mode3_output(text[:100])  # Use first 100 chars as query
        
        return {
            'intake': intake_result,
            'process': process_result,
            'output': output_result,
            'text_length': len(text),
            'field_variance': float(np.var(self.spi.core_field))
        }
    
    def train_batch(self, texts, batch_name="batch"):
        """Train on multiple texts"""
        print(f"\n🔄 Training on {len(texts)} samples...")
        
        results = []
        for i, text in enumerate(texts):
            if i % 10 == 0:
                print(f"  Processing sample {i+1}/{len(texts)}...")
            
            try:
                result = self.train_on_text(text)
                results.append({
                    'sample_id': i,
                    'text_preview': text[:100],
                    'metrics': result
                })
            except Exception as e:
                print(f"  Error on sample {i}: {e}")
                continue
        
        # Analyze results
        field_variances = [r['metrics']['field_variance'] for r in results]
        avg_variance = np.mean(field_variances)
        
        print(f"\n📊 Batch Results:")
        print(f"  Samples processed: {len(results)}")
        print(f"  Average field variance: {avg_variance:.4f}")
        print(f"  Creativity expressions: {len(self.spi.three_field_net['creativity'])}")
        print(f"  Logic clusters: {len(self.spi.three_field_net['logic'])}")
        
        return {
            'batch_name': batch_name,
            'num_samples': len(results),
            'avg_variance': avg_variance,
            'results': results[:5]  # Store first 5 for inspection
        }
    
    def test_understanding(self, test_queries):
        """Test SPINN's understanding after training"""
        print("\n🧪 Testing SPINN understanding...")
        
        test_results = []
        for query in test_queries:
            print(f"\n  Query: {query}")
            output = self.spi.mode3_output(query)
            print(f"  Response preview: {output['response'][:150]}...")
            
            test_results.append({
                'query': query,
                'response': output['response'],
                'creative_prompt': output['creative_prompt'],
                'logical_val': output['logical_val']
            })
        
        return test_results
    
    def run_quantum_analysis(self):
        """Analyze quantum coherence after training"""
        print("\n⚛️ Running quantum coherence analysis...")
        coherence = self.spi.run_quantum_monitor()
        print(f"  Coherence mean: {coherence['coherence_mean']:.4f}")
        return coherence
    
    def save_results(self, filename="spinn_training_results.json"):
        """Save training results"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'training_log': self.training_log,
            'final_state': {
                'creativity': self.spi.three_field_net['creativity'],
                'logic': self.spi.three_field_net['logic'][:10],  # First 10 values
                'core_field_stats': {
                    'mean': float(np.mean(self.spi.core_field)),
                    'variance': float(np.var(self.spi.core_field)),
                    'std': float(np.std(self.spi.core_field))
                }
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to {filename}")

def main():
    print("=" * 60)
    print("SPINN EFFECTIVENESS TEST")
    print("Training on HuggingFace Dataset")
    print("=" * 60)
    
    trainer = SPINNTrainer()
    
    # Load training data
    texts = trainer.prepare_text_data(
        dataset_name="wikitext",
        config="wikitext-2-raw-v1",
        split="train",
        max_samples=50  # Start small to test
    )
    
    if not texts:
        print("❌ No data loaded. Exiting.")
        return
    
    # Train
    batch_result = trainer.train_batch(texts, "wikitext_batch_1")
    trainer.training_log.append(batch_result)
    
    # Test understanding
    test_queries = [
        "What is the meaning of life?",
        "Explain quantum mechanics",
        "How does consciousness work?",
        "What is the nature of reality?"
    ]
    
    test_results = trainer.test_understanding(test_queries)
    trainer.training_log.append({'test_results': test_results})
    
    # Quantum analysis
    quantum_results = trainer.run_quantum_analysis()
    trainer.training_log.append({'quantum_analysis': quantum_results})
    
    # Save results
    trainer.save_results()
    
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Trained on {len(texts)} samples")
    print(f"  Generated {len(trainer.spi.three_field_net['creativity'])} creative expressions")
    print(f"  Processed {len(test_queries)} test queries")
    print(f"  Quantum coherence: {quantum_results['coherence_mean']:.4f}")

if __name__ == "__main__":
    main()
