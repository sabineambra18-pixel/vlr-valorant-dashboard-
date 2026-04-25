import json,os
for f in os.listdir('data'):
  if not f.endswith('.json'): continue
  d=json.load(open(f'data/{f}',encoding='utf-8'))
  t=d.get('teams',{})
  for n in [t.get('left',''),t.get('right','')]:
    if 'ong' in n.lower() or 'NS' in n or 'RedF' in n: print(n)
