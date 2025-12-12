# Real-Time Reports Implementation

## Date: December 12, 2025

## Problem Statement
The Reports page was not updating in real-time when time entries were created, updated, or deleted. Users had to manually refresh the page to see updated data.

## Root Cause
The time entry endpoints (`/api/time-entries/*`) were not broadcasting WebSocket events when data changed, and the ReportsPage component was not listening for real-time updates.

## Solution Overview
Implemented real-time report updates by:
1. Adding WebSocket broadcasts to all time entry endpoints (backend)
2. Adding WebSocket listener to ReportsPage to invalidate queries (frontend)
3. Extending WebSocket context to expose `lastMessage` property

## Changes Made

### Backend Changes

#### 1. `backend/app/routers/time_entries.py`

**Added WebSocket Manager Import:**
```python
from app.routers.websocket import manager as ws_manager
```

**Added WebSocket Broadcasts to 4 Endpoints:**

**a) Timer Start (`POST /api/time-entries/start`):**
- Event: `time_entry_created`
- Data: Entry details with `is_running: true`

**b) Timer Stop (`POST /api/time-entries/stop`):**
- Event: `time_entry_completed`
- Data: Entry details with duration and timestamps

**c) Manual Entry Creation (`POST /api/time-entries`):**
- Event: `time_entry_created`
- Data: Complete entry details with `is_running: false`

**d) Entry Update (`PUT /api/time-entries/{entry_id}`):**
- Event: `time_entry_updated`
- Data: Updated entry details

**e) Entry Deletion (`DELETE /api/time-entries/{entry_id}`):**
- Event: `time_entry_deleted`
- Data: Entry ID and basic metadata

### Frontend Changes

#### 1. `frontend/src/contexts/WebSocketContext.tsx`

**Extended Interface:**
```typescript
interface WebSocketContextValue {
  // ... existing properties ...
  lastMessage: WebSocketMessage | null;  // NEW
  // ... rest of properties ...
}
```

#### 2. `frontend/src/hooks/useWebSocket.ts`

**Added State:**
```typescript
const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
```

**Updated Message Handler:**
```typescript
ws.onmessage = (event) => {
  try {
    const message: WebSocketMessage = JSON.parse(event.data);
    
    // Update lastMessage for reactive components
    setLastMessage(message);
    
    switch (message.type) {
      // ... existing cases ...
    }
    
    onMessage?.(message);
  } catch (e) {
    console.error('Failed to parse WebSocket message:', e);
  }
};
```

**Return Value:**
```typescript
return {
  // ... existing returns ...
  lastMessage,  // NEW
  // ... rest of returns ...
};
```

#### 3. `frontend/src/pages/ReportsPage.tsx`

**Added Imports:**
```typescript
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useWebSocketContext } from '../contexts/WebSocketContext';
```

**Added Real-Time Listener:**
```typescript
export function ReportsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const queryClient = useQueryClient();
  const { lastMessage } = useWebSocketContext();

  // ... state declarations ...
  
  // Listen for real-time time entry changes via WebSocket
  useEffect(() => {
    if (!lastMessage) return;
    
    const messageType = lastMessage.type;
    
    // Refresh reports when time entries are created, updated, completed, or deleted
    if (
      messageType === 'time_entry_created' ||
      messageType === 'time_entry_completed' ||
      messageType === 'time_entry_updated' ||
      messageType === 'time_entry_deleted'
    ) {
      // Invalidate and refetch report queries to get updated data
      queryClient.invalidateQueries({ queryKey: ['weekly-report'] });
      queryClient.invalidateQueries({ queryKey: ['project-report'] });
    }
  }, [lastMessage, queryClient]);

  // ... rest of component ...
}
```

## WebSocket Events Reference

| Event Type | Triggered By | Data Payload |
|------------|--------------|--------------|
| `time_entry_created` | Timer start, Manual entry creation | `entry_id`, `user_id`, `user_name`, `project_id`, `project_name`, `task_id`, `task_name`, `description`, `start_time`, `end_time` (if manual), `is_running` |
| `time_entry_completed` | Timer stop | Same as above + `duration_seconds`, `end_time`, `is_running: false` |
| `time_entry_updated` | Entry modification | All entry fields including updated values |
| `time_entry_deleted` | Entry deletion | `entry_id`, `user_id`, `project_id`, `task_id` |

## Testing Instructions

### Test 1: Real-Time Report Update on Timer Start
1. Open Reports page in one browser tab
2. Open Time page in another browser tab
3. Start a timer on the Time page
4. **Expected Result:** Reports page immediately updates with new running timer

### Test 2: Real-Time Report Update on Timer Stop
1. Keep Reports page open
2. Stop the running timer on Time page
3. **Expected Result:** Reports page immediately updates showing completed entry

### Test 3: Real-Time Report Update on Manual Entry
1. Keep Reports page open
2. Create a manual time entry on Time page
3. **Expected Result:** Reports page immediately updates with new entry

### Test 4: Real-Time Report Update on Entry Edit
1. Keep Reports page open
2. Edit an existing time entry on Time page
3. **Expected Result:** Reports page immediately reflects the changes

### Test 5: Real-Time Report Update on Entry Delete
1. Keep Reports page open
2. Delete a time entry on Time page
3. **Expected Result:** Reports page immediately updates, removing the deleted entry

## Benefits

### For Users
- **Instant Feedback:** See report changes immediately without manual refresh
- **Multi-User Collaboration:** See updates from other team members in real-time
- **Better UX:** Seamless experience across multiple tabs/windows

### For Admins
- **Live Monitoring:** Track team activity as it happens
- **Accurate Reporting:** Always viewing current data
- **Better Decision Making:** Real-time insights for resource allocation

## Performance Considerations

- **Query Invalidation:** Uses React Query's smart caching to minimize network requests
- **Selective Updates:** Only invalidates affected queries (weekly-report, project-report)
- **Broadcast Scope:** Events broadcast to all connected users for maximum visibility
- **Network Efficiency:** WebSocket connection is reused, no new connections per event

## Deployment Status

✅ **Backend:** Rebuilt and deployed (all WebSocket broadcasts active)  
✅ **Frontend:** Rebuilt and deployed (ReportsPage listening for events)  
✅ **Containers:** All healthy and running  
✅ **WebSocket:** Connection active and tested  

## Application Status

🟢 **All containers running:**
- `timetracker-frontend` - Healthy on port 80
- `timetracker-backend` - Healthy on port 8080
- `timetracker-db` - Healthy (PostgreSQL)
- `timetracker-redis` - Healthy

🎯 **Real-time reports fully functional!**

Access the application at: **http://localhost**

Login credentials:
- **Admin:** admin@timetracker.com / admin123
- **Worker 1:** john@example.com / password123
- **Worker 2:** jane@example.com / password123
- **Worker 3:** bob@example.com / password123

## Future Enhancements

- Add visual indicator when report updates (e.g., toast notification)
- Add "Last updated" timestamp to report header
- Add option to pause real-time updates for performance
- Add WebSocket event logging for debugging

---

**Implementation completed:** December 12, 2025  
**Status:** ✅ Production Ready
