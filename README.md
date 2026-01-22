# Purple Agentic Chaos Trace (PACT) 🕵️‍♂️🟣

> **A "Zero-to-Hero" Guide for Instrumenting & Observing GenAI Security Attacks**

## 📖 Overview

**PACT** is a production-grade testbed designed to demonstrate **Observability-Driven Security** for Generative AI. It simulates a "Purple Team" exercise where an **Attacker Agent (Alpha)** continually attacks a **Victim Agent (Beta)**, while we capture every prompt injection and data leak in real-time.

**Architecture:**
* **Cloud:** Google Cloud Platform (GCP)
* **Infrastructure:** Terraform (IaC)
* **Compute:** Cloud Run (Serverless, Private, Authenticated)
* **Observability:** Cloud Logging (JSON) + Cloud Trace (Distributed)

---

## ✅ Prerequisites

1.  **Google Cloud Project:** You need an active project with billing enabled.
2.  **Local Tools:**
    * `gcloud` CLI installed and authenticated.
    * `terraform` installed.
    * `git` installed.
3.  **Permissions:** You must be an **Owner** or **Editor** of the project to grant IAM roles.

---

## 🛠 Step 1: Bootstrap Infrastructure (Terraform)

We use Terraform to handle the "Chicken and Egg" problem of creating Service Accounts and Artifact Registries before we can deploy code.

1.  **Navigate to the infrastructure folder:**
    ```bash
    cd infrastructure
    ```

2.  **Create your variables file** (Prevents manual typing and typos):
    * *Replace `YOUR_PROJECT_ID` with your actual Google Cloud Project ID.*
    ```bash
    cat > terraform.tfvars <<EOF
    project_id = "YOUR_PROJECT_ID"
    region     = "us-central1"
    repo_name  = "agents-repo"
    EOF
    ```

3.  **Initialize and Apply:**
    ```bash
    terraform init
    terraform apply
    ```
    * **Action:** Type `yes` when prompted.
    * **What this does:** Enables APIs (Run, Build, Trace), creates the "Robot" (Service Account), and assigns critical IAM roles (`run.admin`, `logging.logWriter`, `iam.serviceAccountUser`).

    > **⚠️ Known Issue: "Repository Already Exists" (Error 409)**
    > If Terraform complains that the Artifact Registry already exists, you must "import" it into the state:
    > ```bash
    > terraform import google_artifact_registry_repository.agents_repo projects/YOUR_PROJECT_ID/locations/us-central1/repositories/agents-repo
    > ```
    > Then run `terraform apply` again.

---

## ⚙️ Step 2: Pipeline Configuration (Cloud Build)

We utilize a "GitOps" workflow. We do not deploy manually; we push code, and Cloud Build deploys it.

1.  **Review `cloudbuild.yaml`:**
    Ensure the file includes the following security and logging configurations:
    * **Private Access:** Remove `--allow-unauthenticated` from the `gcloud run deploy` steps.
    * **Logging Fix:** Ensure this block is at the bottom to prevent build failures:
        ```yaml
        options:
          logging: CLOUD_LOGGING_ONLY
        ```

2.  **Push to Trigger Deployment:**
    ```bash
    git add .
    git commit -m "chore: configure secure pipeline"
    git push origin main
    ```

3.  **Verify Build:**
    Go to **[Cloud Build History](https://console.cloud.google.com/cloud-build/builds)** and ensure the build turns **Green**.

---

## 🔐 Step 3: Verification (The "Secret Handshake")

Because we made the agents **Private**, clicking the URL in the Cloud Console will result in `403 Forbidden`. This is expected!

To verify they are working, you must use an **Identity Token**:

```bash
# 1. Get the URL of Agent Alpha
ALPHA_URL=$(gcloud run services describe agent-alpha --region us-central1 --format 'value(status.url)')

# 2. Send an Authenticated Request
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $ALPHA_URL
```

* **Success:** You see `"Agent Alpha is Online and Ready."`
* **Failure (404):** Your Python app is missing a root (`/`) route. Add one to `app.py`.
* **Failure (403):** Your user/robot does not have `roles/run.invoker`.

---

## 💥 Step 4: Run the Simulation

Now that the infrastructure is solid, let's start the chaos.

1.  **Run the Mass Traffic Script:**
    ```bash
    cd scripts
    ./mass.sh
    ```
    * *Note:* The script is designed to automatically fetch the URL and Auth Token.

---

## 🕵️‍♂️ Step 5: Observability & Forensics

This is the "Value" step. Prove you can see the attack.

### 1. View Distributed Traces
1.  Go to **[Cloud Trace](https://console.cloud.google.com/traces)**.
2.  **Crucial Step:** If you see "Trace API not enabled" or a simplified view, ensure you click **"Enable"** or **"Upgrade"** if prompted by the banner.
3.  Select **"Trace List"** in the left menu.
4.  Click on any dot in the scatter plot.
5.  **What to see:** You should see a "Waterfall" view showing `Agent Alpha` calling `Agent Beta`.

### 2. View Structured Logs (The Leak)
1.  Go to **[Cloud Logging](https://console.cloud.google.com/logs)**.
2.  In the Query field, paste this to find the specific data leaks:
    ```text
    resource.type="cloud_run_revision"
    jsonPayload.event="genai_transaction"
    jsonPayload.pii_detected=true
    ```
3.  Expand the log entry. You will see the **Prompt**, the **Response**, and the **Fake SSN/Credit Card** numbers that were leaked.

---

## 🧩 Troubleshooting Common Errors

* **Error:** `Permission 'run.services.get' denied` during build.
    * **Fix:** Your Service Account is missing the `run.admin` role. Re-run `terraform apply`.
* **Error:** `build must ... use CLOUD_LOGGING_ONLY`.
    * **Fix:** Add `options: { logging: CLOUD_LOGGING_ONLY }` to `cloudbuild.yaml`.
* **Error:** `Permission 'iam.serviceaccounts.actAs' denied`.
    * **Fix:** Your Service Account is missing `roles/iam.serviceAccountUser`. Update `main.tf` and `terraform apply`.