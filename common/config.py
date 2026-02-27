"""
Configuration for Reddit Research project.
Loads environment variables and provides default settings.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass


# ============================================
# Database Configuration
# ============================================

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'reddit_research')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')


# ============================================
# Azure OpenAI Configuration
# ============================================

AZURE_API_KEY = os.getenv('AZURE_API_KEY', '')
AZURE_ENDPOINT = os.getenv('AZURE_ENDPOINT', '')
AZURE_DEPLOYMENT = os.getenv('AZURE_DEPLOYMENT', 'gpt-4o-mini')
AZURE_API_VERSION = os.getenv('AZURE_API_VERSION', '2024-02-15-preview')


# ============================================
# Rate Limiting Configuration
# ============================================

AZURE_TPM_QUOTA = int(os.getenv('AZURE_TPM_QUOTA', '200000'))  # 200K TPM
AZURE_TPM_TARGET = 0.70  # Stay at 70% of quota
AZURE_TPM_LIMIT = int(AZURE_TPM_QUOTA * AZURE_TPM_TARGET)  # Effective limit


# ============================================
# Processing Configuration
# ============================================

PARALLEL_WORKERS = int(os.getenv('PARALLEL_WORKERS', '5'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
MAX_RETRIES = 5
RETRY_DELAY = 2


# ============================================
# Subreddit to Classifier Mapping
# ============================================

# Configure which subreddits belong to which classifier
# Empty by default - populate via database or here
CLASSIFIER_SUBREDDITS = {
    'vintage': [
        # Example: 'Antiques', 'vintage', 'ThriftStoreHauls', 'Flipping', 'Mid_Century'
    ],
    'sex': [
        # Example: 'DeadBedrooms', 'sex', 'Marriage'
    ],
    'housing': [
        # Example: 'SharedOwnershipUK', 'HousingUK'
    ],
}


# ============================================
# Data Directory
# ============================================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
