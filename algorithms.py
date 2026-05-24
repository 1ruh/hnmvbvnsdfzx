from collections import Counter, defaultdict
import math

TOTAL_TILES = 25
GRID_SIZE = 5

TOWER_ROWS = 8
TOWER_COLS = 3
TOWER_TOTAL = TOWER_ROWS * TOWER_COLS

# ─── Utilities ────────────────────────────────────────────────────────────────

def _get_mine_locations(round_data):
    locs = round_data.get('mineLocations', [])
    if not locs:
        locs = round_data.get('bombLocations', [])
    if not locs:
        locs = round_data.get('mines', [])
    return locs

def _tile_to_row_col(tile):
    return divmod(tile, GRID_SIZE)

def _euclidean_dist(t1, t2):
    r1, c1 = _tile_to_row_col(t1)
    r2, c2 = _tile_to_row_col(t2)
    return math.sqrt((r1 - r2) ** 2 + (c1 - c2) ** 2)

def _manhattan_dist(t1, t2):
    r1, c1 = _tile_to_row_col(t1)
    r2, c2 = _tile_to_row_col(t2)
    return abs(r1 - r2) + abs(c1 - c2)

def _neighbors(tile):
    r, c = _tile_to_row_col(tile)
    result = []
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
            result.append(nr * GRID_SIZE + nc)
    return result

def _diagonal_neighbors(tile):
    r, c = _tile_to_row_col(tile)
    result = []
    for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
            result.append(nr * GRID_SIZE + nc)
    return result

def _all_neighbors(tile):
    return _neighbors(tile) + _diagonal_neighbors(tile)

def _zones():
    return [
        [0,1,2,3,4],
        [5,6,7,8,9],
        [10,11,12,13,14],
        [15,16,17,18,19],
        [20,21,22,23,24],
        [0,5,10,15,20],
        [1,6,11,16,21],
        [2,7,12,17,22],
        [3,8,13,18,23],
        [4,9,14,19,24],
        [0,1,5,6],
        [3,4,8,9],
        [15,16,20,21],
        [18,19,23,24],
        [6,7,8,11,12,13,16,17,18],
    ]

_ZONES = _zones()

def _exponential_weight(i, decay=0.85):
    return decay ** i

# ─── Mines: Strategy 1 — Exponential Decay Frequency ─────────────────────────

