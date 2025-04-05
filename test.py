from storage import GoogleDriveConnector
import os
from typing import Optional

def get_folder_contents(folder_id: str) -> None:
    """Test Google Drive connection and list contents of a folder"""
    connector = GoogleDriveConnector()
    
    try:
        # Authenticate
        print("🔑 Authenticating with Google Drive...")
        connector.authenticate()
        print("✅ Authentication successful!")
        
        # Show which account we're using
        about = connector.service.about().get(fields="user").execute()
        print(f"👤 Using account: {about['user']['emailAddress']}")
        
        # First verify folder access with better error handling
        print(f"\n🔍 Verifying folder access...")
        try:
            # Try to get folder metadata with more fields for better debugging
            folder = connector.service.files().get(
                fileId=folder_id,
                fields='name,mimeType,capabilities,owners,shared,permissions'
            ).execute()
            
            print(f"✅ Found folder: {folder.get('name', 'Unknown')}")
            print(f"👥 Owner: {folder['owners'][0]['emailAddress']}")
            print(f"🔗 Shared: {'Yes' if folder.get('shared') else 'No'}")
            
            if not folder.get('shared'):
                print("\n⚠️ This folder is not shared")
                print("💡 Ask the folder owner to share it with:", about['user']['emailAddress'])
                return
                
            if folder.get('mimeType') != 'application/vnd.google-apps.folder':
                print("❌ The provided ID is not a folder")
                return
                
        except Exception as e:
            error_message = str(e).lower()
            if "404" in error_message:
                print("❌ Folder not found")
                print("\n💡 Troubleshooting tips:")
                print("1. Make sure the folder exists in Google Drive")
                print("2. Verify the folder is shared with:", about['user']['emailAddress'])
                print("3. Try opening this URL in your browser:")
                print(f"   https://drive.google.com/drive/folders/{folder_id}")
                return
            elif "403" in error_message:
                print("❌ Access denied")
                print("\n💡 Troubleshooting tips:")
                print(f"1. Make sure the folder is shared with: {about['user']['emailAddress']}")
                print("2. The sharing settings should be at least 'Viewer'")
                print("3. Try accessing the folder in your browser first:")
                print(f"   https://drive.google.com/drive/folders/{folder_id}")
                return
            else:
                print(f"❌ Error accessing folder: {str(e)}")
                return

        # List all files (not just resumes) to check folder contents
        print("\n📂 Scanning folder contents...")
        all_files = connector.service.files().list(
            q=f"'{folder_id}' in parents",
            spaces='drive',
            fields='files(id, name, mimeType)'
        ).execute().get('files', [])
        
        if not all_files:
            print("❌ Folder is empty")
            return
            
        print(f"📄 Found {len(all_files)} total files:")
        for file in all_files:
            print(f"  - {file['name']} ({file['mimeType']})")
        
        # Now list only resumes
        print("\n🔍 Filtering for resume files...")
        files = connector.list_resumes(folder_id)
        
        if not files:
            print("⚠️ No resume files found (looking for PDF and DOCX files)")
            print("💡 Make sure your resumes are in PDF or DOCX format")
            return
            
        print(f"✅ Found {len(files)} resume(s):")
        for file in files:
            print(f"  - {file['name']}")
            
        # Optional: Download first file as test
        if files and input("\nDownload first file? (y/n): ").lower() == 'y':
            first_file = files[0]
            output_path = f"downloads/{first_file['name']}"
            os.makedirs("downloads", exist_ok=True)
            
            print(f"📥 Downloading {first_file['name']}...")
            connector.download_resume(first_file['id'], output_path)
            print(f"✅ File downloaded to: {output_path}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if "insufficient permission" in str(e).lower():
            print("\n💡 Troubleshooting tips:")
            print("1. Make sure you've shared the folder with your Google account")
            print("2. Verify you have at least 'Viewer' access to the folder")
            print("3. Try opening the folder in your browser to confirm access")

def validate_folder_id(folder_id: str) -> bool:
    """
    Validate Google Drive folder ID format
    Returns True if the format is valid, False otherwise
    """
    # Basic validation - checking length and allowed characters
    if not folder_id:
        return False
    
    # Google Drive IDs are typically 33 characters
    if len(folder_id) != 33:
        return False
    
    # Should only contain alphanumeric characters and hyphens
    valid_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
    return all(c in valid_chars for c in folder_id)

def get_folder_id() -> Optional[str]:
    """Get folder ID from environment or user input"""
    folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    if not folder_id:
        print("\n🔍 To find your folder ID:")
        print("1. Open the folder in Google Drive")
        print("2. Right-click the folder and select 'Get link'")
        print("3. The folder ID is the last part of the URL after 'folders/'")
        print("\nExample URL: https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567")
        
        while True:
            user_input = input("\nEnter Google Drive folder URL or ID (or 'q' to quit): ").strip()
            
            if user_input.lower() == 'q':
                return None
            
            # Extract folder ID if full URL is provided
            if 'drive.google.com' in user_input:
                try:
                    folder_id = user_input.split('folders/')[-1].split('?')[0].split('/')[0]
                except IndexError:
                    print("❌ Invalid URL format")
                    continue
            else:
                folder_id = user_input
            
            if validate_folder_id(folder_id):
                return folder_id
            else:
                print("❌ Invalid folder ID format")
                print("💡 The folder ID should be 33 characters long and contain only letters, numbers, hyphens, and underscores")
    
    return folder_id

if __name__ == "__main__":
    folder_id = get_folder_id()
    if folder_id:
        get_folder_contents(folder_id)
    else:
        print("❌ No folder ID provided")