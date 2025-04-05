from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import tempfile
import os
from processor import ResumeProcessor
from storage import GoogleDriveConnector
from ranking import RankingEngine
from dotenv import load_dotenv
import os
import json
import aiofiles
import logging
import asyncio


# Add at the start of the file, after imports
load_dotenv()

app = FastAPI(title="ATS Resume Screening API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize our components
resume_processor = ResumeProcessor()
drive_connector = GoogleDriveConnector()
ranking_engine = RankingEngine()

# Pydantic models for request/response
class JobRequirements(BaseModel):
    title: str
    required_skills: List[str]
    experience: str
    education: str
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Software Engineer",
                "required_skills": ["Python", "FastAPI", "Docker"],
                "experience": "2 years",
                "education": "Bachelors in Computer Science",
                "description": "Looking for a full-stack developer"
            }
        }

class CandidateResponse(BaseModel):
    name: str
    match_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    experience_match: float
    education_match: float

class ResumeScreeningResponse(BaseModel):
    name: str
    match_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    experience_match: float
    education_match: float

@app.on_event("startup")
async def startup_event():
    """Initialize connections and validate environment"""
    required_vars = ["GROQ_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
    drive_connector.authenticate()

@app.post("/upload-resume/")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and process a single resume"""
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Process resume
        resume_text = resume_processor.load_resume(temp_path)
        skills = resume_processor.extract_skills(resume_text)

        # Clean up temp file
        os.unlink(temp_path)

        return {
            "filename": file.filename,
            "extracted_skills": skills,
            "status": "processed"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/screen-resumes/")
async def screen_resumes(
    folder_id: str = Query(..., description="Google Drive folder ID containing resumes"),
    requirements: JobRequirements = Body(..., description="Job requirements for screening")
) -> List[CandidateResponse]:
    """Screen all resumes in a Google Drive folder against job requirements"""
    try:
        # Validate folder_id
        if not folder_id or len(folder_id.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid folder_id provided"
            )
            
        # List resumes from Google Drive
        resumes = drive_connector.list_resumes(folder_id)
        if not resumes:
            raise HTTPException(status_code=404, detail="No resumes found in folder")
        
        candidates = []
        for resume in resumes:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    drive_connector.download_resume(resume['id'], temp_file.name)
                    resume_text = resume_processor.load_resume(temp_file.name)
                    
                    # Phase 1: NLP Preprocessing
                    extracted_info = resume_processor.preprocess_resume(resume_text)
                    
                    # Phase 2: LLM Analysis
                    analysis_result = resume_processor.analyze_resume(
                        extracted_info,
                        requirements.dict()
                    )
                    
                    candidates.append({
                        'name': resume['name'],
                        'matching_skills': analysis_result.get('matching_skills', []),
                        'missing_skills': analysis_result.get('missing_skills', []),
                        'experience_match': analysis_result.get('experience_match', 0.0),
                        'education_match': analysis_result.get('education_match', 0.0),
                        'overall_score': analysis_result.get('overall_score', 0.0),
                        'reasoning': analysis_result.get('reasoning', 'Analysis failed'),
                        'preprocessed_info': analysis_result.get('preprocessed_info', {})
                    })
                    
                    # Cleanup temp file
                    if os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
                        
            except Exception as resume_error:
                logging.error(f"Error handling resume {resume['name']}: {str(resume_error)}")
                continue

        if not candidates:
            raise HTTPException(
                status_code=422, 
                detail="Failed to process any resumes successfully. Check logs for details."
            )

        # Rank candidates
        try:
            ranked_candidates = await ranking_engine.rank_candidates(
                candidates,
                requirements.dict()
            )
        except Exception as rank_error:
            logging.error(f"Error in ranking candidates: {str(rank_error)}")
            raise HTTPException(
                status_code=500,
                detail="Error ranking candidates"
            )

        return [
            CandidateResponse(
                name=candidate['name'],
                match_score=candidate['overall_score'],
                matching_skills=candidate['matching_skills'],
                missing_skills=candidate['missing_skills'],
                experience_match=candidate['experience_match'],
                education_match=candidate['education_match']
            )
            for candidate in ranked_candidates
        ]

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in screen_resumes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/screen-resume/")
async def screen_resume(
    file: UploadFile = File(...),
    requirements: UploadFile = File(...)
) -> ResumeScreeningResponse:
    """Screen a single resume against job requirements"""
    try:
        # Validate resume file type
        if not file.content_type == "application/pdf":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported resume format: {file.content_type}"
            )
            
        # Read and parse requirements
        requirements_data = await requirements.read()
        try:
            job_requirements = json.loads(requirements_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in requirements file"
            )
            
        # Create temporary file with unique name
        temp_path = tempfile.mktemp(suffix='.pdf')
        try:
            # Process resume
            async with aiofiles.open(temp_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
                
            # Process the resume
            resume_text = resume_processor.load_resume(temp_path)
            match_score = resume_processor.calculate_match_score(
                resume_text,
                job_requirements
            )
            
            return ResumeScreeningResponse(
                name=file.filename,
                match_score=match_score.get('match_percentage', 0.0),
                matching_skills=match_score.get('matching_skills', []),
                missing_skills=match_score.get('missing_skills', []),
                experience_match=match_score.get('experience_match', 0.0),
                education_match=match_score.get('education_match', 0.0)
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/")
async def health_check():
    """API health check endpoint"""
    return {"status": "healthy"}

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)  # Changed from api:app to backend:app