import os

from flask import Flask, request
from flask_wtf.csrf import CSRFProtect, generate_csrf
from calculator import add

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
csrf = CSRFProtect(app)


@app.route("/", methods=["GET"])
def home():
    token = generate_csrf()
    return f"""
    <h1>Simple Web Calculator</h1>
    <form method="POST" action="/calculate">
        <input type="hidden" name="csrf_token" value="{token}">
        <input type="number" name="a" step="any" required>
        <input type="number" name="b" step="any" required>
        <button type="submit">Add</button>
    </form>
    """


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        a = float(request.form["a"])
        b = float(request.form["b"])
    except (KeyError, ValueError):
        return "Invalid input", 400

    result = add(a, b)
    return f"<h1>Result: {result}</h1><a href='/'>Back</a>"


if __name__ == "__main__":
    app.run(debug=False)
