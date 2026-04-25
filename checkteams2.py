import json
d = json.load(open('data/match_598925_veto.json', encoding='utf-8'))
print('teams:', d.get('teams', {}))
for p in d.get('played', []):
    print(f"{p.get('map')}: left={p.get('left_score')} right={p.get('right_score')}")
    s = p.get('sides', {})
    print(f"  sides: {s}")