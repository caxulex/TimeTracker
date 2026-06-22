from datetime import date, timedelta
import uuid

import pytest

from app.ai.services.team_analytics_service import CollaborationEdge, TeamAnalyticsService, TeamVelocity
from app.models import Project, Team, TeamMember, TimeEntry, User
from app.utils.timewindow import now_utc


def _velocity_point(total_hours: float) -> TeamVelocity:
    return TeamVelocity(
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        total_hours=total_hours,
        hours_per_member=0,
        tasks_completed=0,
        projects_active=0,
        avg_task_duration_hours=0,
        velocity_trend="stable",
        change_percent=0,
    )


def test_compute_measurability_flags_thin_data() -> None:
    flags = TeamAnalyticsService._compute_measurability_flags(
        velocity_history=[_velocity_point(12.0)],
        active_members=1,
        task_count=0,
    )

    velocity_measured, collaboration_measured, workload_balance_measured, task_tracking_measured = flags

    assert velocity_measured is False
    assert collaboration_measured is False
    assert workload_balance_measured is False
    assert task_tracking_measured is False


def test_compute_measurability_flags_measured_data() -> None:
    flags = TeamAnalyticsService._compute_measurability_flags(
        velocity_history=[_velocity_point(12.0), _velocity_point(8.0)],
        active_members=2,
        task_count=5,
    )

    velocity_measured, collaboration_measured, workload_balance_measured, task_tracking_measured = flags

    assert velocity_measured is True
    assert collaboration_measured is True
    assert workload_balance_measured is True
    assert task_tracking_measured is True


def test_determine_current_velocity_trend_uses_not_measured_sentinel_when_unmeasured() -> None:
    trend = TeamAnalyticsService._determine_current_velocity_trend(
        velocity_history=[_velocity_point(12.0)],
        velocity_measured=False,
    )

    assert trend == "not_measured"


def test_determine_current_velocity_trend_returns_real_label_when_measured() -> None:
    trend = TeamAnalyticsService._determine_current_velocity_trend(
        velocity_history=[_velocity_point(10.0), _velocity_point(15.0)],
        velocity_measured=True,
    )

    assert trend == "increasing"


def test_collaboration_edge_threshold_counts_exact_point_three() -> None:
    raw_score = TeamAnalyticsService._compute_raw_interaction_score(
        shared_projects=6,
        total_unique_projects=20,
    )

    assert raw_score == pytest.approx(0.3)
    assert TeamAnalyticsService._is_collaboration_edge(raw_score) is True


def test_collaboration_edge_threshold_uses_raw_not_rounded_score() -> None:
    raw_score = TeamAnalyticsService._compute_raw_interaction_score(
        shared_projects=299,
        total_unique_projects=1000,
    )

    assert raw_score == pytest.approx(0.299)
    assert round(raw_score, 2) == 0.30
    assert TeamAnalyticsService._is_collaboration_edge(raw_score) is False


def test_compute_collaboration_density_three_members_two_boundary_edges() -> None:
    edges = [
        CollaborationEdge(
            user1_id=1,
            user1_name="Joe",
            user2_id=2,
            user2_name="Daniel",
            shared_projects=6,
            interaction_score=0.30,
            raw_interaction_score=0.30,
        ),
        CollaborationEdge(
            user1_id=1,
            user1_name="Joe",
            user2_id=3,
            user2_name="Jelry",
            shared_projects=6,
            interaction_score=0.30,
            raw_interaction_score=0.30,
        ),
        CollaborationEdge(
            user1_id=2,
            user1_name="Daniel",
            user2_id=3,
            user2_name="Jelry",
            shared_projects=2,
            interaction_score=0.10,
            raw_interaction_score=0.10,
        ),
    ]

    density = TeamAnalyticsService._compute_collaboration_density(edges, member_count=3)
    assert density == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_generate_ai_insights_respects_unmeasured_axis_flags() -> None:
    service = TeamAnalyticsService(db=None)

    insights, recommendations = await service._generate_ai_insights(
        team_name="Core Team",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0)],
        workload_gini=0.85,
        collaboration_density=0.95,
        velocity_measured=False,
        collaboration_measured=False,
        workload_balance_measured=False,
        task_tracking_measured=False,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "increasing" not in combined
    assert "decreasing" not in combined
    assert "workload is unevenly distributed" not in combined
    assert "collaboration is low" not in combined
    assert "task completion is not tracked" in combined


