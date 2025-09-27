# serve.py
import threading
import time
from flask import Flask, send_from_directory, redirect
import os

app = Flask(__name__, static_folder="public", static_url_path="")

def start_gradio():
    # import your gradio app (app.py must define 'demo' as Blocks)
    import app as krishi_app
    # Launch Gradio in background; prevent_thread_lock=True lets Flask continue
    krishi_app.demo.launch(server_name="127.0.0.1", server_port=7860, share=False, prevent_thread_lock=True)

# Start Gradio in a daemon thread
t = threading.Thread(target=start_gradio, daemon=True)
t.start()

# optional small wait so Gradio has time to start (increase if heavy)
time.sleep(1)

@app.route("/")
def index():
    # serve index.html from public folder
    return app.send_static_file("index.html")

@app.route("/gradio")
def open_gradio():
    # redirect to local Gradio server
    return redirect("http://127.0.0.1:7860/")

if __name__ == "__main__":
    # serve landing page at http://127.0.0.1:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
