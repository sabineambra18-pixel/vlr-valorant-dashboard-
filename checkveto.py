import json,os,re
abbrs=set()
for f in sorted(os.listdir('data')):
  if not f.endswith('.json'): continue
  d=json.load(open(f'data/{f}',encoding='utf-8'))
  veto=d.get('veto',{})
  for e in veto.get('events',[]):
    t=e.get('team','')
    if t: abbrs.add(t)
print('Teams found in veto events:')
for a in sorted(abbrs): print(a)