@pytest.mark.asyncio
async def test_generate_ai_insights_allows_axis_claims_when_measured() -> None:
    service = TeamAnalyticsService(db=None)

    decreasing_point = _velocity_point(8.0)
    decreasing_point.velocity_trend = "decreasing"

    insights, recommendations = await service._generate_ai_insights(
        team_name="Core Team",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0), decreasing_point],
        workload_gini=0.6,
        collaboration_density=0.2,
        velocity_measured=True,
        collaboration_measured=True,
        workload_balance_measured=True,
        task_tracking_measured=True,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "workload is unevenly distributed" in combined
    assert "collaboration is low" in combined
    assert "logged hours have been decreasing recently" in combined
    assert "task completion is not tracked" not in combined


@pytest.mark.asyncio
async def test_generate_ai_insights_avoids_silos_claim_with_visible_pair_sharing() -> None:
    service = TeamAnalyticsService(db=None)
    edges = [
        CollaborationEdge(
            user1_id=1,
            user1_name="Joe",
            user2_id=2,
            user2_name="Daniel",
            shared_projects=2,
            interaction_score=0.10,
            raw_interaction_score=0.10,
        )
    ]

    insights, recommendations = await service._generate_ai_insights(
        team_name="Development",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0)],
        workload_gini=0.2,
        collaboration_density=0.0,
        collaboration_edges=edges,
        velocity_measured=True,
        collaboration_measured=True,
        workload_balance_measured=True,
        task_tracking_measured=True,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "working in silos" not in combined
    assert "encourage pair programming" not in combined
    assert "visible pair-level project sharing" in combined


@pytest.mark.asyncio
async def test_generate_ai_insights_keeps_silos_claim_when_no_meaningful_pair_sharing() -> None:
    service = TeamAnalyticsService(db=None)
    edges = [
        CollaborationEdge(
            user1_id=1,
            user1_name="Joe",
            user2_id=2,
            user2_name="Daniel",
            shared_projects=1,
            interaction_score=0.05,
            raw_interaction_score=0.05,
        )
    ]

    insights, recommendations = await service._generate_ai_insights(
        team_name="Development",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0)],
        workload_gini=0.2,
        collaboration_density=0.0,
        collaboration_edges=edges,
        velocity_measured=True,
        collaboration_measured=True,
        workload_balance_measured=True,
        task_tracking_measured=True,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "working in silos" in combined
    assert "encourage pair programming" in combined


def _compute_old_unscoped_density(project_sets: dict[int, set[str]]) -> float:
    member_ids = sorted(project_sets.keys())
    max_edges = len(member_ids) * (len(member_ids) - 1) / 2
    if max_edges == 0:
        return 0.0

    qualifying_edges = 0
    for i, user1 in enumerate(member_ids):
        for user2 in member_ids[i + 1:]:
            shared = project_sets[user1] & project_sets[user2]
            union = project_sets[user1] | project_sets[user2]
            raw_score = TeamAnalyticsService._compute_raw_interaction_score(
                shared_projects=len(shared),
                total_unique_projects=len(union),
            )
            if TeamAnalyticsService._is_collaboration_edge(raw_score):
                qualifying_edges += 1
    return qualifying_edges / max_edges


