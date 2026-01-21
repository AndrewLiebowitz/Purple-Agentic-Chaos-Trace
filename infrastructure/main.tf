provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "iam.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry
resource "google_artifact_registry_repository" "agents_repo" {
  location      = var.region
  repository_id = var.repo_name
  description   = "Docker repository for AI Red Team agents"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# 3. Service Account Permissions
data "google_project" "project" {}

resource "google_project_iam_member" "sa_permissions" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/run.invoker",
    "roles/run.admin"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.enabled_apis]
}