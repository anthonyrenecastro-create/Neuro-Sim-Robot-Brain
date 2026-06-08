import numpy as np
from sklearn.cluster import KMeans
import random
from math import log
from scipy.integrate import odeint
import speech_recognition as sr  # STT
import pyttsx3  # TTS (offline)
import time  # Throttling
from transformers import AutoTokenizer, AutoModelForCausalLM  # LLM embedding
import torch  # For LLM

# Quantum Error Correction Imports (added for 2025 integration)
import qiskit  # For quantum simulations and surface code
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.quantum_info import Statevector, Operator
from qiskit.visualization import plot_histogram
import matplotlib.pyplot as plt  # For coherence analysis plots

# GUI Imports (added for polished interface)
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from tkinter import font as tkfont
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Core Dynamics (unchanged from prior)
def lorenz_system(state, t, sigma=10, beta=8/3, rho=28):
    x, y, z = state
    dxdt = sigma * (y - x)
    dydt = x * (rho - z) - y
    dzdt = x * y - beta * z
    return [dxdt, dydt, dzdt]

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

def simulate_system(initial_state, t, pid_controller, control_amplitude=0.1):
    dt = t[1] - t[0]
    states = [initial_state]
    state = initial_state
    for time in t[1:]:
        control_signal = pid_controller.control(state[2], dt)
        derivs = lorenz_system(state, time)
        dz_controlled = derivs[2] + control_amplitude * control_signal
        state = [state[i] + derivs[i] * dt if i != 2 else state[2] + dz_controlled * dt for i in range(3)]
        states.append(state)
    return np.array(states)

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

# Enhanced MorphoField (unchanged)
OPERATORS = ['+', '*', '-', '/']
VARIABLES = ['A', 'B', 'C']
MAX_LENGTH = 20
VAR_MAP = {'A': 2, 'B': 3, 'C': 5}
N_GENOMES = 8
MAX_RETRIES = 20

def safe_eval(expr):
    try:
        e = expr.replace('/', '//')
        for v, val in VAR_MAP.items():
            e = e.replace(v, str(val))
        return eval(e)
    except:
        return 1

def factor_count(n):
    if n <= 1:
        return 0
    count = 0
    while n % 2 == 0:
        n //= 2
        count += 1
    d = 3
    while d * d <= n:
        while n % d == 0:
            n //= d
            count += 1
        d += 2
    if n > 1:
        count += 1
    return count

def initialize_expressions(num_expr=N_GENOMES):
    return [f"{random.choice(VARIABLES)}{random.choice(OPERATORS)}{random.choice(VARIABLES)}" for _ in range(num_expr)]

