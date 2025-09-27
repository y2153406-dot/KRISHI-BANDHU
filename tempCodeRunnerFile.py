
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    # Start Gradio in a daemon thread only when running this script directly.
    t = threading.Thread(target=start_gradio, daemon=True)
    t.start()

    # give Gradio a moment to boot (optional)
    time.sleep(2)

    # Run Flask (development). For production, use Gunicorn as described in README:
    # gunicorn serve:app --bind 0.0.0.0:$PORT --workers 1
    app.run(host="0.0.0.0", port=MAIN_PORT)
