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

export interface ParsedDuration {
  hours: number;
  minutes: number;
  total_minutes: number;
  original_text: string;
  confidence: number;
}

export interface ParsedDate {
  date: string;
  original_text: string;
  confidence: number;
}

export interface ParsedEntity {
  name: string;
  id?: number;
  confidence: number;
  alternatives?: Array<{
    name: string;
    id?: number;
    confidence: number;
  }>;
}

export interface NLPParseResult {
  original_text: string;
  duration?: ParsedDuration;
  date?: ParsedDate;
  project?: ParsedEntity;
  task?: ParsedEntity;
  description?: string;
  overall_confidence: number;
  parse_method: 'rule_based' | 'ai_enhanced' | 'hybrid';
  needs_confirmation: boolean;
  suggestions?: string[];
  errors?: string[];
}

export interface NLPParseResponse {
  success: boolean;
  result?: NLPParseResult;
  error?: string;
  enabled?: boolean;
}

export interface NLPConfirmRequest {
  parse_result: NLPParseResult;
  user_modifications?: {
    project_id?: number;
    task_id?: number;
    duration_minutes?: number;
    date?: string;
    description?: string;
  };
}

export interface NLPConfirmResponse {
  success: boolean;
  entry_id?: number;
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
