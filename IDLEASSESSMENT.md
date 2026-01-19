# Idle Time Detection & Activity Monitoring Assessment

## 📋 Overview

This document assesses the options for implementing **activity monitoring** and **idle time detection** in TimeTracker. The goal is to make the app responsive to when a person is actually working vs. idle, ensuring accurate time tracking.

---

## 🎯 Problem Statement

Currently, TimeTracker relies on users manually starting/stopping timers. This creates issues:

| Issue | Impact |
|-------|--------|
| User forgets to stop timer | Inflated hours logged |
| User forgets to start timer | Lost billable time |
| User walks away from computer | Timer keeps running |
| Meetings/calls away from desk | Inaccurate project attribution |
| Context switching | Time logged to wrong project |

**Goal:** Automatically detect when a user is idle and either pause the timer, prompt for action, or flag the time for review.

---

## 🔍 Idle Detection Approaches

### Option 1: Browser-Based Detection (Frontend Only)

**How It Works:**
- JavaScript detects user activity through DOM events
- Events monitored: `mousemove`, `keydown`, `click`, `scroll`, `touchstart`
- After X minutes of no activity, trigger idle state

**Implementation:**

```javascript
// Conceptual example - NOT actual code to implement
let idleTimeout;
const IDLE_THRESHOLD = 5 * 60 * 1000; // 5 minutes

function resetIdleTimer() {
  clearTimeout(idleTimeout);
  idleTimeout = setTimeout(() => {
    // User is idle - trigger action
    showIdlePrompt();
  }, IDLE_THRESHOLD);
}

['mousemove', 'keydown', 'click', 'scroll'].forEach(event => {
  document.addEventListener(event, resetIdleTimer);
});
```

**Pros:**
| Advantage | Description |
|-----------|-------------|
| No installation | Works in any browser |
| Privacy-friendly | Only detects activity, not what user does |
| Simple implementation | Pure JavaScript, no dependencies |
| Cross-platform | Works on Windows, Mac, Linux |

**Cons:**
| Disadvantage | Description |
|--------------|-------------|
| Browser tab must be open | Won't detect if user switches to other apps |
| Limited scope | Only detects browser activity, not system-wide |
| Tab focus issues | May not work if tab is in background |
| Battery drain | Constant event listeners |

**Effort Estimate:** 1-2 days

---

### Option 2: Desktop Application (Electron/Tauri)

**How It Works:**
- Wrap the web app in a desktop container
- Use native APIs to detect system-wide idle time
- Monitor mouse/keyboard activity at OS level

**Implementation Approach:**

```javascript
// Electron example - conceptual
const { powerMonitor } = require('electron');

// Get system idle time in seconds
const idleTime = powerMonitor.getSystemIdleTime();

if (idleTime > 300) { // 5 minutes
  // User is idle system-wide
  notifyUserAboutIdleTime(idleTime);
}
```

**Pros:**
| Advantage | Description |
|-----------|-------------|
| System-wide detection | Detects idle even when app not focused |
| More accurate | Uses OS-level idle APIs |
| Background operation | Can run in system tray |
| Notifications | Native OS notifications |

**Cons:**
| Disadvantage | Description |
|--------------|-------------|
| Requires installation | Users must download app |
| Maintenance burden | Must support Windows, Mac, Linux builds |
| App store approval | May need signing certificates |
| Update mechanism | Need auto-update infrastructure |

**Effort Estimate:** 2-4 weeks (initial), ongoing maintenance

---

### Option 3: Browser Extension

**How It Works:**
- Chrome/Firefox/Edge extension with broader permissions
- Can detect activity across all browser tabs
- Optional: Use `idle` API for system-wide idle detection

**Implementation Approach:**

```javascript
// Chrome Extension - conceptual
chrome.idle.queryState(300, (state) => {
  // state: "active", "idle", or "locked"
  if (state === 'idle') {
    // Notify web app about idle state
    chrome.runtime.sendMessage({ type: 'IDLE_DETECTED', duration: 300 });
  }
});

// Set idle detection interval
chrome.idle.setDetectionInterval(60); // Check every 60 seconds
```

**Pros:**
| Advantage | Description |
|-----------|-------------|
| System idle detection | Chrome's `idle` API detects OS-level idle |
| Lightweight | Smaller than full desktop app |
| Auto-updates | Browser handles updates |
| Cross-browser tabs | Works across all browser activity |

**Cons:**
| Disadvantage | Description |
|--------------|-------------|
| Requires installation | Extension must be installed |
| Browser-specific | Need separate extensions for Chrome/Firefox/Edge |
| Permission concerns | Users may distrust extensions |
| Store approval | Must pass extension store review |

**Effort Estimate:** 1-2 weeks per browser

---

### Option 4: Hybrid Approach (Recommended)

**How It Works:**
Combine multiple approaches for maximum coverage:

