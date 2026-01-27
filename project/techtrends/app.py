import logging
from http import HTTPStatus
from contextlib import contextmanager

import sqlite3
from flask import Flask, jsonify, json, render_template, request, url_for, redirect, flash
from werkzeug.exceptions import abort


class DatabaseWrapper:
    """
    Wrapper class for interacting with database
    """
    def __init__(self):
        # Database query count, stored in memory as to report for the running instance itself
        self.db_connection_count = 0

    @contextmanager
    def get_db_connection(self) -> sqlite3.Connection:
        """
        Function to get a database connection
        This function connects to database with the name `database.db`
        :return: Database connection
        """
        try:
            connection = sqlite3.connect('database.db')
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()

    def execute(self, conn: sqlite3.Connection, sql: str, params=()) -> sqlite3.Cursor:
        """
        Execute database query
        :param conn: Database connection
        :param sql: SQL to be executed against database
        :param params: Parameters to substitute in query, if any
        :return: SQLite cursor
        """
        self.db_connection_count += 1
        return conn.execute(sql, params)


def get_post(post_id: int) -> sqlite3.Row:
    """
    Function to get a post using its ID
    :param post_id: ID of the post to get
    :return: SQLite row of a post
    """
    with db.get_db_connection() as conn:
        sql_query = 'SELECT * FROM posts WHERE id = ?'
        post = db.execute(conn, sql_query, (post_id, )).fetchone()
        return post


def get_post_count() -> int:
    """
    Get post count
    :return: Total amount of posts
    """
    with db.get_db_connection() as conn:
        sql_query = 'SELECT COUNT(*) FROM posts'
        post_count = db.execute(conn, sql_query).fetchone()[0]
        return post_count


# Define the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'
# Set up logging to a file
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
app.logger.setLevel(logging.DEBUG)
db = DatabaseWrapper()


# Define the main route of the web application 
@app.route('/')
def index():
    with db.get_db_connection() as conn:
        posts = db.execute(conn, 'SELECT * FROM posts').fetchall()
        return render_template('index.html', posts=posts)


# Define how each individual article is rendered 
# If the post ID is not found a 404 page is shown
@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    if post is None:
        app.logger.info(f"Non existing article accessed with ID: {post_id}")
        return render_template('404.html'), HTTPStatus.NOT_FOUND
    else:
        app.logger.info(f'Article "{post["title"]}" retrieved!')
        return render_template('post.html', post=post)


# Define the About Us page
@app.route('/about')
def about():
    app.logger.info('About Us retrieved!')
    return render_template('about.html')


# Define the post creation functionality
@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            with db.get_db_connection() as conn:
                db.execute(conn, 'INSERT INTO posts (title, content) VALUES (?, ?)',
                             (title, content))
                conn.commit()
                app.logger.info(f'New article "{title}" created!')
                return redirect(url_for('index'))

    return render_template('create.html')

@app.route('/healthz')
def healthz():
    """
    Check health of the application
    :return: Health of the application
    """
    try:
        with db.get_db_connection() as conn:
            db.execute(conn, 'SELECT 1 FROM posts LIMIT 1')
            return app.response_class(
                response=json.dumps({'result': 'OK - healthy'}),
                status=HTTPStatus.OK,
                mimetype='application/json'
            )
    except sqlite3.OperationalError as err:
        # No post table is fatal as the entirety of the application depends on it and can't be ignored
        # Log error as fatal and return unhealthy response
        app.logger.fatal(str(err))
        return app.response_class(
            response=json.dumps({'result': 'ERROR - unhealthy'}),
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            mimetype='application/json'
        )

@app.route('/metrics')
def metrics_endpoint():
    """
    Get metrics of application
    :return: Metrics of the application
    """
    post_count = get_post_count()
    response = app.response_class(
        response=json.dumps({
            'db_connection_count': db.db_connection_count,
            'post_count': post_count
        }),
        status=HTTPStatus.OK,
        mimetype='application/json'
    )
    return response


# start the application on port 3111
if __name__ == "__main__":
   app.run(host='0.0.0.0', port=3111)
