/**
 * state.js — Application state and localStorage persistence.
 * Depends on: nothing (loaded after api.js)
 */

const STATE = (() => {
  let _reviewerId = null;
  let _ratings = {};      // eval_id → rating object (from server + local changes)
  let _queryIndex = 0;    // current 0-based position in the query list

  function init() {
    _reviewerId = localStorage.getItem('leo_eval_reviewer_id') || null;
    const saved = localStorage.getItem('leo_eval_ratings');
    _ratings = saved ? JSON.parse(saved) : {};
    const idx = localStorage.getItem('leo_eval_query_index');
    _queryIndex = idx !== null ? parseInt(idx, 10) : 0;
  }

  function setSession(token, reviewerId) {
    localStorage.setItem('leo_eval_token', token);
    localStorage.setItem('leo_eval_reviewer_id', reviewerId);
    _reviewerId = reviewerId;
  }

  function getReviewerId() { return _reviewerId; }

  function getQueryIndex() { return _queryIndex; }

  function setQueryIndex(idx) {
    _queryIndex = idx;
    localStorage.setItem('leo_eval_query_index', idx);
  }

  function getRating(evalId) {
    return _ratings[evalId] || null;
  }

  function updateRating(evalId, field, value) {
    if (!_ratings[evalId]) _ratings[evalId] = {};
    _ratings[evalId][field] = value;
    _persistRatings();
  }

  function setRating(evalId, ratingObj) {
    _ratings[evalId] = { ...(_ratings[evalId] || {}), ...ratingObj };
    _persistRatings();
  }

  /** Bulk-load ratings fetched from server (preserves any locally-newer changes). */
  function setServerRatings(ratingsArray) {
    for (const r of ratingsArray) {
      // Server is authoritative; overwrite local cache
      _ratings[r.eval_id] = r;
    }
    _persistRatings();
  }

  function isEvalRated(evalId) {
    const r = _ratings[evalId];
    return r && r.legal_accuracy != null && r.hallucination != null;
  }

  function isQueryComplete(evalIds) {
    return evalIds.length > 0 && evalIds.every(id => isEvalRated(id));
  }

  function isQueryPartial(evalIds) {
    return evalIds.some(id => isEvalRated(id)) && !isQueryComplete(evalIds);
  }

  function isQueryFlagged(evalIds) {
    return evalIds.some(id => _ratings[id]?.flagged === 1);
  }

  function _persistRatings() {
    try {
      localStorage.setItem('leo_eval_ratings', JSON.stringify(_ratings));
    } catch (e) {
      // Storage full — not critical; server is the source of truth
      console.warn('localStorage quota exceeded; ratings not cached locally');
    }
  }

  function clearSession() {
    localStorage.removeItem('leo_eval_token');
    localStorage.removeItem('leo_eval_reviewer_id');
    localStorage.removeItem('leo_eval_ratings');
    localStorage.removeItem('leo_eval_query_index');
    _reviewerId = null;
    _ratings = {};
    _queryIndex = 0;
  }

  return {
    init,
    setSession,
    getReviewerId,
    getQueryIndex,
    setQueryIndex,
    getRating,
    updateRating,
    setRating,
    setServerRatings,
    isEvalRated,
    isQueryComplete,
    isQueryPartial,
    isQueryFlagged,
    clearSession,
  };
})();
