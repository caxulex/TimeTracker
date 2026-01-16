# Project Budget Feature - Assessment Report

**Date:** January 16, 2026  
**Status:** Pre-Implementation Assessment  
**Author:** GitHub Copilot

---

## 📋 Executive Summary

You want to add **manual project budget setup** so admins can define budgets for projects, and the existing AI "Project Budget Forecast" feature can use real data instead of the current hardcoded placeholder (`$50,000`).

### Current State
- ✅ **AI Budget Forecast Panel exists** - `ProjectBudgetPanel.tsx`
- ✅ **API endpoint exists** - `/api/ai/forecast/project-budget`
- ❌ **Project model has NO budget fields**
- ❌ **Budget is HARDCODED** to `$50,000` in `forecasting_service.py` (line 839)
- ❌ **No UI to set/edit project budgets**

---

## 🔍 Technical Analysis

### 1. Current Project Model (No Budget Fields)

**File:** [backend/app/models/__init__.py](backend/app/models/__init__.py#L276-L295)

```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int]
    team_id: Mapped[int]          # FK to Team (for multi-tenancy via Team.company_id)
    name: Mapped[str]
    description: Mapped[Optional[str]]
    color: Mapped[str]            # Hex color
    is_archived: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    
    # NO budget fields currently!
```

### 2. Current Budget Placeholder (Hardcoded)

**File:** [backend/app/ai/services/forecasting_service.py](backend/app/ai/services/forecasting_service.py#L839)

```python
# Line 839 - HARDCODED PLACEHOLDER
budget_total = Decimal("50000.00")  # Placeholder
```

### 3. Current Projects API (No Budget Support)

**File:** [backend/app/routers/projects.py](backend/app/routers/projects.py)

```python
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str]
    team_id: int
    color: Optional[str]
    # NO budget fields!

class ProjectUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    color: Optional[str]
    is_archived: Optional[bool]
    team_id: Optional[int]
    # NO budget fields!
```

### 4. Multi-Tenancy Considerations

| Model | company_id | Access Pattern |
|-------|------------|----------------|
| `Project` | ❌ No (indirect) | Via `Team.company_id` (JOIN) |
| `Team` | ✅ Yes | Direct filter |

**Important:** Projects use `Team.company_id` for multi-tenancy. The existing `check_team_access()` function already handles this.

### 5. White Labeling Impact

**No impact** - Budget is a data feature, not a branding feature.

The `WhiteLabelConfig` controls:
- App name, logo, colors
- Custom domains
- Legal links
- Email customization

Budget fields won't affect white labeling.

---

## 🎯 Proposed Implementation

### New Fields to Add to Project Model

```python
# Budget fields to add to Project model
budget_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
budget_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
budget_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
```

### Why These Fields?

| Field | Purpose | Example |
|-------|---------|---------|
| `budget_amount` | Total monetary budget | `50000.00` |
| `budget_hours` | Total hour budget (alternative to $) | `500` |
| `budget_currency` | Currency code (multi-country support) | `USD`, `EUR`, `GBP` |
| `deadline` | Project deadline for projections | `2026-06-30` |

---

## 📁 Files That Need Changes

### Backend Changes

| File | Change | Complexity |
|------|--------|------------|
| `backend/app/models/__init__.py` | Add 4 fields to `Project` | Low |
| `backend/app/routers/projects.py` | Update schemas + endpoints | Medium |
| `backend/app/ai/services/forecasting_service.py` | Use real budget data | Medium |
| `backend/alembic/versions/012_add_project_budget.py` | **New migration** | Low |

### Frontend Changes

| File | Change | Complexity |
|------|--------|------------|
| `frontend/src/pages/ProjectsPage.tsx` | Add budget fields to form | Medium |
| `frontend/src/api/client.ts` | Update Project type | Low |
| `frontend/src/types/index.ts` | Update Project interface | Low |
| `frontend/src/components/ai/ProjectBudgetPanel.tsx` | No changes (already reads budget_total) | None |

---

## ⚠️ Risk Assessment

### Low Risk ✅
1. **Backward compatible** - All new fields are nullable
2. **No data loss** - Adding columns, not removing
3. **Multi-tenancy safe** - Uses existing Team.company_id pattern
4. **White-label unaffected** - Purely data feature

### Medium Risk ⚠️
1. **Database migration required** - Must run `alembic upgrade head` after deploy
2. **Frontend form changes** - Modal will need new fields

### Mitigations
- Migration adds nullable columns (safe)
- Default values for `budget_currency` (USD)
- Frontend gracefully handles missing data (already does)

---

## 🚀 Implementation Plan

### Phase 1: Backend (Migration + Model)
1. Create Alembic migration `012_add_project_budget.py`
2. Add fields to `Project` model
3. Update `ProjectCreate` and `ProjectUpdate` schemas
4. Update project endpoints to handle budget fields

### Phase 2: Backend (AI Integration)
1. Modify `forecasting_service.py` to read real `budget_amount`
2. Handle projects without budgets (skip or use default message)

### Phase 3: Frontend
1. Update `ProjectsPage.tsx` modal with budget fields
2. Add budget display in project list/cards
3. Currency selector (USD, EUR, etc.)

### Phase 4: Testing & Deploy
1. Test locally
2. Push to git
3. Deploy via `deploy-sequential.sh`
4. Run migration: `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head`

---

## 📊 Estimated Effort

| Phase | Time | Priority |
|-------|------|----------|
| Phase 1: Backend Model/Migration | 30 min | High |
| Phase 2: AI Integration | 20 min | High |
| Phase 3: Frontend Form | 45 min | High |
| Phase 4: Testing | 15 min | High |
| **Total** | **~2 hours** | |

---

## ❓ Questions for You

Before I implement, please confirm:

1. **Currency support?**
   - Just USD? Or multi-currency (USD, EUR, GBP, etc.)?
   
2. **Budget type preference?**
   - Money only? Hours only? Or both options?
   
3. **Deadline field?**
   - Do you want a project deadline date for completion estimates?

4. **Visibility?**
   - Should regular employees see project budgets, or admin-only?

5. **Historical tracking?**
   - Do you need to track budget changes over time (audit trail)?

---

## 🎯 Recommendation

**Proceed with implementation** - This is a low-risk, high-value feature that:

1. Fixes the hardcoded `$50,000` placeholder
2. Makes AI budget forecasts actually useful
3. Adds valuable project management capability
4. No breaking changes to existing functionality

---

*Assessment Date: January 16, 2026*
