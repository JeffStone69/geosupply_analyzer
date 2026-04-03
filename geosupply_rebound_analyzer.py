import argparse
import os
import time
import subprocess
import json
import re
from pathlib import Path
import requests
========================= CONFIG =========================
DEFAULT_TARGET = "target.py"
MAX_ITERATIONS = 20
TIMEOUT_SECONDS = 30
API_MODEL = "grok-4.20-non-reasoning"
API_BASE = "https://api.x.ai/v1"
def get_api_key():
return os.getenv("GROK_API_KEY") or os.getenv("OPENAI_API_KEY")
def call_llm(prompt: str, temperature: float = 0.7) -> str:
api_key = get_api_key()
if not api_key:
raise ValueError("Set GROK_API_KEY (or OPENAI_API_KEY) environment variable.")
headers = {
"Content-Type": "application/json",
"Authorization": f"Bearer {api_key}",
}
data = {
"model": API_MODEL,
"messages": [{"role": "user", "content": prompt}],
"temperature": temperature,
"max_tokens": 4096,
}
try:
response = requests.post(
f"{API_BASE}/chat/completions", headers=headers, json=data, timeout=120
)
response.raise_for_status()
return response.json()["choices"][0]["message"]["content"]
except requests.exceptions.RequestException as e:
raise RuntimeError(f"LLM API call failed: {e}") from e
def read_file(path: str) -> str:
with open(path, "r", encoding="utf-8") as f:
return f.read()
def write_file(path: str, content: str):
with open(path, "w", encoding="utf-8") as f:
f.write(content)
def backup_file(path: str):
path = Path(path)
if path.exists():
backup_path = path.with_suffix(".bak")
backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
print(f"✅ Backed up original to {backup_path}")
def run_script(script_path: str, timeout: int = TIMEOUT_SECONDS):
start = time.time()
try:
result = subprocess.run(
["python", script_path],
capture_output=True,
text=True,
timeout=timeout,
)
duration = time.time() - start
return {
"success": result.returncode == 0,
"stdout": result.stdout.strip(),
"stderr": result.stderr.strip(),
"duration": round(duration, 3),
"returncode": result.returncode,
}
except subprocess.TimeoutExpired:
return {"success": False, "error": "Timeout", "duration": timeout}
except Exception as e:
return {"success": False, "error": str(e), "duration": round(time.time() - start, 3)}
def improve_code(current_code: str, history: list, run_feedback: dict = None) -> str:
prompt = f"""You are an expert Python code optimizer.
Current code to improve:
Python{current_code}
Previous versions and scores (for context):
{json.dumps(history, indent=2)}
"""
if run_feedback:
prompt += f"""
Latest run feedback:
Success: {run_feedback.get('success', False)}
Duration: {run_feedback.get('duration', 'N/A')}s
Stdout: {run_feedback.get('stdout', '')[:500]}
Stderr: {run_feedback.get('stderr', '')[:500]}
"""
prompt += """
Improve this code significantly in one step. Focus on:

Performance (faster execution, better algorithms, vectorization where possible)
Readability and style (PEP 8, clean structure, good names)
Robustness (error handling, type hints where helpful)
Best practices (modern Python)

Maintain the original intent and functionality exactly.
Return ONLY the full improved Python code inside a single ```python
Do not add any explanations, comments, or extra text outside the code block.
"""
response = call_llm(prompt, temperature=0.5)
Extremely robust code extraction to handle Grok's output quirks
Try 1: Standard ```python block
match = re.search(r"python\s*(.*?)", response, re.DOTALL | re.IGNORECASE)
if match:
code = match.group(1).strip()
else:
Try 2: Any ``` block
match = re.search(r"\s*(.*?)", response, re.DOTALL | re.IGNORECASE)
if match:
code = match.group(1).strip()
else:
Try 3: Look for code that starts with "import " or "def " (fallback)
lines = response.splitlines()
code_lines = []
in_code = False
for line in lines:
if not in_code and (line.strip().startswith("import ") or line.strip().startswith("from ") or line.strip().startswith("def ") or line.strip().startswith("#")):
in_code = True
if in_code:
code_lines.append(line)
code = "\n".join(code_lines).strip()
if not code:
Final fallback: return the whole response cleaned
code = response.strip()
Clean up common extra text that might sneak in
if code.startswith(""):         code = code.split("", 1)[-1].strip()
if code.endswith(""):         code = code.rsplit("", 1)[0].strip()
return code
def main():
parser = argparse.ArgumentParser(
description="Self-improving code optimizer"
)
parser.add_argument(
"--target", type=str, default=DEFAULT_TARGET, help="Path to the Python script to optimize"
)
parser.add_argument(
"--max_iters", type=int, default=MAX_ITERATIONS, help="Maximum improvement iterations"
)
parser.add_argument(
"--output_dir", type=str, default="improvements", help="Directory to save versions"
)
parser.add_argument(
"--temperature", type=float, default=0.6, help="LLM creativity"
)
args = parser.parse_args()
target_path = Path(args.target)
if not target_path.exists():
print(f"❌ Error: {target_path} not found.")
return
backup_file(target_path)
out_dir = Path(args.output_dir)
out_dir.mkdir(exist_ok=True)
current_code = read_file(target_path)
history = []
print(f"🚀 Starting self-improvement on {target_path} for up to {args.max_iters} iterations...\n")
for iteration in range(1, args.max_iters + 1):
print(f"\n=== Iteration {iteration}/{args.max_iters} ===")
print("Running current version...")
feedback = run_script(str(target_path))
print(f"✅ Success: {feedback['success']}, Duration: {feedback.get('duration', 'N/A')}s")
score = feedback.get('duration', 999) if feedback['success'] else 9999
if not feedback['success']:
score += 1000
history.append({
"version": iteration - 1,
"code": current_code[:500] + "..." if len(current_code) > 500 else current_code,
"feedback": feedback,
"score": round(score, 3)
})
print("Generating improvements via LLM...")
try:
new_code = improve_code(current_code, history[-5:], feedback)
except Exception as e:
print(f"❌ LLM improvement failed: {e}")
break
new_path = out_dir / f"version_{iteration:03d}.py"
write_file(str(new_path), new_code)
print(f"💾 Saved improved version to {new_path}")
current_code = new_code
write_file(str(target_path), new_code)
if feedback['success'] and feedback.get('duration', 999) < 0.1:
print("🎉 Excellent performance reached. Stopping early.")
break
print("\n=== Self-improvement completed! ===")
print(f"📁 Best versions saved in: {out_dir}")
print("Review the versions and pick the one you like best.")
if name == "main":
main()