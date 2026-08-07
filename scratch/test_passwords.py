import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import DB_CONFIG
import mysql.connector

# Try with 127.0.0.1 and localhost
hosts = ["127.0.0.1", "localhost"]
passwords = ["admin"]

for host in hosts:
    for pwd in passwords:
        config = DB_CONFIG.copy()
        config['host'] = host
        config['password'] = pwd
        try:
            print(f"Trying host={repr(host)}, password={repr(pwd)} ...")
            config_simple = {k: v for k, v in config.items() if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
            conn = mysql.connector.connect(**config_simple)
            print(f"🎉 SUCCESS! Connected with host={repr(host)}, password={repr(pwd)}")
            conn.close()
        except Exception as e:
            print(f"❌ Failed: {e}")


