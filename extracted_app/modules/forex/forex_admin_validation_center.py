from __future__ import annotations
try: import streamlit as st
except Exception: st = None
try: from modules.forex.forex_validation_suite import ForexValidationSuite
except Exception: ForexValidationSuite = None
try: from modules.forex.forex_system_test_harness import ForexSystemTestHarness
except Exception: ForexSystemTestHarness = None
try: from modules.forex.forex_command_processor import ForexCommandProcessor
except Exception: from forex_command_processor import ForexCommandProcessor
try: from modules.forex._forex_runtime_common import iso
except Exception: from _forex_runtime_common import iso

def _run_local_validation():
    processor = ForexCommandProcessor(); checks = []
    for cmd in ['health_check','tick','status','trend']:
        result = processor.execute(cmd); checks.append({'check':cmd,'passed':result.get('status') == 'ok','result':result})
    return {'status':'ok' if all(c['passed'] for c in checks) else 'warning','checks':checks,'completed_at':iso()}

def render_forex_admin_validation_center(  db=None,
    user=None,):
    if st is None: return _run_local_validation()
    st.subheader('Forex Admin Validation Center'); st.caption('Validate Forex runtime, persistence, monitoring, command processing, and dashboards.')
    result = None; c1,c2,c3 = st.columns(3)
    with c1:
        if st.button('Run Local Validation', key='forex_validation_local'): result = _run_local_validation()
    with c2:
        if st.button('Run Validation Suite', key='forex_validation_suite'):
            if ForexValidationSuite is None: result = {'status':'unavailable','message':'ForexValidationSuite not importable.'}
            else:
                suite = ForexValidationSuite(); result = suite.run_all() if hasattr(suite,'run_all') else {'status':'unavailable','message':'run_all() missing.'}
    with c3:
        if st.button('Run System Harness', key='forex_system_harness'):
            if ForexSystemTestHarness is None: result = {'status':'unavailable','message':'ForexSystemTestHarness not importable.'}
            else:
                harness = ForexSystemTestHarness(); result = harness.run() if hasattr(harness,'run') else {'status':'unavailable','message':'run() missing.'}
    if result is not None: st.session_state['forex_validation_result'] = result
    if st.session_state.get('forex_validation_result'): st.json(st.session_state['forex_validation_result'])
    return st.session_state.get('forex_validation_result')
