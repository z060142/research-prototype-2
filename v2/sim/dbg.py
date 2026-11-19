import random, sys
import params as P
from engine import Debate
from policies import POLICIES
from run import summarize
n=int(sys.argv[1]) if len(sys.argv)>1 else 1500
for pol in ["careful","careless","sophist","staller","psych"]:
    for st,opps in P.STAGE_SCENARIOS.items():
        rs=[]
        for o in opps:
            rng=random.Random(hash((pol,o))%10000)
            rs+=[Debate(o,POLICIES[pol],rng).run() for _ in range(n)]
        s=summarize(rs)
        print(pol,st,f"win {s['win']*100:.0f} rd {s['rounds']:.1f}", {k:round(v*100) for k,v in s['kinds'].items()}, f"P{s['cross_p']*100:.0f} G{s['cross_g']*100:.0f} A{s['cross_a']*100:.0f}")