def exponential_frequency(history, count, prediction_history=None):
    scores = [0.0] * TOTAL_TILES
    total_weight = 0.0

    for i, game in enumerate(reversed(history)):
        locs = _get_mine_locations(game)
        if not locs:
            continue
        weight = _exponential_weight(i, 0.82)
        total_weight += weight
        for loc in locs:
            if 0 <= loc < TOTAL_TILES:
                scores[loc] -= weight

    if total_weight > 0:
        for i in range(TOTAL_TILES):
            scores[i] /= total_weight

    indexed = sorted(
        enumerate(scores), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


# ─── Mines: Strategy 2 — Density Heatmap ─────────────────────────────────────

def density_heatmap(history, count, prediction_history=None):
    heat = [0.0] * TOTAL_TILES
    game_count = 0

    for game in history:
        locs = _get_mine_locations(game)
        locs = [l for l in locs if 0 <= l < TOTAL_TILES]
        if not locs:
            continue
        game_count += 1
        for loc in locs:
            heat[loc] += 1.0
            for n in _all_neighbors(loc):
                heat[n] += 0.35
            for n in _neighbors(loc):
                heat[n] += 0.15

    if game_count == 0:
        return list(range(count))

    avg_mine = sum(heat) / TOTAL_TILES

    for game in history:
        locs = _get_mine_locations(game)
        locs = [l for l in locs if 0 <= l < TOTAL_TILES]
        if len(locs) < 2:
            continue
        for i in range(len(locs)):
            for j in range(i + 1, len(locs)):
                d = _manhattan_dist(locs[i], locs[j])
                if d <= 1:
                    for n in _all_neighbors(locs[i]):
                        heat[n] += 0.2
                    for n in _all_neighbors(locs[j]):
                        heat[n] += 0.2

    scores = [avg_mine - h for h in heat]
    indexed = sorted(
        enumerate(scores), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


# ─── Mines: Strategy 3 — Zone Distribution ───────────────────────────────────

def zone_analysis(history, count, prediction_history=None):
    zone_mine_counts = [0] * len(_ZONES)
    zone_total_games = [0] * len(_ZONES)

    for game in history:
        locs = _get_mine_locations(game)
        locs = {l for l in locs if 0 <= l < TOTAL_TILES}
        if not locs:
            continue
        for zi, zone in enumerate(_ZONES):
            zone_total_games[zi] += 1
            mine_in_zone = sum(1 for t in zone if t in locs)
            zone_mine_counts[zi] += mine_in_zone

    tile_scores = [0.0] * TOTAL_TILES
    for zi, zone in enumerate(_ZONES):
        if zone_total_games[zi] == 0:
            continue
        avg_mines_per_game = zone_mine_counts[zi] / zone_total_games[zi]
        zone_size = len(zone)
        expected_rate = avg_mines_per_game / zone_size if zone_size else 0
        for tile in zone:
            tile_scores[tile] -= expected_rate * 2.0

    indexed = sorted(
        enumerate(tile_scores), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


# ─── Mines: Strategy 4 — Regression to Mean ──────────────────────────────────

def regression_to_mean(history, count, prediction_history=None):
    if not history:
        return list(range(count))

    mine_hits = [0] * TOTAL_TILES
    safe_hits = [0] * TOTAL_TILES

    for game in history:
        locs = _get_mine_locations(game)
        locs = {l for l in locs if 0 <= l < TOTAL_TILES}
        for tile in range(TOTAL_TILES):
            if tile in locs:
                mine_hits[tile] += 1
            else:
                safe_hits[tile] += 1

    total_games = len(history)
    global_mine_rate = sum(mine_hits) / (total_games * TOTAL_TILES) if total_games else 0.25
    expected_mines_per_tile = global_mine_rate * total_games

    scores = [0.0] * TOTAL_TILES
    for tile in range(TOTAL_TILES):
        observed = mine_hits[tile]
        deviation = observed - expected_mines_per_tile
        scores[tile] = -deviation

    indexed = sorted(
        enumerate(scores), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


# ─── Mines: Strategy 5 — Consecutive Safe Run Detector ───────────────────────

def consecutive_safe_detector(history, count, prediction_history=None):
    if not history:
        return list(range(count))

    last_mine_round = [-1] * TOTAL_TILES

    for gi, game in enumerate(history):
        locs = _get_mine_locations(game)
        locs = {l for l in locs if 0 <= l < TOTAL_TILES}
        for tile in locs:
            last_mine_round[tile] = gi

    total_games = len(history)
    scores = [0.0] * TOTAL_TILES

    for tile in range(TOTAL_TILES):
        rounds_since_mine = total_games - 1 - last_mine_round[tile]
        if last_mine_round[tile] == -1:
            rounds_since_mine = total_games
        if rounds_since_mine >= 3:
            scores[tile] = rounds_since_mine * 0.5

    indexed = sorted(
        enumerate(scores), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


# ─── Mines: Ensemble ─────────────────────────────────────────────────────────

def _score_strategy_on_history(strategy_fn, history, count, prediction_history):
    if len(history) < 3:
        return 0.5
    correct = 0
    total = 0
    for test_idx in range(max(1, len(history) - 5), len(history)):
        train = history[:test_idx]
        actual = history[test_idx]
        actual_mines = set(_get_mine_locations(actual))
        try:
            pred = set(strategy_fn(train, count, prediction_history))
            total += count
            correct += count - len(actual_mines & pred)
        except Exception:
            pass
    return correct / total if total > 0 else 0.5


def vain_algo(history, count, prediction_history=None):
    raw_strategies = [
        ("freq", exponential_frequency, 0.25),
        ("density", density_heatmap, 0.20),
        ("zone", zone_analysis, 0.20),
        ("regression", regression_to_mean, 0.20),
        ("run", consecutive_safe_detector, 0.15),
    ]

    performances = {}
    for name, fn, _ in raw_strategies:
        try:
            perf = _score_strategy_on_history(fn, history, count, prediction_history)
            performances[name] = perf
        except Exception:
            performances[name] = 0.5

    total_perf = sum(performances.values())
    if total_perf == 0:
        total_perf = 1

    strategies = []
    for name, fn, base_weight in raw_strategies:
        dynamic_weight = base_weight * (performances[name] / total_perf * len(raw_strategies))
        strategies.append((fn, dynamic_weight))

    votes = [0.0] * TOTAL_TILES

    for strategy_fn, weight in strategies:
        try:
            result = strategy_fn(history, count, prediction_history)
            for idx, tile in enumerate(result):
                votes[tile] += weight * (count - idx)
        except Exception:
            pass

    if prediction_history:
        recently_safe = set()
        for round_data in prediction_history[:3]:
            locs = round_data.get('mineLocations', [])
            locs = [l for l in locs if 0 <= l < TOTAL_TILES]
            for tile in range(TOTAL_TILES):
                if tile not in locs:
                    recently_safe.add(tile)
        for tile in recently_safe:
            votes[tile] -= 2.5
        recently_mined = set()
        for round_data in prediction_history[:2]:
            locs = round_data.get('mineLocations', [])
            for l in locs:
                if 0 <= l < TOTAL_TILES:
                    recently_mined.add(l)
        for tile in recently_mined:
            for n in _neighbors(tile) + _diagonal_neighbors(tile):
                votes[n] += 0.3

    indexed = sorted(
        enumerate(votes), key=lambda x: (x[1], x[0]), reverse=True
    )
    return [idx for idx, _ in indexed[:count]]


def past_games(history, count):
    board = [0] * TOTAL_TILES
    for game in history:
        locs = _get_mine_locations(game)
        for loc in locs:
            if 0 <= loc < TOTAL_TILES and board[loc] == 0:
                board[loc] = 1
                if sum(board) >= count:
                    break
        if sum(board) >= count:
            break
    return [i for i in range(TOTAL_TILES) if board[i] == 1][:count]


# ─── Towers Algorithms ───────────────────────────────────────────────────────

def _find_nested_list(obj, depth=0):
    if depth > 5:
        return None
    if isinstance(obj, list):
        if len(obj) == TOWER_ROWS and all(isinstance(r, (list, tuple)) and len(r) >= TOWER_COLS for r in obj):
            return obj
        if len(obj) == TOWER_TOTAL and all(not isinstance(v, (list, tuple)) for v in obj):
            return obj
        if len(obj) > 0 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in obj):
            return obj
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_nested_list(v, depth + 1)
            if found is not None:
                return found
    return None


def parse_tower_rows(history):
    rows = []
    if not isinstance(history, list):
        return rows
    for game in history:
        if not isinstance(game, dict):
            continue
        found = None
        for key in ('tiles', 'bombPositions', 'grid', 'board', 'rows', 'data', 'mineLocations', 'tower_tiles', 'positions', 'bombIndices', 'bombLocations', 'bombs'):
            raw = game.get(key)
            if isinstance(raw, list) and len(raw) >= 3:
                found = raw
                break
        if found is None:
            found = _find_nested_list(game)
        if found is None:
            revealed = game.get('revealed') or game.get('uncoveredLocations') or game.get('safeTiles')
            bombs = game.get('bombIndices') or game.get('bombLocations') or game.get('bombs') or game.get('mineLocations')
            if isinstance(revealed, list) and isinstance(bombs, list):
                grid_flat = [0] * TOWER_TOTAL
                for loc in bombs:
                    if isinstance(loc, (int, float)) and 0 <= int(loc) < TOWER_TOTAL:
                        grid_flat[int(loc)] = 1
                for loc in revealed:
                    if isinstance(loc, (int, float)) and 0 <= int(loc) < TOWER_TOTAL:
                        if grid_flat[int(loc)] != 1:
                            grid_flat[int(loc)] = 0
                for ri in range(TOWER_ROWS):
                    start = ri * TOWER_COLS
                    rows.append(grid_flat[start:start + TOWER_COLS])
                continue
        if found is None:
            continue
        if len(found) == TOWER_ROWS and all(isinstance(r, (list, tuple)) and len(r) >= TOWER_COLS for r in found):
            for r in found[:TOWER_ROWS]:
                row_p = []
                for x in r[:TOWER_COLS]:
                    try:
                        row_p.append(1 if int(x) == 1 else 0)
                    except (ValueError, TypeError):
                        row_p.append(0)
                rows.append(row_p)
        elif len(found) >= TOWER_TOTAL and all(not isinstance(v, (list, tuple)) for v in found[:TOWER_TOTAL]):
            for ri in range(TOWER_ROWS):
                start = ri * TOWER_COLS
                row_p = []
                for c in range(TOWER_COLS):
                    try:
                        row_p.append(1 if int(found[start + c]) == 1 else 0)
                    except (ValueError, TypeError, IndexError):
                        row_p.append(0)
                rows.append(row_p)
        elif len(found) > 0 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in found):
            grid_flat = [0] * TOWER_TOTAL
            for loc in found:
                loc_i = int(loc)
                if 0 <= loc_i < TOWER_TOTAL:
                    grid_flat[loc_i] = 1
            for ri in range(TOWER_ROWS):
                start = ri * TOWER_COLS
                rows.append(grid_flat[start:start + TOWER_COLS])
    return rows


def _get_full_games(history):
    rows = parse_tower_rows(history)
    games = []
    for i in range(0, len(rows), TOWER_ROWS):
        if i + TOWER_ROWS <= len(rows):
            games.append(rows[i:i + TOWER_ROWS])
    return games


def tower_frequency(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [row_i * TOWER_COLS + ((row_i * 2) % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    scores = [[0.0] * TOWER_COLS for _ in range(TOWER_ROWS)]

    for gi, game in enumerate(games):
        weight = _exponential_weight(len(games) - 1 - gi, 0.80)
        for row_i in range(TOWER_ROWS):
            for col in range(TOWER_COLS):
                if game[row_i][col] == 0:
                    scores[row_i][col] += weight

    result = []
    for row_i in range(TOWER_ROWS):
        best = max(
            range(TOWER_COLS),
            key=lambda c: (scores[row_i][c], c)
        )
        result.append(row_i * TOWER_COLS + best)
    return result


def tower_transition(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [row_i * TOWER_COLS + (row_i % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    transition = [
        [[0] * TOWER_COLS for _ in range(TOWER_COLS)]
        for _ in range(TOWER_ROWS)
    ]

    for gi, game in enumerate(games):
        weight = _exponential_weight(len(games) - 1 - gi, 0.85)
        for row_i in range(TOWER_ROWS - 1):
            try:
                bomb_col = game[row_i].index(1)
                for safe_col in range(TOWER_COLS):
                    if game[row_i + 1][safe_col] == 0:
                        transition[row_i + 1][bomb_col][safe_col] += weight
            except ValueError:
                pass

    freq = tower_frequency(history)
    result = []
    for row_i in range(TOWER_ROWS):
        scores = [0.0] * TOWER_COLS
        for bomb_col in range(TOWER_COLS):
            for safe_col in range(TOWER_COLS):
                scores[safe_col] += transition[row_i][bomb_col][safe_col]
        if any(s > 0 for s in scores):
            best = max(range(TOWER_COLS), key=lambda c: (scores[c], c))
        else:
            best = freq[row_i] % TOWER_COLS
        result.append(row_i * TOWER_COLS + best)
    return result


def tower_pattern(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [row_i * TOWER_COLS + ((row_i * 3) % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    pattern_votes = [Counter() for _ in range(TOWER_ROWS)]

    for gi, game in enumerate(games):
        weight = _exponential_weight(len(games) - 1 - gi, 0.82)
        for row_i in range(TOWER_ROWS):
            for col in range(TOWER_COLS):
                if game[row_i][col] == 0:
                    pattern_votes[row_i][col] += weight

    for gi in range(len(games) - 1):
        for row_i in range(TOWER_ROWS):
            try:
                b1 = games[gi][row_i].index(1)
                b2 = games[gi + 1][row_i].index(1)
                if b1 == b2:
                    weight = _exponential_weight(len(games) - 2 - gi, 0.85)
                    for col in range(TOWER_COLS):
                        if games[gi + 1][row_i][col] == 0:
                            pattern_votes[row_i][col] += weight * 0.5
            except ValueError:
                pass

    result = []
    for row_i in range(TOWER_ROWS):
        if pattern_votes[row_i]:
            best = max(
                range(TOWER_COLS),
                key=lambda c: (pattern_votes[row_i][c], c)
            )
        else:
            best = (row_i * 3) % TOWER_COLS
        result.append(row_i * TOWER_COLS + best)
    return result


def tower_column_correlation(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [row_i * TOWER_COLS + ((row_i * 2) % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    col_pair_counts = [[0] * TOWER_COLS for _ in range(TOWER_COLS)]
    col_safe_counts = [0] * TOWER_COLS
    games_used = 0

    for gi, game in enumerate(games):
        weight = _exponential_weight(len(games) - 1 - gi, 0.82)
        games_used += 1
        col_has_bomb = [False] * TOWER_COLS
        for row_i in range(TOWER_ROWS):
            for col in range(TOWER_COLS):
                if game[row_i][col] == 1:
                    col_has_bomb[col] = True
        for col in range(TOWER_COLS):
            if not col_has_bomb[col]:
                col_safe_counts[col] += weight
        for c1 in range(TOWER_COLS):
            for c2 in range(c1 + 1, TOWER_COLS):
                if not col_has_bomb[c1] and not col_has_bomb[c2]:
                    col_pair_counts[c1][c2] += weight
                    col_pair_counts[c2][c1] += weight

    scores = [[0.0] * TOWER_COLS for _ in range(TOWER_ROWS)]
    total_safe = sum(col_safe_counts)
    if total_safe > 0:
        for col in range(TOWER_COLS):
            p_safe = col_safe_counts[col] / games_used if games_used else 0.5
            for row_i in range(TOWER_ROWS):
                scores[row_i][col] += p_safe * 2.0

    for c1 in range(TOWER_COLS):
        for c2 in range(TOWER_COLS):
            if c1 != c2 and col_pair_counts[c1][c2] > 1:
                boost = col_pair_counts[c1][c2] * 0.15
                for row_i in range(TOWER_ROWS):
                    scores[row_i][c2] += boost * 0.5

    result = []
    for row_i in range(TOWER_ROWS):
        best = max(
            range(TOWER_COLS),
            key=lambda c: (scores[row_i][c], c)
        )
        result.append(row_i * TOWER_COLS + best)
    return result


def tower_edge_analysis(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [row_i * TOWER_COLS + (row_i % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    edge_safe = [0.0, 0.0, 0.0]
    center_safe = [0.0, 0.0, 0.0]
    edge_games = 0
    center_games = 0

    for gi, game in enumerate(games):
        weight = _exponential_weight(len(games) - 1 - gi, 0.80)
        for row_i in range(TOWER_ROWS):
            for col in range(TOWER_COLS):
                if game[row_i][col] == 0:
                    if col == 1:
                        center_safe[col] += weight
                    else:
                        edge_safe[col] += weight
        edge_games += weight
        center_games += weight

    scores = [[0.0] * TOWER_COLS for _ in range(TOWER_ROWS)]
    for row_i in range(TOWER_ROWS):
        for col in range(TOWER_COLS):
            if col == 1:
                scores[row_i][col] = center_safe[col] / center_games if center_games > 0 else 0.33
            else:
                scores[row_i][col] = edge_safe[col] / edge_games if edge_games > 0 else 0.33
            scores[row_i][col] *= 3.0

    result = []
    for row_i in range(TOWER_ROWS):
        best = max(
            range(TOWER_COLS),
            key=lambda c: (scores[row_i][c], c)
        )
        result.append(row_i * TOWER_COLS + best)
    return result


def tower_pastgames(history, count=None, prediction_history=None):
    games = _get_full_games(history)
    if not games:
        return [(row_i * TOWER_COLS + (row_i * 2) % TOWER_COLS) for row_i in range(TOWER_ROWS)]

    latest = games[-1]
    result = []
    for row_i in range(TOWER_ROWS):
        safe = [c for c in range(TOWER_COLS) if latest[row_i][c] == 0]
        if safe:
            result.append(row_i * TOWER_COLS + safe[0])
        else:
            result.append(row_i * TOWER_COLS + (row_i % TOWER_COLS))
    return result


def _score_tower_strategy(strategy_fn, history):
    if len(history) < 3:
        return 0.5
    rows = parse_tower_rows(history)
    games = []
    for i in range(0, len(rows), TOWER_ROWS):
        if i + TOWER_ROWS <= len(rows):
            games.append(rows[i:i + TOWER_ROWS])
    if len(games) < 2:
        return 0.5
    correct = 0
    total = 0
    for test_idx in range(max(1, len(games) - 5), len(games)):
        train = history[:test_idx * TOWER_ROWS] if test_idx * TOWER_ROWS < len(history) else history
        actual = games[test_idx]
        try:
            pred = strategy_fn(train)
            for row_i in range(TOWER_ROWS):
                predicted_col = pred[row_i] % TOWER_COLS
                if actual[row_i][predicted_col] == 0:
                    correct += 1
                total += 1
        except Exception:
            pass
    return correct / total if total > 0 else 0.5


def tower_vain(history, count=None, prediction_history=None):
    raw_strategies = [
        ("freq", tower_frequency, 0.25),
        ("trans", tower_transition, 0.20),
        ("patt", tower_pattern, 0.20),
        ("corr", tower_column_correlation, 0.20),
        ("edge", tower_edge_analysis, 0.15),
    ]

    performances = {}
    for name, fn, _ in raw_strategies:
        try:
            perf = _score_tower_strategy(fn, history)
            performances[name] = perf
        except Exception:
            performances[name] = 0.5

    total_perf = sum(performances.values())
    if total_perf == 0:
        total_perf = 1

    strategies = []
    for name, fn, base_weight in raw_strategies:
        dynamic_weight = base_weight * (performances[name] / total_perf * len(raw_strategies))
        strategies.append((fn, dynamic_weight))

    votes = [[0.0] * TOWER_COLS for _ in range(TOWER_ROWS)]

    for strategy_fn, weight in strategies:
        try:
            result = strategy_fn(history)
            for row_i in range(TOWER_ROWS):
                col = result[row_i] % TOWER_COLS
                votes[row_i][col] += weight
        except Exception:
            pass

    if prediction_history:
        for round_data in prediction_history[:3]:
            locs = set(round_data.get('mineLocations', []))
            for row_i in range(TOWER_ROWS):
                for c in range(TOWER_COLS):
                    idx = row_i * TOWER_COLS + c
                    if idx not in locs:
                        votes[row_i][c] -= 0.4

    result = []
    for row_i in range(TOWER_ROWS):
        best = max(
            range(TOWER_COLS),
            key=lambda c: (votes[row_i][c], c)
        )
        result.append(row_i * TOWER_COLS + best)
    return result
