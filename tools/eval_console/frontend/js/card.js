/**
 * card.js — Query card rendering and rating interaction logic.
 * Depends on: marked (CDN), api.js, state.js
 */

const CARD = (() => {
  // Debounce timers keyed by eval_id
  const _saveTimers = {};

  // ─── Public API ──────────────────────────────────────────────────────────────

  function render(query, onRatingSaved) {
    const container = document.getElementById('card-container');
    if (!container) return;
    container.innerHTML = _buildCardHTML(query);
    _renderMarkdown();
    _restoreAllRatings(query);
    _attachListeners(query, onRatingSaved);
  }

  async function saveAll(query) {
    const promises = query.answers.map(a => _saveToServer(a.eval_id, query.reviewer_id ?? STATE.getReviewerId()));
    await Promise.allSettled(promises);
  }

  async function toggleFlag(query) {
    const reviewerId = STATE.getReviewerId();
    for (const answer of query.answers) {
      const current = STATE.getRating(answer.eval_id);
      const isFlagged = current?.flagged === 1;
      STATE.updateRating(answer.eval_id, 'flagged', isFlagged ? 0 : 1);
      await _saveToServer(answer.eval_id, reviewerId);
    }
  }

  // ─── HTML Builders ──────────────────────────────────────────────────────────

  function _buildCardHTML(q) {
    const langBadge = `<span class="badge badge-lang">${_esc(q.language)}</span>`;
    const topicBadge = `<span class="badge badge-topic">${_esc(q.topic.replace(/_/g, ' '))}</span>`;
    const ambiguousBadge = q.is_ambiguous ? '<span class="badge badge-warning">Ambiguous</span>' : '';
    const multiTurnBadge = q.query_type === 'multi_turn' ? '<span class="badge badge-info">Multi-turn</span>' : '';

    const convSection = q.conversation_history?.length
      ? `<details class="conv-history">
           <summary>📋 Conversation History (${q.conversation_history.length} turns)</summary>
           <div class="chat-thread">${_buildChatThread(q.conversation_history)}</div>
         </details>`
      : '';

    const goldRefs = _buildGoldRefs(q.gold_article_refs);

    const answersGrid = `
      <div class="answers-grid">
        ${q.answers.map((a, i) => _buildAnswerColumn(a, q.is_ambiguous, i)).join('')}
      </div>`;

    const turn6Section = q.has_any_turn6
      ? _buildTurn6Block(q)
      : '';

    return `
      <div class="card">
        <div class="card-header">
          <div class="card-header-left">
            <span class="query-id">${_esc(q.query_id)}</span>
            ${langBadge}${topicBadge}${ambiguousBadge}${multiTurnBadge}
          </div>
          <div class="card-header-right">
            <span class="position-label">${q.position} / ${q.total}</span>
          </div>
        </div>

        ${convSection}

        <div class="section query-section">
          <div class="section-label">❓ Query</div>
          <p class="query-text">${_esc(q.query_text)}</p>
        </div>

        <div class="reference-panel">
          <div class="section-label">📚 Reference Answer</div>
          <div class="reference-body" data-markdown="${_escAttr(q.reference_answer)}"></div>
          ${goldRefs}
        </div>

        ${answersGrid}
        ${turn6Section}

        <div class="card-nav">
          <button class="btn btn-prev" onclick="REVIEW.navigatePrev()" ${!q.prev_query_id ? 'disabled' : ''}>
            ← Prev
          </button>
          <button class="btn btn-flag" id="flag-btn" onclick="REVIEW.flagCard()">
            🚩 Flag
          </button>
          <button class="btn btn-next" onclick="REVIEW.saveAndContinue()">
            Save &amp; Continue →
          </button>
        </div>
      </div>`;
  }

  function _buildAnswerColumn(answer, isAmbiguous, colIndex) {
    const letter = String.fromCharCode(65 + colIndex);
    return `
      <div class="answer-col" data-eval-id="${_esc(answer.eval_id)}">
        <div class="answer-col-header">${_esc(answer.system_label)}</div>
        <div class="answer-body">
          <div class="answer-content" data-markdown="${_escAttr(answer.answer)}"></div>
        </div>
        ${_buildRatingBlock(answer.eval_id, isAmbiguous, false)}
      </div>`;
  }

  function _buildTurn6Block(q) {
    const turn5Section = q.turn5_query
      ? `<div class="section query-section turn5-query-section">
           <div class="section-label">❓ Turn 5 — Follow-up Query (context for Turn 6 answers)</div>
           <p class="query-text">${_esc(q.turn5_query)}</p>
         </div>`
      : '';

    const refSection = q.turn6_reference_answer
      ? `<div class="reference-panel reference-panel-sm">
           <div class="section-label">📚 Turn 6 Reference Answer</div>
           <div class="reference-body" data-markdown="${_escAttr(q.turn6_reference_answer)}"></div>
         </div>`
      : '';

    const cols = q.answers.map((a, i) => {
      if (!a.has_turn6) {
        return `
          <div class="answer-col">
            <div class="answer-col-header">${_esc(a.system_label)} (Turn 6)</div>
            <div class="answer-body">
              <p class="no-turn6-msg">— No Turn 6 answer for this system —</p>
            </div>
          </div>`;
      }
      return `
        <div class="answer-col" data-eval-id="${_esc(a.eval_id)}-t6">
          <div class="answer-col-header">${_esc(a.system_label)} (Turn 6)</div>
          <div class="answer-body">
            <div class="answer-content" data-markdown="${_escAttr(a.turn6_answer)}"></div>
          </div>
          ${_buildRatingBlock(a.eval_id, false, true)}
        </div>`;
    }).join('');

    return `
      <div class="turn6-block">
        <div class="turn6-header">Turn 6 Follow-up Evaluation</div>
        ${turn5Section}
        ${refSection}
        <div class="answers-grid">${cols}</div>
      </div>`;
  }

  function _buildRatingBlock(evalId, isAmbiguous, isTurn6) {
    const laName = isTurn6 ? `t6la_${evalId}` : `la_${evalId}`;
    const halName = isTurn6 ? `t6hal_${evalId}` : `hal_${evalId}`;
    const laField = isTurn6 ? 'turn6_legal_accuracy' : 'legal_accuracy';
    const halField = isTurn6 ? 'turn6_hallucination' : 'hallucination';
    const citField = isTurn6 ? 'turn6_citation_notes' : 'citation_notes';
    const notesField = isTurn6 ? 'turn6_notes' : 'notes';
    const ssId = isTurn6 ? `ss-t6-${evalId}` : `ss-${evalId}`;

    const clarificationBlock = (!isTurn6 && isAmbiguous) ? `
      <div class="field-group">
        <div class="field-label">Clarification Quality
          <span class="scale-hint">1=Poor · 4=Excellent</span>
        </div>
        <div class="pill-group">
          ${[1, 2, 3, 4].map(v => `
            <label class="pill">
              <input type="radio" name="clq_${evalId}" value="${v}"
                     data-eval-id="${evalId}" data-field="clarification_score">
              <span>${v}</span>
            </label>`).join('')}
          <label class="pill pill-muted">
            <input type="radio" name="clq_${evalId}" value="na"
                   data-eval-id="${evalId}" data-field="clarification_score">
            <span>N/A</span>
          </label>
        </div>
      </div>` : '';

    return `
      <div class="rating-block">
        <div class="field-group">
          <div class="field-label">Legal Accuracy
            <span class="scale-hint">1=Incorrect · 4=Fully correct</span>
          </div>
          <div class="pill-group">
            ${[1, 2, 3, 4].map(v => `
              <label class="pill">
                <input type="radio" name="${laName}" value="${v}"
                       data-eval-id="${evalId}" data-field="${laField}">
                <span>${v}</span>
              </label>`).join('')}
          </div>
        </div>

        <div class="field-group">
          <div class="field-label">Hallucination Present?</div>
          <div class="pill-group">
            <label class="pill pill-danger">
              <input type="radio" name="${halName}" value="yes"
                     data-eval-id="${evalId}" data-field="${halField}">
              <span>Yes</span>
            </label>
            <label class="pill pill-success">
              <input type="radio" name="${halName}" value="no"
                     data-eval-id="${evalId}" data-field="${halField}">
              <span>No</span>
            </label>
          </div>
        </div>

        <div class="field-group">
          <div class="field-label">Citation Notes</div>
          <textarea rows="2" data-eval-id="${evalId}" data-field="${citField}"
                    placeholder="e.g., correctly cites Art. 298, DO 147-15..."></textarea>
        </div>

        ${clarificationBlock}

        <div class="field-group">
          <div class="field-label">Notes</div>
          <textarea rows="2" data-eval-id="${evalId}" data-field="${notesField}"
                    placeholder="Optional reviewer notes..."></textarea>
        </div>

        <div class="save-status" id="${ssId}"></div>
      </div>`;
  }

  function _buildChatThread(history) {
    return history.map(msg => {
      const isUser = (msg.role || '').toLowerCase() === 'user';
      const text = _esc(msg.text || msg.content || '');
      const icon = isUser ? '👤' : '🤖';
      const cls = isUser ? 'bubble-user' : 'bubble-bot';
      return `<div class="chat-bubble ${cls}">
        <span class="bubble-icon">${icon}</span>
        <span class="bubble-text">${text}</span>
      </div>`;
    }).join('');
  }

  function _buildGoldRefs(refs) {
    if (!refs) return '';
    const parts = refs.split(/[,;]/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) return '';
    const tags = parts.map(r => `<span class="article-tag">${_esc(r)}</span>`).join('');
    return `<div class="gold-refs"><span class="gold-refs-label">Gold Articles:</span>${tags}</div>`;
  }

  // ─── Markdown Rendering ──────────────────────────────────────────────────────

  function _renderMarkdown() {
    document.querySelectorAll('[data-markdown]').forEach(el => {
      const raw = el.dataset.markdown || '';
      el.innerHTML = marked.parse(raw);
    });
  }

  // ─── Value Restoration ───────────────────────────────────────────────────────

  function _restoreAllRatings(query) {
    for (const answer of query.answers) {
      const rating = STATE.getRating(answer.eval_id);
      if (!rating) continue;
      _restoreEvalRating(answer.eval_id, rating, query.is_ambiguous, answer.has_turn6);
    }
    _updateFlagButton(query);
  }

  function _restoreEvalRating(evalId, rating, isAmbiguous, hasTurn6) {
    function setRadio(field, value) {
      if (value == null) return;
      const el = document.querySelector(
        `input[data-eval-id="${evalId}"][data-field="${field}"][value="${String(value)}"]`
      );
      if (el) el.checked = true;
    }
    function setTextarea(field, value) {
      if (!value) return;
      const el = document.querySelector(
        `textarea[data-eval-id="${evalId}"][data-field="${field}"]`
      );
      if (el) el.value = value;
    }

    setRadio('legal_accuracy', rating.legal_accuracy);
    setRadio('hallucination', rating.hallucination);
    setTextarea('citation_notes', rating.citation_notes);
    setTextarea('notes', rating.notes);

    if (isAmbiguous) {
      // null clarification_score on a saved rating means reviewer chose N/A
      const clqVal = rating.legal_accuracy != null && rating.clarification_score == null
        ? 'na'
        : rating.clarification_score;
      setRadio('clarification_score', clqVal);
    }

    if (hasTurn6) {
      setRadio('turn6_legal_accuracy', rating.turn6_legal_accuracy);
      setRadio('turn6_hallucination', rating.turn6_hallucination);
      setTextarea('turn6_citation_notes', rating.turn6_citation_notes);
      setTextarea('turn6_notes', rating.turn6_notes);
    }
  }

  function _updateFlagButton(query) {
    const btn = document.getElementById('flag-btn');
    if (!btn) return;
    const isFlagged = STATE.isQueryFlagged(query.answers.map(a => a.eval_id));
    btn.textContent = isFlagged ? '🚩 Flagged' : '🚩 Flag';
    btn.classList.toggle('flagged', isFlagged);
  }

  // ─── Event Listeners ─────────────────────────────────────────────────────────

  function _attachListeners(query, onRatingSaved) {
    const form = document.getElementById('eval-form');
    if (!form) return;

    // Radio buttons: change → immediate state update + debounced save
    form.addEventListener('change', e => {
      const el = e.target;
      if (el.tagName !== 'INPUT') return;
      const evalId = el.dataset.evalId;
      const field = el.dataset.field;
      if (!evalId || !field) return;

      let value = el.value;
      // N/A radio → store null for clarification_score
      if (field === 'clarification_score' && value === 'na') value = null;
      else if (['legal_accuracy', 'clarification_score',
                 'turn6_legal_accuracy'].includes(field) && value !== null) {
        value = parseInt(value, 10);
      }

      STATE.updateRating(evalId, field, value);
      _scheduleAutoSave(evalId, onRatingSaved);
    });

    // Textareas: input → debounced state update + save
    form.addEventListener('input', e => {
      const el = e.target;
      if (el.tagName !== 'TEXTAREA') return;
      const evalId = el.dataset.evalId;
      const field = el.dataset.field;
      if (!evalId || !field) return;
      STATE.updateRating(evalId, field, el.value.trim() || null);
      _scheduleAutoSave(evalId, onRatingSaved);
    });
  }

  // ─── Server Save ─────────────────────────────────────────────────────────────

  function _scheduleAutoSave(evalId, onRatingSaved) {
    if (_saveTimers[evalId]) clearTimeout(_saveTimers[evalId]);
    _saveTimers[evalId] = setTimeout(async () => {
      await _saveToServer(evalId, STATE.getReviewerId());
      if (onRatingSaved) onRatingSaved(evalId);
    }, 700);
  }

  async function _saveToServer(evalId, reviewerId) {
    const rating = STATE.getRating(evalId) || {};
    const ssId = `ss-${evalId}`;
    _setSaveStatus(ssId, 'saving');
    try {
      await API.post('/api/ratings', {
        eval_id: evalId,
        reviewer_id: reviewerId,
        legal_accuracy: rating.legal_accuracy ?? null,
        hallucination: rating.hallucination ?? null,
        citation_notes: rating.citation_notes ?? null,
        clarification_score: rating.clarification_score ?? null,
        notes: rating.notes ?? null,
        turn6_legal_accuracy: rating.turn6_legal_accuracy ?? null,
        turn6_hallucination: rating.turn6_hallucination ?? null,
        turn6_citation_notes: rating.turn6_citation_notes ?? null,
        turn6_notes: rating.turn6_notes ?? null,
        flagged: rating.flagged ?? 0,
      });
      _setSaveStatus(ssId, 'saved');
      _setSaveStatus(`ss-t6-${evalId}`, 'saved');
    } catch (err) {
      _setSaveStatus(ssId, 'error');
      console.error(`Save failed for ${evalId}:`, err.message);
    }
  }

  function _setSaveStatus(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    const labels = { saving: '⏳ Saving…', saved: '✓ Saved', error: '⚠ Save failed' };
    el.textContent = labels[status] || '';
    el.className = `save-status save-status-${status}`;
    if (status === 'saved') setTimeout(() => { el.textContent = ''; }, 2000);
  }

  // ─── Escape Helpers ───────────────────────────────────────────────────────────

  function _esc(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function _escAttr(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  return { render, saveAll, toggleFlag };
})();
