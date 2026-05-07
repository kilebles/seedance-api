# seedance-api

FastAPI proxy for the **BytePlus Seedance 2.0 Fast** video generation API.

`.env` format:
SEEDANCE_API_KEY=ark-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SEEDANCE_BASE_URL=https://ark.ap-southeast.bytepluses.com

Docs: http://localhost:8000/docs

# dev (hot-reload)                                             
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
                                                                  
# prod                                                    
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000