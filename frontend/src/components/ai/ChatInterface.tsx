/**
 * ChatInterface Component
 * 
 * Natural language input for creating time entries
 * Part of Phase 3 AI NLP features
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Loader2, Check, X, Clock, Calendar, Folder, FileText, AlertCircle } from 'lucide-react';
import { useNLPTimeEntry } from '../../hooks/useNLPServices';
import type { NLPParseResult } from '../../api/nlpServices';

interface ChatInterfaceProps {
  onEntryCreated?: (entryId: number) => void;
  className?: string;
  placeholder?: string;
  autoFocus?: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  onEntryCreated,
  className = '',
  placeholder = 'Type a time entry, e.g., "2 hours on Project Alpha yesterday fixing bugs"',
  autoFocus = false
}) => {
  const [input, setInput] = useState('');
  const [parsedResult, setParsedResult] = useState<NLPParseResult | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [modifications, setModifications] = useState<Record<string, unknown>>({});
  const inputRef = useRef<HTMLInputElement>(null);
  
  const { parse, confirm, isLoading, error } = useNLPTimeEntry();
  
  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);
  
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    try {
      const result = await parse.mutateAsync({ text: input.trim() });
      
      if (result.success && result.result) {
        setParsedResult(result.result);
        setShowConfirmation(true);
        setModifications({});
      }
    } catch (err) {
      console.error('Parse error:', err);
    }
  }, [input, isLoading, parse]);
  
  const handleConfirm = useCallback(async () => {
    if (!parsedResult) return;
    
    try {
      const result = await confirm.mutateAsync({
        parsed_result: parsedResult,
        modifications: Object.keys(modifications).length > 0 
          ? modifications as { project_id?: number; task_id?: number; duration_seconds?: number }
          : undefined
      });
      
      if (result.success && result.time_entry_id) {
        setInput('');
        setParsedResult(null);
        setShowConfirmation(false);
        onEntryCreated?.(result.time_entry_id);
      }
    } catch (err) {
      console.error('Confirm error:', err);
    }
  }, [parsedResult, modifications, confirm, onEntryCreated]);
  
  const handleCancel = useCallback(() => {
    setParsedResult(null);
    setShowConfirmation(false);
    setModifications({});
    inputRef.current?.focus();
  }, []);
  
  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return 'text-green-600 dark:text-green-400';
    if (confidence >= 0.5) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };
  
  const formatDurationFromSeconds = (seconds?: number): string => {
    if (!seconds) return 'Not detected';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0 && mins > 0) return `${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h`;
    return `${mins}m`;
  };
  
  return (
    <div 
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-md ${className}`}
      role="region"
      aria-label="AI Time Entry Assistant"
    >
      {/* Input Area */}
      <form onSubmit={handleSubmit} className="p-4" aria-label="Natural language time entry form">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              disabled={isLoading || showConfirmation}
              aria-label="Enter time entry in natural language"
              aria-describedby="chat-help-text"
              className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 
                rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent
                bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {input && !showConfirmation && (
              <button
                type="button"
                onClick={() => setInput('')}
                aria-label="Clear input"
                className="absolute right-3 top-1/2 -translate-y-1/2 
                  text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X size={16} />
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading || showConfirmation}
            aria-label={isLoading ? 'Processing entry...' : 'Parse time entry'}
            className="px-4 py-3 bg-blue-600 text-white rounded-lg
              hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 size={20} className="animate-spin" aria-hidden="true" />
            ) : (
              <Send size={20} aria-hidden="true" />
            )}
          </button>
        </div>
        <p id="chat-help-text" className="sr-only">
          Enter a time entry in natural language, for example: 2 hours on Project Alpha yesterday fixing bugs
        </p>
        
        {/* Error Display */}
        {error && (
          <div 
            className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 text-red-600 
              dark:text-red-400 rounded flex items-center gap-2 text-sm"
            role="alert"
            aria-live="polite"
          >
            <AlertCircle size={16} aria-hidden="true" />
            {typeof error === 'string' ? error : (error?.message || 'An error occurred')}
          </div>
        )}
      </form>
      
      {/* Parsed Result Confirmation */}
      {showConfirmation && parsedResult && (
        <div 
          className="border-t border-gray-200 dark:border-gray-700 p-4"
          role="region"
          aria-label="Parsed time entry confirmation"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Parsed Time Entry
            </h3>
            <span className={`text-sm ${getConfidenceColor(parsedResult.confidence)}`}>
              Confidence: {Math.round(parsedResult.confidence * 100)}%
            </span>
          </div>
          
          <div className="space-y-3 mb-4">
            {/* Duration - Editable */}
            <div className="flex items-center gap-2">
              <Clock size={16} className="text-blue-500" />
              <label className="text-sm text-gray-600 dark:text-gray-400">Duration:</label>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={Math.floor((modifications.duration_seconds as number ?? parsedResult.duration_seconds ?? 0) / 3600)}
                  onChange={(e) => {
                    const hours = parseInt(e.target.value) || 0;
                    const currentMins = Math.floor(((modifications.duration_seconds as number ?? parsedResult.duration_seconds ?? 0) % 3600) / 60);
                    setModifications(prev => ({
                      ...prev,
                      duration_seconds: hours * 3600 + currentMins * 60
                    }));
                  }}
                  className="w-16 px-2 py-1 border rounded text-center dark:bg-gray-700 dark:border-gray-600"
                />
                <span className="text-gray-500">h</span>
                <input
                  type="number"
                  min="0"
                  max="59"
                  value={Math.floor(((modifications.duration_seconds as number ?? parsedResult.duration_seconds ?? 0) % 3600) / 60)}
                  onChange={(e) => {
                    const mins = parseInt(e.target.value) || 0;
                    const currentHours = Math.floor((modifications.duration_seconds as number ?? parsedResult.duration_seconds ?? 0) / 3600);
                    setModifications(prev => ({
                      ...prev,
                      duration_seconds: currentHours * 3600 + mins * 60
                    }));
                  }}
                  className="w-16 px-2 py-1 border rounded text-center dark:bg-gray-700 dark:border-gray-600"
                />
                <span className="text-gray-500">m</span>
              </div>
            </div>
            
            {/* Date & Time - Editable */}
            <div className="flex items-center gap-2 flex-wrap">
              <Calendar size={16} className="text-green-500" />
              <label className="text-sm text-gray-600 dark:text-gray-400">Date:</label>
              <input
                type="date"
                value={(modifications.start_time as string)?.split('T')[0] || 
                       parsedResult.start_time?.split('T')[0] || 
                       new Date().toISOString().split('T')[0]}
                onChange={(e) => {
                  const currentTime = (modifications.start_time as string)?.split('T')[1]?.substring(0, 5) || 
                                     parsedResult.start_time?.split('T')[1]?.substring(0, 5) || 
                                     '09:00';
                  setModifications(prev => ({
                    ...prev,
                    start_time: e.target.value + 'T' + currentTime + ':00'
                  }));
                }}
                className="px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
              <label className="text-sm text-gray-600 dark:text-gray-400 ml-2">Start:</label>
              <input
                type="time"
                value={(modifications.start_time as string)?.split('T')[1]?.substring(0, 5) || 
                       parsedResult.start_time?.split('T')[1]?.substring(0, 5) || 
                       '09:00'}
                onChange={(e) => {
                  const currentDate = (modifications.start_time as string)?.split('T')[0] || 
                                     parsedResult.start_time?.split('T')[0] || 
                                     new Date().toISOString().split('T')[0];
                  setModifications(prev => ({
                    ...prev,
                    start_time: currentDate + 'T' + e.target.value + ':00'
                  }));
                }}
                className="px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            
            {/* Project */}
            <div className="flex items-center gap-2">
              <Folder size={16} className="text-purple-500" />
              {parsedResult.project_name ? (
                <span className="font-medium text-green-600">{parsedResult.project_name}</span>
              ) : (
                <span className="text-gray-400">Project: Not detected</span>
              )}
            </div>
            
            {/* Task */}
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-orange-500" />
              {parsedResult.task_name ? (
                <span className="font-medium">{parsedResult.task_name}</span>
              ) : (
                <span className="text-gray-400">Task: Not detected</span>
              )}
            </div>
            
            {/* Description - Editable */}
            <div className="flex items-start gap-2">
              <FileText size={16} className="text-gray-500 mt-2" />
              <input
                type="text"
                value={(modifications.description as string) ?? parsedResult.description ?? ''}
                onChange={(e) => {
                  setModifications(prev => ({
                    ...prev,
                    description: e.target.value
                  }));
                }}
                placeholder="Add description..."
                className="flex-1 px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600 
                  text-gray-600 dark:text-gray-300"
              />
            </div>
          </div>
          
          {/* Suggestions - Projects to choose from */}
          {parsedResult.suggestions && parsedResult.suggestions.length > 0 && (
            <div className="mb-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded text-sm">
              <p className="font-medium text-yellow-700 dark:text-yellow-400 mb-1">
                Did you mean one of these projects?
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {parsedResult.suggestions.map((suggestion) => (
                  <button
                    key={suggestion.id}
                    type="button"
                    onClick={() => {
                      setModifications(prev => ({
                        ...prev,
                        project_id: suggestion.id
                      }));
                      setParsedResult(prev => prev ? {
                        ...prev,
                        project: {
                          name: suggestion.name,
                          id: suggestion.id,
                          confidence: 1.0
                        }
                      } : null);
                    }}
                    className="px-3 py-1 bg-yellow-100 dark:bg-yellow-800 text-yellow-800 
                      dark:text-yellow-200 rounded-full hover:bg-yellow-200 
                      dark:hover:bg-yellow-700 transition-colors text-sm"
                  >
                    {suggestion.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {/* Action Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={confirm.isPending}
              className="flex-1 py-2 bg-green-600 text-white rounded-lg
                hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {confirm.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Check size={18} />
              )}
              Confirm & Create Entry
            </button>
            <button
              onClick={handleCancel}
              disabled={confirm.isPending}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 
                text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 
                dark:hover:bg-gray-700 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      
      {/* Helper Text */}
      {!showConfirmation && (
        <div className="px-4 pb-4 text-xs text-gray-500 dark:text-gray-400">
          <span className="font-medium">Examples:</span>
          <span className="ml-2">"3 hours on Website Redesign today"</span>
          <span className="ml-2">•</span>
          <span className="ml-2">"30min bug fixes yesterday"</span>
          <span className="ml-2">•</span>
          <span className="ml-2">"1:30 meeting with client last Monday"</span>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
