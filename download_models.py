"""Run once after installing requirements-ml.txt; then use HF_LOCAL_ONLY=1."""
import os
os.environ['HF_LOCAL_ONLY']='0'
from backend.ml import embeddings, forecaster

if __name__=='__main__':
    print('Downloading MiniLM transaction-description encoder...')
    embeddings()
    print('Downloading Chronos-Bolt tiny cash-flow forecaster...')
    forecaster()
    print('Models ready. Set ENABLE_HF=1 and HF_LOCAL_ONLY=1 in .env, then restart the website.')
