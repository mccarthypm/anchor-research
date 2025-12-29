"""
Firebase Storage service for storing and retrieving SEC filing files.

This module provides a Python interface to Firebase Storage for storing
SEC filing data (metadata, items, statements, and raw content).
"""

import json
import os
from pathlib import Path
from typing import Any

try:
    import firebase_admin
    from firebase_admin import credentials, storage
except ImportError:
    raise ImportError(
        "firebase-admin is required. Install with: uv pip install firebase-admin"
    )


class FirebaseStorageService:
    """
    Service for interacting with Firebase Storage for SEC filing data.
    
    Files are organized in Firebase Storage as:
    companies/{ticker}/sec_edgar/{accession_number}/{file_path}
    
    For example:
    - companies/AAPL/sec_edgar/0000320193-23-000106/filing.json
    - companies/AAPL/sec_edgar/0000320193-23-000106/items/Item 1.txt
    - companies/AAPL/sec_edgar/0000320193-23-000106/statements/CONSOLIDATEDBALANCESHEETS.md
    """

    _initialized = False
    _bucket = None

    @classmethod
    def _ensure_initialized(cls):
        """Initialize Firebase Admin SDK if not already initialized."""
        if cls._initialized and cls._bucket is not None:
            return

        # Check if Firebase app is already initialized
        try:
            app = firebase_admin.get_app()
        except ValueError:
            # Not initialized, so initialize it
            # Try to get credentials from environment variables first
            # If not provided, Firebase Admin SDK will use Application Default Credentials (ADC)
            # which on Cloud Run uses the service account assigned to the Cloud Run service
            cred = None
            
            # Optional: Service account key from environment variable (JSON string)
            # If not set, ADC will be used (recommended for Cloud Run)
            service_account_json = os.environ.get("SOURCES_SERVICE_ACCOUNT_JSON")
            if service_account_json:
                cred_info = json.loads(service_account_json)
                cred = credentials.Certificate(cred_info)
            
            # Get storage bucket from environment
            storage_bucket = os.environ.get("SEC_EDGAR_BUCKET")
            
            if not storage_bucket:
                raise ValueError(
                    "SEC_EDGAR_BUCKET environment variable is required"
                )
            
            firebase_admin.initialize_app(cred, {
                'storageBucket': storage_bucket
            })
        
        cls._bucket = storage.bucket()
        cls._initialized = True

    @classmethod
    def _get_path(cls, ticker: str, accession_number: str, *path_parts: str) -> str:
        """
        Construct a Firebase Storage path.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            accession_number: SEC accession number
            *path_parts: Additional path components (e.g., "items", "Item 1.txt")
            
        Returns:
            Full storage path
        """
        ticker = ticker.upper()
        parts = ["companies", ticker, "sec_edgar", accession_number] + list(path_parts)
        return "/".join(parts)

    @classmethod
    def upload_file(
        cls,
        ticker: str,
        accession_number: str,
        file_path: str,
        content: str | bytes,
        content_type: str | None = None,
    ) -> None:
        """
        Upload a file to Firebase Storage.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_path: Relative file path (e.g., "items/Item 1.txt" or "filing.json")
            content: File content as string or bytes
            content_type: MIME type (auto-detected if None)
        """
        cls._ensure_initialized()
        
        # Convert content to bytes if string
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
            if content_type is None:
                content_type = "text/plain; charset=utf-8"
        else:
            content_bytes = content
            if content_type is None:
                content_type = "application/octet-stream"
        
        # Construct storage path
        storage_path = cls._get_path(ticker, accession_number, file_path)
        
        # Create blob and upload
        blob = cls._bucket.blob(storage_path)
        blob.upload_from_string(content_bytes, content_type=content_type)
        
        # Set metadata
        blob.metadata = {
            "ticker": ticker.upper(),
            "accession_number": accession_number,
            "file_path": file_path,
        }
        blob.patch()

    @classmethod
    def download_file(
        cls,
        ticker: str,
        accession_number: str,
        file_path: str,
    ) -> bytes | None:
        """
        Download a file from Firebase Storage.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_path: Relative file path (e.g., "items/Item 1.txt" or "filing.json")
            
        Returns:
            File content as bytes, or None if file doesn't exist
        """
        cls._ensure_initialized()
        
        storage_path = cls._get_path(ticker, accession_number, file_path)
        blob = cls._bucket.blob(storage_path)
        
        if not blob.exists():
            return None
        
        return blob.download_as_bytes()

    @classmethod
    def download_file_text(
        cls,
        ticker: str,
        accession_number: str,
        file_path: str,
    ) -> str | None:
        """
        Download a text file from Firebase Storage.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_path: Relative file path
            
        Returns:
            File content as string, or None if file doesn't exist
        """
        content = cls.download_file(ticker, accession_number, file_path)
        if content is None:
            return None
        return content.decode("utf-8")

    @classmethod
    def file_exists(
        cls,
        ticker: str,
        accession_number: str,
        file_path: str,
    ) -> bool:
        """
        Check if a file exists in Firebase Storage.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_path: Relative file path
            
        Returns:
            True if file exists, False otherwise
        """
        cls._ensure_initialized()
        
        storage_path = cls._get_path(ticker, accession_number, file_path)
        blob = cls._bucket.blob(storage_path)
        return blob.exists()

    @classmethod
    def list_files(
        cls,
        ticker: str,
        accession_number: str,
        prefix: str = "",
    ) -> list[str]:
        """
        List files in a directory within a filing.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            prefix: Path prefix (e.g., "items/" or "statements/")
            
        Returns:
            List of relative file paths (including the prefix)
        """
        cls._ensure_initialized()
        
        base_path = cls._get_path(ticker, accession_number)
        if prefix:
            search_path = f"{base_path}/{prefix}"
        else:
            search_path = f"{base_path}/"
        
        blobs = cls._bucket.list_blobs(prefix=search_path)
        
        files = []
        base_path_with_slash = f"{base_path}/"
        for blob in blobs:
            # Get relative path from the base_path
            if blob.name.startswith(base_path_with_slash):
                relative_path = blob.name[len(base_path_with_slash):]
                if relative_path:  # Skip empty paths
                    files.append(relative_path)
        
        return sorted(files)

    @classmethod
    def list_filings(cls, ticker: str) -> list[str]:
        """
        List all accession numbers for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            List of accession numbers
        """
        cls._ensure_initialized()
        
        ticker = ticker.upper()
        base_path = f"companies/{ticker}/sec_edgar/"
        
        # List all blobs with the prefix and extract unique accession numbers
        blobs = cls._bucket.list_blobs(prefix=base_path)
        
        # Extract unique accession numbers from blob names
        # Format: companies/{ticker}/sec_edgar/{accession_number}/...
        seen_accessions = set()
        for blob in blobs:
            parts = blob.name.split("/")
            # Expected format: companies/{ticker}/sec_edgar/{accession_number}/...
            if len(parts) >= 4 and parts[0] == "companies" and parts[2] == "sec_edgar":
                accession_number = parts[3]
                if accession_number and accession_number not in seen_accessions:
                    seen_accessions.add(accession_number)
        
        return sorted(list(seen_accessions), reverse=True)  # Most recent first

    @classmethod
    def delete_file(
        cls,
        ticker: str,
        accession_number: str,
        file_path: str,
    ) -> None:
        """
        Delete a file from Firebase Storage.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_path: Relative file path
        """
        cls._ensure_initialized()
        
        storage_path = cls._get_path(ticker, accession_number, file_path)
        blob = cls._bucket.blob(storage_path)
        if blob.exists():
            blob.delete()

    @classmethod
    def delete_filing(
        cls,
        ticker: str,
        accession_number: str,
    ) -> None:
        """
        Delete all files for a filing.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
        """
        cls._ensure_initialized()
        
        base_path = cls._get_path(ticker, accession_number)
        blobs = cls._bucket.list_blobs(prefix=f"{base_path}/")
        
        for blob in blobs:
            blob.delete()

