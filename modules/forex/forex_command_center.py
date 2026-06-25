from __future__ import annotations
import json
try: import streamlit as st
except Exception: st = None
try: from modules.forex.forex_command_processor import ForexCommandProcessor
except Exception: from forex_command_processor import ForexCommandProcessor

def render_forex_command_center(  db=None,
    user=None,):
    if st is None: return {'status':'streamlit_unavailable'}
    st.subheader('Forex Command Center'); st.caption('Run operational commands against the Forex runtime layer.')
    processor = ForexCommandProcessor(); c1,c2,c3,c4 = st.columns(4)
    with c1:
        if st.button('Health Check', key='forex_cmd_health'): st.session_state['forex_cmd_result'] = processor.execute('health_check')
    with c2:
        if st.button('Runtime Tick', key='forex_cmd_tick'): st.session_state['forex_cmd_result'] = processor.execute('tick')
    with c3:
        if st.button('Pause Runtime', key='forex_cmd_pause'): st.session_state['forex_cmd_result'] = processor.execute('pause_runtime')
    with c4:
        if st.button('Resume Runtime', key='forex_cmd_resume'): st.session_state['forex_cmd_result'] = processor.execute('resume_runtime')
    command = st.selectbox('Command', ['status','trend','events','history','snapshot','strategy_snapshot'], key='forex_command_select')
    payload_text = st.text_area('Command Payload JSON', value='{}', key='forex_command_payload')
    if st.button('Execute Command', key='forex_execute_command'):
        try: payload = json.loads(payload_text or '{}')
        except Exception: payload = {}; st.warning('Invalid JSON payload; using empty payload.')
        st.session_state['forex_cmd_result'] = processor.execute(command, payload)
    if st.session_state.get('forex_cmd_result'): st.json(st.session_state['forex_cmd_result'])
    return st.session_state.get('forex_cmd_result')
