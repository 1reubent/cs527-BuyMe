import os
from flask import Flask, render_template
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
import db
import importlib
import pkgutil
import sys



def register_blueprints(app):
  """Register all blueprints"""
  from routes.auth import bp as auth_bp
  from routes.home import bp as home_bp
  from routes.search import bp as search_bp
  from routes.auction import bp as auction_bp
  from routes.rep import bp as rep_bp
  from routes.admin import bp as admin_bp

  app.register_blueprint(auth_bp)
  app.register_blueprint(home_bp)
  app.register_blueprint(search_bp)
  app.register_blueprint(auction_bp)
  app.register_blueprint(rep_bp)
  app.register_blueprint(admin_bp)

def create_app(config_name="default"):
  app = Flask(__name__)
  app.config.from_mapping(
    SECRET_KEY="dev",
    DATABASE=os.path.join(app.instance_path, "buyme.sqlite3"),
    # app.instance_path is the path to the Flask-created instance directory
  )

  # Ensure instance folder exists
  os.makedirs(app.instance_path, exist_ok=True)

  # Initialize database
  db.init_app(app)

  # Register blueprints
  register_blueprints(app)

  # @app.route("/hello")
  # def index():
  #   return render_template("index.html")

  app.add_url_rule("/", endpoint="index")

  return app


if __name__ == "__main__":
  app = create_app()

  # Initialize database on first run
  with app.app_context():
    if not os.path.exists(app.config["DATABASE"]):
      print("Initializing database...")
      db.init_db()

  app.run(debug=True)