def generate_variations(expressions, num_variations=N_GENOMES * 2):
    variations = []
    tortoise = hare = 0
    for _ in range(num_variations):
        expr = random.choice(expressions)
        if random.random() < 0.6:
            if len(expr) < MAX_LENGTH:
                parts = list(expr)
                for i, char in enumerate(parts):
                    if char in OPERATORS:
                        parts[i] = random.choice(OPERATORS)
                    elif char in VARIABLES:
                        parts[i] = random.choice(VARIABLES)
                variations.append(''.join(parts))
            else:
                variations.append(expr + random.choice(OPERATORS) + random.choice(VARIABLES))
        else:
            other = random.choice(expressions)
            split1 = random.randint(1, max(1, len(expr)//2))
            split2 = random.randint(1, max(1, len(other)//2))
            new_expr = expr[:split1] + other[split2:]
            variations.append(new_expr if len(new_expr) <= MAX_LENGTH else expr)

        hare = (hare + 2) % len(variations) if variations else 0
        tortoise = (tortoise + 1) % len(variations) if variations else 0
        if len(variations) > 2 and variations[hare] == variations[tortoise]:
            variations[-1] = random.choice(expressions) + random.choice(OPERATORS) + random.choice(VARIABLES)

    retries = 0
    while len(set(variations)) < num_variations // 2 and retries < MAX_RETRIES:
        variations.append(initialize_expressions(1)[0])
        retries += 1
    return variations[:num_variations]

def simplify_expressions(expressions):
    def fitness(expr):
        val = safe_eval(expr)
        syntactic = len(expr) + sum(expr.count(op) for op in OPERATORS)
        semantic = factor_count(val) * log(val + 1) if val > 1 else 0
        return syntactic - semantic
    complexities = [(expr, fitness(expr)) for expr in expressions]
    complexities.sort(key=lambda x: x[1])
    return [expr for expr, _ in complexities[:N_GENOMES]]

def morphofield_evo_coding(iterations=10):
    expressions = initialize_expressions()
    for i in range(iterations):
        variations = generate_variations(expressions)
        expressions = simplify_expressions(variations)
    return expressions

# Syntropy & Perennial Fields (unchanged)
def syntropy_field(phi_0, t, lambda_damp=0.1, mu=1):
    def dphi_dt(phi, t):
        d2phi = -phi + lambda_damp * np.gradient(phi, t)
        return np.concatenate(([0], np.diff(phi)))
    return odeint(dphi_dt, phi_0, t)[:, 0]

def perennial_morphogenic(t, omega=1, n_terms=5):
    fib = [0, 1]
    for _ in range(2, n_terms + 1):
        fib.append(fib[-1] + fib[-2])
    return sum((fib[k] / np.math.factorial(k)) * np.exp(-1j * omega * t) for k in range(n_terms)).real



# Full LLM Embedding (Phi-3-mini for 2025 lightweight perf)
class LLMEmbed:
    def __init__(self, model_name="microsoft/Phi-3-mini-4k-instruct"):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True
            )
            print("LLM loaded: Phi-3-mini")
        except Exception as e:
            print(f"LLM load error: {e}. Using sim fallback.")
            self.model = None

    def generate(self, prompt, max_length=150):
        if self.model is None:
            return f"Sim response to: {prompt}"
        inputs = self.tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_length=max_length, temperature=0.7, do_sample=True, pad_token_id=self.tokenizer.eos_token_id
            )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

# Quantum Error Correction Module (New for 2025)
class QuantumErrorCorrectionAI:
    def __init__(self, spi_core, num_qubits=10, surface_code_distance=3):
        self.spi = spi_core  # Reference to SPIPrototype for syntropy and perennial fields
        self.num_qubits = num_qubits
        self.surface_code_distance = surface_code_distance
        self.simulator = AerSimulator()
        self.qubit_states = np.random.rand(num_qubits)  # Simulated coherence levels (0-1)
        self.decoherence_rates = np.random.exponential(0.1, num_qubits)  # Simulated decoherence rates
        self.pattern_mod = PatternRecognitionModule(n_clusters=5)  # For surface code pattern analysis

    def simulate_surface_code(self):
        # Simplified surface code simulation using Qiskit
        qc = QuantumCircuit(self.num_qubits)
        # Add data qubits and syndrome qubits (simplified)
        for i in range(self.num_qubits):
            qc.h(i)  # Initialize in superposition
            if random.random() < 0.1:  # Simulate errors
                qc.x(i)  # Bit flip error
        qc.measure_all()
        transpiled = transpile(qc, self.simulator)
        job = self.simulator.run(transpiled, shots=1000)
        result = job.result()
        counts = result.get_counts()
        return counts

    def analyze_coherence(self):
        # Use syntropy field to model coherence dynamics
        t = np.linspace(0, 1, len(self.qubit_states))
        syntropy_coherence = syntropy_field(self.qubit_states, t)
        # Analyze with pattern recognition
        coherence_data = syntropy_coherence.reshape(-1, 1)
        labels = self.pattern_mod.fit(coherence_data)
        centers = self.pattern_mod.analyze_clusters(coherence_data)
        return {'coherence_levels': syntropy_coherence, 'patterns': centers.flatten()}

    def calculate_decoherence_correction(self):
        # Use perennial morphogenic field for adaptive corrections
        t = np.linspace(0, 1, self.num_qubits)
        morph_field = perennial_morphogenic(t)
        corrections = morph_field * (1 - self.qubit_states)  # Scale by decoherence gap
        # LLM-guided reasoning for corrections
        llm_prompt = f"Optimize quantum error correction for decoherence rates {self.decoherence_rates[:5]}. Suggest adjustments using syntropy principles."
        llm_suggestion = self.spi.llm.generate(llm_prompt, max_length=100)
        print(f"LLM Correction Advice: {llm_suggestion}")
        return corrections, llm_suggestion

    def recursive_monitor(self, iterations=10):
        for i in range(iterations):
            # Update qubit data via syntropy (physics inherent in SPI code)
            surface_patterns = self.simulate_surface_code()
            coherence_analysis = self.analyze_coherence()
            corrections, advice = self.calculate_decoherence_correction()
            # Apply corrections (simulated)
            self.qubit_states += corrections * 0.1  # Dampened update
            self.qubit_states = np.clip(self.qubit_states, 0, 1)  # Clamp to valid range
            print(f"Iteration {i+1}: Coherence mean {np.mean(coherence_analysis['coherence_levels']):.3f}, Corrections applied.")
            # Feed back to SPI core for knowledge growth
            self.spi.core_field[:self.num_qubits] += self.qubit_states * 0.01

# Polished GUI Interface (New for 2025)
class SPIGUI:
    def __init__(self, spi_core):
        self.spi = spi_core
        self.root = tk.Tk()
        self.root.title("SPI Prototype - Quantum AI Interface")
        self.root.geometry("1200x800")
        self.root.configure(bg='white')  # Soft soothing white background

        # Custom font for soothing aesthetic
        self.custom_font = tkfont.Font(family="Helvetica", size=12)
        self.header_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        # Style for black and white theme
        style = ttk.Style()
        style.theme_use('clam')  # Base theme for customization
        style.configure('TNotebook', background='white', borderwidth=0)
        style.configure('TNotebook.Tab', background='lightgray', foreground='black', padding=[10, 5], font=self.custom_font)
        style.map('TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', 'black')])
        style.configure('TFrame', background='white')
        style.configure('TButton', background='lightgray', foreground='black', font=self.custom_font, padding=[5, 5])
        style.configure('TLabel', background='white', foreground='black', font=self.custom_font)
        style.configure('TEntry', font=self.custom_font)
        style.configure('TText', font=self.custom_font)

        # Notebook for raised tabs
        self.notebook = ttk.Notebook(self.root, style='TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tabs
        self.intake_tab = ttk.Frame(self.notebook, style='TFrame')
        self.process_tab = ttk.Frame(self.notebook, style='TFrame')
        self.output_tab = ttk.Frame(self.notebook, style='TFrame')
        self.quantum_tab = ttk.Frame(self.notebook, style='TFrame')

        self.notebook.add(self.intake_tab, text='Intake')
        self.notebook.add(self.process_tab, text='Process')
        self.notebook.add(self.output_tab, text='Output')
        self.notebook.add(self.quantum_tab, text='Quantum AI')

        # Intake Tab
        ttk.Label(self.intake_tab, text="Speech/Text Intake", font=self.header_font).pack(pady=10)
        self.speech_button = ttk.Button(self.intake_tab, text="Start Speech Input", command=self.start_speech)
        self.speech_button.pack(pady=5)
        self.text_entry = ttk.Entry(self.intake_tab, width=50)
        self.text_entry.pack(pady=5)
        self.intake_button = ttk.Button(self.intake_tab, text="Process Intake", command=self.process_intake)
        self.intake_button.pack(pady=5)

        # Process Tab
        ttk.Label(self.process_tab, text="Data Processing", font=self.header_font).pack(pady=10)
        self.process_button = ttk.Button(self.process_tab, text="Run Processing", command=self.run_process)
        self.process_button.pack(pady=5)
        self.process_output = scrolledtext.ScrolledText(self.process_tab, wrap=tk.WORD, width=80, height=20, font=self.custom_font)
        self.process_output.pack(pady=5, fill='both', expand=True)

        # Output Tab
        ttk.Label(self.output_tab, text="Response Output", font=self.header_font).pack(pady=10)
        self.query_entry = ttk.Entry(self.output_tab, width=50)
        self.query_entry.pack(pady=5)
        self.output_button = ttk.Button(self.output_tab, text="Generate Output", command=self.generate_output)
        self.output_button.pack(pady=5)
        self.output_text = scrolledtext.ScrolledText(self.output_tab, wrap=tk.WORD, width=80, height=20, font=self.custom_font)
        self.output_text.pack(pady=5, fill='both', expand=True)
        self.speech_out_var = tk.BooleanVar()
        ttk.Checkbutton(self.output_tab, text="Enable Speech Output", variable=self.speech_out_var).pack(pady=5)

        # Quantum Tab
        ttk.Label(self.quantum_tab, text="Quantum Error Correction", font=self.header_font).pack(pady=10)
        self.quantum_button = ttk.Button(self.quantum_tab, text="Run Quantum Monitor", command=self.run_quantum)
        self.quantum_button.pack(pady=5)
        self.quantum_output = scrolledtext.ScrolledText(self.quantum_tab, wrap=tk.WORD, width=80, height=20, font=self.custom_font)
        self.quantum_output.pack(pady=5, fill='both', expand=True)
        # Matplotlib canvas for coherence plot
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor='white')
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.quantum_tab)
        self.canvas.get_tk_widget().pack(pady=5)

    def start_speech(self):
        try:
            self.speech_button.config(text="Listening...")
            self.root.update()
            embedding = self.spi.speech_intake()
            self.text_entry.delete(0, tk.END)
            self.text_entry.insert(0, "Speech processed (embedding generated)")
            self.speech_button.config(text="Start Speech Input")
        except Exception as e:
            messagebox.showerror("Error", f"Speech input failed: {e}")
            self.speech_button.config(text="Start Speech Input")

    def process_intake(self):
        text = self.text_entry.get()
        if text:
            input_data = np.array([ord(c) % 100 for c in text[:100]])
            self.spi.mode1_intake(input_data=input_data)
            messagebox.showinfo("Success", "Intake processed.")
        else:
            messagebox.showwarning("Warning", "Enter text or use speech.")

    def run_process(self):
        result = self.spi.mode2_process()
        self.process_output.delete('1.0', tk.END)
        self.process_output.insert(tk.END, result)

    def generate_output(self):
        query = self.query_entry.get() or "Default query"
        result = self.spi.mode3_output(input_text=query, use_speech_out=self.speech_out_var.get())
        self.output_text.delete('1.0', tk.END)
        self.output_text.insert(tk.END, result)

    def run_quantum(self):
        self.spi.quantum_ai.recursive_monitor(iterations=5)
        coherence = self.spi.quantum_ai.qubit_states
        self.ax.clear()
        self.ax.plot(coherence, color='black', linewidth=2)
        self.ax.set_title("Qubit Coherence Levels", fontsize=14, color='black')
        self.ax.set_xlabel("Qubit Index", color='black')
        self.ax.set_ylabel("Coherence", color='black')
        self.ax.set_facecolor('white')
        self.canvas.draw()
        status = f"Coherence Mean: {np.mean(coherence):.3f}\nCorrections Applied."
        self.quantum_output.delete('1.0', tk.END)
        self.quantum_output.insert(tk.END, status)

    def run(self):
        self.root.mainloop()

