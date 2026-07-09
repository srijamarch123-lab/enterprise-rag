import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

def extract_text_cloud_ocr(file_path: str) -> str | None:
    """
    Extracts text from a scanned document (PDF or image) using Azure Cognitive Services Read API.
    Returns extracted text if successful, or None if not configured or failed.
    """
    from app.config.settings import get_settings
    settings = get_settings()
    
    key = os.environ.get("AZURE_COGNITIVE_KEY") or getattr(settings, "azure_cognitive_key", None)
    endpoint = os.environ.get("AZURE_COGNITIVE_ENDPOINT") or getattr(settings, "azure_cognitive_endpoint", None)
    
    if not key or not endpoint:
        logger.info("Azure Cognitive Services OCR is not configured.")
        return None
        
    endpoint = endpoint.strip().rstrip("/")
    analyze_url = f"{endpoint}/vision/v3.2/read/analyze"
    
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/octet-stream"
        }
        
        response = requests.post(analyze_url, headers=headers, data=data)
        if response.status_code != 202:
            logger.warning("Azure OCR request failed: %s - %s", response.status_code, response.text)
            return None
            
        operation_url = response.headers.get("Operation-Location")
        if not operation_url:
            logger.warning("Azure OCR response missing Operation-Location header.")
            return None
            
        headers_get = {"Ocp-Apim-Subscription-Key": key}
        for _ in range(30):
            time.sleep(1.0)
            res_get = requests.get(operation_url, headers=headers_get)
            if res_get.status_code != 200:
                logger.warning("Failed to poll Azure OCR status: %s", res_get.status_code)
                return None
                
            analysis = res_get.json()
            status = analysis.get("status")
            if status == "succeeded":
                lines = []
                read_results = analysis.get("analyzeResult", {}).get("readResults", [])
                for page in read_results:
                    for line in page.get("lines", []):
                        lines.append(line.get("text", ""))
                return "\n".join(lines).strip()
            elif status == "failed":
                logger.warning("Azure OCR operation reported failure.")
                return None
        
        logger.warning("Azure OCR operation timed out.")
        return None
    except Exception as e:
        logger.warning("Azure OCR failed with exception: %s", e)
        return None
