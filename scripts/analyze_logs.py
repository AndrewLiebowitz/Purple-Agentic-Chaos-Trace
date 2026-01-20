import subprocess
import json
import argparse

def fetch_logs(project_id):
    print(f"Fetching logs for Project: {project_id}...")
    # Fetch logs from the last 10 minutes
    cmd = [
        "gcloud", "logging", "read",
        'resource.type="cloud_run_revision" AND (resource.labels.service_name="agent-alpha" OR resource.labels.service_name="agent-beta") AND timestamp>="2024-01-01T00:00:00Z"',
        "--limit=50",
        "--format=json",
        f"--project={project_id}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        logs = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Failed to parse logs or no logs found yet (give it a minute).")
        return []
        
    return logs

def analyze_logs(logs):
    # Sort by timestamp
    logs.sort(key=lambda x: x.get("timestamp", ""))
    
    print(f"\n--- Purple Team Interaction Timeline ({len(logs)} events) ---\n")
    
    for entry in logs:
        service = entry.get("resource", {}).get("labels", {}).get("service_name", "unknown")
        text = entry.get("textPayload", "")
        timestamp = entry.get("timestamp", "")

        # Skip logs without text payload
        if not text:
            continue

        # Agent Alpha (Attacker) Logs
        if service == "agent-alpha":
            if "[Tool Output]" in text:
                print(f"{timestamp} | 🔴 Alpha (Tool Response): {text[:100]}...") # Truncate for readability
            elif "Final Agent Report" in text:
                print(f"{timestamp} | 🔴 Alpha (REPORT FILED): {text}")
            elif "Flag:" in text or "SECRET" in text:
                 print(f"{timestamp} | 🚨 CRITICAL: FLAG LEAK DETECTED in Alpha Logs: {text}")

        # Agent Beta (Target) Logs
        elif service == "agent-beta":
            if "Processing input" in text:
                print(f"{timestamp} | 🔵 Beta (Input Received): {text}")
            elif "Tool executing query" in text:
                print(f"{timestamp} | 🔵 Beta (Executing SQL): {text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", default="aiexperiment3", help="GCP Project ID")
    args = parser.parse_args()
    
    logs = fetch_logs(args.project_id)
    analyze_logs(logs)