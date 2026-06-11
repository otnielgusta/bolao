from app.services.scoring import calculate_points


def test_exact_score():
    assert calculate_points(2, 1, 2, 1) == 10
    assert calculate_points(0, 0, 0, 0) == 10
    assert calculate_points(3, 3, 3, 3) == 10


def test_correct_winner_and_goal_difference():
    # Home wins by 1, but different scores
    assert calculate_points(3, 2, 2, 1) == 7
    # Away wins by 2
    assert calculate_points(0, 2, 1, 3) == 7
    # Draw but different scores
    assert calculate_points(1, 1, 2, 2) == 7


def test_correct_winner_and_one_team_goals():
    # Home wins, home goals correct
    assert calculate_points(2, 0, 2, 1) == 5
    # Home wins, away goals correct
    assert calculate_points(3, 1, 2, 1) == 5
    # Away wins, away goals correct
    assert calculate_points(0, 3, 1, 3) == 5


def test_correct_winner_only():
    # Home wins, no other match
    assert calculate_points(3, 1, 1, 0) == 3
    # Away wins, no other match
    assert calculate_points(0, 4, 1, 2) == 3


def test_wrong_winner_but_one_team_goals():
    # Predicted home win, actually away win, but away goals match
    assert calculate_points(2, 1, 0, 1) == 1
    # Predicted draw, actually home win, but home goals match
    assert calculate_points(1, 1, 1, 0) == 1


def test_zero_points():
    assert calculate_points(3, 0, 0, 2) == 0
    assert calculate_points(1, 0, 0, 3) == 0


def test_edge_cases():
    # 0-0 exact
    assert calculate_points(0, 0, 0, 0) == 10
    # Large score exact
    assert calculate_points(7, 1, 7, 1) == 10
    # Predicted draw 0-0, actual draw 1-1 -> correct winner(draw) + correct diff(0) = 7
    assert calculate_points(0, 0, 1, 1) == 7
    # Predicted 1-0, actual 0-1 -> wrong winner, one team? pred_home=1!=0, pred_away=0!=1 -> 0
    assert calculate_points(1, 0, 0, 1) == 0
