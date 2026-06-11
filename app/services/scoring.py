def calculate_points(
    predicted_home: int,
    predicted_away: int,
    real_home: int,
    real_away: int,
) -> int:
    exact = predicted_home == real_home and predicted_away == real_away
    if exact:
        return 10

    pred_diff = predicted_home - predicted_away
    real_diff = real_home - real_away

    pred_sign = (1 if pred_diff > 0 else (-1 if pred_diff < 0 else 0))
    real_sign = (1 if real_diff > 0 else (-1 if real_diff < 0 else 0))
    correct_winner = pred_sign == real_sign

    correct_diff = pred_diff == real_diff
    one_team = predicted_home == real_home or predicted_away == real_away

    if correct_winner and correct_diff:
        return 7
    if correct_winner and one_team:
        return 5
    if correct_winner:
        return 3
    if one_team:
        return 1
    return 0
