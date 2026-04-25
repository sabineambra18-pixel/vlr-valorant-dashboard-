import json,os
for f in sorted(os.listdir('data')):
  if not f.endswith('.json'): continue
  d=json.load(open(f'data/{f}',encoding='utf-8'))
  teams=d.get('teams',{})
  left=teams.get('left','');right=teams.get('right','')
  if '100' not in left and '100' not in right: continue
  veto=d.get('veto',{})
  events=veto.get('events',[])
  print(f'{f}: {left} vs {right}')
  for e in events:
    print(f'  {e}')
