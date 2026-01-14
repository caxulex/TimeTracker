/**
 * NLP API Services
 * 
 * API client functions for Phase 3 Natural Language Processing:
 * - Parse natural language time entries
 * - Confirm and create entries from parsed results
 */

import api from './client';

// ============================================
// TYPES
// ============================================

export interface NLPParseRequest {
  text: string;
  user_id?: number;
  team_id?: number;
  context?: {
    recent_projects?: string[];
    recent_tasks?: string[];
    current_date?: string;
  };
}

export interface NLPSuggestion {
  id: number;
  name: string;
}

export interface NLPParsedEntity {
  type: string;
  value: string;
  id?: number;
  confidence: number;
}

/**
 * Backend NLP Parse Result - matches backend NLPParseResult.to_dict()
 */
export interface NLPParseResult {
  original_text: string;
  project_id?: number;
  project_name?: string;
  task_id?: number;
  task_name?: string;
  duration_seconds?: number;
  duration_display?: string;
  start_time?: string;
  end_time?: string;
  description?: string;
  confidence: number;
  confidence_level: 'low' | 'medium' | 'high';
  needs_clarification: boolean;
  clarification_question?: string;
  parsed_entities: NLPParsedEntity[];
  suggestions: NLPSuggestion[];
}

export interface NLPParseResponse {
  success: boolean;
  result?: NLPParseResult;
  error?: string;
  enabled?: boolean;
}

export interface NLPConfirmRequest {
  parsed_result: NLPParseResult;
  modifications?: {
    project_id?: number;
    task_id?: number;
    duration_seconds?: number;
    start_time?: string;
    description?: string;
  };
}

export interface NLPConfirmResponse {
  success: boolean;
  time_entry_id?: number;
  message?: string;
  error?: string;
}

// ============================================
// API FUNCTIONS
// ============================================

/**
 * Parse natural language time entry
 */
export async function parseTimeEntry(
  request: NLPParseRequest
): Promise<NLPParseResponse> {
  const response = await api.post<NLPParseResponse>(
    '/api/ai/nlp/parse',
    request
  );
  return response.data;
}

/**
 * Confirm parsed entry and create time entry
 */
export async function confirmParsedEntry(
  request: NLPConfirmRequest
): Promise<NLPConfirmResponse> {
  const response = await api.post<NLPConfirmResponse>(
    '/api/ai/nlp/confirm',
    request
  );
  return response.data;
}

// ============================================
// EXPORT API OBJECT
// ============================================

export const nlpApi = {
  parseTimeEntry,
  confirmParsedEntry
};

export default nlpApi;
