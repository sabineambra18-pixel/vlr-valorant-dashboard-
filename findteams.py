import json,os
for f in sorted(os.listdir('data')):
  if not f.endswith('.json'): continue
  d=json.load(open(f'data/{f}',encoding='utf-8'))
  t=d.get('teams',{})
  l=t.get('left','');r=t.get('right','')
  if 'BBL' in l or 'BBL' in r or 'KR' in l or 'KR' in r:
    print(f'{f}: {l} vs {r}')
