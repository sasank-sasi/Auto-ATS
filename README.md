# Auto-ATS
# ATS Resume Screening System

## Overview

This ATS (Applicant Tracking System) is a modern resume screening application that combines FastAPI backend with Streamlit frontend to automate the resume screening process. It leverages AI/ML technologies for intelligent resume parsing and candidate ranking.

## Features

- 📄 Single resume processing
- 📁 Bulk resume processing via Google Drive
- 🔍 Intelligent skill extraction
- 📊 Detailed match scoring
- 🎯 Custom job requirement configuration
- 📈 Candidate ranking
- 🔄 Real-time processing

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: Streamlit
- **AI/ML**: 
  - Groq LLM API
  - LangChain
  - FAISS for vector similarity
- **Storage**: Google Drive API
- **Document Processing**: PyPDF, docx2txt

## System Architecture

```
project/
├── backend/
│   ├── processor.py      # Resume processing logic
│   ├── storage.py        # Google Drive integration
│   ├── ranking.py        # Candidate ranking engine
│   └── backend.py        # FastAPI application
├── frontend/
│   └── app.py           # Streamlit interface
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

```bash
python 3.8+
pip
Google Cloud credentials
Groq API key
```

### Environment Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Create .env file
GROQ_API_KEY=your_groq_api_key
GOOGLE_APPLICATION_CREDENTIALS=path_to_credentials.json
```

### Running the Application

1. Start the FastAPI backend:
```bash
uvicorn backend:app --reload --port 8000
```

2. Start the Streamlit frontend:
```bash
streamlit run app.py
```

## Usage Guide

### 1. Single Resume Processing

1. Navigate to "Single Resume" tab
2. Fill in job requirements in the sidebar
3. Upload a PDF resume
4. Click "Analyze Resume"
5. View detailed matching results

### 2. Bulk Processing

1. Navigate to "Bulk Processing" tab
2. Configure job requirements
3. Enter Google Drive folder ID containing resumes
4. Click "Process Resumes"
5. View ranked results for all candidates

## Features in Detail

### Resume Processing
- PDF and DOCX support
- Text extraction and cleaning
- Section identification (experience, education, skills)
- Intelligent skill mapping

### Scoring System
- Overall match percentage
- Skill matching
- Experience evaluation
- Education compatibility
- Detailed reasoning

### Ranking Algorithm
- Weighted scoring system
  - Skills: 50%
  - Experience: 30%
  - Education: 20%
- Candidate sorting by match score

## API Endpoints

```python
POST /upload-resume/
POST /screen-resumes/
POST /screen-resume/
GET /health/
```

## Security Features

- CORS middleware
- File validation
- Error handling
- Environment variable validation
- Temporary file cleanup

## Error Handling

The system includes comprehensive error handling for:
- Invalid file formats
- Processing failures
- API errors
- Authentication issues
- Missing requirements

## Future Improvements

1. Multi-language resume support
2. Advanced ML models for skill extraction
3. Custom scoring weights
4. Resume formatting suggestions
5. API rate limiting
6. Batch processing optimization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License

## Contact

For support or queries, please create an issue in the repository.

## Acknowledgments

- FastAPI
- Streamlit
- Groq
- Google Cloud Platform
- LangChain
- FAISS

---

**Note**: Remember to keep your API keys and credentials secure and never commit them to version control.

This project demonstrates modern Python application development with AI integration for practical business use cases.