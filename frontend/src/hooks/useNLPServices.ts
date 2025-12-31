/**
 * NLP Hooks
 * 
 * React Query hooks for Phase 3 Natural Language Processing
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { nlpApi } from '../api/nlpServices';
import type {
  NLPParseRequest,
  NLPParseResponse,
  NLPConfirmRequest,
  NLPConfirmResponse
} from '../api/nlpServices';

// ============================================
// QUERY KEYS
// ============================================

export const nlpKeys = {
  all: ['nlp'] as const,
  parse: () => [...nlpKeys.all, 'parse'] as const,
  history: () => [...nlpKeys.all, 'history'] as const
};

// ============================================
// HOOKS
// ============================================

/**
 * Hook for parsing natural language time entry
 * Uses mutation since it's a user-initiated action
 */
export function useNLPParse() {
  return useMutation<NLPParseResponse, Error, NLPParseRequest>({
    mutationFn: (request) => nlpApi.parseTimeEntry(request),
    onError: (error) => {
      console.error('NLP parse error:', error);
    }
  });
}

/**
 * Hook for confirming parsed entry and creating time entry
 */
export function useNLPConfirm() {
  const queryClient = useQueryClient();
  
  return useMutation<NLPConfirmResponse, Error, NLPConfirmRequest>({
    mutationFn: (request) => nlpApi.confirmParsedEntry(request),
    onSuccess: () => {
      // Invalidate time entries cache when new entry created
      queryClient.invalidateQueries({ queryKey: ['timeEntries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (error) => {
      console.error('NLP confirm error:', error);
    }
  });
}

/**
 * Combined hook for NLP time entry creation flow
 */
export function useNLPTimeEntry() {
  const parseMutation = useNLPParse();
  const confirmMutation = useNLPConfirm();
  
  const parseAndConfirm = async (
    text: string,
    options?: {
      autoConfirm?: boolean;
      confidenceThreshold?: number;
    }
  ) => {
    const parseResult = await parseMutation.mutateAsync({ text });
    
    if (!parseResult.success || !parseResult.result) {
      return { success: false, error: parseResult.error };
    }
    
    const { autoConfirm = false, confidenceThreshold = 0.8 } = options || {};
    
    // Auto-confirm if confidence is high enough
    if (
      autoConfirm && 
      !parseResult.result.needs_confirmation && 
      parseResult.result.overall_confidence >= confidenceThreshold
    ) {
      const confirmResult = await confirmMutation.mutateAsync({
        parse_result: parseResult.result
      });
      return { 
        success: confirmResult.success, 
        parsed: parseResult.result,
        entry_id: confirmResult.entry_id
      };
    }
    
    // Return parsed result for manual confirmation
    return { 
      success: true, 
      parsed: parseResult.result,
      needs_confirmation: true 
    };
  };
  
  return {
    parse: parseMutation,
    confirm: confirmMutation,
    parseAndConfirm,
    isLoading: parseMutation.isPending || confirmMutation.isPending,
    error: parseMutation.error || confirmMutation.error
  };
}

export default {
  useNLPParse,
  useNLPConfirm,
  useNLPTimeEntry
};
