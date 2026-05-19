import os

def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA") or os.getcwd()
    app_dir = os.path.join(base, "EquityResearchTerminal")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

def get_db_path():
    return os.path.join(get_app_data_dir(), "app.db")

def get_cache_dir(name):
    path = os.path.join(get_app_data_dir(), name)
    os.makedirs(path, exist_ok=True)
    return path