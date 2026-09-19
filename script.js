let currentQuizData = [];
let timerInterval = null;
let timeRemaining = 15 * 60;
let matchedPdfFilename = "sample_ai.pdf";

let currentUserId = "KARM-UNKNOWN";
let candidateName = "Candidate";
let selectedRole = "Junior Statistical Officer (JSO)";
let passedDomain = "Official Statistical System Assessment";
let initialCompetencyBreakdown = { statistical: 65, technical: 80, digital_governance: 55, behavioral: 70 };

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

function updateStepper(activeStep) {
  for (let i = 1; i <= 4; i++) {
    const node = document.getElementById(`node-${i}`);
    if (node) {
      if (i <= activeStep) {
        node.classList.add('active');
      } else {
        node.classList.remove('active');
      }
    }
  }
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

      initialCompetencyBreakdown = a.competency_breakdown || { statistical: 65, technical: 80, digital_governance: 55, behavioral: 70 };
      const skillsHTML = (a.key_skills || []).map(s => `<span class="badge">${s}</span>`).join(' ');

      document.getElementById('analysis-results').innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; background: #f8fafc; padding: 12px; border-radius: 8px;">
          <div><span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Candidate ID</span><br><span class="user-id-badge">${currentUserId}</span></div>
          <div><span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Official Name</span><br><strong>${candidateName}</strong></div>
          <div><span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Designation</span><br><strong>${selectedRole}</strong></div>
        </div>
        
        <div style="background: #ffffff; padding: 16px; border-radius: 10px; margin: 15px 0; border: 1px solid #e2e8f0;">
          <h4 style="margin: 0 0 14px 0; color: #1e3a8a; font-size: 15px;">📊 MoSPI FRAC Competency Radar Evaluation</h4>
          
          <div class="competency-bar-wrapper">
            <div class="competency-label"><span>📈 Statistical Competencies</span><span>${initialCompetencyBreakdown.statistical}%</span></div>
            <div class="progress-track"><div class="progress-fill" style="width: ${initialCompetencyBreakdown.statistical}%;"></div></div>
          </div>

          <div class="competency-bar-wrapper">
            <div class="competency-label"><span>💻 Technical Competencies</span><span>${initialCompetencyBreakdown.technical}%</span></div>
            <div class="progress-track"><div class="progress-fill" style="width: ${initialCompetencyBreakdown.technical}%; background: #3b82f6;"></div></div>
          </div>

          <div class="competency-bar-wrapper">
            <div class="competency-label"><span>🔒 Digital Governance</span><span>${initialCompetencyBreakdown.digital_governance}%</span></div>
            <div class="progress-track"><div class="progress-fill" style="width: ${initialCompetencyBreakdown.digital_governance}%; background: #8b5cf6;"></div></div>
          </div>

          <div class="competency-bar-wrapper">
            <div class="competency-label"><span>👔 Behavioral & Managerial</span><span>${initialCompetencyBreakdown.behavioral}%</span></div>
            <div class="progress-track"><div class="progress-fill" style="width: ${initialCompetencyBreakdown.behavioral}%; background: #f59e0b;"></div></div>
          </div>
        </div>

        <p style="margin-bottom: 6px;"><strong>Key Skills Identified:</strong> ${skillsHTML}</p>
        <p style="margin-bottom: 6px;"><strong>Matched Reference Module:</strong> <code>${a.recommended_pdf}</code></p>
        <p style="color: #64748b; font-size: 13px; margin-top: 8px;"><em>${a.reasoning}</em></p>
      `;

      document.getElementById('step-2-card').style.display = 'block';
      updateStepper(2);
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
      updateStepper(3);
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
  scoreBanner.textContent = `Your Assessment Score: ${score} / ${currentQuizData.length} (${percentage}%)`;
  scoreBanner.style.display = 'block';

  if (percentage >= 70) {
    document.getElementById('cert-btn').style.display = 'block';
    if (window.confetti) {
      confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
    }
  }

  document.getElementById('score-btn').style.display = 'none';
  updateStepper(4);

  renderSkillProgression(percentage);
  await fetchIGOTRecommendations(percentage, incorrectQuestionsList);
}

function renderSkillProgression(scorePercentage) {
  const card = document.getElementById('skill-progression-card');
  const content = document.getElementById('progression-content');
  const reassessmentCard = document.getElementById('reassessment-card');
  
  card.style.display = 'block';
  reassessmentCard.style.display = 'block';

  // Calculate re-evaluated skill score based on baseline + quiz performance weight
  const reEvaluatedScore = Math.min(100, Math.round((initialCompetencyBreakdown.statistical * 0.4) + (scorePercentage * 0.6)));
  const gapDelta = scorePercentage - 70; // Target passing threshold is 70%

  let statusBadge = scorePercentage >= 70 
    ? `<span style="background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 6px; font-weight: 700;">Target Competency Level Achieved (≥70%)</span>`
    : `<span style="background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 6px; font-weight: 700;">Target Gap Remaining (${Math.abs(gapDelta)}% below 70% threshold)</span>`;

  content.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
      <div style="background: #f8fafc; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0;">
        <span style="font-size: 12px; color: #64748b; font-weight: 700;">INITIAL BASELINE (RESUME)</span>
        <div style="font-size: 22px; font-weight: 800; color: #1e3a8a; margin-top: 4px;">${initialCompetencyBreakdown.statistical}%</div>
      </div>
      <div style="background: #f8fafc; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0;">
        <span style="font-size: 12px; color: #64748b; font-weight: 700;">RE-EVALUATED POST-ASSESSMENT LEVEL</span>
        <div style="font-size: 22px; font-weight: 800; color: #10b981; margin-top: 4px;">${reEvaluatedScore}%</div>
      </div>
    </div>
    <div style="margin-top: 10px;">${statusBadge}</div>
  `;
}

