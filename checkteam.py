import json
d=json.load(open('data/match_595632_veto.json',encoding='utf-8'))
print(d.get('teams',{}))
