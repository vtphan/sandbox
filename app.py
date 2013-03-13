from config import app, auth
from flask import render_template, redirect, url_for
from user import user_page


# ----------------------------------------------------------------------------
@app.route('/')
def index():
	user = auth.get_logged_in_user()
	if not user:
		return redirect(url_for('auth.login'))
	return render_template('index.html', user=user)


# ----------------------------------------------------------------------------

app.register_blueprint(user_page)

if __name__ == "__main__":
	app.run(port=8000)