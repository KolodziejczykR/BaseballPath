# Backend

## Setup Instructions

- Install dependencies: `pip install -r requirements.txt`
- See subfolders for ML, LLM, scraping, and API details. 

You need 3 processes running in separate terminals:                                                                                                                         
                                                                                                                                                                              
  Terminal 1 — Redis:                                                                                                                                                       
  redis-server                                                                                                                                                                
                                                                                                                                                                              
  Terminal 2 — Celery worker (from the repo root):                                                                                                                            
  cd /Users/ryankolodziejczyk/Documents/AI\ Baseball\ Recruitment/code                                                                                                        
  celery -A backend.llm.tasks:celery_app worker --loglevel=info                                                                                                             
                                                                                                                                                                              
  Terminal 3 — FastAPI server (from the repo root):                                                                                                                           
  cd /Users/ryankolodziejczyk/Documents/AI\ Baseball\ Recruitment/code                                                                                                        
  uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000                                                                                                            

  The flow is: FastAPI receives the evaluation request → dispatches the LLM reasoning task to Celery → Celery worker picks it up from the Redis broker → runs the LLM call →
  caches the result back in Redis.