import json, os

for f in sorted(os.listdir('data')):
    if not f.endswith('.json'):
        continue
    d = json.load(open(f'data/{f}', encoding='utf-8'))
    t = d.get('teams', {})
    l = t.get('left', '')
    r = t.get('right', '')
    if 'All Gamers' not in l and 'All Gamers' not in r:
        continue
    is_left = 'All Gamers' in l
    for p in d.get('played', []):
        if p.get('map') != 'Abyss':
            continue
        s = p.get('sides', {})
        if is_left:
            my_atk = s.get('left_atk', 0)
            my_def = s.get('left_def', 0)
            op_atk = s.get('right_atk', 0)
            op_def = s.get('right_def', 0)
        else:
            my_atk = s.get('right_atk', 0)
            my_def = s.get('right_def', 0)
            op_atk = s.get('left_atk', 0)
            op_def = s.get('left_def', 0)
        opp = r if is_left else l
        ls = p.get('left_score', 0)
        rs = p.get('right_score', 0)
        print(f'{f}: vs {opp} Score: {ls}-{rs}')
        print(f'  AG atk_won={my_atk} def_won={my_def} | opp atk_won={op_atk} opp def_won={op_def}')