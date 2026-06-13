import datetime as dt

from app.models import Match, Pool, Prediction, User
from app.routers.pools import (
    _can_view_match_predictions,
    _match_predictions_copy_text,
)


UTC = dt.timezone.utc


def make_match(**overrides) -> Match:
    data = {
        "id": 1,
        "home_team": "BRA",
        "away_team": "MAR",
        "match_datetime": dt.datetime(2026, 6, 13, 22, 0, tzinfo=UTC),
        "stage": "Grupo C",
        "home_score": None,
        "away_score": None,
        "is_finished": False,
    }
    data.update(overrides)
    return Match(**data)


def make_prediction(points_awarded: int | None = None) -> Prediction:
    user = User(id=1, email="ana@example.com", display_name="Ana")
    return Prediction(
        user_id=1,
        pool_id=1,
        match_id=1,
        predicted_home=2,
        predicted_away=1,
        points_awarded=points_awarded,
        user=user,
    )


def test_predictions_hidden_before_deadline_when_pool_disables_visibility():
    pool = Pool(id=1, name="Teste", owner_id=1, show_predictions_before_deadline=False)
    match = make_match()

    can_view = _can_view_match_predictions(
        pool,
        match,
        dt.datetime(2026, 6, 13, 21, 0, tzinfo=UTC),
    )
    text = _match_predictions_copy_text(
        pool,
        match,
        [make_prediction()],
        visible=can_view,
    )

    assert can_view is False
    assert "ocultos" in text
    assert "Ana: 2 x 1" not in text


def test_predictions_visible_after_deadline_when_pool_disables_visibility():
    pool = Pool(id=1, name="Teste", owner_id=1, show_predictions_before_deadline=False)
    match = make_match()

    can_view = _can_view_match_predictions(
        pool,
        match,
        dt.datetime(2026, 6, 13, 21, 56, tzinfo=UTC),
    )
    text = _match_predictions_copy_text(
        pool,
        match,
        [make_prediction()],
        visible=can_view,
    )

    assert can_view is True
    assert "Ana: 2 x 1" in text


def test_finished_match_copy_includes_result_and_points():
    pool = Pool(id=1, name="Teste", owner_id=1, show_predictions_before_deadline=False)
    match = make_match(
        is_finished=True,
        home_score=2,
        away_score=1,
    )

    text = _match_predictions_copy_text(
        pool,
        match,
        [make_prediction(points_awarded=10)],
    )

    assert "Resultado saiu" in text
    assert "BRA 2 x 1 MAR" in text
    assert "Ana: 2 x 1 (+10 pts)" in text
