from typing import List, Dict
from dataclasses import dataclass
import json
import os
import logging
import asyncio
from dotenv import load_dotenv
from groq import Groq

# Remove unused imports
# from langchain_groq import ChatGroq
# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# import numpy as np
from utils import rate_limit
import backoff
import httpx

@dataclass
class RankedCandidate:
    name: str
    match_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    experience_match: float
    education_match: float

class RankingEngine:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
    async def rank_candidates(self, candidates: List[dict], requirements: dict) -> List[dict]:
        """Rank candidates based on their match scores"""
        try:
            # Calculate overall score for each candidate
            for candidate in candidates:
                # Calculate percentage scores
                total_required = len(requirements['required_skills'])
                if total_required > 0:
                    skills_match = len(candidate.get('matching_skills', [])) / total_required
                else:
                    skills_match = 0.0
                    
                experience_match = float(candidate.get('experience_match', 0))
                education_match = float(candidate.get('education_match', 0))
                
                # Calculate weighted overall score (0-100 scale)
                overall_score = (
                    skills_match * 50 +          # 50% weight to skills
                    experience_match * 30 +       # 30% weight to experience
                    education_match * 20          # 20% weight to education
                )
                
                candidate['overall_score'] = overall_score
                candidate['skills_match'] = skills_match * 100  # Convert to percentage
            
            # Sort candidates
            ranked_candidates = sorted(
                candidates,
                key=lambda x: (
                    x['overall_score'],
                    len(x.get('matching_skills', [])),
                    -len(x.get('missing_skills', []))
                ),
                reverse=True
            )
            
            logging.debug(f"Ranked {len(ranked_candidates)} candidates")
            return ranked_candidates
            
        except Exception as e:
            logging.error(f"Error ranking candidates: {str(e)}", exc_info=True)
            raise

    def calculate_match_score(self, resume_text: str, requirements: dict) -> dict:
        try:
            prompt = self._create_analysis_prompt(resume_text, requirements)
            
            response = self.client.completions.create(
                model="mistral-saba-24b",
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000
            )
            
            result = json.loads(response.choices[0].text.strip())
            return self._normalize_scores(result, requirements)
            
        except Exception as e:
            logging.error(f"Error in calculate_match_score: {str(e)}")
            return self._get_default_scores(requirements)
    
    def _create_analysis_prompt(self, resume_text: str, requirements: dict) -> str:
        return f"""
        Analyze this resume against the job requirements and provide scores:

        RESUME:
        {resume_text[:4000]}

        REQUIREMENTS:
        Title: {requirements['title']}
        Skills: {', '.join(requirements['required_skills'])}
        Experience: {requirements['experience']}
        Education: {requirements['education']}

        Return JSON in format:
        {{
            "matching_skills": ["skill1", "skill2"],
            "missing_skills": ["skill3"],
            "experience_match": 0.0 to 1.0,
            "education_match": 0.0 to 1.0
        }}
        """
    
    def _normalize_scores(self, result: dict, requirements: dict) -> dict:
        try:
            logging.debug(f"Parsed LLM response: {result}")
            
            # Normalize and validate scores
            normalized = {
                'matching_skills': [
                    skill.lower() for skill in result.get('matching_skills', [])
                    if skill.lower() in [s.lower() for s in requirements['required_skills']]
                ],
                'experience_match': min(max(float(result.get('experience_match', 0)), 0), 1),
                'education_match': min(max(float(result.get('education_match', 0)), 0), 1)
            }
            
            # Calculate missing skills
            required_skills = [s.lower() for s in requirements['required_skills']]
            normalized['missing_skills'] = [
                skill for skill in required_skills 
                if skill not in [s.lower() for s in normalized['matching_skills']]
            ]
            
            logging.info(f"Calculated scores for resume: {normalized}")
            return normalized
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM response: {e}")
            return self._get_default_scores(requirements)
    
    def _get_default_scores(self, requirements: dict) -> dict:
        return {
            'matching_skills': [],
            'missing_skills': requirements['required_skills'],
            'experience_match': 0.0,
            'education_match': 0.0
        }