@pytest.mark.asyncio
async def test_generate_team_report_scopes_collaboration_to_report_team(db_session) -> None:
    service = TeamAnalyticsService(db=db_session)

    users = []
    for idx in range(4):
        user = User(
            email=f"collab-team-scope-{idx}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="test-hash",
            name=f"Member {idx + 1}",
            role="regular_user",
            is_active=True,
        )
        db_session.add(user)
        users.append(user)

    await db_session.flush()

    report_team = Team(name="Development", owner_id=users[0].id)
    other_team = Team(name="Other Team", owner_id=users[0].id)
    db_session.add_all([report_team, other_team])
    await db_session.flush()

    db_session.add_all(
        [
            TeamMember(team_id=report_team.id, user_id=user.id, role="member")
            for user in users
        ]
    )
    await db_session.flush()

    report_projects = {}
    for idx in range(1, 12):
        project = Project(team_id=report_team.id, name=f"report-p{idx}")
        db_session.add(project)
        report_projects[f"r{idx}"] = project

    other_projects = {}
    for idx in range(1, 27):
        project = Project(team_id=other_team.id, name=f"other-p{idx}")
        db_session.add(project)
        other_projects[f"o{idx}"] = project

    await db_session.flush()

    period_time = now_utc() - timedelta(days=2)

    user_report_project_keys = {
        users[0].id: {"r1", "r2", "r3", "r4", "r5", "r6"},
        users[1].id: {"r1", "r2", "r3", "r4", "r5", "r6"},
        users[2].id: {"r7", "r8"},
        users[3].id: {"r7", "r8", "r9", "r10", "r11"},
    }

    user_other_project_keys = {
        users[0].id: {"o1", "o2", "o3", "o4", "o5", "o6", "o7", "o8", "o9", "o10", "o11", "o23", "o24"},
        users[1].id: {"o12", "o13", "o14", "o15", "o16", "o17", "o18", "o19", "o20", "o21", "o22"},
        users[2].id: {"o23", "o24", "o25", "o26"},
        users[3].id: {"o19", "o20"},
    }

    for user in users:
        for project_key in user_report_project_keys[user.id]:
            project = report_projects[project_key]
            db_session.add(
                TimeEntry(
                    user_id=user.id,
                    project_id=project.id,
                    start_time=period_time,
                    end_time=period_time + timedelta(hours=1),
                    duration_seconds=3600,
                    description=f"report:{project_key}",
                    is_running=False,
                )
            )
        for project_key in user_other_project_keys[user.id]:
            project = other_projects[project_key]
            db_session.add(
                TimeEntry(
                    user_id=user.id,
                    project_id=project.id,
                    start_time=period_time,
                    end_time=period_time + timedelta(hours=1),
                    duration_seconds=3600,
                    description=f"other:{project_key}",
                    is_running=False,
                )
            )

    await db_session.commit()

    old_unscoped_sets = {
        user.id: user_report_project_keys[user.id] | user_other_project_keys[user.id]
        for user in users
    }
    old_unscoped_density = _compute_old_unscoped_density(old_unscoped_sets)
    assert old_unscoped_density == pytest.approx(0.0)

    report = await service.generate_team_report(
        team_id=report_team.id,
        period_days=30,
        include_ai_insights=True,
    )

    assert report.collaboration_density == pytest.approx(0.33, abs=0.01)
    assert report.collaboration_density > 0

    qualifying_edges = [
        edge for edge in report.collaboration_edges
        if TeamAnalyticsService._is_collaboration_edge(edge.raw_interaction_score)
    ]
    assert len(qualifying_edges) == 2
    assert any(edge.raw_interaction_score < 0.3 for edge in report.collaboration_edges)

    user1_id = users[0].id
    user3_id = users[2].id
    cross_team_only_pair = next(
        edge
        for edge in report.collaboration_edges
        if {edge.user1_id, edge.user2_id} == {user1_id, user3_id}
    )
    assert cross_team_only_pair.shared_projects == 0
    assert cross_team_only_pair.raw_interaction_score == pytest.approx(0.0)

    combined = " ".join(report.ai_insights + report.recommendations).lower()
    assert "working in silos" not in combined
    assert "encourage pair programming" not in combined
