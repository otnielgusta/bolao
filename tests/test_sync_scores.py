from app.services.sync import extract_bolao_score


def match_score(score):
    return {'score': score}


def test_regular_duration_uses_full_time():
    assert extract_bolao_score(match_score({
        'duration': 'REGULAR',
        'fullTime': {'home': 2, 'away': 1},
    })) == (2, 1)


def test_penalty_shootout_uses_regular_time_when_available():
    assert extract_bolao_score(match_score({
        'duration': 'PENALTY_SHOOTOUT',
        'fullTime': {'home': 4, 'away': 5},
        'regularTime': {'home': 1, 'away': 1},
        'extraTime': {'home': 0, 'away': 0},
        'penalties': {'home': 3, 'away': 4},
    })) == (1, 1)


def test_extra_time_derives_regular_time_when_missing():
    assert extract_bolao_score(match_score({
        'duration': 'EXTRA_TIME',
        'fullTime': {'home': 3, 'away': 2},
        'regularTime': {'home': None, 'away': None},
        'extraTime': {'home': 1, 'away': 0},
    })) == (2, 2)


def test_penalty_shootout_derives_regular_time_when_missing():
    assert extract_bolao_score(match_score({
        'duration': 'PENALTY_SHOOTOUT',
        'fullTime': {'home': 5, 'away': 4},
        'extraTime': {'home': 1, 'away': 1},
        'penalties': {'home': 3, 'away': 2},
    })) == (1, 1)


def test_score_nodes_accept_documentation_key_names():
    assert extract_bolao_score(match_score({
        'duration': 'PENALTY_SHOOTOUT',
        'regularTime': {'homeTeam': 1, 'awayTeam': 1},
    })) == (1, 1)


def test_non_regular_without_breakdown_returns_none():
    assert extract_bolao_score(match_score({
        'duration': 'EXTRA_TIME',
        'fullTime': {'home': 2, 'away': 1},
    })) is None
