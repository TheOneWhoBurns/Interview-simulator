// ── State ────────────────────────────────────────────────────────────────

let state = {
    currentView: 'home',
    currentJobId: null,
    currentRound: null,
    currentQuestionIndex: 0,
    totalQuestions: 0,
    timerInterval: null,
    timerSeconds: 0,
    editor: null,
    currentLanguage: 'python',
};

// ── API helpers ─────────────────────────────────────────────────────────

async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

function showLoading(text = 'Working...') {
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading').classList.remove('hidden');
}

function updateLoading(text) {
    document.getElementById('loading-text').textContent = text;
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

/**
 * Call a streaming SSE endpoint. Shows live status in the loading overlay.
 * Returns the parsed JSON from the final "done" event.
 */
async function apiStream(path, body, loadingLabel = 'Working...') {
    showLoading(loadingLabel);
    return new Promise((resolve, reject) => {
        const ctrl = new AbortController();
        fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: ctrl.signal,
        }).then(res => {
            if (!res.ok) {
                res.json().catch(() => ({ detail: res.statusText })).then(err => {
                    reject(new Error(err.detail || 'Request failed'));
                });
                return;
            }
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function read() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        reject(new Error('Stream ended without result'));
                        return;
                    }
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // keep incomplete line

                    let eventType = null;
                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ') && eventType) {
                            const data = line.slice(6);
                            if (eventType === 'status') {
                                updateLoading(data);
                            } else if (eventType === 'thinking') {
                                updateLoading('Thinking: ' + data);
                            } else if (eventType === 'done') {
                                resolve(JSON.parse(data));
                                ctrl.abort(); // clean up
                                return;
                            } else if (eventType === 'error') {
                                reject(new Error(data));
                                ctrl.abort();
                                return;
                            }
                            eventType = null;
                        }
                    }
                    read();
                }).catch(err => {
                    if (err.name !== 'AbortError') reject(err);
                });
            }
            read();
        }).catch(err => {
            if (err.name !== 'AbortError') reject(err);
        });
    });
}

// ── Navigation ──────────────────────────────────────────────────────────

function showView(view) {
    // Stop timer when leaving quiz view
    if (state.currentView === 'quiz' && view !== 'quiz') {
        stopTimer();
    }

    ['home', 'research', 'quiz', 'progress'].forEach(v => {
        document.getElementById(`view-${v}`).classList.toggle('hidden', v !== view);
        document.getElementById(`nav-${v}`).classList.toggle('active', v === view);
    });
    state.currentView = view;

    if (view === 'home') loadJobs();
    if (view === 'quiz') loadQuizJobs();
    if (view === 'progress') loadProgressJobs();
}

// ── Home View ───────────────────────────────────────────────────────────

