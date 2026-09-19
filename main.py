import os
import json
import io
import re
import sqlite3
import secrets
import uuid
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

app = FastAPI(title="MoSPI Skill Intelligence API")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

# Admin Credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "karmayogi123")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# SQLite Persistence Setup
DB_FILE = "assessments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            candidate_name TEXT,
            official_role TEXT,
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
    user_id: Optional[str] = None
    candidate_name: Optional[str] = "Candidate"
    official_role: Optional[str] = "Junior Statistical Officer (JSO)"
    detected_domain: str
    score_percentage: float
    incorrect_questions: List[IncorrectQuestion]

def extract_text_from_pdf_bytes(pdf_bytes):
    extracted_text = ""
    # Try PyPDF first
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
    except Exception as e:
        print("PyPDF extraction failed:", e)

    # Fallback to pdfplumber if PyPDF returns empty string
    if not extracted_text.strip():
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
        except Exception as e:
            print("pdfplumber extraction failed:", e)

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
    return {"status": "online", "message": "MoSPI Skill Intelligence Engine API is active!"}

@app.post("/api/analyze-resume")
async def analyze_resume(
    file: UploadFile = File(...),
    official_role: str = Form("Junior Statistical Officer (JSO)")
):
    try:
        pdf_bytes = await file.read()
        resume_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not resume_text:
            return {"status": "error", "message": "Could not extract text from uploaded PDF."}

        unique_user_id = f"KARM-{uuid.uuid4().hex[:6].upper()}"

        available_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
        if not available_files:
            available_files = ["sample_ai.pdf"]

        file_list_str = ", ".join([f'"{f}"' for f in available_files])

        prompt = f"""You are an HR Capacity Building Expert for India's Official Statistical System (MoSPI / iGOT Karmayogi).

Target Cadre/Role: {official_role}

Task:
1. Extract the candidate's full legal name from the resume text (or "Candidate" if missing).
2. Evaluate competency proficiency (0-100%) across 4 MoSPI Pillars:
   - Statistical Competencies (Survey design, sampling, price/labour stats, NAS, SDG indicators)
   - Technical Competencies (Python, R, SQL, SPSS, GIS, AI/ML)
   - Digital Governance (Cybersecurity, data privacy, government cloud, DPI)
   - Behavioral & Managerial (Leadership, public sector ethics, decision-making)
3. Match primary skill gap to ONE available reference PDF file: [{file_list_str}].

Return ONLY raw valid JSON object.

Format:
{{
  "candidate_name": "Full Name",
  "detected_domain": "Official Statistical Analysis & Sampling",
  "competency_breakdown": {{
    "statistical": 65,
    "technical": 80,
    "digital_governance": 55,
    "behavioral": 70
  }},
  "key_skills": ["Python", "NSSO Survey Design", "SQL"],
  "recommended_pdf": "{available_files[0]}",
  "reasoning": "Candidate exhibits strong technical capability but requires competency enhancement in NSSO Survey Sampling Methods."
}}

Resume Text:
{resume_text[:2500]}"""

        raw_response = call_groq_llm(prompt)
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            analysis = safe_parse_json(match.group(0))
            analysis["user_id"] = unique_user_id
            analysis["official_role"] = official_role
            return {"status": "success", "analysis": analysis}
        return {"status": "error", "message": "Failed to parse analysis response."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/generate-quiz")
async def generate_quiz(file: UploadFile = File(...), num_questions: int = Form(20)):
    try:
        pdf_bytes = await file.read()
        if not pdf_bytes or len(pdf_bytes) == 0:
            return {"status": "error", "message": "Uploaded reference file is empty. Please verify that reference PDFs exist on the server."}

        extracted_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not extracted_text:
            return {"status": "error", "message": "Could not extract text from document. Ensure reference PDF contains readable text."}

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
        return {"status": "error", "message": "Failed to parse quiz JSON from LLM response."}

    except Exception as e:
        print("Quiz Generation Error:", str(e))
        return {"status": "error", "message": f"Server Error: {str(e)}"}

@app.post("/api/recommend-igot-courses")
async def recommend_igot_courses(payload: CourseRecommendationRequest):
    try:
        user_id = payload.user_id or f"KARM-{uuid.uuid4().hex[:6].upper()}"
        missed_summary = ""
        for idx, item in enumerate(payload.incorrect_questions, 1):
            missed_summary += f"{idx}. Question: {item.question}\n   User Selected: {item.user_answer}\n   Correct Answer: {item.correct_answer}\n   Explanation: {item.explanation}\n\n"

        prompt = f"""You are an HR Capacity Building Expert for India's iGOT Karmayogi platform.

Official Context:
- User ID: {user_id}
- Official Name: {payload.candidate_name}
- Cadre/Role: {payload.official_role}
- Domain: {payload.detected_domain}
- Quiz Score: {payload.score_percentage}%
- Missed Concepts:
{missed_summary if missed_summary else "None! Perfect score."}

Task:
Analyze missed concepts and suggest 3 relevant iGOT Karmayogi government courses across Statistical, Technical, Digital Governance, or Managerial competencies.

Return ONLY raw valid JSON array.

Format:
[
  {{
    "title": "Course Name",
    "competency_type": "Statistical / Technical / Digital Governance / Behavioral",
    "target_skill_gap": "What competency gap this course bridges",
    "description": "Short 1-sentence summary",
    "portal_url": "https://igotkarmayogi.gov.in/"
  }}
]"""

        raw_output = call_groq_llm(prompt)
        match = re.search(r'\[.*\]', raw_output, re.DOTALL)
        if match:
            recommended_courses = safe_parse_json(match.group(0))

            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO submissions (user_id, candidate_name, official_role, detected_domain, score_percentage, recommended_courses, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        payload.candidate_name,
                        payload.official_role,
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

            return {"status": "success", "user_id": user_id, "courses": recommended_courses}
        return {"status": "error", "message": "Failed to parse recommendations."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- ADMIN API & SOURCE FILE MANAGEMENT ENDPOINTS ---

@app.get("/api/admin/sources")
def get_source_files(username: str = Depends(authenticate_admin)):
    pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
    files_info = []
    for f in pdf_files:
        size_kb = round(os.path.getsize(f) / 1024, 2)
        files_info.append({"filename": f, "size_kb": f"{size_kb} KB"})
    return {"status": "success", "files": files_info}

@app.post("/api/admin/sources/upload")
async def upload_source_file(file: UploadFile = File(...), username: str = Depends(authenticate_admin)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    file_path = os.path.join(".", file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    return {"status": "success", "message": f"Successfully uploaded {file.filename}"}

@app.delete("/api/admin/sources/delete/{filename}")
def delete_source_file(filename: str, username: str = Depends(authenticate_admin)):
    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type.")
    
    file_path = os.path.join(".", filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "success", "message": f"Deleted {filename}"}
    else:
        raise HTTPException(status_code=404, detail="File not found.")

@app.get("/api/admin/submissions")
def get_admin_submissions(username: str = Depends(authenticate_admin)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, candidate_name, official_role, detected_domain, score_percentage, recommended_courses, timestamp FROM submissions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "user_id": row[1] if row[1] else "N/A",
            "candidate_name": row[2],
            "official_role": row[3] if row[3] else "JSO",
            "detected_domain": row[4],
            "score_percentage": row[5],
            "recommended_courses": json.loads(row[6]) if row[6] else [],
            "timestamp": row[7]
        })

    return {"status": "success", "total_submissions": len(results), "data": results}

@app.get("/admin", response_class=HTMLResponse)
def get_admin_dashboard(username: str = Depends(authenticate_admin)):
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <title>iGOT Skill Intelligence Admin Dashboard</title>
      <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background: #f8f9fa; color: #2c3e50; }
        .header-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        h1 { color: #1a252c; margin: 0; }
        .btn { background: #3498db; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 14px; }
        .export-btn { background: #27ae60; }
        .export-btn:hover { background: #219653; }
        .delete-btn { background: #e74c3c; padding: 5px 10px; font-size: 12px; }
        .delete-btn:hover { background: #c0392b; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-left: 5px solid #3498db; }
        .card h3 { margin: 0 0 10px 0; color: #7f8c8d; font-size: 14px; }
        .card p { margin: 0; font-size: 28px; font-weight: bold; }
        .section-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: #2c3e50; color: white; }
        tr:hover { background: #f1f5f9; }
        .badge { background: #e74c3c; color: white; padding: 3px 6px; border-radius: 4px; font-size: 11px; }
        .user-id-badge { background: #8e44ad; color: white; padding: 3px 6px; border-radius: 4px; font-size: 12px; font-family: monospace; }
      </style>
    </head>
    <body>
      <div class="header-container">
        <div>
          <h1>🏛️ MoSPI Skill Intelligence Admin Dashboard</h1>
          <p style="margin: 5px 0 0 0;">Real-time official capacity logs, pass rates & assessment PDF management.</p>
        </div>
        <button class="btn export-btn" onclick="exportTableToCSV('official_submissions.csv')">📥 Export CSV</button>
      </div>
      
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

      <!-- Source File Management Section -->
      <div class="section-card">
        <h2>📁 Reference Material PDFs</h2>
        <p style="font-size: 14px; color: #666;">Upload or delete reference PDFs used to generate domain quizzes.</p>
        
        <form id="upload-form" style="margin-bottom: 20px; display: flex; gap: 10px;">
          <input type="file" id="pdf-input" accept=".pdf" required style="padding: 8px; background: #f1f5f9; border-radius: 4px;" />
          <button type="submit" class="btn">Upload New PDF</button>
        </form>

        <table>
          <thead>
            <tr>
              <th>Filename</th>
              <th>File Size</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="sources-body">
            <tr><td colspan="3">Loading source files...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Candidate Submissions Section -->
      <div class="section-card">
        <h2>Official Assessment Submissions</h2>
        <table id="submissions-table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Official Name</th>
              <th>Role / Cadre</th>
              <th>Domain</th>
              <th>Score</th>
              <th>Timestamp</th>
              <th>Recommended iGOT Courses</th>
            </tr>
          </thead>
          <tbody id="table-body">
            <tr><td colspan="7">Loading official logs...</td></tr>
          </tbody>
        </table>
      </div>

      <script>
        let rawSubmissionsData = [];

        async function loadSources() {
          try {
            const res = await fetch('/api/admin/sources');
            const result = await res.json();
            if(result.status === 'success') {
              const tbody = document.getElementById('sources-body');
              tbody.innerHTML = '';
              result.files.forEach(file => {
                tbody.innerHTML += `
                  <tr>
                    <td><strong>${file.filename}</strong></td>
                    <td>${file.size_kb}</td>
                    <td><button class="btn delete-btn" onclick="deleteSource('${file.filename}')">🗑️ Delete</button></td>
                  </tr>
                `;
              });
            }
          } catch(err) { console.error(err); }
        }

        document.getElementById('upload-form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const fileInput = document.getElementById('pdf-input');
          if(!fileInput.files[0]) return;

          const formData = new FormData();
          formData.append('file', fileInput.files[0]);

          const res = await fetch('/api/admin/sources/upload', { method: 'POST', body: formData });
          const data = await res.json();
          if(data.status === 'success') {
            alert(data.message);
            fileInput.value = '';
            loadSources();
          } else {
            alert(data.detail || 'Upload failed');
          }
        });

        async function deleteSource(filename) {
          if(!confirm(`Are you sure you want to delete ${filename}?`)) return;
          const res = await fetch(`/api/admin/sources/delete/${filename}`, { method: 'DELETE' });
          const data = await res.json();
          if(data.status === 'success') {
            alert(data.message);
            loadSources();
          }
        }

        async function loadAdminData() {
          try {
            const res = await fetch('/api/admin/submissions');
            const result = await res.json();
            if(result.status === 'success') {
              rawSubmissionsData = result.data;
              document.getElementById('stat-total').textContent = rawSubmissionsData.length;
              
              if(rawSubmissionsData.length > 0) {
                const totalScore = rawSubmissionsData.reduce((acc, curr) => acc + curr.score_percentage, 0);
                const avgScore = Math.round(totalScore / rawSubmissionsData.length);
                document.getElementById('stat-avg').textContent = `${avgScore}%`;

                const passed = rawSubmissionsData.filter(d => d.score_percentage >= 70).length;
                const passRate = Math.round((passed / rawSubmissionsData.length) * 100);
                document.getElementById('stat-pass').textContent = `${passRate}%`;
              }

              const tbody = document.getElementById('table-body');
              tbody.innerHTML = '';
              
              rawSubmissionsData.forEach(item => {
                const coursesHTML = item.recommended_courses.map(c => `• ${c.title} <span class="badge">${c.competency_type}</span>`).join('<br>');
                tbody.innerHTML += `
                  <tr>
                    <td><span class="user-id-badge">${item.user_id}</span></td>
                    <td><strong>${item.candidate_name}</strong></td>
                    <td>${item.official_role}</td>
                    <td>${item.detected_domain}</td>
                    <td><strong>${item.score_percentage}%</strong></td>
                    <td>${item.timestamp}</td>
                    <td style="font-size: 13px;">${coursesHTML || 'None'}</td>
                  </tr>
                `;
              });
            }
          } catch(err) { console.error(err); }
        }

        function exportTableToCSV(filename) {
          if (!rawSubmissionsData || rawSubmissionsData.length === 0) {
            alert("No data available to export.");
            return;
          }

          let csv = [];
          csv.push(["User ID", "Official Name", "Role Cadre", "Detected Domain", "Score Percentage", "Timestamp", "Recommended Courses"].join(","));

          rawSubmissionsData.forEach(item => {
            const courseList = item.recommended_courses.map(c => c.title).join("; ");
            const row = [
              `"${item.user_id}"`,
              `"${item.candidate_name.replace(/"/g, '""')}"`,
              `"${item.official_role.replace(/"/g, '""')}"`,
              `"${item.detected_domain.replace(/"/g, '""')}"`,
              `"${item.score_percentage}%"`,
              `"${item.timestamp}"`,
              `"${courseList.replace(/"/g, '""')}"`
            ];
            csv.push(row.join(","));
          });

          const csvFile = new Blob([csv.join("\\n")], { type: "text/csv" });
          const downloadLink = document.createElement("a");
          downloadLink.download = filename;
          downloadLink.href = window.URL.createObjectURL(csvFile);
          downloadLink.style.display = "none";
          document.body.appendChild(downloadLink);
          downloadLink.click();
          document.body.removeChild(downloadLink);
        }

        loadSources();
        loadAdminData();
      </script>
    </body>
    </html>
    """