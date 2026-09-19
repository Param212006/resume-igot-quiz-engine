let currentQuizData = [];
let timerInterval = null;
let timeRemaining = 15 * 60;
let matchedPdfFilename = "sample_ai.pdf";

let currentUserId = "KARM-UNKNOWN";
let candidateName = "Candidate";
let selectedRole = "Junior Statistical Officer (JSO)";
let passedDomain = "Official Statistical System Assessment";

// Live Render backend URL
const API_BASE = "https://resume-igot-quiz-engine-1.onrender.com";

function shuffleArray(array) {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

function randomizeQuizData(quizArray) {
  const shuffledQuestions = shuffleArray(quizArray);
  return shuffledQuestions.map((q) => ({
    ...q,
    options: shuffleArray([...q.options])
  }));
}

document.getElementById('resume-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('resume-file');
  const roleInput = document.getElementById('official-role').value;
  const analyzeBtn = document.getElementById('analyze-btn');
  const errorBox = document.getElementById('error-box');

  if (!fileInput.files[0]) return;

  errorBox.style.display = 'none';
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Evaluating Competencies against MoSPI FRAC Framework...';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('official_role', roleInput);

  try {
    const response = await fetch(`${API_BASE}/api/analyze-resume`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (data.status === 'success' && data.analysis) {
      const a = data.analysis;
      matchedPdfFilename = a.recommended_pdf;
      passedDomain = a.detected_domain || "Official Statistics Assessment";
      candidateName = a.candidate_name || "Candidate";
      selectedRole = a.official_role || roleInput;
      currentUserId = a.user_id || `KARM-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

      const cb = a.competency_breakdown || { statistical: 65, technical: 80, digital_governance: 55, behavioral: 70 };
      const skillsHTML = (a.key_skills || []).map(s => `<span class="badge">${s}</span>`).join(' ');

      document.getElementById('analysis-results').innerHTML = `
        <p><strong>Candidate ID:</strong> <span class="user-id-badge">${currentUserId}</span></p>
        <p><strong>Official Name:</strong> ${candidateName}</p>
        <p><strong>Target Cadre:</strong> ${selectedRole}</p>
        
        <div style="background: #eef2f7; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #3498db;">
          <h4 style="margin: 0 0 10px 0; color: #2c3e50;">📊 MoSPI FRAC Competency Radar Evaluation</h4>
          <p style="margin: 4px 0;">📈 <strong>Statistical Competencies:</strong> ${cb.statistical}%</p>
          <p style="margin: 4px 0;">💻 <strong>Technical Competencies:</strong> ${cb.technical}%</p>
          <p style="margin: 4px 0;">🔒 <strong>Digital Governance:</strong> ${cb.digital_governance}%</p>
          <p style="margin: 4px 0;">👔 <strong>Behavioral & Managerial:</strong> ${cb.behavioral}%</p>
        </div>

        <p><strong>Key Skills Identified:</strong> ${skillsHTML}</p>
        <p><strong>Matched Reference Module:</strong> <code>${a.recommended_pdf}</code></p>
        <p><em>${a.reasoning}</em></p>
      `;

      document.getElementById('step-2-card').style.display = 'block';
    } else {
      throw new Error(data.message || 'Failed to analyze resume.');
    }
  } catch (err) {
    errorBox.textContent = `Error: ${err.message}`;
    errorBox.style.display = 'block';
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze Competencies & Match iGOT Module';
  }
});

document.getElementById('generate-quiz-btn').addEventListener('click', async () => {
  const errorBox = document.getElementById('error-box');
  const quizContainer = document.getElementById('quiz-container');
  const genBtn = document.getElementById('generate-quiz-btn');
  const scoreBtn = document.getElementById('score-btn');
  const scoreBanner = document.getElementById('score-banner');
  const certBtn = document.getElementById('cert-btn');

  errorBox.style.display = 'none';
  scoreBanner.style.display = 'none';
  certBtn.style.display = 'none';
  scoreBtn.style.display = 'none';
  quizContainer.innerHTML = '';
  genBtn.disabled = true;
  genBtn.textContent = 'Generating 20-Question Domain Assessment...';

  try {
    const pdfResponse = await fetch(matchedPdfFilename);
    const pdfBlob = await pdfResponse.blob();
    const pdfFile = new File([pdfBlob], matchedPdfFilename, { type: 'application/pdf' });

    const formData = new FormData();
    formData.append('file', pdfFile);
    formData.append('num_questions', 20);

    const response = await fetch(`${API_BASE}/api/generate-quiz`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (data.status === 'success' && data.quiz) {
      currentQuizData = randomizeQuizData(data.quiz);
      renderQuiz(currentQuizData);
      scoreBtn.style.display = 'block';
      startTimer();
    } else {
      throw new Error(data.message || 'Failed to generate quiz.');
    }
  } catch (err) {
    errorBox.textContent = `Error: ${err.message}`;
    errorBox.style.display = 'block';
  } finally {
    genBtn.disabled = false;
    genBtn.textContent = 'Generate 20-Question Domain Assessment';
  }
});

function startTimer() {
  clearInterval(timerInterval);
  timeRemaining = 15 * 60;
  const timerBanner = document.getElementById('timer-banner');
  const timerClock = document.getElementById('timer-clock');
  
  timerBanner.style.display = 'block';

  timerInterval = setInterval(() => {
    timeRemaining--;
    const minutes = Math.floor(timeRemaining / 60);
    const seconds = timeRemaining % 60;
    
    timerClock.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    if (timeRemaining <= 0) {
      clearInterval(timerInterval);
      alert('Time is up! Submitting assessment automatically.');
      calculateScore();
    }
  }, 1000);
}

function renderQuiz(quiz) {
  const quizContainer = document.getElementById('quiz-container');
  quizContainer.innerHTML = '';

  quiz.forEach((q, index) => {
    const qCard = document.createElement('div');
    qCard.className = 'question-card';

    let optionsHTML = q.options.map((opt) => `
      <label class="option-label" id="label-${index}-${opt.replace(/[^a-zA-Z0-9]/g, '')}">
        <input type="radio" name="question-${index}" value="${opt}">
        ${opt}
      </label>
    `).join('');

    qCard.innerHTML = `
      <h3>Q${index + 1}. ${q.question}</h3>
      <div class="options-group">${optionsHTML}</div>
      <div class="explanation" id="exp-${index}">
        <strong>Correct Answer:</strong> ${q.answer}<br>
        <strong>Explanation:</strong> ${q.explanation}
      </div>
    `;

    quizContainer.appendChild(qCard);
  });
}

async function calculateScore() {
  clearInterval(timerInterval);
  let score = 0;
  const incorrectQuestionsList = [];

  currentQuizData.forEach((q, index) => {
    const selected = document.querySelector(`input[name="question-${index}"]:checked`);
    const expDiv = document.getElementById(`exp-${index}`);
    expDiv.style.display = 'block';

    q.options.forEach((opt) => {
      const label = document.getElementById(`label-${index}-${opt.replace(/[^a-zA-Z0-9]/g, '')}`);
      if (opt === q.answer) {
        label.classList.add('correct');
      }
    });

    if (selected) {
      const selectedValue = selected.value;
      if (selectedValue === q.answer) {
        score++;
      } else {
        const selectedLabel = document.getElementById(`label-${index}-${selectedValue.replace(/[^a-zA-Z0-9]/g, '')}`);
        if (selectedLabel) selectedLabel.classList.add('incorrect');

        incorrectQuestionsList.push({
          question: q.question,
          user_answer: selectedValue,
          correct_answer: q.answer,
          explanation: q.explanation
        });
      }
    } else {
      incorrectQuestionsList.push({
        question: q.question,
        user_answer: "Not Answered",
        correct_answer: q.answer,
        explanation: q.explanation
      });
    }
  });

  const percentage = Math.round((score / currentQuizData.length) * 100);
  const scoreBanner = document.getElementById('score-banner');
  scoreBanner.textContent = `Your Score: ${score} / ${currentQuizData.length} (${percentage}%)`;
  scoreBanner.style.display = 'block';

  if (percentage >= 70) {
    document.getElementById('cert-btn').style.display = 'block';
    if (window.confetti) {
      confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
    }
  }

  document.getElementById('score-btn').style.display = 'none';

  await fetchIGOTRecommendations(percentage, incorrectQuestionsList);
}

async function fetchIGOTRecommendations(scorePercentage, incorrectList) {
  try {
    const response = await fetch(`${API_BASE}/api/recommend-igot-courses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        candidate_name: candidateName,
        official_role: selectedRole,
        detected_domain: passedDomain,
        score_percentage: scorePercentage,
        incorrect_questions: incorrectList
      })
    });

    const data = await response.json();

    if (data.status === 'success' && data.courses) {
      renderIGOTCards(data.courses);
    }
  } catch (err) {
    console.error("Failed to fetch iGOT recommendations:", err);
  }
}

