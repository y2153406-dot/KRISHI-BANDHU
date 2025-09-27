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




# # serve.py  (Flask + background Gradio)  — improved version
# import threading
# import time
# import os
# from flask import Flask, redirect, send_from_directory, jsonify

# # Make sure this matches your repo folder name (Public vs public)
# STATIC_DIR = os.path.join(os.path.dirname(__file__), "Public")

# app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

# # Read ports from env
# # Render will set PORT for the main HTTP entrypoint.
# MAIN_PORT = int(os.environ.get("PORT", 8080))
# # Gradio can run on a different internal port; choose one not equal to MAIN_PORT
# GRADIO_PORT = int(os.environ.get("GRADIO_PORT", 7860))
# GRADIO_HOST = "127.0.0.1"

# def start_gradio():
#     try:
#         # import your gradio app which must define `demo` variable (Blocks)
#         import app as krishi_app
#         print("Starting Gradio on", GRADIO_HOST, GRADIO_PORT)
#         krishi_app.demo.launch(
#             server_name=GRADIO_HOST,
#             server_port=GRADIO_PORT,
#             share=False,
#             prevent_thread_lock=True,
#             show_error=True
#         )
#     except Exception as e:
#         print("Failed to start Gradio:", e)

# # Start Gradio in a daemon thread
# t = threading.Thread(target=start_gradio, daemon=True)
# t.start()

# # wait a bit for Gradio to start (if needed)
# time.sleep(3)

# @app.route("/")
# def index():
#     # serve index.html from Public/index.html
#     index_path = os.path.join(STATIC_DIR, "index.html")
#     if os.path.exists(index_path):
#         return app.send_static_file("index.html")
#     return "Index not found", 404

# @app.route("/app")
# def open_gradio():
#     # internal redirect to local Gradio server
#     # this is an internal redirect; browser will be redirected to same host but a different port
#     return redirect(f"http://{GRADIO_HOST}:{GRADIO_PORT}/")

# @app.route("/health")
# def health():
#     return jsonify({"status":"ok"})

# if __name__ == "__main__":
#     # run Flask on MAIN_PORT (uses env PORT)
#     app.run(host="0.0.0.0", port=MAIN_PORT)



# # serve.py  (Flask + background Gradio) — Render-friendly
# import threading
# import time
# import os
# import sys
# from flask import Flask, redirect, jsonify

# STATIC_DIR = os.path.join(os.path.dirname(__file__), "Public")

# app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

# # Read ports from env
# MAIN_PORT = int(os.environ.get("PORT", 8080))
# GRADIO_PORT = int(os.environ.get("GRADIO_PORT", 7860))
# GRADIO_HOST = "127.0.0.1"

# # Avoid accidental port clash
# if GRADIO_PORT == MAIN_PORT:
#     print(f"[warn] GRADIO_PORT ({GRADIO_PORT}) equals MAIN_PORT ({MAIN_PORT}), changing GRADIO_PORT -> {GRADIO_PORT + 1}")
#     GRADIO_PORT += 1

# def start_gradio():
#     try:
#         # import your gradio app module which must define `demo` (Blocks)
#         import app as krishi_app  # ensure this import works
#         print(f"[info] Starting Gradio on {GRADIO_HOST}:{GRADIO_PORT}")
#         krishi_app.demo.launch(
#             server_name=GRADIO_HOST,
#             server_port=GRADIO_PORT,
#             share=False,
#             prevent_thread_lock=True,
#             show_error=True
#         )
#     except Exception as e:
#         print("[error] Failed to start Gradio:", e, file=sys.stderr)

# @app.route("/")
# def index():
#     index_path = os.path.join(STATIC_DIR, "index.html")
#     if os.path.exists(index_path):
#         return app.send_static_file("index.html")
#     return "Index not found", 404

# @app.route("/app")
# def open_gradio():
#     # NOTE: Redirect to internal gradio host. This works for local dev.
#     # For production on Render, external browsers can't reach 127.0.0.1:GRADIO_PORT directly.
#     # See README or docs for proxy/embed options.
#     return redirect(f"http://{GRADIO_HOST}:{GRADIO_PORT}/")

# @app.route("/health")
# def health():
#     return jsonify({"status":"ok"})

# if __name__ == "__main__":
#     # Start Gradio in a daemon thread only when running this script directly.
#     t = threading.Thread(target=start_gradio, daemon=True)
#     t.start()

#     # give Gradio a moment to boot (optional)
#     time.sleep(2)

#     # Run Flask (development). For production, use Gunicorn as described in README:
#     # gunicorn serve:app --bind 0.0.0.0:$PORT --workers 1
#     app.run(host="0.0.0.0", port=MAIN_PORT)
