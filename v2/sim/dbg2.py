import random, sys
import params as P
from engine import Debate
from policies import POLICIES
from run import summarize
n=int(sys.argv[1]); opps=sys.argv[2].split(','); pols=sys.argv[3].split(',')
for pol in pols:
    for o in opps:
        rng=random.Random(7)
        rs=[Debate(o,POLICIES[pol],rng).run() for _ in range(n)]
        s=summarize(rs)
        print(pol,o,f"win {s['win']*100:.0f} rd {s['rounds']:.1f} rdW {s['rounds_win']:.1f}", {k:round(v*100) for k,v in s['kinds'].items()}, f"P{s['cross_p']*100:.0f} G{s['cross_g']*100:.0f} A{s['cross_a']*100:.0f} cr{s['cracks']:.1f}")