function renderIGOTCards(courses) {
  const quizContainer = document.getElementById('quiz-container');

  let cardsHTML = `
    <div class="card" style="margin-top: 30px; border-left: 5px solid #27ae60; background: #ffffff; padding: 20px; border-radius: 8px;">
      <h3 style="color: #2c3e50; margin-top: 0;">🏛️ Recommended iGOT Karmayogi Learning Pathways</h3>
      <p style="color: #555; font-size: 14px;">Based on your missed competency concepts, Groq AI generated these targeted government modules:</p>
      <div style="display: grid; gap: 15px; margin-top: 15px;">
  `;

  courses.forEach((c) => {
    cardsHTML += `
      <div style="background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h4 style="margin: 0; color: #1a252c;">${c.title}</h4>
          <span class="badge" style="background: #e74c3c;">${c.competency_type}</span>
        </div>
        <p style="margin: 8px 0; font-size: 13px; color: #2c3e50;"><strong>Target Skill Gap:</strong> ${c.target_skill_gap}</p>
        <p style="margin: 0 0 10px 0; font-size: 13px; color: #666;">${c.description}</p>
        <a href="${c.portal_url}" target="_blank" style="color: #27ae60; font-weight: bold; text-decoration: none; font-size: 14px;">
          🔗 Enroll on iGOT Karmayogi Portal →
        </a>
      </div>
    `;
  });

  cardsHTML += `</div></div>`;
  quizContainer.insertAdjacentHTML('beforeend', cardsHTML);
}

