import random, sys, importlib
import params as P
import engine
from policies import POLICIES
from run import summarize
def go(label, **kw):
    for k,v in kw.items(): setattr(P,k,v)
    out=[]
    for pol in ["careful","sophist","careless"]:
        row=[]
        for o in ["fitch","pierce","mid_expert","mid_noble","mid_veteran","late_noble","wolfhart"]:
            rng=random.Random(11)
            rs=[engine.Debate(o,POLICIES[pol],rng).run() for _ in range(800)]
            s=summarize(rs)
            row.append(f"{o[:6]}:{s['win']*100:.0f}/{s['rounds']:.0f}/g{s['kinds'].get('grind',0)*100:.0f}/L{s['loss_after_ronpa']*100:.0f}")
        print(label,pol,' '.join(row))
go("asis")
go("lock", GRIND_LOCK=True)
go("soph10", GRIND_LOCK=False, SOPH_INTERCEPT_DMG=10.0, SOPH_INTERCEPT_BREAKS=False)
