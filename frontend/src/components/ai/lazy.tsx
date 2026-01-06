/**
 * Lazy-loaded AI Components
 * ============================================
 * These components are code-split to reduce initial bundle size.
 * AI features are only loaded when accessed.
 */
import { lazy, Suspense } from 'react';

// ============================================
// LOADING FALLBACK
// ============================================
function AIComponentLoader() {
  return (
    <div className="flex items-center justify-center p-8 min-h-[200px]">
      <div className="flex flex-col items-center gap-2">
        <div className="w-6 h-6 border-3 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Loading AI...</span>
      </div>
    </div>
  );
}

// ============================================
// LAZY AI COMPONENTS WITH SUSPENSE WRAPPER
// ============================================

// AI Feature Management - Lazy loaded
const LazyAIFeatureToggleInner = lazy(() => 
  import('./AIFeatureToggle').then(m => ({ default: m.AIFeatureToggle }))
);
const LazyAIFeaturePanelInner = lazy(() => 
  import('./AIFeaturePanel').then(m => ({ default: m.AIFeaturePanel }))
);
const LazyAdminAISettingsInner = lazy(() => 
  import('./AdminAISettings').then(m => ({ default: m.AdminAISettings }))
);

// AI Services - Lazy loaded
const LazySuggestionDropdownInner = lazy(() => 
  import('./SuggestionDropdown').then(m => ({ default: m.SuggestionDropdown }))
);
const LazyAnomalyAlertPanelInner = lazy(() => 
  import('./AnomalyAlertPanel').then(m => ({ default: m.AnomalyAlertPanel }))
);

// Forecasting - Lazy loaded
const LazyPayrollForecastPanelInner = lazy(() => 
  import('./PayrollForecastPanel').then(m => ({ default: m.PayrollForecastPanel }))
);
const LazyOvertimeRiskPanelInner = lazy(() => 
  import('./OvertimeRiskPanel').then(m => ({ default: m.OvertimeRiskPanel }))
);
const LazyProjectBudgetPanelInner = lazy(() => 
  import('./ProjectBudgetPanel').then(m => ({ default: m.ProjectBudgetPanel }))
);
const LazyCashFlowChartInner = lazy(() => 
  import('./CashFlowChart').then(m => ({ default: m.CashFlowChart }))
);

// NLP & Reporting - Lazy loaded (already default exports)
const LazyChatInterfaceInner = lazy(() => import('./ChatInterface'));
const LazyWeeklySummaryPanelInner = lazy(() => import('./WeeklySummaryPanel'));
const LazyProjectHealthCardInner = lazy(() => import('./ProjectHealthCard'));
const LazyUserInsightsPanelInner = lazy(() => import('./UserInsightsPanel'));

// ML Anomaly & Estimation - Lazy loaded (already default exports)
const LazyBurnoutRiskPanelInner = lazy(() => import('./BurnoutRiskPanel'));
const LazyTaskEstimationCardInner = lazy(() => import('./TaskEstimationCard'));

// ============================================
// WRAPPED EXPORTS WITH SUSPENSE
// ============================================

// Wrapper components with Suspense fallback
export function LazyAIFeatureToggle(props: Parameters<typeof LazyAIFeatureToggleInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyAIFeatureToggleInner {...props} /></Suspense>;
}

export function LazyAIFeaturePanel(props: Parameters<typeof LazyAIFeaturePanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyAIFeaturePanelInner {...props} /></Suspense>;
}

export function LazyAdminAISettings(props: Parameters<typeof LazyAdminAISettingsInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyAdminAISettingsInner {...props} /></Suspense>;
}

export function LazySuggestionDropdown(props: Parameters<typeof LazySuggestionDropdownInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazySuggestionDropdownInner {...props} /></Suspense>;
}

export function LazyAnomalyAlertPanel(props: Parameters<typeof LazyAnomalyAlertPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyAnomalyAlertPanelInner {...props} /></Suspense>;
}

export function LazyPayrollForecastPanel(props: Parameters<typeof LazyPayrollForecastPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyPayrollForecastPanelInner {...props} /></Suspense>;
}

export function LazyOvertimeRiskPanel(props: Parameters<typeof LazyOvertimeRiskPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyOvertimeRiskPanelInner {...props} /></Suspense>;
}

export function LazyProjectBudgetPanel(props: Parameters<typeof LazyProjectBudgetPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyProjectBudgetPanelInner {...props} /></Suspense>;
}

export function LazyCashFlowChart(props: Parameters<typeof LazyCashFlowChartInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyCashFlowChartInner {...props} /></Suspense>;
}

export function LazyChatInterface(props: Parameters<typeof LazyChatInterfaceInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyChatInterfaceInner {...props} /></Suspense>;
}

export function LazyWeeklySummaryPanel(props: Parameters<typeof LazyWeeklySummaryPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyWeeklySummaryPanelInner {...props} /></Suspense>;
}

export function LazyProjectHealthCard(props: Parameters<typeof LazyProjectHealthCardInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyProjectHealthCardInner {...props} /></Suspense>;
}

export function LazyUserInsightsPanel(props: Parameters<typeof LazyUserInsightsPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyUserInsightsPanelInner {...props} /></Suspense>;
}

export function LazyBurnoutRiskPanel(props: Parameters<typeof LazyBurnoutRiskPanelInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyBurnoutRiskPanelInner {...props} /></Suspense>;
}

export function LazyTaskEstimationCard(props: Parameters<typeof LazyTaskEstimationCardInner>[0]) {
  return <Suspense fallback={<AIComponentLoader />}><LazyTaskEstimationCardInner {...props} /></Suspense>;
}