# SPI Core Loop Prototype (Enhanced with Quantum Integration and GUI)
class SPIPrototype:
    def __init__(self):
        self.core_field = np.zeros(100)  # Raw data
        self.pid = PIDController(set_point=0)
        self.pattern_mod = PatternRecognitionModule(n_clusters=3)
        self.three_field_net = {'creativity': [], 'logic': [], 'deduction': []}
        self.recognizer = sr.Recognizer()  # STT init
        self.tts_engine = pyttsx3.init()  # TTS init
        self.tts_engine.setProperty('rate', 150)  # Speed
        self.llm = LLMEmbed()  # Full LLM
        # New: Quantum Error Correction AI
        self.quantum_ai = QuantumErrorCorrectionAI(self, num_qubits=20, surface_code_distance=5)
        # GUI
        self.gui = SPIGUI(self)

    def speech_intake(self, audio_file=None):  # Mode 1: STT (unchanged)
        try:
            if audio_file:
                with sr.AudioFile(audio_file) as source:
                    audio = self.recognizer.record(source)
            else:
                with sr.Microphone() as source:
                    print("Listening...")
                    audio = self.recognizer.listen(source, timeout=5)
            text = self.recognizer.recognize_sphinx(audio)
            print(f"Transcribed: {text}")
            embedding = np.array([ord(c) % 100 for c in text[:100]])
            return embedding
        except sr.UnknownValueError:
            return np.random.randn(100)
        except Exception as e:
            print(f"STT Error: {e}")
            return np.zeros(100)

    def mode1_intake(self, input_data=None, use_speech=False, audio_file=None):
        if use_speech:
            input_data = self.speech_intake(audio_file)
        vibes = np.array([np.sin(omega * np.arange(len(input_data)) + phi) for omega, phi in zip([1,2,3], [0, np.pi/2, np.pi])])
        self.core_field[:len(input_data)] = input_data * np.mean(vibes, axis=0)[:len(input_data)]
        return self.core_field



    def mode2_process(self, variance_threshold=5):
        var = np.var(self.core_field)
        if var > variance_threshold:
            t = np.linspace(0, 10, len(self.core_field))
            controlled = simulate_system(self.core_field[:3], t, self.pid)[-1, :]
            self.core_field[:3] = controlled

        if len(self.core_field) > 3:
            labels = self.pattern_mod.fit(self.core_field.reshape(-1, 1))
            centers = self.pattern_mod.analyze_clusters(self.core_field.reshape(-1, 1))
            self.three_field_net['logic'] = centers.flatten().tolist()

        self.three_field_net['creativity'] = morphofield_evo_coding(5)
        llm_prompt = random.choice(self.three_field_net['creativity'])
        return f"Processed with LLM prompt: {llm_prompt}"

    def speech_output(self, text):  # Mode 3: TTS (unchanged)
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            print(f"Spoken: {text[:50]}...")
        except Exception as e:
            print(f"TTS Error: {e}; Text: {text}")

    def mode3_output(self, input_text="Sample query", use_speech_out=True):
        t = np.linspace(0, 1, 10)
        morph_field = perennial_morphogenic(t)
        damped_field = syntropy_field(morph_field, t)

        creative_prompt = random.choice(self.three_field_net['creativity'])
        logical_val = np.mean(self.three_field_net['logic'])
        balanced_prompt = f"{creative_prompt} (Logic: {logical_val:.2f}). Query: {input_text}. Generate human-like response using Syntropy-Perennial principles and quantum error correction insights."

        llm_response = self.llm.generate(balanced_prompt, max_length=200)

        knowledge_growth = np.prod([1 + 0.1 * fib for fib in [1,1,2,3,5]])
        print(f"Knowledge multiplier (24h): {knowledge_growth:.2f}x")

        # Integrate quantum monitoring
        self.quantum_ai.recursive_monitor(iterations=5)  # Run quantum error correction cycle
        quantum_status = f"Quantum Coherence: {np.mean(self.quantum_ai.qubit_states):.3f}"

        response = f"{llm_response}\n{quantum_status}\nStabilized: Fractal insights from Syntropy-damped fields and surface code patterns."

        if use_speech_out:
            self.speech_output(response)
        return response

# Demo Run
if __name__ == "__main__":
    random.seed(42)
    spi = SPIPrototype()
    spi.gui.run()  # Launch GUI