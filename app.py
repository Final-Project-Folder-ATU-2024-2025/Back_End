from flask import Flask, jsonify
from flask_cors import CORS

# Create an instance of the Flask application
app = Flask(__name__)
CORS(app)  # Enables Cross-Origin Resource Sharing for all routes

# Define a route
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    # Sample data to return as JSON
    tasks = [
        {"id": 1, "title": "Sample Task", "description": "This is a sample task"},
        {"id": 2, "title": "Another Task", "description": "This is another task"}
    ]
    return jsonify(tasks)

# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True)
