from flask import Flask
from tasks import tasks_bp
from products import products_bp
from categories import categories_bp
from users import users_bp
from flask_cors import CORS
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from extensions import db, login_manager
from models import User
import os
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('POSTGRESQL_CONN_STRING')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    app.register_blueprint(products_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)
    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