1. **Basic (Default):** Browser-based detection for all users
2. **Enhanced (Optional):** Browser extension for users who want system-wide detection
3. **Premium (Future):** Desktop app for power users

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     TimeTracker Backend                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Idle Time Processing Service            │    │
│  │  - Receives idle events from all sources            │    │
│  │  - Calculates actual work time                      │    │
│  │  - Flags suspicious entries for review              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
        │                    │                    │
   WebSocket            WebSocket            WebSocket
        │                    │                    │
┌───────┴───────┐  ┌────────┴────────┐  ┌───────┴───────┐
│  Browser Tab  │  │ Browser Extension│  │  Desktop App  │
│  (Basic)      │  │ (Enhanced)       │  │  (Premium)    │
│               │  │                  │  │               │
│ - DOM events  │  │ - chrome.idle    │  │ - OS APIs     │
│ - Tab visible │  │ - All tabs       │  │ - System tray │
│ - 5min detect │  │ - System idle    │  │ - Screenshots │
└───────────────┘  └──────────────────┘  └───────────────┘
```

---

## ⚙️ Feature Specifications

### Core Idle Detection Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **Idle Threshold** | Configurable time before considered idle (default: 5 min) | High |
| **Idle Prompt** | Modal asking what to do with idle time | High |
| **Auto-Pause** | Automatically pause timer after idle threshold | Medium |
| **Idle Time Attribution** | Let user assign idle time to project or discard | High |
| **Activity Heartbeat** | Regular pings to server confirming user active | Medium |
| **Session Recovery** | Handle browser refresh/crash during tracking | High |

### Idle Prompt Options

When idle is detected, prompt user with options:

```
┌──────────────────────────────────────────────────────┐
│  ⏸️  You've been idle for 15 minutes                  │
│                                                      │
│  What would you like to do with this time?           │
│                                                      │
│  [Keep All]     - Add 15 min to current project      │
│  [Keep Some]    - I was working for ___ minutes      │
│  [Discard]      - Remove idle time from entry        │
│  [Reassign]     - Assign to different project        │
│                                                      │
│  ☐ Remember my choice for short breaks              │
└──────────────────────────────────────────────────────┘
```

### Admin Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `idle_detection_enabled` | Enable/disable for company | `true` |
| `idle_threshold_minutes` | Minutes before idle prompt | `5` |
| `auto_pause_enabled` | Auto-pause vs. prompt only | `false` |
| `max_idle_before_stop` | Auto-stop timer after X min | `30` |
| `require_idle_justification` | Force note when keeping idle time | `false` |
| `idle_detection_method` | `browser` / `extension` / `desktop` | `browser` |

---

## 📊 Data Model Changes

### New Tables/Fields Required

**Option A: Extend TimeEntry**

```sql
-- Add to time_entries table
ALTER TABLE time_entries ADD COLUMN idle_time_seconds INTEGER DEFAULT 0;
ALTER TABLE time_entries ADD COLUMN idle_events JSONB DEFAULT '[]';
-- idle_events: [{"start": "2026-01-19T10:00:00Z", "end": "2026-01-19T10:05:00Z", "action": "kept"}]
```

**Option B: Separate Idle Events Table**

```sql
CREATE TABLE idle_events (
    id SERIAL PRIMARY KEY,
    time_entry_id INTEGER REFERENCES time_entries(id),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    action VARCHAR(20), -- 'kept', 'discarded', 'reassigned', 'pending'
    reassigned_to_entry_id INTEGER REFERENCES time_entries(id),
    user_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Recommendation:** Option B provides better audit trail and reporting capabilities.

---

## 🔐 Privacy Considerations

### What We SHOULD Track

| Data | Purpose | Storage |
|------|---------|---------|
| Idle start/end times | Calculate actual work time | Database |
| User's idle action choice | Audit trail | Database |
| Activity heartbeat | Confirm user active | Temporary |

### What We Should NOT Track

| Data | Reason |
|------|--------|
| Keystrokes | Privacy violation, unnecessary |
| Screenshots | Privacy violation, legal issues |
| Application names | Privacy concerns, not needed |
| URLs visited | Privacy violation |
| Mouse coordinates | Unnecessary detail |

### User Consent Requirements

1. **Opt-in by default** - Users must enable idle detection
2. **Clear disclosure** - Explain what is tracked in settings
3. **Data access** - Users can view their idle event history
4. **Data deletion** - Users can delete idle event data
5. **Admin transparency** - Show if company requires idle tracking

---

## 📱 UI/UX Considerations

### User Dashboard Additions

1. **Activity Indicator** - Show if idle detection is active
2. **Idle Time Summary** - "You had 45 min idle time today"
3. **Quick Actions** - Handle pending idle prompts

### Timer Widget Changes

```
Current Timer Display:
┌─────────────────────────────┐
│  Project ABC     02:34:15   │
│  [Stop]                     │
└─────────────────────────────┘

With Idle Detection:
┌─────────────────────────────┐
│  Project ABC     02:34:15   │
│  🟢 Active                  │
│  [Stop]                     │
└─────────────────────────────┘

When Idle Detected:
┌─────────────────────────────┐
│  Project ABC     02:34:15   │
│  ⏸️ Idle (5:32)             │
│  [Resume] [Stop]            │
└─────────────────────────────┘
```

### Admin Reports

New report: **Idle Time Analysis**
- Total idle time by user
- Idle time by project
- Average idle events per day
- Idle time kept vs. discarded ratio

---

## 🛠️ Technical Implementation Phases

### Phase 1: Browser-Based Detection (MVP)
**Timeline: 1-2 weeks**

| Task | Effort |
|------|--------|
| Frontend idle detection hook | 2 days |
| Idle prompt modal component | 1 day |
| Backend idle events API | 2 days |
| Database schema changes | 1 day |
| User settings for idle threshold | 1 day |
| Testing & bug fixes | 2 days |

### Phase 2: Enhanced Features
**Timeline: 1-2 weeks**

| Task | Effort |
|------|--------|
| Admin configuration panel | 2 days |
| Idle time reports | 3 days |
| WebSocket for real-time sync | 2 days |
| Session recovery on refresh | 2 days |
| Mobile responsiveness | 1 day |

### Phase 3: Browser Extension (Optional)
**Timeline: 2-3 weeks**

| Task | Effort |
|------|--------|
| Chrome extension development | 1 week |
| Firefox extension port | 3 days |
| Extension-to-webapp communication | 2 days |
| Extension settings sync | 2 days |
| Store submission & review | 1 week |

### Phase 4: Desktop App (Future)
**Timeline: 4-6 weeks**

| Task | Effort |
|------|--------|
| Electron/Tauri setup | 1 week |
| System tray integration | 3 days |
| Native idle detection | 3 days |
| Auto-update mechanism | 1 week |
| Code signing & distribution | 1 week |
| Platform-specific testing | 1 week |

---

## 💰 Cost-Benefit Analysis

### Development Costs

| Phase | Effort | Approximate Cost* |
|-------|--------|-------------------|
| Phase 1 (Browser MVP) | 2 weeks | $3,000 - $5,000 |
| Phase 2 (Enhanced) | 2 weeks | $3,000 - $5,000 |
| Phase 3 (Extension) | 3 weeks | $4,500 - $7,500 |
| Phase 4 (Desktop) | 6 weeks | $9,000 - $15,000 |

*Based on typical contractor rates

### Benefits

| Benefit | Impact |
|---------|--------|
| More accurate billing | +10-20% billing accuracy |
| Reduced time theft | -5-15% inflated hours |
| Better project estimates | Historical data more reliable |
| User accountability | Employees aware of tracking |
| Client trust | Verifiable work hours |

---

## 🚀 Recommendation

### Start with Phase 1: Browser-Based Detection

**Why:**
1. **Lowest effort** - 1-2 weeks to MVP
2. **No installation** - Works immediately for all users
3. **Validates demand** - See if users actually want this
4. **Foundation** - Backend APIs work for all future approaches

### Phase 1 Deliverables

1. ✅ Idle detection using DOM events
2. ✅ Configurable idle threshold (user setting)
3. ✅ Idle prompt with Keep/Discard/Reassign options
4. ✅ Idle events stored in database
5. ✅ Basic idle time summary on dashboard

### Success Metrics

| Metric | Target |
|--------|--------|
| User adoption | 50% of active users enable idle detection |
| Idle time captured | Average 30 min/day flagged for review |
| User satisfaction | <10% disable feature after trying |
| Billing accuracy | 15% reduction in disputed hours |

---

## 📚 References & Prior Art

### Similar Implementations

| Product | Approach | Notes |
|---------|----------|-------|
| **Toggl Track** | Browser + Desktop | Idle detection with prompt |
| **Clockify** | Browser extension | System-wide idle via extension |
| **Hubstaff** | Desktop app | Screenshots + activity levels |
| **RescueTime** | Desktop app | Automatic categorization |
| **Time Doctor** | Desktop app | Screenshots + idle alerts |

### Technologies to Evaluate

| Technology | Use Case |
|------------|----------|
| `Page Visibility API` | Detect tab focus/blur |
| `Beacon API` | Send data before tab close |
| `Service Workers` | Background heartbeat |
| `chrome.idle` | Extension idle detection |
| `Electron powerMonitor` | Desktop idle detection |

---

## ❓ Open Questions for User Decision

1. **Privacy level:** Should we offer screenshot capture for enterprise clients?
2. **Enforcement:** Can admins force idle detection, or always user choice?
3. **Offline handling:** What happens when user goes offline during idle?
4. **Mobile:** Should mobile app have idle detection (lock screen)?
5. **Team visibility:** Can managers see individual idle time reports?

---

## 📋 Next Steps

1. **Review this assessment** - Confirm approach alignment
2. **Decide on Phase 1 scope** - Any features to add/remove?
3. **User feedback** - Survey existing users about interest
4. **Technical spike** - Prototype browser idle detection
5. **Design mockups** - Create UI/UX designs for idle prompt

---

*Assessment Created: January 19, 2026*  
*Author: GitHub Copilot*  
*Status: 📋 ASSESSMENT COMPLETE - AWAITING DECISION*