function triggerReassessment() {
  const reassessmentCard = document.getElementById('reassessment-card');
  reassessmentCard.style.display = 'none';
  document.getElementById('quiz-container').scrollIntoView({ behavior: 'smooth' });
  const genBtn = document.getElementById('generate-quiz-btn');
  genBtn.click();
}

async function fetchIGOTRecommendations(scorePercentage, incorrectList) {
  const loadingBox = document.getElementById('igot-loading');
  if (loadingBox) loadingBox.style.display = 'block';

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
  } finally {
    if (loadingBox) loadingBox.style.display = 'none';
  }
}

function renderIGOTCards(courses) {
  const quizContainer = document.getElementById('quiz-container');

  let cardsHTML = `
    <div class="card" style="margin-top: 30px; border-left: 5px solid #10b981; background: #ffffff; padding: 24px;">
      <h3 style="color: #1e3a8a; margin-top: 0;">🏛️ Recommended iGOT Karmayogi Learning Pathways (Mapped to Skill Gaps)</h3>
      <p style="color: #64748b; font-size: 14px; margin-bottom: 18px;">Based on your re-evaluated competency level and missed domain concepts, Groq AI has assigned these targeted modules:</p>
      <div style="display: grid; gap: 16px;">
  `;

  courses.forEach((c) => {
    cardsHTML += `
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h4 style="margin: 0; color: #0f172a; font-size: 16px;">${c.title}</h4>
          <span class="badge" style="background: #fee2e2; color: #991b1b;">${c.competency_type}</span>
        </div>
        <p style="margin: 6px 0; font-size: 13px; color: #1e3a8a;"><strong>Target Skill Gap Addressed:</strong> ${c.target_skill_gap}</p>
        <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748b;">${c.description}</p>
        <a href="${c.portal_url}" target="_blank" style="color: #10b981; font-weight: 700; text-decoration: none; font-size: 14px;">
          🔗 Enroll in Mapped Pathway on iGOT Karmayogi Portal →
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
  doc.setDrawColor(30, 58, 138);
  doc.rect(20, 20, 760, 560);

  doc.setLineWidth(2);
  doc.setDrawColor(59, 130, 246);
  doc.rect(28, 28, 744, 544);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(26);
  doc.setTextColor(30, 58, 138);
  doc.text("CERTIFICATE OF COMPETENCY ACHIEVEMENT", 400, 95, { align: "center" });

  doc.setFontSize(11);
  doc.setFont("courier", "bold");
  doc.setTextColor(107, 33, 168);
  doc.text(`OFFICIAL ID: ${currentUserId}`, 400, 120, { align: "center" });

  doc.setFontSize(12);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(100, 116, 139);
  doc.text("THIS IS PROUDLY PRESENTED TO", 400, 160, { align: "center" });

  doc.setFontSize(24);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(15, 23, 42);
  doc.text(candidateName, 400, 200, { align: "center" });

  doc.setFontSize(13);
  doc.setFont("helvetica", "italic");
  doc.setTextColor(30, 58, 138);
  doc.text(`Cadre: ${selectedRole}`, 400, 225, { align: "center" });

  doc.setLineWidth(1);
  doc.setDrawColor(226, 232, 240);
  doc.line(250, 240, 550, 240);

  doc.setFontSize(13);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(30, 58, 138);
  doc.text("For successfully passing the iGOT Karmayogi assessment in:", 400, 280, { align: "center" });

  doc.setFontSize(20);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(16, 185, 129);
  doc.text(passedDomain, 400, 315, { align: "center" });

  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  doc.setFontSize(11);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(100, 116, 139);
  doc.text(`Date Issued: ${today}`, 100, 490);
  doc.text("Verified by: MoSPI Skill Intelligence Engine", 700, 490, { align: "right" });

  doc.save(`${currentUserId}_${candidateName.replace(/\s+/g, '_')}_Certificate.pdf`);
}