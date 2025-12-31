/**
 * ChatInterface Component
 * 
 * Natural language input for creating time entries
 * Part of Phase 3 AI NLP features
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Loader2, Check, X, Clock, Calendar, Folder, FileText, AlertCircle } from 'lucide-react';
import { useNLPTimeEntry } from '../../hooks/useNLPServices';
import type { NLPParseResult, ParsedEntity } from '../../api/nlpServices';

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
        parse_result: parsedResult,
        user_modifications: Object.keys(modifications).length > 0 
          ? modifications 
          : undefined
      });
      
      if (result.success && result.entry_id) {
        setInput('');
        setParsedResult(null);
        setShowConfirmation(false);
        onEntryCreated?.(result.entry_id);
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
  
  const formatDuration = (duration: NLPParseResult['duration']): string => {
    if (!duration) return 'Not detected';
    const hours = Math.floor(duration.total_minutes / 60);
    const mins = duration.total_minutes % 60;
    if (hours > 0 && mins > 0) return `${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h`;
    return `${mins}m`;
  };
  
  const renderEntity = (
    entity: ParsedEntity | undefined,
    label: string,
    icon: React.ReactNode
  ) => {
    if (!entity) {
      return (
        <div className="flex items-center gap-2 text-gray-400">
          {icon}
          <span>{label}: Not detected</span>
        </div>
      );
    }
    
    return (
      <div className="flex items-center gap-2">
        {icon}
        <span className="font-medium">{entity.name}</span>
        <span className={`text-xs ${getConfidenceColor(entity.confidence)}`}>
          ({Math.round(entity.confidence * 100)}%)
        </span>
        {entity.alternatives && entity.alternatives.length > 0 && (
          <select
            className="ml-2 text-sm border rounded px-1 py-0.5 
              bg-white dark:bg-gray-800 dark:border-gray-600"
            onChange={(e) => {
              const alt = entity.alternatives?.find(a => a.name === e.target.value);
              if (alt?.id) {
                setModifications(prev => ({
                  ...prev,
                  [`${label.toLowerCase()}_id`]: alt.id
                }));
              }
            }}
          >
            <option value={entity.name}>{entity.name}</option>
            {entity.alternatives.map((alt, i) => (
              <option key={i} value={alt.name}>
                {alt.name} ({Math.round(alt.confidence * 100)}%)
              </option>
            ))}
          </select>
        )}
      </div>
    );
  };
  
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md ${className}`}>
      {/* Input Area */}
      <form onSubmit={handleSubmit} className="p-4">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              disabled={isLoading || showConfirmation}
              className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 
                rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent
                bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {input && !showConfirmation && (
              <button
                type="button"
                onClick={() => setInput('')}
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
            className="px-4 py-3 bg-blue-600 text-white rounded-lg
              hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )}
          </button>
        </div>
        
        {/* Error Display */}
        {error && (
          <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 text-red-600 
            dark:text-red-400 rounded flex items-center gap-2 text-sm">
            <AlertCircle size={16} />
            {error.message}
          </div>
        )}
      </form>
      
      {/* Parsed Result Confirmation */}
      {showConfirmation && parsedResult && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Parsed Time Entry
            </h3>
            <span className={`text-sm ${getConfidenceColor(parsedResult.overall_confidence)}`}>
              Overall confidence: {Math.round(parsedResult.overall_confidence * 100)}%
            </span>
          </div>
          
          <div className="space-y-2 mb-4">
            {/* Duration */}
            <div className="flex items-center gap-2">
              <Clock size={16} className="text-blue-500" />
              <span className="font-medium">{formatDuration(parsedResult.duration)}</span>
              {parsedResult.duration && (
                <span className={`text-xs ${getConfidenceColor(parsedResult.duration.confidence)}`}>
                  ({Math.round(parsedResult.duration.confidence * 100)}%)
                </span>
              )}
            </div>
            
            {/* Date */}
            <div className="flex items-center gap-2">
              <Calendar size={16} className="text-green-500" />
              <span className="font-medium">
                {parsedResult.date?.date || 'Today'}
              </span>
              {parsedResult.date && (
                <span className={`text-xs ${getConfidenceColor(parsedResult.date.confidence)}`}>
                  ({Math.round(parsedResult.date.confidence * 100)}%)
                </span>
              )}
            </div>
            
            {/* Project */}
            {renderEntity(
              parsedResult.project,
              'Project',
              <Folder size={16} className="text-purple-500" />
            )}
            
            {/* Task */}
            {renderEntity(
              parsedResult.task,
              'Task',
              <FileText size={16} className="text-orange-500" />
            )}
            
            {/* Description */}
            {parsedResult.description && (
              <div className="flex items-start gap-2">
                <FileText size={16} className="text-gray-500 mt-0.5" />
                <span className="text-gray-600 dark:text-gray-400 italic">
                  "{parsedResult.description}"
                </span>
              </div>
            )}
          </div>
          
          {/* Suggestions */}
          {parsedResult.suggestions && parsedResult.suggestions.length > 0 && (
            <div className="mb-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded text-sm">
              <p className="font-medium text-yellow-700 dark:text-yellow-400 mb-1">
                Suggestions:
              </p>
              <ul className="list-disc list-inside text-yellow-600 dark:text-yellow-300">
                {parsedResult.suggestions.map((suggestion, i) => (
                  <li key={i}>{suggestion}</li>
                ))}
              </ul>
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
