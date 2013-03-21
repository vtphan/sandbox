from config import app, auth, red
from flask import render_template, redirect, url_for
from user import user_page
from sse import sse_bp
from sandbox import sandbox_bp
from problem_set import problem_set_page

# ----------------------------------------------------------------------------
@app.route('/')
def index():
	user = auth.get_logged_in_user()
	if not user:
		return redirect(url_for('auth.login'))
	return render_template('index.html', user=user)

# ----------------------------------------------------------------------------
# @app.before_first_request
# def clear_redis():
#    red.flushdb()

# ----------------------------------------------------------------------------
app.register_blueprint(user_page)
app.register_blueprint(problem_set_page)
app.register_blueprint(sse_bp)
app.register_blueprint(sandbox_bp)


if __name__ == "__main__":
	app.run(port=8000)