async function loadJobs() {
    try {
        const jobs = await api('/api/jobs');
        const el = document.getElementById('job-list');
        if (!jobs.length) {
            el.innerHTML = '<p class="text-dim text-sm">No jobs yet. Research a job listing to get started.</p>';
            return;
        }
        el.innerHTML = jobs.map(j => `
            <div class="job-item" onclick="selectJob('${j.job_id}')">
                <div>
                    <div class="job-info">${esc(j.company)} &mdash; ${esc(j.role)}</div>
                    <div class="job-meta">${j.finalized ? 'Ready' : 'Needs finalization'} &middot; ${j.rounds} round(s)</div>
                </div>
                <div class="text-dim">&rarr;</div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('job-list').innerHTML = `<p class="text-error text-sm">${esc(e.message)}</p>`;
    }
}

function selectJob(jobId) {
    state.currentJobId = jobId;
    showView('quiz');
}

// ── Research Flow ───────────────────────────────────────────────────────

async function startResearch() {
    const url = document.getElementById('job-url').value.trim();
    if (!url) return;

    try {
        const data = await apiStream('/api/stream/jobs/research', { url }, 'Researching job listing...');
        state.currentJobId = data.job_id;

        // Show company info
        const info = document.getElementById('research-info');
        info.innerHTML = `
            <strong>${esc(data.company.name)}</strong> &mdash; ${esc(data.role.title)}<br>
            <span class="text-dim text-sm">${esc(data.company.industry)} &middot; ${esc(data.company.size)}</span>
        `;

        // Show clarifying questions
        const qEl = document.getElementById('clarifying-questions');
        qEl.innerHTML = data.clarifying_questions.map(q => `
            <div class="mb-16">
                <label>${esc(q.question)}</label>
                <span class="text-dim text-sm">${esc(q.context)}</span>
                <textarea id="cq-${q.id}" rows="2" class="mt-8"></textarea>
            </div>
        `).join('');

        document.getElementById('research-step1').classList.add('hidden');
        document.getElementById('research-step2').classList.remove('hidden');
    } catch (e) {
        alert('Research failed: ' + e.message);
    } finally {
        hideLoading();
    }
}

async function finalizeProfile() {
    const textareas = document.querySelectorAll('[id^="cq-"]');
    const answers = {};
    textareas.forEach(ta => {
        const id = ta.id.replace('cq-', '');
        answers[id] = ta.value.trim();
    });

    try {
        await apiStream(`/api/stream/jobs/${state.currentJobId}/finalize`, { answers }, 'Finalizing your profile...');
        document.getElementById('research-step2').classList.add('hidden');
        document.getElementById('research-step3').classList.remove('hidden');
    } catch (e) {
        alert('Finalization failed: ' + e.message);
    } finally {
        hideLoading();
    }
}

function startInterviewFromProfile() {
    showView('quiz');
}

// ── Quiz View ───────────────────────────────────────────────────────────

async function loadQuizJobs() {
    try {
        const jobs = await api('/api/jobs');
        const ready = jobs.filter(j => j.finalized);
        const el = document.getElementById('quiz-job-list');

        if (!ready.length) {
            el.innerHTML = '<p class="text-dim text-sm">No finalized jobs. Research a job first.</p>';
            return;
        }

        // Check which jobs have active rounds
        const activeChecks = await Promise.all(
            ready.map(j => api(`/api/jobs/${j.job_id}/rounds/active`).catch(() => ({ active: false })))
        );

        el.innerHTML = ready.map((j, i) => {
            const active = activeChecks[i];
            const hasActive = active.active && !active.completed;
            const label = hasActive
                ? `Resume (${active.answered}/${active.total_questions} answered)`
                : 'Start Round';
            const btnClass = hasActive ? 'btn' : 'btn btn-secondary';
            return `
                <div class="job-item" onclick="startQuizForJob('${j.job_id}')">
                    <div>
                        <div class="job-info">${esc(j.company)} &mdash; ${esc(j.role)}</div>
                        <div class="job-meta">${j.rounds} round(s) completed</div>
                    </div>
                    <div class="${btnClass}" style="padding:6px 12px">${label}</div>
                </div>
            `;
        }).join('');

        // If we came from research flow with a job selected, auto-start
        if (state.currentJobId && ready.find(j => j.job_id === state.currentJobId)) {
            document.getElementById('quiz-select').classList.remove('hidden');
        }
    } catch (e) {
        document.getElementById('quiz-job-list').innerHTML = `<p class="text-error text-sm">${esc(e.message)}</p>`;
    }
}

async function startQuizForJob(jobId) {
    state.currentJobId = jobId;

    // Check for an in-progress round first
    try {
        const active = await api(`/api/jobs/${jobId}/rounds/active`);
        if (active.active && !active.completed) {
            // Resume the existing round
            state.currentRound = active.round_number;
            state.totalQuestions = active.total_questions;

            document.getElementById('quiz-select').classList.add('hidden');
            document.getElementById('quiz-active').classList.remove('hidden');
            document.getElementById('quiz-eval').classList.add('hidden');
            document.getElementById('quiz-results').classList.add('hidden');

            initEditor();
            displayQuestion(active.current_question);
            return;
        }
        if (active.active && active.completed) {
            // Round is done but not evaluated — go straight to eval
            state.currentRound = active.round_number;
            document.getElementById('quiz-select').classList.add('hidden');
            document.getElementById('quiz-eval').classList.remove('hidden');
            return;
        }
    } catch (e) {
        // No active round, proceed to generate
    }

    // Generate a new round
    try {
        const data = await apiStream(`/api/stream/jobs/${jobId}/rounds/start`, { num_questions: 4 }, 'Generating interview questions...');
        state.currentRound = data.round_number;
        state.totalQuestions = data.total_questions;
        state.currentQuestionIndex = 0;

        document.getElementById('quiz-select').classList.add('hidden');
        document.getElementById('quiz-active').classList.remove('hidden');
        document.getElementById('quiz-eval').classList.add('hidden');
        document.getElementById('quiz-results').classList.add('hidden');

        initEditor();
        displayQuestion(data.first_question);
    } catch (e) {
        alert('Failed to start round: ' + e.message);
    } finally {
        hideLoading();
    }
}

function pauseInterview() {
    // Save current answer text/code before leaving (without submitting)
    stopTimer();
    document.getElementById('quiz-active').classList.add('hidden');
    document.getElementById('quiz-select').classList.remove('hidden');
    showView('home');
}

function displayQuestion(q) {
    state.currentQuestionIndex = q.index;
    document.getElementById('q-current').textContent = q.index + 1;
    document.getElementById('q-total').textContent = q.total_questions;
    document.getElementById('q-title').textContent = q.title;
    document.getElementById('q-body').textContent = q.body;

    // Meta badges
    document.getElementById('q-meta').innerHTML = `
        <span class="badge badge-topic">${esc(q.topic)}</span>
        <span class="badge badge-difficulty-${q.difficulty}">${esc(q.difficulty)}</span>
        <span class="badge badge-type">${esc(q.type)}</span>
    `;

    // Test cases
    const tcEl = document.getElementById('q-test-cases');
    if (q.test_cases && q.test_cases.length) {
        tcEl.innerHTML = '<h3 class="text-sm mb-8">Examples</h3>' + q.test_cases.map((tc, i) => `
            <div class="test-case">
                <div class="label">${tc.description || 'Example ' + (i + 1)}</div>
                <div>Input: <code>${esc(tc.input)}</code></div>
                <div>Output: <code>${esc(tc.expected_output)}</code></div>
            </div>
        `).join('');
    } else {
        tcEl.innerHTML = '';
    }

    // Hints
    const hEl = document.getElementById('q-hints');
    if (q.hints && q.hints.length) {
        hEl.innerHTML = q.hints.map((h, i) => `
            <div>
                <span class="hint-toggle" onclick="this.nextElementSibling.classList.toggle('hidden')">
                    Show hint ${i + 1}
                </span>
                <div class="hint-content hidden">${esc(h)}</div>
            </div>
        `).join('');
    } else {
        hEl.innerHTML = '';
    }

    // Show code tab for coding, text tab otherwise
    if (q.type === 'coding') {
        switchAnswerTab('code');
        // Auto-detect language from question content
        const lang = detectLanguage(q);
        document.getElementById('lang-select').value = lang;
        changeLanguage(lang);
    } else {
        switchAnswerTab('text');
    }

    // Clear previous answer
    if (state.editor) state.editor.setValue('');
    document.getElementById('text-answer').value = '';
    document.getElementById('test-results').classList.add('hidden');
    document.getElementById('test-results').innerHTML = '';

    // Update submit button
    const isLast = q.index >= q.total_questions - 1;
    document.getElementById('submit-btn').textContent = isLast ? 'Submit Final Answer' : 'Submit & Next';

    // Reset timer
    startTimer();
}

// ── Answer Tabs ─────────────────────────────────────────────────────────

function switchAnswerTab(tab) {
    document.querySelectorAll('.answer-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('answer-code').classList.toggle('hidden', tab !== 'code');
    document.getElementById('answer-text').classList.toggle('hidden', tab !== 'text');
    const tabs = document.querySelectorAll('.answer-tab');
    if (tab === 'code') tabs[0].classList.add('active');
    else tabs[1].classList.add('active');

    if (tab === 'code' && state.editor) {
        setTimeout(() => state.editor.refresh(), 10);
    }
}

// ── Code Editor ─────────────────────────────────────────────────────────

const LANG_TO_CM_MODE = {
    'python': 'python',
    'javascript': 'javascript',
    'jsx': 'jsx',
    'java': 'text/x-java',
    'c++': 'text/x-c++src',
    'c': 'text/x-csrc',
    'go': 'go',
    'rust': 'rust',
    'ruby': 'ruby',
    'sql': 'sql',
    'html': 'htmlmixed',
    'css': 'css',
    'shell': 'shell',
};

function initEditor() {
    if (state.editor) return;
    state.editor = CodeMirror(document.getElementById('code-editor-container'), {
        mode: 'python',
        theme: 'material-darker',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        extraKeys: { 'Tab': (cm) => cm.replaceSelection('    ', 'end') },
    });
}

function changeLanguage(lang) {
    state.currentLanguage = lang;
    if (state.editor) {
        state.editor.setOption('mode', LANG_TO_CM_MODE[lang] || lang);
    }
}

function detectLanguage(question) {
    const text = (question.body + ' ' + question.topic + ' ' + question.title).toLowerCase();
    if (/\breact\b|\bjsx\b|\bcomponent\b.*\brender\b/.test(text)) return 'jsx';
    if (/\bjavascript\b|\bjs\b|\bnode\b|\btypescript\b|\bts\b/.test(text)) return 'javascript';
    if (/\bjava\b(?!script)/.test(text)) return 'java';
    if (/\bc\+\+\b|\bcpp\b/.test(text)) return 'c++';
    if (/\bgo\b|\bgolang\b/.test(text)) return 'go';
    if (/\brust\b/.test(text)) return 'rust';
    if (/\bruby\b/.test(text)) return 'ruby';
    if (/\bsql\b/.test(text)) return 'sql';
    if (/\bhtml\b/.test(text)) return 'html';
    if (/\bcss\b/.test(text)) return 'css';
    if (/\bbash\b|\bshell\b/.test(text)) return 'shell';
    if (/\bpython\b/.test(text)) return 'python';
    // Default based on question type keywords
    if (/context api|usestate|hooks|component/.test(text)) return 'jsx';
    return 'python';
}

async function runCode() {
    if (!state.editor) return;
    const code = state.editor.getValue();
    if (!code.trim()) return;

    const statusEl = document.getElementById('run-status');
    statusEl.textContent = 'Running...';
    try {
        const result = await api('/api/execute', {
            method: 'POST',
            body: { code, stdin: '' },
        });
        statusEl.textContent = result.timed_out ? 'Timed out' :
            result.return_code !== 0 ? 'Error' : 'Done';

        const resEl = document.getElementById('test-results');
        resEl.classList.remove('hidden');
        resEl.innerHTML = `
            <div class="card" style="margin:0">
                <h2>Output</h2>
                ${result.stdout ? `<pre style="white-space:pre-wrap;font-size:12px">${esc(result.stdout)}</pre>` : ''}
                ${result.stderr ? `<pre style="white-space:pre-wrap;font-size:12px;color:var(--error)">${esc(result.stderr)}</pre>` : ''}
                ${!result.stdout && !result.stderr ? '<p class="text-dim text-sm">No output</p>' : ''}
            </div>
        `;
    } catch (e) {
        statusEl.textContent = 'Error: ' + e.message;
    }
}

// ── Submit Answer ───────────────────────────────────────────────────────

async function submitAnswer() {
    const code = state.editor ? state.editor.getValue() : '';
    const text = document.getElementById('text-answer').value;

    if (!code.trim() && !text.trim()) {
        if (!confirm('Submit empty answer?')) return;
    }

    stopTimer();
    showLoading('Submitting answer...');
    try {
        const result = await api(
            `/api/jobs/${state.currentJobId}/rounds/${state.currentRound}/answer/${state.currentQuestionIndex}`,
            {
                method: 'POST',
                body: {
                    code,
                    answer_text: text,
                    language: state.currentLanguage || 'python',
                    time_spent_seconds: state.timerSeconds,
                },
            }
        );

        // Show test results if any
        if (result.test_results && result.test_results.length) {
            const resEl = document.getElementById('test-results');
            resEl.classList.remove('hidden');
            resEl.innerHTML = `
                <h3 class="text-sm mb-8">Test Results</h3>
                ${result.test_results.map((r, i) => `
                    <div class="test-result ${r.passed ? 'pass' : 'fail'}">
                        <span>${r.passed ? 'PASS' : 'FAIL'}</span>
                        <span class="text-dim">Expected: ${esc(r.expected)} | Got: ${esc(r.actual)}</span>
                    </div>
                `).join('')}
            `;
        }

        hideLoading();

        if (result.completed) {
            // Show evaluation prompt
            document.getElementById('quiz-active').classList.add('hidden');
            document.getElementById('quiz-eval').classList.remove('hidden');
        } else {
            // Update button to advance manually
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.textContent = 'Next Question';
            submitBtn.onclick = async () => {
                submitBtn.onclick = submitAnswer;
                showLoading('Loading next question...');
                try {
                    const q = await api(
                        `/api/jobs/${state.currentJobId}/rounds/${state.currentRound}/question/${result.next_question_index}`
                    );
                    displayQuestion(q);
                } catch (err) {
                    alert('Failed to load question: ' + err.message);
                } finally {
                    hideLoading();
                }
            };
        }
    } catch (e) {
        hideLoading();
        alert('Submit failed: ' + e.message);
    }
}

// ── Evaluation ──────────────────────────────────────────────────────────

async function evaluateRound() {
    try {
        const data = await apiStream(
            `/api/stream/jobs/${state.currentJobId}/rounds/${state.currentRound}/evaluate`,
            {},
            'Evaluating your answers...',
        );
        hideLoading();
        displayResults(data);
    } catch (e) {
        hideLoading();
        alert('Evaluation failed: ' + e.message);
    }
}

function displayResults(data) {
    document.getElementById('quiz-eval').classList.add('hidden');
    const el = document.getElementById('quiz-results');
    el.classList.remove('hidden');

    const report = data.report;
    const progress = data.progress;
    const s = report.summary;

    let scoreColor = s.overall_score >= 7 ? 'text-success' :
                     s.overall_score >= 5 ? 'text-warning' : 'text-error';

    let html = `
        <div class="card">
            <h2>Round ${report.round_number} Results</h2>
            <div class="flex-between mb-16">
                <div>
                    <div style="font-size:36px;font-weight:700" class="${scoreColor}">${s.overall_score.toFixed(1)}</div>
                    <div class="text-dim text-sm">out of 10</div>
                </div>
                <div class="text-sm text-dim" style="text-align:right">
                    ${s.questions_passed}/${s.total_questions} passed<br>
                    Strongest: ${esc(s.strongest_topic)}<br>
                    Weakest: ${esc(s.weakest_topic)}
                </div>
            </div>
        </div>
    `;

    // Per-question evaluations
    report.evaluations.forEach(ev => {
        let evColor = ev.score >= 7 ? 'text-success' : ev.score >= 5 ? 'text-warning' : 'text-error';
        html += `
            <div class="card">
                <div class="flex-between">
                    <h3>Q${ev.question_id}: ${esc(ev.topic)}</h3>
                    <span class="${evColor}" style="font-size:18px;font-weight:700">${ev.score.toFixed(1)}/10</span>
                </div>
                <div class="question-meta mt-8 mb-8">
                    <span class="badge badge-topic">${esc(ev.subtopic || ev.topic)}</span>
                </div>
                <p class="text-sm mb-8">${esc(ev.feedback)}</p>
                ${ev.strengths.length ? `
                    <div class="feedback-item strength">
                        <div class="text-sm"><strong>Strengths:</strong> ${ev.strengths.map(esc).join(', ')}</div>
                    </div>
                ` : ''}
                ${ev.weaknesses.length ? `
                    <div class="feedback-item weakness">
                        <div class="text-sm"><strong>Weaknesses:</strong> ${ev.weaknesses.map(esc).join(', ')}</div>
                    </div>
                ` : ''}
                ${ev.missed_key_points.length ? `
                    <div class="feedback-item suggestion">
                        <div class="text-sm"><strong>Missed:</strong> ${ev.missed_key_points.map(esc).join(', ')}</div>
                    </div>
                ` : ''}
            </div>
        `;
    });

    // Key takeaways
    if (s.key_takeaways.length) {
        html += `
            <div class="card">
                <h2>Key Takeaways</h2>
                ${s.key_takeaways.map(t => `<p class="text-sm mb-8">&bull; ${esc(t)}</p>`).join('')}
            </div>
        `;
    }

    // Improvement suggestions
    if (s.improvement_suggestions.length) {
        html += `
            <div class="card">
                <h2>Next Steps</h2>
                ${s.improvement_suggestions.map(t => `<p class="text-sm mb-8">&bull; ${esc(t)}</p>`).join('')}
            </div>
        `;
    }

    // Store takeaways for TTS
    state.lastTakeaways = s.key_takeaways || [];

    // Actions
    html += `
        <div class="card flex gap-8">
            <button class="btn" onclick="startQuizForJob('${state.currentJobId}')">Start Another Round</button>
            <button class="btn btn-secondary" onclick="showView('progress')">View Progress</button>
            <button class="btn btn-secondary" onclick="speakFeedback(state.lastTakeaways)">Read Feedback Aloud</button>
        </div>
    `;

    el.innerHTML = html;
}

// ── Progress View ───────────────────────────────────────────────────────

async function loadProgressJobs() {
    try {
        const jobs = await api('/api/jobs');
        const withRounds = jobs.filter(j => j.rounds > 0);
        const el = document.getElementById('progress-job-list');

        if (!withRounds.length) {
            el.innerHTML = '<p class="text-dim text-sm">Complete at least one round to see progress.</p>';
            return;
        }

        el.innerHTML = withRounds.map(j => `
            <div class="job-item" onclick="loadProgressForJob('${j.job_id}')">
                <div class="job-info">${esc(j.company)} &mdash; ${esc(j.role)}</div>
                <div class="job-meta">${j.rounds} round(s)</div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('progress-job-list').innerHTML = `<p class="text-error">${esc(e.message)}</p>`;
    }
}

async function loadProgressForJob(jobId) {
    showLoading('Loading progress...');
    try {
        const [progress, rounds] = await Promise.all([
            api(`/api/jobs/${jobId}/progress`),
            api(`/api/jobs/${jobId}/rounds`),
        ]);

        document.getElementById('progress-select').classList.add('hidden');
        const el = document.getElementById('progress-content');
        el.classList.remove('hidden');

        let scoreColor = progress.overall_score >= 7 ? 'text-success' :
                         progress.overall_score >= 5 ? 'text-warning' : 'text-error';

        let html = `
            <div class="card">
                <h2>Overall Progress</h2>
                <div class="flex-between mb-16">
                    <div>
                        <div style="font-size:36px;font-weight:700" class="${scoreColor}">${progress.overall_score.toFixed(1)}</div>
                        <div class="text-dim text-sm">overall score &middot; ${progress.total_rounds} round(s)</div>
                    </div>
                </div>
        `;

        // Score history chart
        if (progress.score_history && progress.score_history.length > 1) {
            html += `<div class="score-chart">`;
            progress.score_history.forEach((s, i) => {
                const h = (s / 10) * 100;
                html += `<div class="col" style="height:${h}%"><span class="label">R${i + 1}</span></div>`;
            });
            html += `</div>`;
        }

        html += `</div>`;

        // Topic mastery
        if (progress.topic_mastery && progress.topic_mastery.length) {
            html += `<div class="card"><h2>Topic Mastery</h2>`;
            progress.topic_mastery.forEach(t => {
                const pct = (t.score / 10) * 100;
                const color = t.score >= 7 ? 'var(--success)' : t.score >= 5 ? 'var(--warning)' : 'var(--error)';
                html += `
                    <div class="score-bar">
                        <div style="min-width:140px" class="text-sm">${esc(t.topic)}</div>
                        <div class="bar"><div class="fill" style="width:${pct}%;background:${color}"></div></div>
                        <div class="value">${t.score.toFixed(1)}</div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        // Weaknesses
        if (progress.persistent_weaknesses && progress.persistent_weaknesses.length) {
            html += `<div class="card"><h2>Areas to Improve</h2>`;
            progress.persistent_weaknesses.forEach(w => {
                html += `<div class="feedback-item weakness"><strong>${esc(w.area)}</strong><br><span class="text-sm">${esc(w.description)}</span></div>`;
            });
            html += `</div>`;
        }

        // Strengths
        if (progress.demonstrated_strengths && progress.demonstrated_strengths.length) {
            html += `<div class="card"><h2>Strengths</h2>`;
            progress.demonstrated_strengths.forEach(s => {
                html += `<div class="feedback-item strength"><strong>${esc(s.area)}</strong><br><span class="text-sm">${esc(s.description)}</span></div>`;
            });
            html += `</div>`;
        }

        // Round history
        if (rounds.length) {
            html += `<div class="card"><h2>Round History</h2>`;
            rounds.forEach(r => {
                html += `
                    <div class="job-item" onclick="viewRoundDetail('${jobId}', ${r.round_number})">
                        <div class="job-info">Round ${r.round_number}</div>
                        <div class="job-meta">Score: ${r.overall_score.toFixed(1)} &middot; ${r.questions_passed}/${r.total_questions} passed</div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        // Action
        html += `
            <div class="card">
                <button class="btn" onclick="startQuizForJob('${jobId}')">Start New Round</button>
                <button class="btn btn-secondary ml-8" onclick="showView('progress'); document.getElementById('progress-select').classList.remove('hidden'); document.getElementById('progress-content').classList.add('hidden');">Back</button>
            </div>
        `;

        el.innerHTML = html;
    } catch (e) {
        alert('Failed to load progress: ' + e.message);
    } finally {
        hideLoading();
    }
}

async function viewRoundDetail(jobId, roundNumber) {
    showLoading('Loading round details...');
    try {
        const report = await api(`/api/jobs/${jobId}/rounds/${roundNumber}`);
        displayResults({ report, progress: {} });
        showView('quiz');
        document.getElementById('quiz-select').classList.add('hidden');
    } catch (e) {
        alert('Failed: ' + e.message);
    } finally {
        hideLoading();
    }
}

// ── Timer ───────────────────────────────────────────────────────────────

function startTimer() {
    stopTimer();
    state.timerSeconds = 0;
    const el = document.getElementById('q-timer');
    state.timerInterval = setInterval(() => {
        state.timerSeconds++;
        const m = Math.floor(state.timerSeconds / 60);
        const s = state.timerSeconds % 60;
        el.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        el.className = 'timer' + (state.timerSeconds > 600 ? ' danger' : state.timerSeconds > 300 ? ' warning' : '');
    }, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

// ── TTS ─────────────────────────────────────────────────────────────────

async function speakQuestion() {
    const text = document.getElementById('q-body').textContent;
    await speak(text);
}

async function speakFeedback(takeaways) {
    const text = takeaways.join('. ');
    await speak(text);
}

async function speak(text) {
    try {
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        const contentType = res.headers.get('content-type');
        if (contentType && contentType.includes('audio')) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
        } else {
            // Browser fallback
            if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance(text);
                utter.rate = 1.0;
                speechSynthesis.speak(utter);
            }
        }
    } catch {
        // Silent fallback to browser TTS
        if ('speechSynthesis' in window) {
            const utter = new SpeechSynthesisUtterance(text);
            speechSynthesis.speak(utter);
        }
    }
}

// ── Util ────────────────────────────────────────────────────────────────

function esc(s) {
    if (s == null) return '';
    const div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
}

// ── Init ────────────────────────────────────────────────────────────────

loadJobs();
