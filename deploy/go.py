import os
import subprocess
import sys
from dotenv import load_dotenv
import yaml

# Path to the deploy directory
DEPLOY_DIR = "deploy"

# Function to load environment variables from the .env file at runtime
def load_env_to_dict():
    env_file_path = os.path.join('.env')
    if not os.path.exists(env_file_path):
        print(".env file not found. Please make sure it's present.")
        return {}

    load_dotenv(dotenv_path=env_file_path)  # Load the .env file into the environment

    # Collect environment variables from the .env file into a dictionary
    env_vars = {}
    with open(env_file_path) as f:
        for line in f:
            # Ignore empty lines and comments
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                env_vars[key] = value

    return env_vars

# Function to generate a Cloud Run YAML file with environment variables
def generate_env_yaml(env_vars):
    # Remove 'PORT' and 'LOCAL_URL' from the env_vars dictionary as they are reserved in Cloud Run
    if 'PORT' in env_vars:
        del env_vars['PORT']
    if 'LOCAL_URL' in env_vars:
        del env_vars['LOCAL_URL']

    env_vars['ENVIRONMENT'] = 'production'

    # Create a simple key-value structure for the YAML
    yaml_data = env_vars  # Directly use the dictionary as YAML content

    yaml_file_path = os.path.join(DEPLOY_DIR, "env.yaml")
    # Write to the env.yaml file inside the deploy directory
    with open(yaml_file_path, "w") as file:
        yaml.dump(yaml_data, file, default_flow_style=False)

    print(f"Environment variables have been written to {yaml_file_path}")

# Function to run shell commands and capture output
def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.cmd}")
        print(f"Error message: {e.stderr}")
        sys.exit(1)

# Docker image building and pushing to Google Container Registry
def build_and_push_docker_image(project_id, image_name):
    print("Building Docker image...")
    run_command(f"docker build --platform=linux/amd64 -t gcr.io/{project_id}/{image_name} .")

    print("Pushing Docker image to Google Container Registry...")
    run_command(f"docker push gcr.io/{project_id}/{image_name}")

# Deploy to Google Cloud Run
def deploy_to_cloud_run(project_id, image_name, region):
    print("Deploying to Google Cloud Run using env.yaml...")
    run_command(f"gcloud run deploy {image_name} "
                f"--image gcr.io/{project_id}/{image_name} "
                f"--platform managed "
                f"--region {region} "
                f"--allow-unauthenticated "
                f"--project {project_id} "
                f"--memory 1Gi " 
                f"--env-vars-file={os.path.join(DEPLOY_DIR, 'env.yaml')}")

# Upload frontend files to Google Cloud Storage
def upload_frontend_files(frontend_bucket):
    print("Uploading frontend files to Google Cloud Storage...")
    run_command(f"gsutil cp ./templates/login.html gs://{frontend_bucket}/")
    run_command(f"gsutil cp ./templates/home.html gs://{frontend_bucket}/")

    print("Setting up Cloud Storage as a static website...")
    run_command(f"gsutil web set -m login.html -e 404.html gs://{frontend_bucket}/")

# Main function to execute the deployment
def main():
    # Step 1: Load environment variables dynamically from .env file
    env_vars = load_env_to_dict()

    if not env_vars:
        print("No environment variables found in .env. Exiting.")
        return

    # Step 2: Generate the env.yaml dynamically with environment variables
    generate_env_yaml(env_vars)

    # Step 3: Build Docker image and push to Google Container Registry
    build_and_push_docker_image(env_vars["PROJECT_ID"], env_vars["IMAGE_NAME"])

    # Step 4: Deploy the app to Google Cloud Run
    deploy_to_cloud_run(env_vars["PROJECT_ID"], env_vars["IMAGE_NAME"], env_vars["REGION"])

    # Step 5: Upload frontend files to Google Cloud Storage (optional)
    # upload_frontend_files(env_vars["FRONTEND_BUCKET"])

    print("Deployment completed successfully.")

if __name__ == "__main__":
    main()
