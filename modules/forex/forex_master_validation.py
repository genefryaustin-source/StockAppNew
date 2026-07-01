
"""
Phase 21 Master Validation
"""
from importlib import import_module

HELPERS=[
"modules.forex.forex_phase19_validation",
"modules.forex.forex_phase20_validation",
]

def validate_forex_master(db=None,snapshot=None):
    snapshot=snapshot or {}
    results=[]
    artifacts={}
    for mod in HELPERS:
        try:
            import_module(mod)
            results.append({"Category":"Phase21","Test":f"Import {mod}","Passed":True})
        except Exception as e:
            results.append({"Category":"Phase21","Test":f"Import {mod}","Passed":False,"Details":str(e)})
    try:
        from modules.forex.forex_phase19_validation import validate_phase19_decision_platform
        p19=validate_phase19_decision_platform(db=db,snapshot=snapshot)
        artifacts["phase19"]=p19
        results.extend(p19["results"])
    except Exception as e:
        results.append({"Category":"Phase21","Test":"Phase19","Passed":False,"Details":str(e)})
    try:
        from modules.forex.forex_phase20_validation import validate_phase20_autonomous_platform
        p20=validate_phase20_autonomous_platform(db=db,snapshot=snapshot)
        artifacts["phase20"]=p20
        results.extend(p20["results"])
    except Exception as e:
        results.append({"Category":"Phase21","Test":"Phase20","Passed":False,"Details":str(e)})
    passed=all(r.get("Passed",False) for r in results)
    return {
      "status":"PASS" if passed else "FAIL",
      "summary":{
        "validated_phases":"1-20",
        "major_platforms":[
          "Institutional Terminal","AI & Quant","Data Fabric",
          "Executive Decision Center","Autonomous Trading Platform"
        ]
      },
      "results":results,
      "artifacts":artifacts
    }
