import streamlit as st
import requests
import json
import os
from typing import Dict, List
import tempfile

# Constants
API_URL = "http://localhost:8000"

def upload_single_resume(file, requirements: Dict) -> Dict:
    """Upload and screen a single resume"""
    
    if not file:
        return None
        
    # Create temporary requirements file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as req_file:
        json.dump(requirements, req_file)
        req_file_path = req_file.name
        
    try:
        files = {
            'file': ('resume.pdf', file.getvalue(), 'application/pdf'),
            'requirements': ('requirements.json', open(req_file_path, 'rb'), 'application/json')
        }
        
        response = requests.post(f"{API_URL}/screen-resume/", files=files)
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        st.error(f"Error processing resume: {str(e)}")
        return None
    finally:
        if os.path.exists(req_file_path):
            os.remove(req_file_path)

def screen_drive_resumes(folder_id: str, requirements: Dict) -> List[Dict]:
    """Screen all resumes in a Google Drive folder"""
    try:
        response = requests.post(
            f"{API_URL}/screen-resumes/",
            params={"folder_id": folder_id},
            json=requirements
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error screening resumes: {str(e)}")
        return []

def display_results(results: Dict):
    """Display resume screening results"""
    if not results:
        return
        
    st.write("### Results")
    
    # Create columns for metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Overall Match", f"{results['match_score']:.1f}%")
        st.metric("Experience Match", f"{results['experience_match'] * 100:.1f}%")
        
    with col2:
        # Calculate skills match percentage
        total_skills = len(results['matching_skills']) + len(results['missing_skills'])
        if total_skills > 0:
            skills_match = len(results['matching_skills']) / total_skills * 100
        else:
            skills_match = 0
            
        st.metric("Skills Match", f"{skills_match:.1f}%")
        st.metric("Education Match", f"{results['education_match'] * 100:.1f}%")
    
    # Display skills breakdown
    st.write("#### Skills Analysis")
    skill_cols = st.columns(2)
    
    with skill_cols[0]:
        st.write("✅ Matching Skills")
        for skill in results['matching_skills']:
            st.markdown(f"- {skill}")
            
    with skill_cols[1]:
        st.write("❌ Missing Skills")
        for skill in results['missing_skills']:
            st.markdown(f"- {skill}")

def main():
    st.set_page_config(
        page_title="Resume Screening App",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Resume Screening Assistant")
    
    # Sidebar - Job Requirements
    with st.sidebar:
        st.header("Job Requirements")
        
        title = st.text_input("Job Title", "Software Engineer")
        skills = st.text_area(
            "Required Skills (one per line)", 
            "Python\nFastAPI\nDocker"
        ).strip()
        experience = st.text_input("Required Experience", "2 years")
        education = st.text_input("Required Education", "Bachelors in Computer Science")
        description = st.text_area("Job Description", "Looking for a full-stack developer")
        
        requirements = {
            "title": title,
            "required_skills": [skill.strip() for skill in skills.split('\n') if skill.strip()],
            "experience": experience,
            "education": education,
            "description": description
        }
    
    # Main content - Tabs
    tab1, tab2 = st.tabs(["Single Resume", "Bulk Processing"])
    
    # Single Resume Upload
    with tab1:
        st.header("Upload Single Resume")
        uploaded_file = st.file_uploader("Choose PDF resume", type=['pdf'])
        
        if uploaded_file and st.button("Analyze Resume"):
            with st.spinner("Analyzing resume..."):
                results = upload_single_resume(uploaded_file, requirements)
                if results:
                    display_results(results)
    
    # Bulk Processing
    with tab2:
        st.header("Bulk Resume Processing")
        folder_id = st.text_input(
            "Google Drive Folder ID",
            help="Enter the folder ID from your Google Drive URL"
        )
        
        if folder_id and st.button("Process Resumes"):
            with st.spinner("Processing resumes from Drive..."):
                results = screen_drive_resumes(folder_id, requirements)
                
                if results:
                    st.success(f"Successfully processed {len(results)} resumes!")
                    
                    # Display sorted results
                    sorted_results = sorted(
                        results,
                        key=lambda x: x['match_score'],
                        reverse=True
                    )
                    
                    for i, result in enumerate(sorted_results, 1):
                        with st.expander(f"#{i} - {result['name']} ({result['match_score']:.1f}% Match)"):
                            display_results(result)

if __name__ == "__main__":
    main()