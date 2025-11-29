from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import re
import time
from urllib.parse import urlparse

app = FastAPI()

SECRET = "my-secret-123"

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

@app.post("/solve_quiz")
async def solve_quiz(request: QuizRequest):
    # Check secret
    if request.secret != SECRET:
        raise HTTPException(status_code=403, detail={"error": "Invalid secret"})
    
    # Solve the quiz chain
    try:
        result = await solve_quiz_chain(request.email, request.secret, request.url)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def solve_quiz_chain(email: str, secret: str, initial_url: str):
    """Solve multiple quizzes in a chain within 3 minutes"""
    
    start_time = time.time()
    max_time = 180  # 3 minutes
    
    current_url = initial_url
    quiz_history = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while current_url and (time.time() - start_time < max_time):
            # Solve one quiz
            result = await solve_single_quiz(client, email, secret, current_url)
            quiz_history.append(result)
            
            # Check if there's a next URL
            if result.get("server_response", {}).get("url"):
                current_url = result["server_response"]["url"]
            else:
                # No more quizzes
                break
        
        return {
            "status": "chain_completed",
            "total_quizzes": len(quiz_history),
            "time_taken": round(time.time() - start_time, 2),
            "quizzes": quiz_history
        }

async def solve_single_quiz(client: httpx.AsyncClient, email: str, secret: str, quiz_url: str):
    """Solve a single quiz"""
    
    try:
        # Step 1: Get the quiz page
        response = await client.get(quiz_url)
        html_content = response.text
        
        # Step 2: Build submit URL
        parsed = urlparse(quiz_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        submit_url = f"{base_url}/submit"
        
        # Step 3: Parse the question and generate answer
        # For now, we'll use "test" for demo
        # Later add real parsing for actual questions
        answer = "test"
        
        # Step 4: Submit answer
        answer_payload = {
            "email": email,
            "secret": secret,
            "url": quiz_url,
            "answer": answer
        }
        
        submit_response = await client.post(submit_url, json=answer_payload)
        result = submit_response.json()
        
        return {
            "quiz_url": quiz_url,
            "submit_url": submit_url,
            "answer": answer,
            "server_response": result
        }
        
    except Exception as e:
        return {
            "quiz_url": quiz_url,
            "error": str(e)
        }
