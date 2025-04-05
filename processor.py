import os
import json
import logging
import re
from typing import Dict, List
from groq import Groq
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq.chat_models import ChatGroq  # Updated import
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import CommaSeparatedListOutputParser

class ResumeProcessor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Validate Groq API key
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
            
        # Initialize components
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.llm = ChatGroq(
            temperature=0,
            groq_api_key=self.api_key,
            model="llama-3.3-70b-versatile",  # Updated model
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.output_parser = CommaSeparatedListOutputParser()
        
    def load_resume(self, file_path: str) -> str:
        """Load and extract text from resume file"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if (file_extension == '.pdf'):
            loader = PyPDFLoader(file_path)
            pages = loader.load_and_split()
            return ' '.join([page.page_content for page in pages])
        elif file_extension in ['.docx', '.doc']:
            loader = Docx2txtLoader(file_path)
            return loader.load()[0].page_content
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text"""
        try:
            # Create prompt for skill extraction
            messages = [
                {"role": "system", "content": "You are a technical skill extractor. Return only a comma-separated list of skills."},
                {"role": "user", "content": f"Extract all technical skills, tools, and technologies from this text:\n\n{text}"}
            ]
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model="llama2-70b-4096",
                messages=messages,
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            skills_text = response.choices[0].message.content.strip()
            skills = [
                skill.strip().lower() 
                for skill in skills_text.split(',')
                if skill.strip()
            ]
            
            logging.debug(f"Extracted {len(skills)} skills from resume")
            return skills
            
        except Exception as e:
            logging.error(f"Error extracting skills: {str(e)}")
            return []

    def calculate_match_score(self, resume_text: str, requirements: dict) -> dict:
        try:
            # Split long text into chunks
            chunks = chunk_text(resume_text)
            
            # Process each chunk separately
            all_skills = set()
            max_experience_match = 0
            max_education_match = 0
            
            for chunk in chunks:
                try:
                    # Process chunk with LLM
                    result = self._process_chunk(chunk, requirements)
                    
                    # Aggregate skills
                    all_skills.update(result.get('matching_skills', []))
                    
                    # Take highest experience and education matches
                    max_experience_match = max(
                        max_experience_match,
                        float(result.get('experience_match', 0))
                    )
                    max_education_match = max(
                        max_education_match,
                        float(result.get('education_match', 0))
                    )
                    
                except Exception as chunk_error:
                    logging.warning(f"Error processing chunk: {str(chunk_error)}")
                    continue
            
            # Calculate missing skills
            required_skills = set(requirements['required_skills'])
            missing_skills = required_skills - all_skills
            
            return {
                'matching_skills': list(all_skills),
                'missing_skills': list(missing_skills),
                'experience_match': max_experience_match,
                'education_match': max_education_match
            }
            
        except Exception as e:
            logging.error(f"Error in calculate_match_score: {str(e)}")
            raise
    
    def _process_chunk(self, chunk: str, requirements: dict) -> dict:
        """Process a single chunk of text"""
        try:
            messages = [
                {"role": "system", "content": "You are an AI assistant analyzing resume content."},
                {"role": "user", "content": f"""
                Analyze this resume section against the requirements and return a JSON object:
                
                RESUME TEXT:
                {chunk}
                
                REQUIREMENTS:
                - Skills: {', '.join(requirements['required_skills'])}
                - Experience: {requirements['experience']}
                - Education: {requirements['education']}
                
                Return a JSON object with:
                - matching_skills: list of found skills that match requirements
                - missing_skills: list of required skills not found
                - experience_match: score from 0.0 to 1.0
                - education_match: score from 0.0 to 1.0
                """}
            ]
            
            response = self.client.chat.completions.create(
                model="llama2-70b-4096",
                messages=messages,
                temperature=0.1,
                max_tokens=1000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logging.error(f"Error processing chunk: {str(e)}")
            return {
                "matching_skills": [],
                "missing_skills": requirements['required_skills'],
                "experience_match": 0.0,
                "education_match": 0.0
            }

    def create_vector_store(self, resumes: List[str]) -> FAISS:
        """Create a vector store for semantic search"""
        texts = self.text_splitter.split_text('\n'.join(resumes))
        return FAISS.from_texts(texts, self.embeddings)

    def preprocess_resume(self, text: str) -> Dict[str, any]:
        """Extract relevant information from resume text"""
        try:
            # Extract sections
            sections = self._split_into_sections(text)
            
            # Process each section
            extracted_info = {
                'skills': self._extract_technical_skills(sections.get('skills', '')),
                'experience': self._extract_experience(sections.get('experience', '')),
                'education': sections.get('education', ''),
                'summary': sections.get('summary', '')
            }
            
            logging.debug(f"Extracted info from resume: {json.dumps(extracted_info, indent=2)}")
            return extracted_info
            
        except Exception as e:
            logging.error(f"Error preprocessing resume: {str(e)}")
            return {
                'skills': [],
                'experience': [],
                'education': '',
                'summary': ''
            }

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Split resume into sections using regex patterns"""
        sections = {}
        
        # Define section patterns
        patterns = {
            'summary': r'(?i)(summary|profile|objective).*?\n(.*?)(?=\n\n|\Z)',
            'experience': r'(?i)(experience|work\s+experience|employment).*?\n(.*?)(?=\n\n|\Z)',
            'education': r'(?i)(education|academic|qualification).*?\n(.*?)(?=\n\n|\Z)',
            'skills': r'(?i)(skills|technical skills|technologies).*?\n(.*?)(?=\n\n|\Z)'
        }
        
        for section, pattern in patterns.items():
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                sections[section] = matches[0][1].strip()
                
        return sections

    def _extract_technical_skills(self, text: str) -> List[str]:
        """Extract technical skills from text"""
        common_skills = [
            r'python', r'java\b', r'javascript', r'typescript', r'react', 
            r'node\.?js', r'docker', r'kubernetes', r'aws', r'azure', 
            r'gcp', r'sql', r'nosql', r'mongodb', r'postgresql', 
            r'mysql', r'git', r'ci/cd', r'jenkins', r'machine\s+learning',
            r'deep\s+learning', r'ai', r'nlp', r'fastapi', r'django'
        ]
        
        skills = set()
        text = text.lower()
        
        # Extract skills using patterns
        for skill in common_skills:
            matches = re.finditer(skill, text, re.IGNORECASE)
            for match in matches:
                skills.add(match.group(0).strip())
        
        return list(skills)

    def _extract_experience(self, text: str) -> List[Dict]:
        """Extract work experience details"""
        experiences = []
        
        # Match job entries
        job_entries = re.finditer(
            r'(?i)(?P<title>.*?)\n(?P<company>.*?)\n(?P<period>.*?)\n(?P<description>.*?)(?=\n\n|\Z)',
            text,
            re.DOTALL
        )
        
        for entry in job_entries:
            experiences.append({
                'title': entry.group('title').strip(),
                'company': entry.group('company').strip(),
                'period': entry.group('period').strip(),
                'description': entry.group('description').strip()
            })
            
        return experiences

    def analyze_resume(self, extracted_info: Dict, requirements: Dict) -> Dict:
        """Analyze preprocessed resume against requirements using LLM"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": ("You are a resume analyzer. Return only valid JSON with scores and explanations. "
                               "Do not include any other text in your response.")
                },
                {
                    "role": "user",
                    "content": self._create_analysis_prompt(extracted_info, requirements)
                }
            ]
            
            # Call Groq API with Mistral model
            response = self.client.chat.completions.create(
                model="mistral-saba-24b",
                messages=messages,
                temperature=0.1,
                max_tokens=3000,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Extract and validate JSON response
            try:
                content = response.choices[0].message.content.strip()
                logging.debug(f"Raw LLM response: {content}")
                
                # Parse JSON response
                result = json.loads(content)
                
                # Validate required fields
                required_fields = ['matching_skills', 'missing_skills', 'experience_match', 'education_match', 'reasoning']
                if not all(field in result for field in required_fields):
                    raise ValueError("Missing required fields in LLM response")
                    
                # Calculate overall score
                num_required_skills = len(requirements['required_skills'])
                skills_score = len(result['matching_skills']) / num_required_skills if num_required_skills > 0 else 0
                
                result.update({
                    'overall_score': (
                        skills_score * 0.5 +  # 50% weight to skills
                        result['experience_match'] * 0.3 +  # 30% weight to experience
                        result['education_match'] * 0.2  # 20% weight to education
                    ) * 100,  # Convert to percentage
                    'preprocessed_info': extracted_info
                })
                
                return result
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logging.error(f"Error parsing LLM response: {str(e)}")
                raise
                
        except Exception as e:
            logging.error(f"Error in resume analysis: {str(e)}")
            return self._get_default_scores(requirements, extracted_info)

    def _create_analysis_prompt(self, extracted_info: Dict, requirements: Dict) -> str:
        """Create prompt for LLM analysis"""
        return f"""
        Analyze this preprocessed resume information against the job requirements and provide detailed scoring:

        RESUME INFORMATION:
        Skills Found: {', '.join(extracted_info['skills'])}
        
        Experience Summary:
        {json.dumps(self._format_experience(extracted_info['experience']), indent=2)}
        
        Education: {extracted_info['education']}
        
        Professional Summary: {extracted_info['summary'][:500]}...

        JOB REQUIREMENTS:
        Title: {requirements['title']}
        Required Skills: {', '.join(requirements['required_skills'])}
        Required Experience: {requirements['experience']}
        Required Education: {requirements['education']}

        Provide analysis in this exact JSON format:
        {{
            "matching_skills": ["list of skills that exactly match requirements"],
            "missing_skills": ["list of required skills not found"],
            "experience_match": <score 0.0 to 1.0 based on years and relevance>,
            "education_match": <score 0.0 to 1.0 based on education requirements>,
            "reasoning": "Detailed explanation of why these scores were assigned, broken down by category"
        }}
        """

    def _format_experience(self, experiences: List[Dict]) -> List[Dict]:
        """Format experience entries for analysis"""
        formatted = []
        for exp in experiences:
            if isinstance(exp, dict):
                formatted.append({
                    'title': exp.get('title', '').strip(),
                    'duration': exp.get('period', '').strip(),
                    'highlights': [
                        highlight.strip() 
                        for highlight in exp.get('description', '').split('\n') 
                        if highlight.strip() and highlight.strip().startswith('•')
                    ]
                })
        return formatted

    def _get_default_scores(self, requirements: Dict, extracted_info: Dict = None) -> Dict:
        """Return default scores when analysis fails"""
        return {
            'matching_skills': [],
            'missing_skills': requirements['required_skills'],
            'experience_match': 0.0,
            'education_match': 0.0,
            'overall_score': 0.0,
            'reasoning': 'Failed to analyze resume',
            'preprocessed_info': extracted_info or {}
        }