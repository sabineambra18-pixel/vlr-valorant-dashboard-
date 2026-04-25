import json
d=json.load(open('web/data.json',encoding='utf-8'))
ids=[m['id'] for m in d['matches']]
print(len(ids),'matches')
print('598941:', 598941 in ids)
print('596421:', 596421 in ids)
print('596422:', 596422 in ids)