function generateCertificate() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({
    orientation: "landscape",
    unit: "px",
    format: [800, 600]
  });

  doc.setFillColor(248, 249, 250);
  doc.rect(0, 0, 800, 600, "F");

  doc.setLineWidth(5);
  doc.setDrawColor(44, 62, 80);
  doc.rect(20, 20, 760, 560);

  doc.setLineWidth(2);
  doc.setDrawColor(52, 152, 219);
  doc.rect(28, 28, 744, 544);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(28);
  doc.setTextColor(44, 62, 80);
  doc.text("CERTIFICATE OF COMPETENCY ACHIEVEMENT", 400, 95, { align: "center" });

  doc.setFontSize(11);
  doc.setFont("courier", "bold");
  doc.setTextColor(142, 68, 173);
  doc.text(`OFFICIAL ID: ${currentUserId}`, 400, 120, { align: "center" });

  doc.setFontSize(12);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(127, 140, 141);
  doc.text("THIS IS PROUDLY PRESENTED TO", 400, 160, { align: "center" });

  doc.setFontSize(24);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(41, 128, 185);
  doc.text(candidateName, 400, 200, { align: "center" });

  doc.setFontSize(13);
  doc.setFont("helvetica", "italic");
  doc.setTextColor(52, 73, 94);
  doc.text(`Cadre: ${selectedRole}`, 400, 225, { align: "center" });

  doc.setLineWidth(1);
  doc.setDrawColor(189, 195, 199);
  doc.line(250, 240, 550, 240);

  doc.setFontSize(13);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(52, 73, 94);
  doc.text("For successfully passing the iGOT Karmayogi assessment in:", 400, 280, { align: "center" });

  doc.setFontSize(20);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(39, 174, 96);
  doc.text(passedDomain, 400, 315, { align: "center" });

  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  doc.setFontSize(11);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(127, 140, 141);
  doc.text(`Date Issued: ${today}`, 100, 490);
  doc.text("Verified by: MoSPI Skill Intelligence Engine", 700, 490, { align: "right" });

  doc.save(`${currentUserId}_${candidateName.replace(/\s+/g, '_')}_Certificate.pdf`);
}