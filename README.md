# GenAI Purple Team Lab 🛡️⚔️

**An autonomous AI-on-AI security simulation environment.**

This project demonstrates a complete "Purple Team" lifecycle for Generative AI applications. It consists of an **Attacker Agent (Alpha)** that autonomously probes for vulnerabilities and a **Victim Agent (Beta)** instrumented with enterprise-grade observability to detect data exfiltration in real-time.

---

## 🏗️ Architecture

The lab simulates a "Red Team vs. Blue Team" scenario entirely within Google Cloud Run.

* **🔴 Agent Alpha (Red Team):** An autonomous Python agent powered by Gemini 1.5 Pro. It is instructed to perform SQL Injection (SQLi) and Prompt Injection attacks to steal sensitive data.
* **🔵 Agent Beta (Blue Team):** A vulnerable RAG (Retrieval-Augmented Generation) chatbot. It holds a simulated Customer PII database (Credit Cards, SSNs) and is "vulnerable by design" to excessive data exposure.
* **🟣 Observability Layer:** A custom implementation of **OpenTelemetry GenAI Semantic Conventions** that captures:
    * Full prompt/response payloads (`gen_ai.input.messages`).
    * Token usage costs (`gen_ai.usage.output_tokens`).
    * Deep links between Application Logs and Distributed Traces.

---

## 🚀 Getting Started

### Prerequisites
* Google Cloud Project with billing enabled.
* `gcloud` CLI installed and authenticated.
* APIs Enabled: Cloud Run, Vertex AI, Cloud Trace, Cloud Logging.

### 1. Installation
Clone the repository and enter the directory:
```bash
git clone [https://github.com/AndrewLiebowitz/genai-purple-team-lab.git](https://github.com/AndrewLiebowitz/genai-purple-team-lab.git)
cd genai-purple-team-lab


Follow this guide to deploy the arena, launch the attack, and use Google Cloud observability tools to catch the data exfiltration in real-time.

1. Environment Setup
Initialize the lab infrastructure. This script containerizes the Red Team (Alpha) and Blue Team (Beta) agents, creates the necessary Artifact Registry repositories, and deploys them to Cloud Run as authenticated microservices.

bash scripts/setup.sh

2. Verify Trace Capabilities
Ensure your Google Cloud Project is capturing deep forensic data. If you see a warning during setup about "Trace Storage," the setup script attempts to enable the Cloud Trace API automatically. You may still need to visit the Trace Explorer and click "Enable Trace"

Why this matters: Without the Trace API enabled, you will see high-level latency but miss the critical payload details (the "Deep Storage") required to prove what data was stolen, and without upgrading the log storage you wont be able to visuall inspect the traces.

3. Launch the Attack
Trigger the autonomous botnet. This script spins up a fleet of Red Team agents that concurrently probe Agent Beta for vulnerabilities.

Bash
bash scripts/mass.sh
Observation: Watch the terminal output. You will see batches of agents launching attacks in parallel, flooding the victim service to simulate a sustained, high-volume threat.

4. Forensics: Cloud Trace Explorer
Navigate to the Google Cloud Trace console.

Visualize the Traffic: Look at the "Select Time" heatmap. You will see a density of normal requests (approx. 400ms duration).

Identify the Anomaly: Look for the outlier traces—specifically those with high latency (e.g., >30s). In GenAI, massive latency is often a high-fidelity signal of a large output generation.

5. Isolate the "Smoking Gun"
Click on a high-latency trace to inspect the waterfall view.

Inspect Attributes: Click the Attributes tab and look for gen_ai.output.messages.

The Evidence: You will see the raw LLM response containing the exfiltrated customers table, including fake credit card numbers and PII. This confirms the model was tricked into dumping the database.

6. Correlate with Logs
While viewing the same trace, switch to the Logs & Events tab.

The Root Cause: Because the application is instrumented with Trace IDs, you will see the exact application log nested within the trace.

The Query: Locate the entry: Executing SQL Query: SELECT * FROM customers.... This correlates the latency spike directly to the vulnerable code path.

7. Establish Defense (Alerting)
Automate the detection so you don't need to watch the dashboard.

Navigate to Cloud Logging: Filter for logs where jsonPayload.response_size_bytes > 2000 (indicating a large data dump).

Create Alert: Select "Create Alert" to define a policy that notifies you (via Email, Slack, or PagerDuty) immediately when a response of this size is detected.
