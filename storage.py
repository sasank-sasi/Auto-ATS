from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional, Any
import os
import pickle
import json
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define OAuth 2.0 scopes - use only necessary permissions
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',  # Per-file access
    'https://www.googleapis.com/auth/drive.metadata',  # Read and write metadata
    'https://www.googleapis.com/auth/drive',  # Full drive access
]
TOKEN_PATH = 'credentials/token.pickle'

class GoogleDriveConnector:
    def __init__(self):
        self.service = None
        self.credentials = None

    def authenticate(self):
        """Authenticate with Google Drive using OAuth 2.0"""
        try:
            # Create credentials directory if it doesn't exist
            os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)

            if os.path.exists(TOKEN_PATH):
                logger.debug("Loading existing credentials from token file")
                with open(TOKEN_PATH, 'rb') as token:
                    self.credentials = pickle.load(token)

            # If credentials don't exist or are invalid
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.debug("Refreshing expired credentials")
                    self.credentials.refresh(Request())
                else:
                    logger.debug("Getting new credentials")
                    if not os.path.exists('credentials.json'):
                        raise FileNotFoundError("credentials.json not found")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', 
                        SCOPES,
                        redirect_uri='http://localhost'
                    )
                    self.credentials = flow.run_local_server(port=0)

                # Save credentials for future use
                logger.debug("Saving credentials to token file")
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(self.credentials, token)

            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.info("Successfully authenticated with Google Drive")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")

    def list_resumes(self, folder_id: str) -> List[Dict[str, Any]]:
        """List PDF files in a folder"""
        if not self.service:
            logger.error("Service not initialized")
            raise RuntimeError("Not authenticated. Call authenticate() first")

        try:
            # Validate folder_id format
            folder_id = folder_id.strip()
            if 'folders/' in folder_id:
                folder_id = folder_id.split('folders/')[-1].split('?')[0]

            logger.debug(f"Querying files in folder: {folder_id}")
            query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime)",
                pageSize=100,
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                logger.warning(f"No PDF files found in folder {folder_id}")
                return []
                
            logger.info(f"Found {len(files)} PDF files")
            return files

        except HttpError as e:
            logger.error(f"Google API error: {str(e)}")
            raise RuntimeError(f"Google API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise RuntimeError(f"Error listing files: {str(e)}")

    def download_resume(self, file_id: str, output_path: str) -> bool:
        """Download and validate a PDF file"""
        if not self.service:
            logger.error("Service not initialized")
            raise ValueError("Not authenticated. Call authenticate() first")

        try:
            # Validate file existence and type
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType'
            ).execute()

            if not file:
                raise ValueError(f"File {file_id} not found")

            if file.get('mimeType') != 'application/pdf':
                raise ValueError(f"File {file.get('name')} is not a PDF")

            # Download file
            logger.debug(f"Downloading file {file.get('name')}")
            request = self.service.files().get_media(fileId=file_id)
            
            with open(output_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%")

            # Verify file was downloaded
            if not os.path.exists(output_path):
                raise RuntimeError(f"Failed to download file to {output_path}")

            logger.info(f"Successfully downloaded {file.get('name')}")
            return True

        except HttpError as e:
            logger.error(f"Google API error: {str(e)}")
            raise RuntimeError(f"Google API error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to download file: {str(e)}")
            raise RuntimeError(f"Failed to download file: {str(e)}")