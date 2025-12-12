# Quick Access Guide - Admin Reports

## Accessing the Feature

1. **Login** as admin user:
   - Email: `admin@timetracker.com`
   - Password: `admin123`

2. **Navigate** to Admin Reports:
   - Open sidebar
   - Expand "Analytics" section (purple icon)
   - Click "Admin Reports"

## What You'll See

### Overview Tab
- **System Metrics:** Total hours today (23.5h), this week (156.8h), this month (687.3h)
- **Activity:** 3 active users today, 2 running timers, 11 active projects
- **Top Performers Chart:** Bar chart showing who's working the most today
- **Time Distribution Pie:** Visual breakdown of time by user

### Teams Tab
- **Comparison Chart:** Side-by-side team performance bars
- **Team Cards:** Each team shows:
  - Member count (e.g., "4 members")
  - Hours today/week/month
  - Active members and running timers
  - Top 3 performers with hours

### Individuals Tab
- **Period Selector:** Switch between Today/Week/Month
- **Performance Chart:** Horizontal bar chart ranking all users
- **User Table:** Detailed breakdown with:
  - Rank (🏆 for top 3)
  - Name
  - Hours worked
  - Entry count
  - Average hours per entry
  - **"View Details →"** button

## Drill-Down View

Click "View Details" on any user to see:

1. **User Header:**
   - Name, email, role
   - Team memberships (tags)
   - Timer status (✅ Running / ❌ Inactive)
   - Last activity timestamp

2. **Key Metrics Cards:**
   - Today: 2.5h
   - This Week: 18.3h
   - This Month: 82.7h
   - Avg Hours/Day: 4.1h (20 active days)

3. **Project Distribution:**
   - Bar chart by project
   - Pie chart showing allocation
   - Table with hours and entries per project

## Real-Time Features

- **Auto-refresh:** Data updates every 30 seconds
- **Live timers:** Active timer hours update in real-time
- **Instant navigation:** Fast switching between views
- **Responsive charts:** Interactive tooltips and legends

## Key Insights You Can Get

✅ **Who's working right now?** (Running Timers count)
✅ **Who are the top performers?** (Rankings and charts)
✅ **How productive is each team?** (Team comparison)
✅ **What projects is someone working on?** (Individual breakdown)
✅ **Who hasn't logged time recently?** (Last activity tracking)
✅ **What's the average productivity?** (Avg hours per day per user)

## Tips

- **Use the period selector** in Individuals tab to compare daily/weekly/monthly performance
- **Click team names** to identify members quickly
- **Check "Running Timers"** to see who's actively working
- **Review "Active Days"** in user details to spot attendance patterns
- **Compare projects** in drill-down view to see work distribution

## Navigation

- **Back to Reports:** Click "← Back to Admin Reports" in user detail view
- **Quick Access:** Analytics menu always visible in sidebar for admins
- **Home:** Click "TimeTracker" logo to return to dashboard

## Example Use Cases

1. **Daily Standup:** Check Overview tab to see who's active today
2. **Performance Review:** Use Individuals tab (Month view) for comprehensive stats
3. **Team Management:** Teams tab shows which teams need attention
4. **Project Planning:** User detail view shows project time allocation
5. **Payroll Prep:** Export data shows hours worked per person per period

## Troubleshooting

- **No data showing?** Make sure users have logged time entries
- **Can't see the menu?** Only admins and super_admins can access
- **Charts not loading?** Check that backend is running (http://localhost:8080/health)
- **Data seems old?** Wait for 30-second auto-refresh or manually reload page

Enjoy your awesome admin reports! 🎉
