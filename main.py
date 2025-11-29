from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import re
import time
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import asyncio

app = FastAPI()

SECRET = "my-secret-123"

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

@app.post("/solve_quiz")
async def solve_quiz(request: QuizRequest):
    if request.secret != SECRET:
        raise HTTPException(status_code=403, detail={"error": "Invalid secret"})
    
    try:
        result = await solve_quiz_chain(request.email, request.secret, request.url)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def solve_quiz_chain(email: str, secret: str, initial_url: str):
    start_time = time.time()
    max_time = 170
    
    current_url = initial_url
    quiz_history = []
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        while current_url and (time.time() - start_time < max_time):
            result = await solve_single_quiz(client, email, secret, current_url)
            quiz_history.append(result)
            
            if result.get("server_response", {}).get("url"):
                current_url = result["server_response"]["url"]
                delay = result.get("server_response", {}).get("delay")
                if delay and delay > 0:
                    await asyncio.sleep(min(delay, 10))
            else:
                break
        
        return {
            "status": "chain_completed",
            "total_quizzes": len(quiz_history),
            "time_taken": round(time.time() - start_time, 2),
            "quizzes": quiz_history
        }

async def solve_single_quiz(client: httpx.AsyncClient, email: str, secret: str, quiz_url: str):
    try:
        response = await client.get(quiz_url)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        parsed = urlparse(quiz_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        submit_url = f"{base_url}/submit"
        
        answer = await parse_and_solve(soup, html_content, quiz_url, client, base_url)
        
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
            "answer": answer,
            "server_response": result
        }
        
    except Exception as e:
        return {
            "quiz_url": quiz_url,
            "error": str(e)
        }

async def parse_and_solve(soup: BeautifulSoup, html: str, url: str, client: httpx.AsyncClient, base_url: str):
    text = soup.get_text(separator=' ', strip=True)
    text_lower = text.lower()
    
    # Demo quiz
    if '/demo' in url and 'demo' not in url.split('/')[-1]:
        return "test"
    
    # Extract secret from page
    if 'scrape' in url or ('secret' in text_lower and 'find' in text_lower):
        # Look for hidden elements or specific patterns
        for tag in soup.find_all(['span', 'div', 'p', 'code', 'pre']):
            tag_text = tag.get_text(strip=True)
            if re.match(r'^[a-zA-Z0-9]{6,20}$', tag_text):
                return tag_text
        
        # Try pattern matching
        secret_match = re.search(r'\b([a-zA-Z0-9]{8,})\b', text)
        if secret_match:
            return secret_match.group(1)
    
    # Audio sum task
    if 'audio' in url.lower():
        # Find all numbers mentioned
        numbers = re.findall(r'\b(\d+)\b', text)
        if len(numbers) >= 2:
            return str(sum(int(n) for n in numbers))
    
    # CSV/file download tasks
    links = soup.find_all('a', href=True)
    for link in links:
        href = link['href']
        if '.csv' in href.lower():
            try:
                import pandas as pd
                from io import StringIO
                file_url = urljoin(base_url, href)
                file_response = await client.get(file_url)
                df = pd.read_csv(StringIO(file_response.text))
                
                if 'sum' in text_lower:
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        return str(int(df[numeric_cols[0]].sum()))
                
                return str(len(df))
            except:
                pass
    
    # Sum/addition tasks
    if any(word in text_lower for word in ['sum', 'add', 'total']):
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            return str(sum(int(n) for n in numbers))
    
    # Count tasks
    if 'how many' in text_lower or 'count' in text_lower:
        numbers = re.findall(r'\b\d+\b', text)
        return str(len(numbers))
    
    # Default
    numbers = re.findall(r'\b\d+\b', text)
    if numbers:
        return numbers[0]
    
    return "test"

