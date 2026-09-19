import os
import json
import io
import re
import sqlite3
import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from pypdf import PdfReader
import pdfplumber
from groq import Groq

try:
    import dirtyjson
except ImportError:
    dirtyjson = None

app = FastAPI(title="Resume Quiz & iGOT Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

# Admin Credentials (Set these in Render Environment Variables for production)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "karmayogi123")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# SQLite Setup
DB_FILE = "assessments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            detected_domain TEXT,
            score_percentage REAL,
            recommended_courses TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin Credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

class IncorrectQuestion(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    explanation: str

class CourseRecommendationRequest(BaseModel):
    candidate_name: Optional[str] = "Candidate"
    detected_domain: str
    score_percentage: float
    incorrect_questions: List[IncorrectQuestion]

def extract_text_from_pdf_bytes(pdf_bytes):
    extracted_text = ""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
    except Exception:
        extracted_text = ""

    if not extracted_text.strip():
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
        except Exception:
            extracted_text = ""

    return extracted_text.strip()

def call_groq_llm(prompt):
    if not client:
        raise Exception("GROQ_API_KEY environment variable is missing on Render.")

    available_models = []
    try:
        models_response = client.models.list()
        available_models = [m.id for m in models_response.data if "whisper" not in m.id and "safeguard" not in m.id]
    except Exception:
        available_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    raw_output = None
    last_error = None

    for model_id in available_models:
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2500
            )
            raw_output = response.choices[0].message.content.strip()
            if raw_output:
                break
        except Exception as err:
            last_error = err
            continue

    if not raw_output:
        raise Exception(f"Groq API Error: {str(last_error)}")

    return raw_output

def safe_parse_json(json_str):
    clean_str = re.sub(r'```json\s*|\s*```', '', json_str).strip()
    if dirtyjson:
        try:
            return dirtyjson.loads(clean_str)
        except Exception:
            pass
    try:
        return json.loads(clean_str)
    except json.JSONDecodeError:
        fixed_str = re.sub(r',\s*([\]}])', r'\1', clean_str)
        return json.loads(fixed_str)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Resume Quiz & iGOT Engine API is active!"}

@app.post("/api/analyze-resume")
async def analyze_resume(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        resume_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not resume_text:
            return {"status": "error", "message": "Could not extract text from uploaded PDF."}

        prompt = f"""Analyze this resume and classify expertise into ONE of these categories:
1. "Science & Biology" -> recommended_pdf: "sample.pdf"
2. "AI & Machine Learning" -> recommended_pdf: "sample_ai.pdf"
3. "World History & Social Sciences" -> recommended_pdf: "sample_history.pdf"

Return ONLY a valid JSON object.

Format:
{{
  "detected_domain": "AI & Machine Learning",
  "key_skills": ["Python", "FastAPI", "Machine Learning"],
  "recommended_pdf": "sample_ai.pdf",
  "reasoning": "Candidate displays experience in programming and artificial intelligence."
}}

Resume Text:
{resume_text[:2500]}"""

        raw_response = call_groq_llm(prompt)
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            return {"status": "success", "analysis": safe_parse_json(match.group(0))}
        return {"status": "error", "message": "Failed to parse analysis response."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/generate-quiz")
async def generate_quiz(file: UploadFile = File(...), num_questions: int = Form(20)):
    try:
        pdf_bytes = await file.read()
        extracted_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not extracted_text:
            return {"status": "error", "message": "Could not extract text from document."}

        prompt = f"""Generate exactly {num_questions} multiple-choice questions from this text.
Use single quotes inside string values.
Return ONLY raw valid JSON array.

Format:
[
  {{
    "question": "Sample Question?",
    "options": ["Opt A", "Opt B", "Opt C", "Opt D"],
    "answer": "Opt A",
    "explanation": "Explanation here"
  }}
]

Source Text:
{extracted_text[:2500]}"""

        raw_output = call_groq_llm(prompt)
        match = re.search(r'\[.*\]', raw_output, re.DOTALL)
        if match:
            return {"status": "success", "quiz": safe_parse_json(match.group(0))}
        return {"status": "error", "message": "Failed to generate quiz JSON."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/recommend-igot-courses")
async def recommend_igot_courses(payload: CourseRecommendationRequest):
    try:
        missed_summary = ""
        for idx, item in enumerate(payload.incorrect_questions, 1):
            missed_summary += f"{idx}. Question: {item.question}\n   User Selected: {item.user_answer}\n   Correct Answer: {item.correct_answer}\n   Explanation: {item.explanation}\n\n"

        prompt = f"""You are an HR Capacity Building Expert for India's iGOT Karmayogi platform.

Candidate Context:
- Domain: {payload.detected_domain}
- Quiz Score: {payload.score_percentage}%
- Missed Questions:
{missed_summary if missed_summary else "None! Perfect score."}

Task:
Analyze the missed concepts and suggest 3 relevant iGOT Karmayogi courses to bridge these skill gaps.

Return ONLY raw valid JSON array.

Format:
[
  {{
    "title": "Course Name",
    "competency_type": "Functional / Behavioural / Domain",
    "target_skill_gap": "What skill gap this course addresses",
    "description": "Short 1-sentence summary",
    "portal_url": "https://igotkarmayogi.gov.in/"
  }}
]"""

        raw_output = call_groq_llm(prompt)
        match = re.search(r'\[.*\]', raw_output, re.DOTALL)
        if match:
            recommended_courses = safe_parse_json(match.group(0))

            # Store result in SQLite database
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO submissions (candidate_name, detected_domain, score_percentage, recommended_courses, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (
                        payload.candidate_name,
                        payload.detected_domain,
                        payload.score_percentage,
                        json.dumps(recommended_courses),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )
                conn.commit()
                conn.close()
            except Exception as db_err:
                print("DB Insertion Error:", db_err)

            return {"status": "success", "courses": recommended_courses}
        return {"status": "error", "message": "Failed to parse recommendations."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- ADMIN DASHBOARD ENDPOINTS ---

@app.get("/api/admin/submissions")
def get_admin_submissions(username: str = Depends(authenticate_admin)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, candidate_name, detected_domain, score_percentage, recommended_courses, timestamp FROM submissions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "candidate_name": row[1],
            "detected_domain": row[2],
            "score_percentage": row[3],
            "recommended_courses": json.loads(row[4]) if row[4] else [],
            "timestamp": row[5]
        })

    return {"status": "success", "total_submissions": len(results), "data": results}

@app.get("/admin", response_class=HTMLResponse)
def get_admin_dashboard(username: str = Depends(authenticate_admin)):
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <title>iGOT Assessment Admin Dashboard</title>
      <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background: #f8f9fa; color: #2c3e50; }
        h1 { color: #1a252c; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-left: 5px solid #3498db; }
        .card h3 { margin: 0 0 10px 0; color: #7f8c8d; font-size: 14px; }
        .card p { margin: 0; font-size: 28px; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: #2c3e50; color: white; }
        tr:hover { background: #f1f5f9; }
        .badge { background: #e74c3c; color: white; padding: 3px 6px; border-radius: 4px; font-size: 11px; }
      </style>
    </head>
    <body>
      <h1>🏛️ iGOT Assessment Admin Dashboard</h1>
      <p>Real-time analytics and candidate assessment logs.</p>
      
      <div class="stats-grid">
        <div class="card">
          <h3>TOTAL SUBMISSIONS</h3>
          <p id="stat-total">0</p>
        </div>
        <div class="card" style="border-left-color: #27ae60;">
          <h3>AVERAGE SCORE</h3>
          <p id="stat-avg">0%</p>
        </div>
        <div class="card" style="border-left-color: #f39c12;">
          <h3>PASS RATE (&ge;70%)</h3>
          <p id="stat-pass">0%</p>
        </div>
      </div>

      <h2>Candidate Submissions</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Candidate Name</th>
            <th>Domain</th>
            <th>Score</th>
            <th>Timestamp</th>
            <th>Recommended iGOT Courses</th>
          </tr>
        </thead>
        <tbody id="table-body">
          <tr><td colspan="6">Loading candidate logs...</td></tr>
        </tbody>
      </table>

      <script>
        async function loadAdminData() {
          try {
            const res = await fetch('/api/admin/submissions');
            const result = await res.json();
            if(result.status === 'success') {
              const data = result.data;
              document.getElementById('stat-total').textContent = data.length;
              
              if(data.length > 0) {
                const totalScore = data.reduce((acc, curr) => acc + curr.score_percentage, 0);
                const avgScore = Math.round(totalScore / data.length);
                document.getElementById('stat-avg').textContent = `${avgScore}%`;

                const passed = data.filter(d => d.score_percentage >= 70).length;
                const passRate = Math.round((passed / data.length) * 100);
                document.getElementById('stat-pass').textContent = `${passRate}%`;
              }

              const tbody = document.getElementById('table-body');
              tbody.innerHTML = '';
              
              data.forEach(item => {
                const coursesHTML = item.recommended_courses.map(c => `• ${c.title} <span class="badge">${c.competency_type}</span>`).join('<br>');
                tbody.innerHTML += `
                  <tr>
                    <td>#${item.id}</td>
                    <td><strong>${item.candidate_name}</strong></td>
                    <td>${item.detected_domain}</td>
                    <td><strong>${item.score_percentage}%</strong></td>
                    <td>${item.timestamp}</td>
                    <td style="font-size: 13px;">${coursesHTML || 'None'}</td>
                  </tr>
                `;
              });
            }
          } catch(err) {
            console.error(err);
          }
        }
        loadAdminData();
      </script>
    </body>
    </html>
    """