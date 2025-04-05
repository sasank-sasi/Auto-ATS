import os
import json
import requests
import tempfile
from dotenv import load_dotenv
from storage import GoogleDriveConnector

def test_backend_processing():
    # Initialize
    load_dotenv()
    drive_connector = GoogleDriveConnector()
    
    # Authenticate Google Drive
    print("Authenticating Google Drive...")
    try:
        drive_connector.authenticate()
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        print("Make sure GOOGLE_APPLICATION_CREDENTIALS is set in .env file")
        return

    # API endpoint
    BASE_URL = "http://localhost:8000"
    
    # Test data
    requirements = {
        "title": "Software Engineer",
        "required_skills": ["Python", "FastAPI", "Docker"],
        "experience": "2 years",
        "education": "Bachelors in Computer Science",
        "description": "Test role"
    }
    
    # Save requirements to a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as req_file:
        json.dump(requirements, req_file)
        requirements_path = req_file.name
    
    try:
        # Step 1: Test health check
        print("\n1. Testing health check endpoint...")
        health_response = requests.get(f"{BASE_URL}/health/")
        print(f"Health check status: {health_response.json()}")

        # Step 2: Process Drive resumes one by one
        print("\n2. Processing resumes from Drive...")
        folder_id = "14rYV8_owcVrxDNX3YiuAOV3p8z3T0r_w"
        
        try:
            resumes = drive_connector.list_resumes(folder_id)
            print(f"Found {len(resumes)} resumes in the folder")
        except Exception as e:
            print(f"Error listing resumes: {str(e)}")
            return
        
        results = []
        for resume in resumes:
            print(f"\nProcessing: {resume['name']}")
            
            # Download resume to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                drive_connector.download_resume(resume['id'], temp_file.name)
                
                try:
                    # Test single resume screening
                    with open(temp_file.name, 'rb') as resume_file:
                        files = {
                            'file': ('resume.pdf', resume_file, 'application/pdf'),
                            'requirements': ('requirements.json', open(requirements_path, 'rb'), 'application/json')
                        }
                        
                        response = requests.post(
                            f"{BASE_URL}/screen-resume/",
                            files=files
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            result['file_name'] = resume['name']
                            results.append(result)
                            print(f"Successfully processed {resume['name']}")
                        else:
                            print(f"Error processing {resume['name']}: {response.text}")
                            
                finally:
                    # Clean up temp resume file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
        
        # Save results to JSON
        print("\nSaving results...")
        with open('test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"\nProcessing complete! Processed {len(results)} resumes")
        print("Results saved to test_results.json")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    
    finally:
        # Clean up requirements file
        if os.path.exists(requirements_path):
            os.unlink(requirements_path)

if __name__ == "__main__":
    test_backend_processing()