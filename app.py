from flask import Flask, request
from calculator import add

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <h1>Simple Web Calculator</h1>
    <form method="POST" action="/calculate">
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
