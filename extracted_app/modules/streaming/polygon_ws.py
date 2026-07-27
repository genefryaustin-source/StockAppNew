# polygon_ws.py in streaming
import websocket
import json
import streamlit as st

def start_stream(symbol):

    key = st.secrets["market_data"]["POLYGON_API_KEY"]

    url = "wss://socket.polygon.io/stocks"

    ws = websocket.WebSocket()

    ws.connect(url)

    ws.send(json.dumps({
        "action": "auth",
        "params": key
    }))

    ws.send(json.dumps({
        "action": "subscribe",
        "params": f"T.{symbol}"
    }))

    return ws