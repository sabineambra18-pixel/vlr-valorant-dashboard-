import os,re
ids=[re.search(r'match_(\d+)',f).group(1) for f in os.listdir('data') if f.startswith('match_') and f.endswith('.json')]
print(' '.join(sorted(set(ids))))
