import os
import zipfile
import requests

# Directory where raw data is saved
RAW_DATA_DIR = os.path.join("data", "raw")

def download_sbb_actual_data(year, month):
    """
    Attempts to download a monthly zip archive of actual data (Ist-Daten) from the SBB Archive.
    Stores and extracts it to data/raw.
    
    Parameters:
    - year: Year integer (e.g., 2025)
    - month: Month integer (e.g., 12)
    
    Returns:
    - True if download and extraction succeeded, False otherwise.
    """
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    
    # Swiss SBB actual data archive patterns
    # Format typically: https://archive.opentransportdata.swiss/istdaten/YYYY/MM/YYYY-MM_istdaten.zip
    # Or newer: istdaten-v2-YYYY-MM.zip
    urls_to_try = [
        f"https://archive.opentransportdata.swiss/istdaten/{year}/{month:02d}/{year}-{month:02d}_istdaten.zip",
        f"https://archive.opentransportdata.swiss/istdaten/v2/{year}/{month:02d}/istdaten-v2-{year}-{month:02d}.zip",
        f"https://archive.opentransportdata.swiss/{year}-{month:02d}_istdaten.zip"
    ]
    
    target_zip = os.path.join(RAW_DATA_DIR, f"{year}-{month:02d}_istdaten.zip")
    
    # If already downloaded and extracted, return True
    extracted_dir = os.path.join(RAW_DATA_DIR, f"{year}-{month:02d}")
    if os.path.exists(extracted_dir) and len(os.listdir(extracted_dir)) > 0:
        print(f"Dataset for {year}-{month:02d} already downloaded and extracted at {extracted_dir}.")
        return True

    success = False
    for url in urls_to_try:
        try:
            print(f"Trying to download SBB data from: {url}...")
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code == 200:
                print(f"Connection successful! Downloading {year}-{month:02d} data (this may take a few minutes)...")
                
                with open(target_zip, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                        if chunk:
                            f.write(chunk)
                
                print("Download complete. Extracting files...")
                os.makedirs(extracted_dir, exist_ok=True)
                with zipfile.ZipFile(target_zip, 'r') as zip_ref:
                    zip_ref.extractall(extracted_dir)
                
                # Clean up zip file to save disk space
                os.remove(target_zip)
                print(f"Extracted successfully to {extracted_dir}.")
                success = True
                break
            else:
                print(f"Failed (HTTP {response.status_code}) for URL: {url}")
        except Exception as e:
            print(f"Error trying {url}: {e}")
            
    if not success:
        print("\n" + "="*80)
        print("NOTICE: Could not download actual SBB data from the official archive.")
        print("This is expected if the archive URL shifted, or if network limits apply.")
        print("To proceed with development and testing without any blockers:")
        print("--> PLEASE SET SIMULATION_MODE=True in your .env file to generate synthetic data.")
        print("="*80 + "\n")
        
    return success
